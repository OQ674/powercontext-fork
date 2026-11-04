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

"""Real ingestion, retries, revisions and separately scored report collections."""

from __future__ import annotations

import io
import json
import re
import socket
from collections import Counter
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from pypdf import PdfReader

from powercontext.builtin.persistence.memory import RelationalMemoryBackend
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import (
    BuiltinConfig,
    GetMemoryEntryRequest,
    MemoryEntryInput,
    RememberMemoryRequest,
    SubmitSourceObservation,
    open_builtin_runtime,
)
from powercontext.builtin.scope import ScopeDraft
from powercontext.sources import SourceDefinitionRegistry, manifest_for_definition, project_source_for_transport
from powercontext.sources.pdf_pages import (
    PDF_PAGE_SOURCE_DEFINITION,
    PDFDocumentInput,
    parse_pdf_document,
    search_pdf_pages,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY
from tests.pdf_financial_quality import PagePipeline, reports
from tests.test_pdf_pages import pdf_bytes


@pytest_asyncio.fixture(autouse=True)
async def offline_evidence_checks(monkeypatch):
    """Build the event loop first, then reject all outbound connections."""

    def deny_network(*args, **kwargs):
        raise AssertionError("PDF ingestion and retrieval must remain offline")  # noqa: TRY003

    with monkeypatch.context() as patch:
        patch.setattr(socket.socket, "connect", deny_network)
        patch.setattr(socket, "create_connection", deny_network)
        yield


async def _submit(runtime, scope_id, raw, identifier):
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    result = []
    for page in parse_pdf_document(PDFDocumentInput(document_id=identifier, content=raw)):
        observation = project_source_for_transport(registry, await registry.resolve(page))
        await runtime.ingestion.submit(SubmitSourceObservation(scope_id=scope_id, observation=observation))
        result.append(observation)
    return result


async def _flush(memory):
    for _ in range(100):
        if not (await memory.flush()).processed:
            return
    raise AssertionError("source processing failed to drain")  # noqa: TRY003


@pytest.mark.asyncio
async def test_real_retry_scopes_revisions_and_identical_pages(tmp_path, monkeypatch):
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'pages.db'}"))
    old_raw = pdf_bytes(("Revenue 700 cash 200", "Revenue 700 cash 200"), title="old")
    new_raw = pdf_bytes(("Revenue 700 cash 200", "Revenue 700 cash 200"), title="new metadata")
    async with open_builtin_runtime(config, candidate_pipeline=PagePipeline()) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(ScopeDraft(title="Reports", summary="Reports", idempotency_key="reports"))
        private = await runtime.scopes.create(ScopeDraft(title="Private", summary="Private", idempotency_key="private"))
        await runtime.ingestion.register(manifest_for_definition(PDF_PAGE_SOURCE_DEFINITION))
        observations = await _submit(runtime, scope.scope_id, old_raw, "Example_2024")
        await runtime.ingestion.submit(SubmitSourceObservation(scope_id=scope.scope_id, observation=observations[0]))
        memory = runtime.memory.for_scope(scope.scope_id)
        cursor = await memory.cursor()
        with monkeypatch.context() as patch:
            patch.setattr(
                RelationalMemoryBackend, "_commit", AsyncMock(side_effect=RuntimeError("controlled write failure"))
            )
            with pytest.raises(RuntimeError, match="controlled write failure"):
                await memory.flush()
        assert await memory.cursor() == cursor
    async with open_builtin_runtime(config, candidate_pipeline=PagePipeline()) as runtime:
        memory = runtime.memory.for_scope(scope.scope_id)
        await _flush(memory)
        old = await search_pdf_pages(memory, "Example revenue cash", 20)
        assert len(old) == 2
        observations += await _submit(runtime, scope.scope_id, new_raw, "Example_2024")
        secret = await _submit(runtime, private.scope_id, pdf_bytes(("Revenue secret 999",)), "Private_2024")
        await _flush(memory)
        await _flush(runtime.memory.for_scope(private.scope_id))
        await memory.remember(
            RememberMemoryRequest(entries=(MemoryEntryInput(kind="note", text="Revenue cash 999999"),))
        )
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope.scope_id)
        found = await search_pdf_pages(memory, "Example revenue cash", 20)
        repeated = await search_pdf_pages(memory, "Example revenue cash", 20)
        assert found == repeated and len(found) == 4
        expected = {observation.name for observation in observations}
        actual = set()
        for citation in found:
            record = await memory.get(GetMemoryEntryRequest(citation=citation))
            assert record.entry.text == "Example_2024\nRevenue 700 cash 200"
            actual.add(record.entry.sources[0].source_id)
        assert actual == expected
        for citation in old:
            assert (await memory.get(GetMemoryEntryRequest(citation=citation))).entry.sources[0].source_id in expected
        assert len(await search_pdf_pages(memory, "revenue", 1)) == 1
        assert await search_pdf_pages(memory, "revenue", 0) == ()
        assert await search_pdf_pages(memory, "", 20) == ()
        assert await search_pdf_pages(memory, "zzqvnonexistent", 20) == ()
        private_memory = runtime.memory.for_scope(private.scope_id)
        private_hits = await search_pdf_pages(private_memory, "revenue", 20)
        assert len(private_hits) == 1
        record = await private_memory.get(GetMemoryEntryRequest(citation=private_hits[0]))
        assert record.entry.sources[0].source_id == secret[0].name


@pytest.mark.asyncio
@pytest.mark.parametrize("split", ["development", "held_out"])
async def test_independent_financial_recall_and_full_page_fidelity(tmp_path, split):
    documents, questions = reports(split)
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'financial.db'}"))
    locations = {}
    async with open_builtin_runtime(config, candidate_pipeline=PagePipeline()) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(
            ScopeDraft(title="Financial", summary="Financial", idempotency_key="financial")
        )
        await runtime.ingestion.register(manifest_for_definition(PDF_PAGE_SOURCE_DEFINITION))
        for document in documents:
            raw = pdf_bytes(document.pages)
            expected = [page.extract_text(extraction_mode="plain") or "" for page in PdfReader(io.BytesIO(raw)).pages]
            parsed = parse_pdf_document(PDFDocumentInput(document_id=document.identifier, content=raw))
            for page, original in zip(parsed, expected, strict=True):
                tokens = lambda text: Counter(re.findall(r"[a-z]+|\d+", text.casefold()))
                assert tokens(page.text) == tokens(original)
            observations = await _submit(runtime, scope.scope_id, raw, document.identifier)
            for observation in observations:
                metadata = observation.projection(TEXT_EVIDENCE_PROJECTION_KEY)["metadata"]
                locations[observation.name] = (metadata["document_id"], metadata["page_number"])
        await _flush(runtime.memory.for_scope(scope.scope_id))
    results = []
    found_count, expected_count = 0, 0
    async with open_builtin_runtime(config) as runtime:
        memory = runtime.memory.for_scope(scope.scope_id)
        for question in questions:
            citations = await search_pdf_pages(memory, question.text, 20)
            actual = []
            for citation in citations:
                record = await memory.get(GetMemoryEntryRequest(citation=citation))
                assert len(record.entry.sources) == 1
                actual.append(locations[record.entry.sources[0].source_id])
            assert len(actual) == len(set(actual)) <= 20
            found_count += len(set(actual) & set(question.evidence))
            expected_count += len(question.evidence)
            results.append({
                "question": question.text,
                "found": len(set(actual) & set(question.evidence)),
                "expected": len(question.evidence),
                "ranking": actual,
                "gold": question.evidence,
            })
    recall = found_count / expected_count
    print(
        json.dumps({
            "synthetic": True,
            "split": split,
            "documents": len(documents),
            "pages": len(locations),
            "recall_at_20": recall,
            "queries": results,
        }),
        flush=True,
    )
    assert recall >= 0.95
