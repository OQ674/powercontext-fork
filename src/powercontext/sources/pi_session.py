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

"""Capture complete Pi v3 branch evidence with durable, immutable progress."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from powercontext.sources.connectors import (
    ConnectorRunCompletion,
    ConnectorRunSession,
    ConnectorRunStatus,
    ConnectorSubmissionStatus,
)
from powercontext.sources.definitions import SourceDefinition, SourceProjection
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence


class PiSessionInput(BaseModel):
    """An entire offline Pi JSONL archive and an optional selected leaf."""

    content: bytes
    leaf_id: str | None = None


class PiEventInput(BaseModel):
    """One visible event, including its complete unmodified input record."""

    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: dict[str, JsonValue]


class PiEventSource(Source):
    """Captured original evidence independent of the model's compacted view."""

    source_id: str
    session_id: str
    event_id: str
    parent_id: str | None
    event_type: str
    role: str
    content: str
    record: dict[str, JsonValue]


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_json_text(value).encode("utf-8")).hexdigest()


def _event_identity(session_id: str, event_id: str) -> str:
    # A framed pair avoids delimiter ambiguity; the digest bounds even long IDs.
    return f"pi:{_digest([session_id, event_id])}"


def _require_id(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Pi IDs must be nonempty strings")  # noqa: TRY003
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")  # noqa: TRY003


def _visible_content(content: JsonValue, *, tool_calls: bool = False) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if block.get("type") == "text" and isinstance(text, str):
            parts.append(text)
        elif tool_calls and block.get("type") == "toolCall":
            arguments = _json_text(block.get("arguments", {}))
            parts.append(f"[tool_call {block.get('name', '')} {block.get('id', '')}] {arguments}")
    return "\n".join(parts) if any(parts) else ""


def _parent_id(record: dict[str, JsonValue]) -> str | None:
    if "parentId" not in record:
        raise ValueError("Pi events must have an explicit parentId")  # noqa: TRY003
    parent = record["parentId"]
    if parent is not None and not isinstance(parent, str):
        raise ValueError("Pi parentId must be a string or null")  # noqa: TRY003
    return parent


def _visible_event(session_id: str, record: dict[str, JsonValue]) -> PiEventInput | None:
    event_type = _require_id(record.get("type"))
    if event_type in {"compaction", "branch_summary"}:
        role, body = str(event_type), record.get("summary", "")
    elif event_type == "custom_message":
        role, body = "custom", _visible_content(record.get("content"))
    elif event_type == "message":
        message = record.get("message")
        if not isinstance(message, dict):
            raise ValueError("Pi message records must contain a message object")  # noqa: TRY003
        role = message.get("role")
        body = _visible_content(message.get("content"), tool_calls=True)
        if role == "toolResult":
            body = f"[tool_result {message.get('toolName', '')} {message.get('toolCallId', '')}] {body}"
        elif role == "bashExecution":
            body = f"$ {message.get('command', '')}\n{message.get('output', '')}"
    else:
        return None
    if not isinstance(body, str) or not isinstance(role, str):
        raise ValueError("Pi visible event roles and bodies must be strings")  # noqa: TRY003, TRY004
    if not body:
        return None
    return PiEventInput(
        session_id=session_id,
        event_id=_require_id(record["id"]),
        parent_id=_parent_id(record),
        event_type=event_type,
        role=role,
        content=f"{role}: {body}",
        record=record,
    )


def _read_records(content: bytes) -> list[dict[str, JsonValue]]:
    records: list[dict[str, JsonValue]] = []
    for line in io.StringIO(content.decode("utf-8-sig", errors="strict")):
        if not line.strip():
            continue
        record = json.loads(line, parse_constant=_reject_json_constant)
        if not isinstance(record, dict):
            raise ValueError("Pi JSONL records must be objects")  # noqa: TRY003, TRY004
        records.append(record)
    return records


def _parse_archive(value: PiSessionInput) -> tuple[str, dict[str, dict[str, JsonValue]], tuple[PiEventInput, ...]]:
    records = _read_records(value.content)
    if not records:
        raise ValueError("Pi archives must begin with a v3 session header")  # noqa: TRY003
    header = records[0]
    if header.get("type") != "session" or type(header.get("version")) is not int or header["version"] != 3:
        raise ValueError("Pi archives must begin with a v3 session header")  # noqa: TRY003
    session_id = _require_id(header.get("id"))
    by_id: dict[str, dict[str, JsonValue]] = {}
    parents: dict[str, str | None] = {}
    visible: dict[str, PiEventInput] = {}
    for record in records[1:]:
        event_id = _require_id(record.get("id"))
        if event_id in by_id:
            raise ValueError("Pi events must have unique IDs")  # noqa: TRY003
        parent = _parent_id(record)
        if parent and parent not in by_id:
            raise ValueError("Pi parents must be empty or refer to an earlier node")  # noqa: TRY003
        by_id[event_id] = record
        parents[event_id] = parent
        event = _visible_event(session_id, record)
        if event is not None:
            visible[event_id] = event
    leaf_id = value.leaf_id if value.leaf_id is not None else next(reversed(by_id), None)
    if leaf_id is not None and leaf_id not in by_id:
        raise ValueError("The selected Pi leaf does not exist")  # noqa: TRY003
    chain: list[PiEventInput] = []
    while leaf_id:
        if leaf_id in visible:
            chain.append(visible[leaf_id])
        leaf_id = parents[leaf_id]
    return session_id, by_id, tuple(reversed(chain))


def parse_pi_session(value: PiSessionInput) -> tuple[PiEventInput, ...]:
    """Validate the whole archive and return the selected root-to-leaf evidence."""

    return _parse_archive(value)[2]


class PiEventTextEvidenceProjection:
    """Project full event text without the Memory entry size limitation."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class: type[PiEventSource] = PiEventSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PiEventSource, /) -> TextEvidence:
        return TextEvidence(
            source_type="pi-event",
            source_id=source.name,
            content=source.content,
            metadata={
                "session_id": source.session_id,
                "event_id": source.event_id,
                "parent_id": source.parent_id,
                "event_type": source.event_type,
                "role": source.role,
            },
        )


class PiEventSourceDefinition:
    """Bind immutable Pi events to the native Source registry and transport."""

    input_class: type[PiEventInput] = PiEventInput
    source_class: type[PiEventSource] = PiEventSource
    name = "pi-event"
    version = "1"
    projections: tuple[SourceProjection[PiEventSource], ...] = (PiEventTextEvidenceProjection(),)

    async def resolve(self, value: PiEventInput, /) -> PiEventSource:
        identity = _event_identity(value.session_id, value.event_id)
        return PiEventSource(
            name=identity,
            source_id=identity,
            definition_version=self.version,
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: PiEventSource, /) -> PiEventInput:
        return PiEventInput(
            session_id=source.session_id,
            event_id=source.event_id,
            parent_id=source.parent_id,
            event_type=source.event_type,
            role=source.role,
            content=source.content,
            record=source.record,
        )


PI_EVENT_SOURCE_DEFINITION: SourceDefinition[PiEventInput, PiEventSource, PiEventInput] = PiEventSourceDefinition()


class _PiCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    session_id: str
    events: dict[str, str] = Field(default_factory=dict)


class PiSessionConnector:
    """Import a selected branch using only lifecycle-managed durable progress."""

    name = "pi-session-history"
    version = "1"
    source_definitions = frozenset({"pi-event"})

    def __init__(self, path: str | Path, leaf_id: str | None = None) -> None:
        self.path = Path(path)
        self.leaf_id = leaf_id

    async def run(self, session: ConnectorRunSession, /) -> ConnectorRunCompletion:
        content = await asyncio.to_thread(self.path.read_bytes)
        session_id, records, events = _parse_archive(PiSessionInput(content=content, leaf_id=self.leaf_id))
        previous = (
            _PiCheckpoint(session_id=session_id)
            if session.checkpoint is None
            else _PiCheckpoint.model_validate(session.checkpoint)
        )
        if previous.session_id != session_id:
            raise ValueError("The checkpoint belongs to a different Pi session")  # noqa: TRY003
        # Check imported events across every branch, including events now hidden
        # by a changed role or body. Do this before submitting any new evidence.
        for event_id, digest in previous.events.items():
            if event_id not in records or _digest(records[event_id]) != digest:
                raise ValueError("An imported Pi event was changed or removed")  # noqa: TRY003
        imported = dict(previous.events)
        for event in events:
            if event.event_id in imported:
                continue
            outcome = await session.submit(_event_identity(session_id, event.event_id), "pi-event", event)
            if outcome.status is not ConnectorSubmissionStatus.ACCEPTED:
                return ConnectorRunCompletion(status=ConnectorRunStatus.INCOMPLETE, checkpoint=session.checkpoint)
            imported[event.event_id] = _digest(event.record)
        checkpoint = _PiCheckpoint(session_id=session_id, events=imported)
        return ConnectorRunCompletion(status=ConnectorRunStatus.COMPLETE, checkpoint=checkpoint.model_dump(mode="json"))
