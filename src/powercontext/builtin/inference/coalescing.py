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

"""Share embedding work across callers without sharing caller cancellation."""

from __future__ import annotations

import asyncio
import math
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias

from powercontext.builtin.inference.models import EmbeddingResult, EmbeddingVector, InferenceUsage
from powercontext.builtin.inference.protocols import EmbeddingModel, QueryEmbeddingModel, embed_query


@dataclass(frozen=True, eq=False)
class _BatchUsage:
    # Identity, rather than equal numeric usage, distinguishes provider batches.
    usage: InferenceUsage


_Key: TypeAlias = tuple[bool, str]
_SharedResult: TypeAlias = tuple[EmbeddingVector, _BatchUsage]
_Batch: TypeAlias = tuple[tuple[_Key, asyncio.Future[_SharedResult]], ...]


def _optional_total(values: Iterable[int | None]) -> int | None:
    total = 0
    for value in values:
        if value is None:
            return None
        total += value
    return total


def _observe_result(future: asyncio.Future[_SharedResult]) -> None:
    # All callers may cancel before a batch fails. Retrieving the exception
    # prevents an orphan warning without changing what other waiters receive.
    if not future.cancelled():
        future.exception()


class CoalescingEmbeddingModel:
    """Coalesce same-loop requests and retain a bounded LRU of successful vectors."""

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        max_batch_size: int = 64,
        coalesce_ms: float = 5.0,
        cache_size: int = 1024,
    ) -> None:
        if type(max_batch_size) is not int or max_batch_size <= 0:
            raise ValueError("max_batch_size must be a positive integer")  # noqa: TRY003
        if type(cache_size) is not int or cache_size < 0:
            raise ValueError("cache_size must be a nonnegative integer")  # noqa: TRY003
        if isinstance(coalesce_ms, bool) or not isinstance(coalesce_ms, (int, float)):
            raise ValueError("coalesce_ms must be a finite nonnegative number")  # noqa: TRY003, TRY004
        try:
            milliseconds = float(coalesce_ms)
        except (ValueError, OverflowError) as error:
            raise ValueError("coalesce_ms must be a finite nonnegative number") from error  # noqa: TRY003
        if not math.isfinite(milliseconds) or milliseconds < 0:
            raise ValueError("coalesce_ms must be a finite nonnegative number")  # noqa: TRY003
        self.profile = model.profile
        self._model = model
        self._max_batch_size = max_batch_size
        self._delay = milliseconds / 1000
        self._cache_size = cache_size
        self._cache: OrderedDict[_Key, EmbeddingVector] = OrderedDict()
        self._inflight: dict[_Key, asyncio.Future[_SharedResult]] = {}
        self._pending: dict[_Key, asyncio.Future[_SharedResult]] = {}
        self._dispatcher: asyncio.Task[None] | None = None
        self._running: set[asyncio.Task[None]] = set()

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        """Return document vectors in original order, including duplicate positions."""
        return await self._embed(texts, query=False)

    async def embed_query(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        """Preserve asymmetric query embedding; symmetric models share their cache."""
        return await self._embed(texts, query=isinstance(self._model, QueryEmbeddingModel))

    async def _embed(self, texts: tuple[str, ...], *, query: bool) -> EmbeddingResult:
        loop = asyncio.get_running_loop()
        ready: dict[str, EmbeddingVector] = {}
        waiting: dict[str, asyncio.Future[_SharedResult]] = {}
        # There is no await during registration: same-loop callers cannot race
        # between inspecting a key and registering its shared computation.
        for text in texts:
            key = (query, text)
            if key in self._cache:
                ready[text] = self._cache[key]
                self._cache.move_to_end(key)
                continue
            future = self._inflight.get(key)
            if future is None:
                future = loop.create_future()
                future.add_done_callback(_observe_result)
                self._inflight[key] = future
                self._pending[key] = future
            waiting[text] = future
        if self._pending and (self._dispatcher is None or self._dispatcher.done()):
            self._dispatcher = loop.create_task(self._dispatch())
            self._dispatcher.add_done_callback(self._dispatch_done)
        batches: set[_BatchUsage] = set()
        if waiting:
            values = await asyncio.gather(*(asyncio.shield(future) for future in waiting.values()))
            for text, (vector, batch) in zip(waiting, values, strict=True):
                ready[text] = vector
                batches.add(batch)
        return EmbeddingResult(
            vectors=tuple(ready[text] for text in texts),
            usage=InferenceUsage(
                requests=sum(batch.usage.requests for batch in batches),
                input_tokens=_optional_total(batch.usage.input_tokens for batch in batches),
                output_tokens=_optional_total(batch.usage.output_tokens for batch in batches),
            ),
        )

    async def _dispatch(self) -> None:
        # Even zero delay yields once so simultaneous registrations can merge.
        await asyncio.sleep(self._delay)
        pending = tuple(self._pending.items())
        self._pending.clear()
        for query in (False, True):
            group = tuple(item for item in pending if item[0][0] == query)
            for start in range(0, len(group), self._max_batch_size):
                task = asyncio.create_task(self._execute(group[start : start + self._max_batch_size], query=query))
                self._running.add(task)
                task.add_done_callback(self._running.discard)

    def _dispatch_done(self, task: asyncio.Task[None]) -> None:
        if self._dispatcher is not task:
            return
        self._dispatcher = None
        error = None if task.cancelled() else task.exception()
        if not task.cancelled() and error is None:
            return
        # Also clean up a timer canceled before its coroutine started, such as
        # during event-loop shutdown after every caller has left.
        pending = tuple(self._pending.items())
        self._pending.clear()
        for key, future in pending:
            self._inflight.pop(key, None)
            if task.cancelled():
                future.cancel()
            elif not future.done() and error is not None:
                future.set_exception(error)

    async def _execute(self, batch: _Batch, *, query: bool) -> None:
        texts = tuple(key[1] for key, _ in batch)
        try:
            result = await embed_query(self._model, texts) if query else await self._model.embed(texts)
            self._publish(batch, result)
        except asyncio.CancelledError:
            for key, future in batch:
                self._inflight.pop(key, None)
                future.cancel()
            raise
        except Exception as error:
            for key, future in batch:
                self._inflight.pop(key, None)
                if not future.done():
                    future.set_exception(error)

    def _publish(self, batch: _Batch, result: EmbeddingResult) -> None:
        # Validate the whole response before caching or releasing any vector.
        if len(result.vectors) != len(batch):
            raise ValueError("Provider vector count does not match the requested batch")  # noqa: TRY003
        usage = _BatchUsage(result.usage.model_copy())
        for (key, future), vector in zip(batch, result.vectors, strict=True):
            if self._cache_size:
                self._cache[key] = vector
                self._cache.move_to_end(key)
                if len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            self._inflight.pop(key, None)
            if not future.done():
                future.set_result((vector, usage))
