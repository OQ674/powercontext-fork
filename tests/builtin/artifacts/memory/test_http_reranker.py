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

"""HTTP reranking boundaries, global identities and transport semantics."""

from __future__ import annotations

import asyncio
import json
from typing import cast

import httpx
import pytest

from powercontext.artifacts import ArtifactRef
from powercontext.builtin.artifacts.memory.http_reranker import HTTPMemoryReranker
from powercontext.builtin.artifacts.memory.models import MemoryHit


def hit(rank: int) -> MemoryHit:
    return MemoryHit(
        memory_ref=ArtifactRef(family="memory", artifact_id=f"memory-{rank % 3}", revision=rank % 3 + 1),
        entry_id=f"entry-{rank}",
        entry_version_id=f"version-{rank}",
        text=f'  原文 {rank}\n"quoted" ',
        score=1 / rank,
        matched_by=("fts",),
    )


def test_full_173_candidate_pool_keeps_global_ranks_ties_and_actual_request_count() -> None:
    candidates = tuple(hit(rank) for rank in range(1, 174))
    original = tuple(candidate.model_dump_json() for candidate in candidates)
    sent: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert set(body) == {"query", "candidates"} and body["query"] == "原始查询"
        assert request.headers["x-client-setting"] == "preserved"
        assert request.method == "POST" and request.url.path == "/score"
        assert 1 <= len(body["candidates"]) <= 7
        scores = []
        for item in body["candidates"]:
            assert set(item) == {"rank", "text"}
            rank = item["rank"]
            assert item["text"] == candidates[rank - 1].text
            sent.append(rank)
            scores.append({"rank": rank, "score": 1000 if rank in (172, 173) else rank})
        return httpx.Response(200, json={"scores": list(reversed(scores))})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://score.invalid",
            headers={"x-client-setting": "preserved"},
        ) as client:
            reranker = HTTPMemoryReranker("/score", client=client, batch_size=7, policy_id="custom-policy")
            decision = await reranker.rerank("原始查询", candidates, 10)
            assert not client.is_closed and reranker.policy_id == "custom-policy"
        assert decision.selected_ranks == (172, 173, 171, 170, 169, 168, 167, 166, 165, 164)
        assert decision.usage.requests == 25
        assert decision.discarded_rank_count == 0 and not decision.used_fallback
        assert sent == list(range(1, 174))
        assert tuple(candidate.model_dump_json() for candidate in candidates) == original

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"scores": None},
        {"scores": {}},
        {"scores": []},
        {"scores": [{"rank": 1}]},
        {"scores": [{"score": 0.5}]},
        {"scores": [{"rank": True, "score": 0.5}]},
        {"scores": [{"rank": 1.0, "score": 0.5}]},
        {"scores": [{"rank": "1", "score": 0.5}]},
        {"scores": [{"rank": 0, "score": 0.5}]},
        {"scores": [{"rank": -1, "score": 0.5}]},
        {"scores": [{"rank": 1, "score": True}]},
        {"scores": [{"rank": 1, "score": "0.5"}]},
        {"scores": [{"rank": 1, "score": None}]},
        {"scores": [{"rank": 1, "score": float("-inf")}]},
    ],
)
def test_strict_response_values_are_rejected(payload: object) -> None:
    async def scenario() -> None:
        transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=json.dumps(payload).encode()))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError):
                await HTTPMemoryReranker("https://score.invalid", client=client).rerank("q", (hit(1),), 1)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "content", [b"not json", b"\xff", b'{"scores":[],"scores":[]}', b'{"scores":[{"rank":1,"rank":1,"score":0.5}]}']
)
def test_malformed_json_and_duplicate_fields_are_value_errors(content: bytes) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=content))
        ) as client:
            with pytest.raises(ValueError):
                await HTTPMemoryReranker("https://score.invalid", client=client).rerank("q", (hit(1),), 1)

    asyncio.run(scenario())


def test_cross_batch_rank_is_rejected_even_if_it_is_globally_valid() -> None:
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        rank = body["candidates"][0]["rank"]
        sent.append(rank)
        return httpx.Response(200, json={"scores": [{"rank": 1, "score": 0.5}]})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError):
                await HTTPMemoryReranker("https://score.invalid", client=client, batch_size=1).rerank(
                    "q", (hit(1), hit(2)), 1
                )
        assert sent == [1, 2]

    asyncio.run(scenario())


def test_large_integer_scores_do_not_lose_ordering_precision() -> None:
    async def scenario() -> None:
        payload = {"scores": [{"rank": 1, "score": 2**80}, {"rank": 2, "score": 2**80 + 1}]}
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload))
        ) as client:
            decision = await HTTPMemoryReranker("https://score.invalid", client=client).rerank("q", (hit(1), hit(2)), 2)
            assert decision.selected_ranks == (2, 1)

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [204, 301, 400, 429, 500])
def test_http_statuses_and_redirects_do_not_trigger_extra_requests(status: int) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, headers={"Location": "https://redirect.invalid"}, content=b"invalid json")

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
            expected = ValueError if status == 204 else httpx.HTTPStatusError
            with pytest.raises(expected):
                await HTTPMemoryReranker("https://score.invalid", client=client).rerank("q", (hit(1),), 1)
        assert len(seen) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_transport_exception_is_preserved(error_type: type[httpx.RequestError]) -> None:
    original = error_type("transport failed")

    def handler(_request: httpx.Request) -> httpx.Response:
        raise original

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(error_type) as caught:
                await HTTPMemoryReranker("https://score.invalid", client=client).rerank("q", (hit(1),), 1)
            assert caught.value is original

    asyncio.run(scenario())


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5, "2"])
def test_invalid_batch_size_fails_before_io(batch_size: object) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: pytest.fail("unexpected HTTP"))
        ) as client:
            with pytest.raises(ValueError):
                HTTPMemoryReranker("https://score.invalid", client=client, batch_size=cast(int, batch_size))

    asyncio.run(scenario())


@pytest.mark.parametrize("limit", [0, -1, 2, True, 1.5, "1"])
def test_invalid_limit_fails_before_io(limit: object) -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: pytest.fail("unexpected HTTP"))
        ) as client:
            with pytest.raises(ValueError):
                await HTTPMemoryReranker("https://score.invalid", client=client).rerank(
                    "q", (hit(1),), cast(int, limit)
                )

    asyncio.run(scenario())
