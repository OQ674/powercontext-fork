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

"""Incremental preparation through the real persistent scoped Runtime."""

from __future__ import annotations

from typing import cast

import pytest

from powercontext.builtin.artifacts.memory import MemoryCandidateRequest, MemoryEntryInput
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import (
    BuiltinConfig,
    CaptureSource,
    ContextAssembly,
    PrepareContextRequest,
    open_builtin_runtime,
)
from powercontext.builtin.runtime.context_pack import (
    ContextPack,
    ContextPackDelta,
    ContextPackError,
    apply_context_pack_delta,
)
from powercontext.builtin.scope import ScopeDraft
from powercontext.builtin.sources import ContentSource


class _CandidatePipeline:
    async def extract(self, request: MemoryCandidateRequest, /) -> tuple[MemoryEntryInput, ...]:
        return tuple(
            MemoryEntryInput(kind="conversation-turn", text=source.content, sources=(source,))
            for source in request.sources
            if isinstance(source, ContentSource)
        )


@pytest.mark.asyncio
async def test_incremental_preparation_preserves_empty_results_citations_and_restart(tmp_path) -> None:
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'pack.db'}"))
    request = PrepareContextRequest(query="remote controls", max_bytes=8192)
    empty_request = PrepareContextRequest(query="remote", assembly=ContextAssembly(sections=()))
    wires: list[bytes] = []
    expected: list[bytes] = []
    async with open_builtin_runtime(config, candidate_pipeline=_CandidatePipeline()) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(
            ScopeDraft(title="Packets", summary="Persistent context", idempotency_key="pack")
        )
        scope_id = scope.scope_id
        context = runtime.context.for_scope(scope_id)
        receiver = await context.prepare_incremental(empty_request)
        assert isinstance(receiver, ContextPack) and receiver.items == ()
        assert (await context.prepare(empty_request)).content is None
        wires.append(receiver.to_bytes())
        expected.append(b"")
        sources = runtime.sources.for_scope(scope_id)
        memory = runtime.memory.for_scope(scope_id)
        for index, text in enumerate([
            "Remote controls need durable buttons. 中文说明。",
            "The remote control battery compartment must remain accessible.",
        ]):
            await sources.capture(CaptureSource(source_id=f"turn-{index}", content=text, metadata={}))
            while (await memory.flush()).processed:
                pass
            for current_request in [request, PrepareContextRequest(query="battery", max_bytes=8192), empty_request]:
                ordinary = await context.prepare(current_request)
                delta = await context.prepare_incremental(current_request, base_pack=receiver)
                assert isinstance(delta, ContextPackDelta)
                wires.append(delta.to_bytes())
                expected.append((ordinary.content or "").encode())
                receiver = apply_context_pack_delta(
                    ContextPack.from_bytes(receiver.to_bytes()), ContextPackDelta.from_bytes(delta.to_bytes())
                )
                assert b"".join(receiver.items) == expected[-1]
        with pytest.raises(ContextPackError):
            await context.prepare_incremental(request, base_pack=cast("ContextPack", object()))

    # Decode only wire data after closing the sender and its database connections.
    restored = ContextPack.from_bytes(wires[0])
    for wire, content in zip(wires[1:], expected[1:], strict=True):
        restored = apply_context_pack_delta(restored, ContextPackDelta.from_bytes(wire))
        assert b"".join(restored.items) == content
    assert any(content for content in expected)
    async with open_builtin_runtime(config, candidate_pipeline=_CandidatePipeline()) as runtime:
        context = runtime.context.for_scope(scope_id)
        target = await context.prepare(request)
        delta = await context.prepare_incremental(request, restored)
        assert isinstance(delta, ContextPackDelta)
    assert target.content is not None
    assert (
        b"".join(apply_context_pack_delta(restored, ContextPackDelta.from_bytes(delta.to_bytes())).items)
        == target.content.encode()
    )


@pytest.mark.asyncio
async def test_incremental_preparation_uses_ordinary_scope_authorization() -> None:
    seen: list[tuple[str, ...]] = []

    async def authorize(scope_ids: tuple[str, ...]) -> None:
        seen.append(scope_ids)

    async def reject(scope_ids: tuple[str, ...]) -> None:
        raise PermissionError(scope_ids)

    async with open_builtin_runtime(BuiltinConfig()) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(
            ScopeDraft(title="Authorization", summary="Packets", idempotency_key="pack-auth")
        )
        context = runtime.context.for_scope(scope.scope_id)
        request = PrepareContextRequest(query="nothing")
        result = await context.prepare_incremental(request, authorize_scopes=authorize)
        assert isinstance(result, ContextPack) and result.items == ()
        assert seen == [(scope.scope_id,)]
        with pytest.raises(PermissionError):
            await context.prepare_incremental(request, authorize_scopes=reject)
