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

"""Candidate statement budget, bound filters and current-reference adaptation.

These use an isolated connection double; native execution and index plans are
covered separately by the Linux seekdb acceptance scenario.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import mysql

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory import (
    CapabilityNotSupportedError,
    EmbeddingProfile,
    MemorySearchChannels,
    MemorySearchRequest,
)
from powercontext.builtin.persistence.memory_index import CompositeMemoryIndex
from powercontext.builtin.persistence.oceanbase.memory_index import OceanBaseMemoryVectorIndex
from powercontext.builtin.persistence.seekdb.memory_index import SeekDBMemoryIndex
from powercontext.builtin.tags import TagFilter

PROFILE = EmbeddingProfile(profile_id="hybrid-test", model="offline", dimension=3, distance="l2", normalization="unit")
HEAD = ArtifactRef(family="memory", artifact_id="memory-current", revision=9)


def _request(**changes) -> MemorySearchRequest:
    return MemorySearchRequest.model_validate({
        "query": "alpha",
        "analyzed_query": "alpha",
        "memories": (HEAD,),
        "candidate_limit": 7,
        "mode": "hybrid",
        "query_vector": (1.0, 0.0, 0.0),
        "embedding_profile": PROFILE,
        **changes,
    })


@pytest.mark.asyncio
@pytest.mark.parametrize("tag_filter", [None, TagFilter(tags=("chosen",)), TagFilter(tags=("one", "two"), match="any")])
async def test_one_candidate_statement_keeps_channels_and_current_head_references(monkeypatch, tag_filter) -> None:
    monkeypatch.setattr(OceanBaseMemoryVectorIndex, "vector_complete", AsyncMock(return_value=True))
    rows = [
        {
            "channel": channel,
            "memory_artifact_id": HEAD.artifact_id,
            "head_revision": 2,
            "entry_id": entry,
            "entry_version_id": entry + "-v1",
            "text": body,
            "distance": distance,
        }
        for channel, entry, body, distance in (
            ("fts", "lexical", "alpha exact original body", None),
            ("vector", "semantic", "a related exact original body", 0.2),
            ("vector", "lexical", "alpha exact original body", 0.4),
        )
    ]
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    connection = AsyncMock()
    connection.execute.return_value = result
    channels = await SeekDBMemoryIndex(PROFILE).search(connection, "scope-1", _request(tag_filter=tag_filter))
    assert connection.execute.await_count == 1
    assert [hit.entry_id for hit in channels.fts] == ["lexical"]
    assert [hit.entry_id for hit in channels.vector] == ["semantic", "lexical"]
    assert all(hit.memory_ref == HEAD for hit in (*channels.fts, *channels.vector))
    assert channels.fts[0].text == "alpha exact original body"
    assert channels.vector[0].distance == 0.2
    statement, parameters = connection.execute.await_args.args
    compiled = statement.params(**parameters).compile(
        dialect=mysql.dialect(), compile_kwargs={"render_postcompile": True}
    )
    assert "scope-1" not in compiled.string
    assert "memory-current" not in compiled.string
    assert compiled.params["scope_id"] == "scope-1"
    assert compiled.params["candidate_limit"] == 7
    if tag_filter is not None:
        assert compiled.params["tag_minimum"] == (len(tag_filter.tags) if tag_filter.match == "all" else 1)


@pytest.mark.asyncio
async def test_query_and_tags_remain_bound_values(monkeypatch) -> None:
    monkeypatch.setattr(OceanBaseMemoryVectorIndex, "vector_complete", AsyncMock(return_value=True))
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    connection = AsyncMock()
    connection.execute.return_value = result
    query = "alpha' UNION SELECT secret --"
    tag = "chosen' OR 1=1 --"
    channels = await SeekDBMemoryIndex(PROFILE).search(
        connection,
        "scope-1",
        _request(
            query=query,
            analyzed_query=query,
            tag_filter=TagFilter(tags=(tag,)),
        ),
    )
    assert channels == MemorySearchChannels()
    statement, parameters = connection.execute.await_args.args
    compiled = statement.params(**parameters).compile(
        dialect=mysql.dialect(), compile_kwargs={"render_postcompile": True}
    )
    assert query not in compiled.string and tag not in compiled.string
    assert compiled.params["query"] == query


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [{"query_vector": None}, {"embedding_profile": None}])
async def test_invalid_embedding_does_not_execute_candidate_statement(changes) -> None:
    connection = AsyncMock()
    with pytest.raises(CapabilityNotSupportedError):
        await SeekDBMemoryIndex(PROFILE).search(connection, "scope", _request(**changes))
    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("complete", [False, CapabilityNotSupportedError("head")])
async def test_incomplete_projection_and_stale_head_preserve_existing_rejection(monkeypatch, complete) -> None:
    check = AsyncMock(side_effect=complete) if isinstance(complete, Exception) else AsyncMock(return_value=complete)
    monkeypatch.setattr(OceanBaseMemoryVectorIndex, "vector_complete", check)
    connection = AsyncMock()
    with pytest.raises(CapabilityNotSupportedError):
        await SeekDBMemoryIndex(PROFILE).search(connection, "scope", _request())
    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["fts", "vector"])
async def test_single_channel_search_keeps_existing_adapter_behavior(monkeypatch, mode) -> None:
    channels = MemorySearchChannels()
    original = AsyncMock(return_value=channels)
    monkeypatch.setattr(CompositeMemoryIndex, "search", original)
    connection = AsyncMock()
    request = _request(mode=mode)
    assert await SeekDBMemoryIndex(PROFILE).search(connection, "scope", request) is channels
    original.assert_awaited_once_with(connection, "scope", request)
