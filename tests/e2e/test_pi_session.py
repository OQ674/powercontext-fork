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

"""Pi recovery against real ingestion, SQLite checkpoints and exact citations."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import JsonValue

from powercontext.builtin.artifacts.memory import MemoryEntryInput
from powercontext.builtin.artifacts.memory.models import MemoryCitation
from powercontext.builtin.artifacts.memory.protocols import MemoryCandidateRequest
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import (
    BuiltinConfig,
    BuiltinRuntime,
    CommitConnectorCheckpoint,
    GetMemoryEntryRequest,
    SearchMemoryRequest,
    SubmitSourceObservation,
    open_builtin_contexts,
    open_builtin_runtime,
)
from powercontext.builtin.scope import ScopeDraft
from powercontext.errors import ConnectorSubmissionRejectedError
from powercontext.sources import (
    ConnectorBinding,
    ConnectorRunResult,
    ConnectorRunStatus,
    SourceDefinitionRegistry,
    SourceObservation,
    SourceRef,
    TextEvidence,
    manifest_for_definition,
    project_source_for_transport,
)
from powercontext.sources.connectors import ConnectorLifecycle
from powercontext.sources.pi_session import PI_EVENT_SOURCE_DEFINITION, PiEventInput, PiSessionConnector
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


class RuntimeSink:
    def __init__(self, runtime: BuiltinRuntime, *, fail: str | None = None, reject: str | None = None) -> None:
        self.runtime = runtime
        self.registry = SourceDefinitionRegistry((PI_EVENT_SOURCE_DEFINITION,))
        self.fail = fail
        self.reject = reject

    async def submit(
        self, binding: ConnectorBinding, item_id: str, definition_name: str, value: object, /
    ) -> SourceRef:
        assert isinstance(value, PiEventInput)
        assert definition_name == "pi-event"
        if value.event_id == self.fail:
            raise RuntimeError("injected sink failure")  # noqa: TRY003
        if value.event_id == self.reject:
            raise ConnectorSubmissionRejectedError("injected rejection")  # noqa: TRY003
        source = await self.registry.resolve(value)
        assert source.name == item_id
        result = await self.runtime.ingestion.submit(
            SubmitSourceObservation(
                scope_id=binding.scope_id, observation=project_source_for_transport(self.registry, source)
            )
        )
        return result.source_ref


class RuntimeCheckpoints:
    def __init__(self, runtime: BuiltinRuntime) -> None:
        self.runtime = runtime

    async def load(self, binding: ConnectorBinding, /) -> JsonValue | None:
        return (await self.runtime.ingestion.checkpoint(binding)).checkpoint

    async def save(
        self, binding: ConnectorBinding, checkpoint: JsonValue | None, /, *, expected: JsonValue | None
    ) -> None:
        await self.runtime.ingestion.commit(
            CommitConnectorCheckpoint(binding=binding, checkpoint=checkpoint, expected=expected)
        )


class ChunkedEvidencePipeline:
    async def extract(self, request: MemoryCandidateRequest, /) -> tuple[MemoryEntryInput, ...]:
        entries = []
        for source in request.sources:
            assert isinstance(source, SourceObservation)
            evidence = TextEvidence.model_validate(source.projection(TEXT_EVIDENCE_PROJECTION_KEY))
            for index in range(0, len(evidence.content), 1000):
                part = evidence.content[index : index + 1000]
                if part.strip():
                    entries.append(MemoryEntryInput(kind=f"event-part-{index}", text=part, sources=(source,)))
        return tuple(entries)


@pytest.mark.asyncio
async def test_native_failure_repair_off_branch_mutation_and_full_tool_citation(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    full_tool_result = "bigtoolquery 开始\n" + "原始工具输出" * 2000 + "\n末尾 bigtoolquery"
    records: list[dict[str, JsonValue]] = [
        {"type": "message", "id": "root", "parentId": None, "message": {"role": "user", "content": "shared request"}},
        {
            "type": "message",
            "id": "left",
            "parentId": "root",
            "message": {"role": "assistant", "content": "left evidence"},
        },
        {"type": "model_change", "id": "control", "parentId": "root"},
        {
            "type": "message",
            "id": "right",
            "parentId": "control",
            "message": {
                "role": "toolResult",
                "toolName": "read",
                "toolCallId": "call-1",
                "content": [{"type": "text", "text": full_tool_result}],
            },
        },
    ]

    def write(rows: list[dict[str, JsonValue]]) -> None:
        header = {"type": "session", "version": 3, "id": "durable"}
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in [header, *rows]) + "\n", encoding="utf-8"
        )

    write(records)
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'pi.db'}"))
    async with open_builtin_runtime(config) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(ScopeDraft(title="Pi", summary="Recovery", idempotency_key="pi"))
        await runtime.ingestion.register(manifest_for_definition(PI_EVENT_SOURCE_DEFINITION))
    binding = ConnectorBinding(
        scope_id=scope.scope_id, binding_id="pi", connector_name="pi-session-history", connector_version="1"
    )

    async def run(leaf: str, *, fail: str | None = None, reject: str | None = None) -> ConnectorRunResult:
        async with open_builtin_runtime(config) as runtime:
            return await ConnectorLifecycle(
                sink=RuntimeSink(runtime, fail=fail, reject=reject), checkpoints=RuntimeCheckpoints(runtime)
            ).run(PiSessionConnector(path, leaf), binding)

    async def snapshot() -> tuple[JsonValue | None, dict[str, SourceObservation]]:
        async with open_builtin_runtime(config) as runtime:
            checkpoint = (await runtime.ingestion.checkpoint(binding)).checkpoint
        async with open_builtin_contexts(config) as contexts:
            entries = await (await contexts.get(binding.scope_id)).sources.journal.entries()
            stored: dict[str, SourceObservation] = {}
            for entry in entries:
                assert isinstance(entry.source, SourceObservation)
                event_id = entry.source.payload["event_id"]
                assert isinstance(event_id, str)
                stored[event_id] = entry.source
        return checkpoint, stored

    # A durable partial write must be safe to retry after recreating the runtime.
    with pytest.raises(RuntimeError, match="injected sink failure"):
        await run("left", fail="left")
    checkpoint, stored = await snapshot()
    assert checkpoint is None and set(stored) == {"root"}
    first = await run("left")
    checkpoint, stored = await snapshot()
    assert checkpoint == first.committed_checkpoint and set(stored) == {"root", "left"}

    # Changing an imported event on the other branch must fail before right is submitted.
    original = deepcopy(records)
    records[1]["extra"] = {"changed": True}
    write(records)
    with pytest.raises(ValueError, match="changed or removed"):
        await run("right")
    assert await snapshot() == (checkpoint, stored)
    records = original
    write(records)
    second = await run("right")
    assert len(second.items) == 1 and second.previous_checkpoint == checkpoint
    assert (await run("right")).items == ()
    checkpoint, stored = await snapshot()
    assert set(stored) == {"root", "left", "right"}
    right = stored["right"]
    assert right.payload["record"] == records[3]
    expected_content = f"toolResult: [tool_result read call-1] {full_tool_result}"
    assert len(expected_content.encode("utf-8")) > 8192
    assert TextEvidence.model_validate(right.projection(TEXT_EVIDENCE_PROJECTION_KEY)).content == expected_content

    # Typed rejection and malformed input must leave the same durable progress.
    records.append({"type": "custom_message", "id": "tail", "parentId": "right", "content": "tail evidence"})
    write(records)
    rejected = await run("tail", reject="tail")
    assert rejected.status is ConnectorRunStatus.INCOMPLETE
    assert rejected.committed_checkpoint == checkpoint
    assert await snapshot() == (checkpoint, stored)
    with path.open("ab") as stream:
        stream.write(b"{bad json}\n")
    with pytest.raises(ValueError):
        await run("tail")
    assert await snapshot() == (checkpoint, stored)
    write(records)
    repaired = await run("tail")
    assert repaired.previous_checkpoint == checkpoint and len(repaired.items) == 1

    # Memory stores bounded chunks; the exact citation resolves the full Source.
    async with open_builtin_runtime(config, candidate_pipeline=ChunkedEvidencePipeline()) as runtime:
        memory = runtime.memory.for_scope(binding.scope_id)
        flushed = await memory.flush()
        assert flushed.processed and flushed.source_count == 4
        search = await memory.search(SearchMemoryRequest(query="bigtoolquery", mode="fts", limit=100))
        assert search.hits
        for hit in search.hits:
            citation = MemoryCitation(
                memory_ref=hit.memory_ref, entry_id=hit.entry_id, entry_version_id=hit.entry_version_id
            )
            entry = await memory.get(GetMemoryEntryRequest(citation=citation))
            assert any(source.source_id == right.name for source in entry.entry.sources)
    async with open_builtin_contexts(config) as contexts:
        context = await contexts.get(binding.scope_id)
        assert await context.sources.get(right) == right
        restored = TextEvidence.model_validate(right.projection(TEXT_EVIDENCE_PROJECTION_KEY))
        assert restored.content == expected_content
