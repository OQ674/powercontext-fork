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

"""Persistent lifecycle propagation, retry boundaries and exact audit references."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import EmbeddingProfile, MemoryEntryInput, MemoryService
from powercontext.builtin.inference import EmbeddingResult
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.records import ArtifactWrite
from powercontext.builtin.runtime import (
    BuiltinConfig,
    CaptureSource,
    GetTopicMemoryRequest,
    RememberMemoryRequest,
    SearchTopicMemoryRequest,
    open_builtin_runtime,
)
from powercontext.builtin.runtime.source_lifecycle import SourceLifecycleError, SourceLifecycleEvent
from powercontext.builtin.scope import ScopeDraft
from powercontext.sources import SourceRef


def _event(*, available: bool = False, sequence: int = 1, reason: str = "withdrawal") -> SourceLifecycleEvent:
    return SourceLifecycleEvent(node_id="source", revision=3, sequence=sequence, available=available, reason=reason)


async def _bind(runtime, scope_id: str):
    lifecycle = runtime.lifecycle.for_scope(scope_id)
    receipt = await runtime.sources.for_scope(scope_id).capture(
        CaptureSource(source_id="origin", content="evidence", metadata={})
    )
    await lifecycle.register_source("source", receipt.source_ref, revision=3)
    result = await runtime.memory.for_scope(scope_id).remember(
        RememberMemoryRequest(entries=(MemoryEntryInput(kind="fact", text="Persisted supported fact"),)),
    )
    citation = result.entry.citation
    await lifecycle.register_memory("memory", citation, parents=("source",))
    return lifecycle, receipt.source_ref, citation


@pytest.mark.parametrize(
    "override",
    [
        {"node_id": " "},
        {"node_id": 1},
        {"reason": "\n\t"},
        {"reason": None},
        {"revision": True},
        {"revision": "3"},
        {"revision": 0},
        {"sequence": False},
        {"sequence": 1.0},
        {"sequence": -1},
        {"available": 1},
        {"available": "false"},
        {"extra": 0},
    ],
)
def test_event_rejects_coercions_blank_text_and_extra_fields(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SourceLifecycleEvent.model_validate({**_event().model_dump(), **override})


@pytest.mark.asyncio
@pytest.mark.parametrize("committed", [False, True])
async def test_interrupted_native_write_retries_after_restart_without_duplicate_revisions(
    tmp_path, monkeypatch, committed
):
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'retry.db'}"))
    original_forget = MemoryService.forget
    failure = RuntimeError("interrupted native write")

    async def interrupt(self, *args, **kwargs):
        if committed:
            await original_forget(self, *args, **kwargs)
        raise failure

    async with open_builtin_runtime(config) as runtime:
        assert runtime.scopes is not None
        scope_id = (
            await runtime.scopes.create(ScopeDraft(title="Retry", summary="Retry", idempotency_key="retry"))
        ).scope_id
        lifecycle, _, citation = await _bind(runtime, scope_id)
        initial_ref = (await runtime.memory.for_scope(scope_id).list()).memory_ref
        assert initial_ref is not None
        initial = initial_ref.revision
        with monkeypatch.context() as patch:
            patch.setattr(MemoryService, "forget", interrupt)
            with pytest.raises(RuntimeError, match="interrupted native write"):
                await lifecycle.apply(_event())
    async with open_builtin_runtime(config) as runtime:
        lifecycle = runtime.lifecycle.for_scope(scope_id)
        assert await lifecycle.apply(_event()) == []
        memory = runtime.memory.for_scope(scope_id)
        page = await memory.list(include_inactive=True)
        assert page.entries[0].state == "inactive"
        assert page.memory_ref is not None
        assert page.memory_ref.revision == initial + 1
        assert await lifecycle.resolve("memory", purpose="audit") == citation
        assert await lifecycle.apply(_event()) == []
        assert (await memory.list()).memory_ref == page.memory_ref
        assert await lifecycle.apply(_event(sequence=2, available=True)) == ["memory", "source"]
        restored = (await memory.list()).memory_ref
        assert restored is not None and restored.revision == initial + 2
        assert await lifecycle.resolve("memory") == citation


@pytest.mark.asyncio
async def test_binding_identity_missing_references_and_scope_isolation():
    async with open_builtin_runtime(BuiltinConfig(database=SQLiteConfig())) as runtime:
        assert runtime.scopes is not None
        first = (
            await runtime.scopes.create(ScopeDraft(title="First", summary="First", idempotency_key="first"))
        ).scope_id
        second = (
            await runtime.scopes.create(ScopeDraft(title="Second", summary="Second", idempotency_key="second"))
        ).scope_id
        left, source, citation = await _bind(runtime, first)
        right, _, _ = await _bind(runtime, second)
        before = (await runtime.memory.for_scope(first).list()).memory_ref
        await left.register_source("source", source, revision=3)
        await left.register_memory("memory", citation, parents=("source",))
        assert (await runtime.memory.for_scope(first).list()).memory_ref == before
        for parents in [("unknown",), ("source", "source"), ("new",), ()]:
            with pytest.raises(SourceLifecycleError):
                await left.register_memory("new", citation, parents=parents)
        with pytest.raises(SourceLifecycleError):
            await left.register_source("source", source, revision=4)
        with pytest.raises(SourceLifecycleError):
            await left.register_source("missing", SourceRef(source_type="content", source_id="missing"))
        with pytest.raises(SourceLifecycleError):
            await left.register_memory(
                "missing", citation.model_copy(update={"entry_version_id": "missing"}), parents=("source",)
            )
        with pytest.raises(SourceLifecycleError):
            await left.register_topic(
                "missing", ArtifactRef(family="topic-memory", artifact_id="missing", revision=1), parents=("source",)
            )
        with pytest.raises(SourceLifecycleError):
            await left.resolve("memory", purpose="other")
        with pytest.raises(SourceLifecycleError):
            await left.resolve("missing", purpose="audit")
        await left.apply(_event(reason="long reason " * 100))
        assert (await runtime.memory.for_scope(first).list()).entries == ()
        assert len((await runtime.memory.for_scope(second).list()).entries) == 1
        assert await right.resolve("source") == source
        with pytest.raises(SourceLifecycleError):
            await left.apply(_event(reason="different reason"))


class _Embedding:
    profile = EmbeddingProfile(profile_id="lifecycle", model="offline", dimension=2)

    async def embed(self, texts: tuple[str, ...], /) -> EmbeddingResult:
        return EmbeddingResult(vectors=tuple((1.0, 0.0) for _ in texts))


@pytest.mark.asyncio
async def test_topic_vector_fts_browse_and_exact_reads_preserve_history(tmp_path):
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'topics.db'}"))
    async with open_builtin_runtime(config, embedding_model=_Embedding()) as runtime:
        assert runtime.scopes is not None
        scope_id = (
            await runtime.scopes.create(ScopeDraft(title="Topics", summary="Topics", idempotency_key="topics"))
        ).scope_id
        lifecycle, _, _ = await _bind(runtime, scope_id)
        records = runtime.records.for_scope(scope_id)
        reference = None
        for node in ("withdrawn", "survivor"):
            created = await records.create_artifact(
                "topic-memory",
                ArtifactWrite(
                    content={
                        "title": node,
                        "summary": "Shared evidence summary",
                        "detail": "Shared detailed evidence",
                    }
                ),
            )
            ref = ArtifactRef(family="topic-memory", artifact_id=created.artifact_id, revision=created.revision)
            if node == "withdrawn":
                reference = ref
                await lifecycle.register_topic(node, ref, parents=("memory",))
        await lifecycle.apply(_event())
        assert reference is not None
        assert await lifecycle.resolve("withdrawn", purpose="audit") == reference
        topic = runtime.topic_memory.for_scope(scope_id)
        result = await topic.search(SearchTopicMemoryRequest(query="Shared", limit=1))
        assert [hit.title for hit in result.hits] == ["survivor"]
        assert {item.title for item in await topic.browse(limit=5)} == {"survivor"}
        exact = await topic.get(GetTopicMemoryRequest(artifact=reference))
        assert exact.topic.content.title == "withdrawn"
    async with open_builtin_runtime(config, embedding_model=_Embedding()) as runtime:
        lifecycle = runtime.lifecycle.for_scope(scope_id)
        topic = runtime.topic_memory.for_scope(scope_id)
        result = await topic.search(SearchTopicMemoryRequest(query="Shared", limit=5))
        assert [hit.title for hit in result.hits] == ["survivor"]
        await lifecycle.apply(_event(sequence=2, available=True))
        result = await topic.search(SearchTopicMemoryRequest(query="Shared", limit=5))
        assert {hit.title for hit in result.hits} == {"withdrawn", "survivor"}
        assert await lifecycle.resolve("withdrawn") == reference
