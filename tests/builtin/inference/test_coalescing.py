# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cross-call sharing, independent failures and provider usage accounting."""

from __future__ import annotations

import asyncio
import gc
from typing import Any

import pytest
from typing_extensions import override

from powercontext.builtin.artifacts.memory import EmbeddingProfile
from powercontext.builtin.inference import EmbeddingResult, InferenceUsage, embed_query
from powercontext.builtin.inference.coalescing import CoalescingEmbeddingModel


class _Model:
    profile = EmbeddingProfile(profile_id="coalescing", model="offline", dimension=1)

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        self.calls.append(texts)
        return EmbeddingResult(
            vectors=tuple((float(len(text)),) for text in texts),
            usage=InferenceUsage(requests=2, input_tokens=7, output_tokens=0),
        )


@pytest.mark.parametrize(
    "settings",
    [{"max_batch_size": value} for value in [0, -1, True, 1.5, "3"]]
    + [{"cache_size": value} for value in [-1, True, 1.5, "3"]]
    + [{"coalesce_ms": value} for value in [-1, True, "3", float("nan"), float("inf"), None]],
)
def test_invalid_settings_are_rejected(settings: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        CoalescingEmbeddingModel(_Model(), **settings)


@pytest.mark.asyncio
async def test_distinct_equal_usage_batches_are_summed_once_per_call() -> None:
    base = _Model()
    model = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=0)
    first, second = await asyncio.gather(model.embed(("a", "bb", "a")), model.embed(("bb", "bb")))
    assert first.vectors == ((1.0,), (2.0,), (1.0,))
    assert first.usage == InferenceUsage(requests=4, input_tokens=14, output_tokens=0)
    assert second.usage == InferenceUsage(requests=2, input_tokens=7, output_tokens=0)
    assert base.calls == [("a",), ("bb",)]
    cached = await model.embed(("bb", "a"))
    assert cached.usage == InferenceUsage(requests=0, input_tokens=0, output_tokens=0)
    assert model.profile is base.profile


@pytest.mark.asyncio
async def test_late_waiter_shares_inflight_without_cache_and_fresh_batch_can_finish_independently() -> None:
    started, release, fresh = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Blocked(_Model):
        @override
        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            if texts == ("shared",):
                started.set()
                await release.wait()
            else:
                fresh.set()
            return await super().embed(texts)

    base = Blocked()
    model = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=0, cache_size=0)
    first = asyncio.create_task(model.embed(("shared",)))
    await asyncio.wait_for(started.wait(), 3)
    late = asyncio.create_task(model.embed(("shared", "new", "shared")))
    await asyncio.wait_for(fresh.wait(), 3)
    release.set()
    a, b = await asyncio.wait_for(asyncio.gather(first, late), 3)
    assert a.usage.requests == 2 and b.usage.requests == 4
    assert b.vectors == ((6.0,), (3.0,), (6.0,))
    assert sum(call.count("shared") for call in base.calls) == 1
    await model.embed(("shared",))
    assert sum(call.count("shared") for call in base.calls) == 2


@pytest.mark.asyncio
async def test_failed_batch_isolated_and_retry_does_not_discard_successful_cache() -> None:
    failure = RuntimeError("controlled failure")

    class Flaky(_Model):
        fail = True

        @override
        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            if texts == ("bad",) and self.fail:
                self.fail = False
                self.calls.append(texts)
                raise failure
            return await super().embed(texts)

    base = Flaky()
    model = CoalescingEmbeddingModel(base, max_batch_size=1, coalesce_ms=0)
    failed, good = await asyncio.gather(model.embed(("bad",)), model.embed(("good",)), return_exceptions=True)
    assert failed is failure
    assert isinstance(good, EmbeddingResult) and good.vectors == ((4.0,),)
    recovered = await model.embed(("bad", "good"))
    assert recovered.vectors == ((3.0,), (4.0,))
    assert recovered.usage.requests == 2
    assert base.calls.count(("good",)) == 1 and base.calls.count(("bad",)) == 2


@pytest.mark.asyncio
async def test_invalid_count_fails_every_dependent_waiter_and_caches_no_partial_batch() -> None:
    class Invalid(_Model):
        invalid = True

        @override
        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            result = await super().embed(texts)
            if self.invalid:
                return result.model_copy(update={"vectors": result.vectors[:-1]})
            return result

    base = Invalid()
    model = CoalescingEmbeddingModel(base, coalesce_ms=0)
    failed = await asyncio.gather(model.embed(("a", "b")), model.embed(("a",)), return_exceptions=True)
    assert all(isinstance(error, ValueError) for error in failed)
    base.invalid = False
    assert (await model.embed(("a", "b"))).vectors == ((1.0,), (1.0,))
    assert base.calls == [("a", "b"), ("a", "b")]


@pytest.mark.asyncio
async def test_all_waiters_can_cancel_then_failed_work_can_retry_without_orphan_errors() -> None:
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class BlockedFailure(_Model):
        fail = True

        @override
        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            if self.fail:
                started.set()
                await release.wait()
                self.fail = False
                finished.set()
                raise RuntimeError("abandoned batch")  # noqa: TRY003
            return await super().embed(texts)

    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    unhandled: list[dict[str, Any]] = []
    loop.set_exception_handler(lambda _, context: unhandled.append(context))
    try:
        base = BlockedFailure()
        model = CoalescingEmbeddingModel(base, coalesce_ms=0, cache_size=0)
        callers = [asyncio.create_task(model.embed(("a",))) for _ in range(2)]
        await asyncio.wait_for(started.wait(), 3)
        for caller in callers:
            caller.cancel()
        assert all(
            isinstance(error, asyncio.CancelledError)
            for error in await asyncio.gather(*callers, return_exceptions=True)
        )
        release.set()
        await asyncio.wait_for(finished.wait(), 3)
        assert (await model.embed(("a",))).vectors == ((1.0,),)
        gc.collect()
        await asyncio.sleep(0)
        assert not unhandled
    finally:
        loop.set_exception_handler(previous)


@pytest.mark.asyncio
async def test_repeated_cache_access_refreshes_recency_in_original_order() -> None:
    base = _Model()
    model = CoalescingEmbeddingModel(base, coalesce_ms=0, cache_size=2)
    await model.embed(("a", "b"))
    await model.embed(("a", "b", "a"))
    await model.embed(("c",))
    assert (await model.embed(("a",))).usage.requests == 0
    assert (await model.embed(("b",))).usage.requests == 2
    assert base.calls == [("a", "b"), ("c",), ("b",)]


@pytest.mark.asyncio
async def test_query_vectors_are_isolated_only_for_asymmetric_provider() -> None:
    class Asymmetric(_Model):
        query_calls: list[tuple[str, ...]]

        def __init__(self) -> None:
            super().__init__()
            self.query_calls = []

        async def embed_query(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            self.query_calls.append(texts)
            return EmbeddingResult(vectors=tuple((-1.0,) for _ in texts), usage=InferenceUsage(requests=3))

    base = Asymmetric()
    model = CoalescingEmbeddingModel(base, coalesce_ms=0)
    document, query = await asyncio.gather(model.embed(("a",)), embed_query(model, ("a",)))
    assert document.vectors == ((1.0,),) and query.vectors == ((-1.0,),)
    assert (await model.embed(("a",))).usage.requests == (await embed_query(model, ("a",))).usage.requests == 0
    assert base.calls == [("a",)] and base.query_calls == [("a",)]
    symmetric = CoalescingEmbeddingModel(_Model(), coalesce_ms=0)
    await symmetric.embed(("a",))
    assert (await embed_query(symmetric, ("a",))).usage.requests == 0


@pytest.mark.asyncio
async def test_unknown_tokens_are_not_reported_as_a_known_partial_total() -> None:
    class MixedUsage(_Model):
        @override
        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            return EmbeddingResult(
                vectors=tuple((1.0,) for _ in texts),
                usage=InferenceUsage(requests=1, input_tokens=None if texts == ("a",) else 7, output_tokens=0),
            )

    model = CoalescingEmbeddingModel(MixedUsage(), max_batch_size=1, coalesce_ms=0)
    result = await model.embed(("a", "b"))
    assert result.usage == InferenceUsage(requests=2, input_tokens=None, output_tokens=0)
