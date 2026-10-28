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

"""Pi branch parsing and exact captured-event fidelity."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import JsonValue

from powercontext.sources import SourceDefinitionRegistry, SourceMaterialization, TextEvidence
from powercontext.sources.pi_session import (
    PI_EVENT_SOURCE_DEFINITION,
    PiEventSource,
    PiSessionInput,
    parse_pi_session,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


def archive(records: list[dict[str, JsonValue]], *, session_id: str = "session") -> bytes:
    header = {"type": "session", "version": 3, "id": session_id}
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in [header, *records]).encode("utf-8")


def test_full_branch_retains_raw_records_and_exact_visible_text() -> None:
    records: list[dict[str, JsonValue]] = [
        {"type": "message", "id": "root", "parentId": None, "message": {"role": "user", "content": "  请求\n原文  "}},
        {"type": "thinking_level_change", "id": "control", "parentId": "root", "level": "high"},
        {
            "type": "message",
            "id": "call",
            "parentId": "control",
            "timestamp": "2026-01-01T00:00:00Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "private"},
                    {"type": "text", "text": "先读取"},
                    {"type": "image", "data": "hidden image"},
                    {"type": "toolCall", "name": "read", "id": "工具/1", "arguments": {"z": 2, "a": {"字": True}}},
                    {"type": "text", "text": "随后分析"},
                ],
                "usage": {"input": 12},
            },
        },
        {"type": "compaction", "id": "compact", "parentId": "call", "summary": "摘要", "firstKeptEntryId": "call"},
        {"type": "branch_summary", "id": "summary", "parentId": "compact", "summary": "分支摘要", "fromId": "root"},
        {
            "type": "custom_message",
            "id": "custom",
            "parentId": "summary",
            "content": [{"type": "text", "text": "自定义"}],
        },
    ]
    events = parse_pi_session(PiSessionInput(content=archive(records)))
    assert [event.event_id for event in events] == ["root", "call", "compact", "summary", "custom"]
    assert [event.content for event in events] == [
        "user:   请求\n原文  ",
        'assistant: 先读取\n[tool_call read 工具/1] {"a":{"字":true},"z":2}\n随后分析',
        "compaction: 摘要",
        "branch_summary: 分支摘要",
        "custom: 自定义",
    ]
    assert events[1].parent_id == "control"
    assert events[1].record == records[2]
    registry = SourceDefinitionRegistry((PI_EVENT_SOURCE_DEFINITION,))
    for event in events:
        source = asyncio.run(registry.resolve(event))
        assert isinstance(source, PiEventSource)
        assert source.materialization == SourceMaterialization.CAPTURED
        restored = PiEventSource.model_validate_json(source.model_dump_json())
        assert asyncio.run(registry.read(restored)) == event
        evidence = TextEvidence.model_validate(registry.project(restored, TEXT_EVIDENCE_PROJECTION_KEY))
        assert evidence.source_id == source.source_id == source.name
        assert evidence.content == event.content
        assert evidence.metadata == {
            "session_id": event.session_id,
            "event_id": event.event_id,
            "parent_id": event.parent_id,
            "event_type": event.event_type,
            "role": event.role,
        }


def test_control_leaf_empty_session_and_unicode_line_separators() -> None:
    assert parse_pi_session(PiSessionInput(content=archive([]))) == ()
    with pytest.raises(ValueError):
        parse_pi_session(PiSessionInput(content=archive([]), leaf_id="missing"))
    records: list[dict[str, JsonValue]] = [
        {"type": "message", "id": "a", "parentId": "", "message": {"role": "user", "content": "a\u2028b\u2029c"}},
        {
            "type": "message",
            "id": "b",
            "parentId": "a",
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "hidden"}]},
        },
        {"type": "model_change", "id": "c", "parentId": "b"},
        {"type": "message", "id": "other", "parentId": None, "message": {"role": "user", "content": "other root"}},
    ]
    content = b"\xef\xbb\xbf\r\n" + archive(records).replace(b"\n", b"\r\n") + b"\r\n\r\n"
    events = parse_pi_session(PiSessionInput(content=content, leaf_id="c"))
    assert [event.event_id for event in events] == ["a"]
    assert events[0].content == "user: a\u2028b\u2029c"
    assert parse_pi_session(PiSessionInput(content=content))[0].event_id == "other"


@pytest.mark.parametrize(
    "bad_record",
    [
        {"type": "model_change", "id": "bad"},
        {"type": "model_change", "id": "bad", "parentId": "later"},
        {"type": "model_change", "id": "bad", "parentId": "bad"},
        {"type": "model_change", "id": "bad", "parentId": []},
        {"type": "model_change", "id": "a", "parentId": None},
        {"type": "model_change", "id": "", "parentId": None},
        {"type": "model_change", "id": 123, "parentId": None},
        {"type": [], "id": "bad", "parentId": None},
    ],
)
def test_invalid_unselected_history_also_rejects_the_complete_input(bad_record: dict[str, JsonValue]) -> None:
    valid: dict[str, JsonValue] = {
        "type": "message",
        "id": "a",
        "parentId": None,
        "message": {"role": "user", "content": "valid"},
    }
    with pytest.raises(ValueError):
        parse_pi_session(PiSessionInput(content=archive([valid, bad_record]), leaf_id="a"))


@pytest.mark.parametrize(
    "raw",
    [
        b"\xef\xbb\xbf",
        b'{"type":"session","version":3,"id":""}',
        b'{"type":"session","version":3,"id":1}',
        b'{"type":"session","version":3.0,"id":"x"}',
        b'{"type":"session","version":3,"id":"x","bad":NaN}',
        b'{"type":"session","version":3,"id":"x"}\n{"bad":Infinity}',
        b'{"type":"session","version":3,"id":"x"}\n\xff',
    ],
)
def test_invalid_encoding_and_header_fail_as_value_errors(raw: bytes) -> None:
    with pytest.raises(ValueError):
        parse_pi_session(PiSessionInput(content=raw))


def test_long_identity_components_are_bounded_distinct_and_stable() -> None:
    registry = SourceDefinitionRegistry((PI_EVENT_SOURCE_DEFINITION,))

    def identity(session_id: str, event_id: str) -> str:
        records: list[dict[str, JsonValue]] = [
            {"type": "message", "id": event_id, "parentId": None, "message": {"role": "user", "content": "original"}}
        ]
        event = parse_pi_session(PiSessionInput(content=archive(records, session_id=session_id)))[0]
        return asyncio.run(registry.resolve(event)).name

    pairs = [("s:a", "b"), ("s", "a:b"), ("s%3Aa", "b"), ("会话" * 300, "事件" * 300)]
    names = [identity(*pair) for pair in pairs]
    assert len(set(names)) == len(pairs)
    assert all(len(name) <= 256 for name in names)
    assert names == [identity(*pair) for pair in pairs]
