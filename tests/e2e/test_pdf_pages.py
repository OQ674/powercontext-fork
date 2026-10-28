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

"""Real scoped retrieval, financial query expansion and durable PDF citations."""

from __future__ import annotations

from pathlib import Path

import pytest

from powercontext.builtin.artifacts.memory import MemoryEntryInput
from powercontext.builtin.artifacts.memory.models import MemoryCitation
from powercontext.builtin.artifacts.memory.protocols import MemoryCandidateRequest
from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime import (
    BuiltinConfig,
    GetMemoryEntryRequest,
    ScopedMemoryApplication,
    SubmitSourceObservation,
    open_builtin_contexts,
    open_builtin_runtime,
)
from powercontext.builtin.scope import ScopeDraft
from powercontext.sources import (
    SourceDefinitionRegistry,
    SourceObservation,
    TextEvidence,
    manifest_for_definition,
    project_source_for_transport,
)
from powercontext.sources.pdf_pages import (
    PDF_PAGE_SOURCE_DEFINITION,
    PDFDocumentInput,
    parse_pdf_document,
    search_pdf_pages,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY
from tests.test_pdf_pages import make_pdf


class PagePipeline:
    async def extract(self, request: MemoryCandidateRequest, /) -> tuple[MemoryEntryInput, ...]:
        entries = []
        for source in request.sources:
            assert isinstance(source, SourceObservation)
            evidence = TextEvidence.model_validate(source.projection(TEXT_EVIDENCE_PROJECTION_KEY))
            entries.append(MemoryEntryInput(kind="pdf-page", text=evidence.content, sources=(source,)))
            if evidence.metadata["page_number"] == 2:
                entries.append(MemoryEntryInput(kind="same-page-copy", text=evidence.content, sources=(source,)))
        return tuple(entries)


async def locations_for(
    memory: ScopedMemoryApplication,
    observations: dict[str, SourceObservation],
    question: str,
    expected_document: str,
) -> set[int]:
    locations: set[int] = set()
    identities = set()
    for citation in await search_pdf_pages(memory, question, limit=3):
        entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
        source = observations[entry.sources[0].source_id]
        evidence = TextEvidence.model_validate(source.projection(TEXT_EVIDENCE_PROJECTION_KEY))
        assert evidence.metadata["document_id"] == expected_document
        assert source.name not in identities
        identities.add(source.name)
        physical_page = evidence.metadata["page_number"]
        assert isinstance(physical_page, int)
        locations.add(physical_page)
    return locations


@pytest.mark.asyncio
async def test_distinct_financial_pages_document_scope_and_old_revision_citations(tmp_path: Path) -> None:
    texts = (
        "Business and geographic segments\nInternational operations in Europe, Asia and North America.",
        "Consolidated Statement of Income\nRevenue 1200\nOperating income 80\nNet income 60",
        "Consolidated Statement of Cash Flows\nDepreciation and amortization 20\nCapital expenditures (10)",
        "Legal Proceedings\nThe company defends ongoing civil litigation and lawsuits.",
        "Consolidated Balance Sheets\nCurrent assets 500\nCurrent liabilities 210\nEquity 300",
        *(
            f"General annual report discussion {index}\nBusiness developments and cash management."
            for index in range(30)
        ),
    )
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    observations: dict[str, SourceObservation] = {}
    river_ids = []
    for document in ("RIVER_2023_10K", "MOUNTAIN_2023_10K", "3M_2023_10K"):
        document_texts = texts[:5] if document.startswith("3M_") else texts
        pages = parse_pdf_document(PDFDocumentInput(document_id=document, content=make_pdf(document_texts)))
        for page in pages:
            observation = project_source_for_transport(registry, await registry.resolve(page))
            observations[observation.name] = observation
            if document == "RIVER_2023_10K":
                river_ids.append(observation.name)
    config = BuiltinConfig(database=SQLiteConfig(url=f"sqlite+aiosqlite:///{tmp_path / 'pages.db'}"))
    async with open_builtin_runtime(config) as runtime:
        assert runtime.scopes is not None
        scope = await runtime.scopes.create(
            ScopeDraft(title="Reports", summary="PDF evidence", idempotency_key="reports")
        )
        other = await runtime.scopes.create(
            ScopeDraft(title="Other", summary="Scope isolation", idempotency_key="other")
        )
        await runtime.ingestion.register(manifest_for_definition(PDF_PAGE_SOURCE_DEFINITION))
        for observation in observations.values():
            await runtime.ingestion.submit(SubmitSourceObservation(scope_id=scope.scope_id, observation=observation))
        # Repeating a page must not create another canonical Source.
        await runtime.ingestion.submit(
            SubmitSourceObservation(scope_id=scope.scope_id, observation=observations[river_ids[0]])
        )

    selected: MemoryCitation | None = None
    async with open_builtin_runtime(config, candidate_pipeline=PagePipeline()) as runtime:
        memory = runtime.memory.for_scope(scope.scope_id)
        assert (await memory.flush()).source_count == len(observations)
        # The pipeline's two Memory entries for page 2 must yield one page citation.
        question = "What is River's EBITDA less capex in FY2023 using the income statement and cash flow statement?"
        citations = await search_pdf_pages(memory, question, limit=5)
        assert 2 <= len(citations) <= 5
        locations = set()
        identities = set()
        for citation in citations:
            entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
            source = observations[entry.sources[0].source_id]
            page = TextEvidence.model_validate(source.projection(TEXT_EVIDENCE_PROJECTION_KEY))
            assert page.metadata["document_id"] == "RIVER_2023_10K"
            assert source.name not in identities
            identities.add(source.name)
            locations.add(page.metadata["page_number"])
            if page.metadata["page_number"] == 2:
                selected = citation
        assert {2, 3}.issubset(locations) and selected is not None
        assert {2, 3}.issubset(
            await locations_for(memory, observations, "What is 3M's EBITDA less capex in FY2023?", "3M_2023_10K")
        )
        for question, physical_page in [
            ("Which regions does River operate in?", 1),
            ("Has River reported legal battles?", 4),
            ("What are River's current assets and liabilities?", 5),
        ]:
            assert physical_page in await locations_for(memory, observations, question, "RIVER_2023_10K")
        assert await search_pdf_pages(runtime.memory.for_scope(other.scope_id), question, limit=3) == ()
        assert await search_pdf_pages(memory, "", limit=0) == ()
        with pytest.raises(ValueError):
            await search_pdf_pages(memory, "question", limit=-1)
        with pytest.raises(ValueError):
            await search_pdf_pages(memory, "  ")
        assert len(await search_pdf_pages(memory, "River operating income", limit=1)) == 1

    # A replacement PDF creates new page sources; an old exact citation must
    # still return the original file digest and physical page after restart.
    updated_pdf = make_pdf((texts[0], texts[1].replace("80", "90")), title="revised")
    updated = parse_pdf_document(PDFDocumentInput(document_id="RIVER_2023_10K", content=updated_pdf))
    async with open_builtin_runtime(config, candidate_pipeline=PagePipeline()) as runtime:
        for page in updated:
            observation = project_source_for_transport(registry, await registry.resolve(page))
            await runtime.ingestion.submit(SubmitSourceObservation(scope_id=scope.scope_id, observation=observation))
        memory = runtime.memory.for_scope(scope.scope_id)
        assert (await memory.flush()).source_count == 2
        old = (await memory.get(GetMemoryEntryRequest(citation=selected))).entry
        assert old.sources[0].source_id == river_ids[1] and "income 80" in old.text
    async with open_builtin_contexts(config) as contexts:
        context = await contexts.get(scope.scope_id)
        entries = await context.sources.journal.entries()
        assert len(entries) == len(observations) + 2
        source = await context.sources.get(observations[river_ids[1]])
        assert isinstance(source, SourceObservation)
        evidence = TextEvidence.model_validate(source.projection(TEXT_EVIDENCE_PROJECTION_KEY))
        assert evidence.metadata["page_number"] == 2
        assert evidence.metadata["document_sha256"] != updated[1].document_sha256
