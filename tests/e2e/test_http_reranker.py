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

"""HTTP decisions applied to real, reopened scoped Memory and exact citations."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from powercontext.builtin.artifacts.memory import MemoryEntryInput
from powercontext.builtin.artifacts.memory.http_reranker import HTTPMemoryReranker
from powercontext.builtin.artifacts.memory.models import MemoryCitation
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import (
    BuiltinConfig,
    GetMemoryEntryRequest,
    RememberMemoryRequest,
    RuntimeConfig,
    SearchMemoryRequest,
    open_builtin_runtime,
)
from powercontext.builtin.scope import ScopeDraft


@pytest.mark.asyncio
async def test_cross_batch_decision_preserves_reopened_memory_hits_and_citations(tmp_path: Path) -> None:
    config = BuiltinConfig(
        database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'rerank.db'}"),
        runtime=RuntimeConfig(memory_rerank_candidate_limit=36),
    )
    async with open_builtin_runtime(config) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(
            ScopeDraft(title="Calibration", summary="HTTP scores", idempotency_key="rerank")
        )
        await runtime.memory.for_scope(scope.scope_id).remember(
            RememberMemoryRequest(
                entries=tuple(
                    MemoryEntryInput(kind="fact", text=f"Calibration evidence {index}: original instrument record.")
                    for index in range(36)
                )
            )
        )

    sent: list[tuple[int, str]] = []
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        body = json.loads(request.content)
        assert body["query"] == "calibration" and 1 <= len(body["candidates"]) <= 7
        sent.extend((item["rank"], item["text"]) for item in body["candidates"])
        return httpx.Response(
            200,
            json={
                "scores": [
                    {"rank": item["rank"], "score": float(item["rank"])} for item in reversed(body["candidates"])
                ]
            },
        )

    citations: list[MemoryCitation] = []
    texts = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        reranker = HTTPMemoryReranker(
            "https://score.invalid", client=client, batch_size=7, policy_id="local-http-scoring"
        )
        async with open_builtin_runtime(config, memory_reranker=reranker) as runtime:
            memory = runtime.memory.for_scope(scope.scope_id)
            result = await memory.search(SearchMemoryRequest(query="calibration", mode="fts", limit=5))
            trace = result.rerank
            assert trace is not None and len(trace.candidate_hits) == 36
            assert trace.policy_id == "local-http-scoring"
            assert trace.selected_ranks == (36, 35, 34, 33, 32)
            assert trace.usage.requests == requests == 6
            assert result.hits == tuple(trace.candidate_hits[rank - 1] for rank in trace.selected_ranks)
            assert sent == [(rank, hit.text) for rank, hit in enumerate(trace.candidate_hits, start=1)]
            for hit in result.hits:
                citation = MemoryCitation(
                    memory_ref=hit.memory_ref, entry_id=hit.entry_id, entry_version_id=hit.entry_version_id
                )
                entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
                assert entry.text == hit.text and entry.entry_version_id == hit.entry_version_id
                citations.append(citation)
                texts.append(hit.text)
            second = await memory.search(SearchMemoryRequest(query="calibration", mode="fts", limit=1))
            assert second.rerank is not None and second.rerank.usage.requests == 6
            assert requests == 12
        assert not client.is_closed
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope.scope_id)
        for citation, text in zip(citations, texts, strict=True):
            entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
            assert entry.entry_version_id == citation.entry_version_id and entry.text == text
