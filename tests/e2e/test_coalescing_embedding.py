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

"""Canceled native Memory writes leave other scopes' shared embeddings usable."""

from __future__ import annotations

import asyncio

import pytest

from powercontext.builtin.artifacts.memory import EmbeddingProfile, MemoryEntryInput
from powercontext.builtin.inference import EmbeddingResult, InferenceUsage
from powercontext.builtin.inference.coalescing import CoalescingEmbeddingModel
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import BuiltinConfig, open_builtin_contexts


class _BlockedEmbedding:
    profile = EmbeddingProfile(profile_id="cancelled-native-write", model="offline", dimension=2)

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls: list[tuple[str, ...]] = []

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        self.calls.append(texts)
        self.started.set()
        await self.release.wait()
        return EmbeddingResult(
            vectors=tuple((1.0, 0.0) if text.startswith("Alpha") else (0.0, 1.0) for text in texts),
            usage=InferenceUsage(requests=1, input_tokens=5, output_tokens=0),
        )


@pytest.mark.asyncio
async def test_cancelled_memory_writer_does_not_cancel_other_scope_and_index_survives_restart(tmp_path) -> None:
    base = _BlockedEmbedding()
    model = CoalescingEmbeddingModel(base, coalesce_ms=0)

    class Together:
        profile = model.profile

        def __init__(self) -> None:
            self.arrived = 0
            self.release = asyncio.Event()

        async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
            if self.arrived < 2:
                self.arrived += 1
                if self.arrived == 2:
                    self.release.set()
                await self.release.wait()
            return await model.embed(texts)

    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}"))
    entries = tuple(
        MemoryEntryInput(kind="fact", text=text) for text in ("Alpha stable evidence", "Beta stable evidence")
    )
    async with open_builtin_contexts(config, embedding_model=Together()) as contexts:
        first = (await contexts.get("first")).artifacts.memory
        second = (await contexts.get("second")).artifacts.memory
        cancelled = asyncio.create_task(first.remember(memory=None, entries=entries, mode="append"))
        survivor = asyncio.create_task(second.remember(memory=None, entries=entries, mode="append"))
        await asyncio.wait_for(base.started.wait(), 5)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        base.release.set()
        memory = await asyncio.wait_for(survivor, 5)
        assert memory is not None
        result = await second.search("Alpha stable evidence", memories=(memory,), mode="vector", limit=1)
        assert result.hits[0].text == "Alpha stable evidence"
        original_hit = result.hits[0]
        assert len(base.calls) == 1
        assert len(base.calls[0]) == 2
        assert set(base.calls[0]) == {"Alpha stable evidence", "Beta stable evidence"}
    cold = _BlockedEmbedding()
    cold.release.set()
    async with open_builtin_contexts(config, embedding_model=CoalescingEmbeddingModel(cold, coalesce_ms=0)) as contexts:
        second = (await contexts.get("second")).artifacts.memory
        result = await second.search("Alpha stable evidence", memories=(memory,), mode="vector", limit=1)
        assert result.hits[0] == original_hit
        assert cold.calls == [("Alpha stable evidence",)]
