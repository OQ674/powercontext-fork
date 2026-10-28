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

"""Offline financial query expansion and ranking over public Memory results."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from powercontext.builtin.artifacts.memory.models import MemoryCitation, MemoryHit
    from powercontext.builtin.runtime.models import (
        GetMemoryEntryRequest,
        MemoryEntryRecord,
        MemorySearchPage,
        SearchMemoryRequest,
    )


class PDFMemory(Protocol):
    """Only the public operations required to obtain and verify real citations."""

    async def search(self, request: SearchMemoryRequest, /) -> MemorySearchPage: ...

    async def get(self, request: GetMemoryEntryRequest, /) -> MemoryEntryRecord: ...


_FUNCTION_WORDS = frozenset([
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "in",
    "to",
    "on",
    "by",
    "at",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "what",
    "which",
    "who",
    "how",
    "why",
    "when",
    "where",
    "do",
    "does",
    "did",
    "has",
    "have",
    "had",
    "can",
    "could",
    "should",
    "would",
    "will",
    "shall",
    "it",
    "its",
    "they",
    "their",
    "them",
    "this",
    "that",
    "these",
    "those",
    "for",
    "from",
    "with",
    "into",
    "during",
    "between",
    "through",
    "according",
    "about",
    "any",
    "using",
    "use",
    "given",
    "give",
    "provide",
    "please",
    "answer",
    "respond",
    "response",
    "question",
    "calculate",
    "calculation",
    "define",
    "assuming",
    "assume",
    "perspective",
    "investment",
    "analyst",
    "only",
    "details",
    "shown",
    "within",
    "relying",
    "based",
    "state",
    "directly",
    "explicitly",
    "outlined",
    "reported",
    "report",
    "reports",
    "fiscal",
    "fy",
    "year",
    "years",
    "usd",
    "dollar",
    "dollars",
    "million",
    "millions",
    "billion",
    "billions",
    "quantity",
    "amount",
    "unadjusted",
    "important",
    "materially",
    "ongoing",
    "primarily",
    "not",
    "if",
    "then",
    "than",
    "s",
])


@dataclass(frozen=True)
class _Facet:
    triggers: tuple[str, ...]
    query: str
    heading: str = ""


# General financial vocabulary, independent of any document, benchmark or answer.
_FACETS = (
    _Facet(
        ("income", "earnings", "profit", "revenue", "sales", "margin", "ebit", "eps", "p&l", "return on", "coverage"),
        "consolidated statements income operations earnings revenue sales",
        r"\bstatements?\s+of\s+(?:income|operations|earnings)\b",
    ),
    _Facet(
        ("cash", "capex", "ebitda", "depreciation", "amortization", "d&a", "capital expenditure"),
        "consolidated statements cash flows operating activities expenditures",
        r"\bstatements?\s+of\s+cash\s+flows\b",
    ),
    _Facet(
        (
            "balance",
            "assets",
            "liabilities",
            "equity",
            "leverage",
            "current ratio",
            "quick ratio",
            "working capital",
            "capital employed",
            "cash conversion",
            "receivabl",
            "payabl",
            "return on",
        ),
        "consolidated balance sheets assets liabilities equity",
        r"\b(?:balance\s+sheets?|statements?\s+of\s+financial\s+position)\b",
    ),
    _Facet(
        ("geograph", "countries", "regions", "operates", "segments", "markets", "locations", "where"),
        "geographic segments countries international business operations",
        r"\b(?:our\s+(?:business|divisions)|business\s+overview|geographic(?:al)?\s+(?:information|areas?|segments?)|business\s+segments?)\b",
    ),
    _Facet(
        ("legal", "litigation", "lawsuit", "battles", "contingenc"),
        "legal proceedings litigation lawsuits commitments contingencies",
        r"\b(?:legal\s+proceedings|commitments?\s+and\s+contingencies)\b",
    ),
    _Facet(("restructur", "impairment"), "restructuring impairment charges productivity costs"),
    _Facet(("debt", "borrow", "interest", "financing"), "debt borrowings notes interest obligations"),
    _Facet(("dividend", "repurchase", "buyback"), "dividends repurchases treasury shares stock"),
    _Facet(("pension", "retirement", "benefit"), "pension retirement benefit plans obligations"),
    _Facet(("tax",), "income taxes effective rate deferred"),
    _Facet(("acquisition", "acquired", "goodwill", "divest"), "acquisitions divestitures goodwill purchase"),
    _Facet(("lease",), "leases operating finance obligations"),
    _Facet(("inventory", "inventories"), "inventories inventory cost accounting"),
    _Facet(("employee", "workforce", "headcount"), "employees human capital workforce"),
)


def _stem(term: str) -> str:
    for prefix in ("operat", "geograph", "restructur", "depreciat", "amortiz", "amortis"):
        if term.startswith(prefix):
            return prefix.replace("amortis", "amortiz")
    if len(term) > 4 and term.endswith("ies"):
        return term[:-3] + "y"
    if len(term) > 4 and term.endswith("s") and not term.endswith(("ss", "us")):
        return term[:-1]
    return term


def _terms(text: str) -> list[str]:
    return [_stem(term) for term in re.findall(r"[a-z]+|\d+", text.casefold())]


def _query_plan(question: str) -> tuple[list[str], tuple[_Facet, ...], tuple[str, ...]]:
    raw = re.findall(r"[a-z]+|\d+", question.casefold())
    core = list(dict.fromkeys(term for term in raw if term not in _FUNCTION_WORDS and len(term) > 1))
    facets = tuple(facet for facet in _FACETS if any(trigger in question.casefold() for trigger in facet.triggers))
    variants = [" ".join(core[:24]) or question]
    variants.extend(facet.query for facet in facets)
    # Short lexical probes avoid imposing the original question's instruction
    # words as Memory's admission floor, and also find named-company pages.
    variants.extend(core[:4])
    years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", question)
    if years:
        variants.append(" ".join(dict.fromkeys(years)))
    return core, facets, tuple(dict.fromkeys(variant for variant in variants if variant.strip()))


@dataclass
class _Candidate:
    hit: MemoryHit
    frequency: Counter[str]
    fusion: float = 0.0


def _company_match(document_id: str, question: str) -> float:
    # Keep alphanumeric names (e.g. a digit followed by a letter) intact, while
    # excluding filing years and generic filename words from company matching.
    prefix = re.split(r"(?<!\d)(?:19|20)\d{2}(?!\d)", document_id.casefold(), maxsplit=1)[0]
    terms = [
        term
        for term in re.findall(r"[a-z]+|\d+", prefix)
        if term
        not in {
            "k",
            "q",
            "f",
            "pdf",
            "pdfs",
            "inc",
            "corp",
            "corporation",
            "company",
            "co",
            "ltd",
            "plc",
            "report",
            "reports",
            "annual",
            "financial",
            "statement",
            "statements",
        }
    ]
    if not terms:
        return 0.0
    compact = "".join(terms)
    if len(compact) < 2:
        return 0.0
    if compact in "".join(re.findall(r"[a-z]+|\d+", question.casefold())):
        return 1.0
    query_terms = set(re.findall(r"[a-z]+|\d+", question.casefold()))
    return sum(term in query_terms for term in terms) / len(terms)


def _matching_documents(candidates: list[_Candidate], question: str) -> tuple[str, ...]:
    matches = {candidate.hit.text.partition("\n")[0]: 0.0 for candidate in candidates}
    for document in matches:
        matches[document] = _company_match(document, question)
    best = max(matches.values(), default=0.0)
    if best == 0:
        return ()
    return tuple(document for document, match in matches.items() if match == best)


def _bm25(query: list[str], frequency: Counter[str], idf: dict[str, float], average_length: float) -> float:
    normalization = 1.2 * (0.25 + 0.75 * frequency.total() / max(average_length, 1.0))
    return sum(
        idf.get(term, 0.0) * frequency[term] * 2.2 / (frequency[term] + normalization)
        for term in set(query)
        if frequency[term]
    )


def _heading_bonus(candidate: _Candidate, facet: _Facet) -> float:
    if not facet.heading:
        return 0.0
    text = " ".join(candidate.hit.text.casefold().split())
    if not re.search(facet.heading, text[:1400]):
        return 0.0
    # Full statement tables outrank a contents-page mention of their title.
    numbers = sum(count for term, count in candidate.frequency.items() if term.isdigit())
    return 4.0 * (1.0 + min(numbers / 40.0, 1.0))


def _rank(
    candidates: list[_Candidate], question: str, core: list[str], facets: tuple[_Facet, ...], limit: int
) -> list[_Candidate]:
    documents = _matching_documents(candidates, question)
    if documents:
        candidates = [candidate for candidate in candidates if candidate.hit.text.partition("\n")[0] in documents]
    if not candidates:
        return []
    counts: Counter[str] = Counter(term for candidate in candidates for term in candidate.frequency)
    total = len(candidates)
    idf = {term: math.log(1.0 + (total - count + 0.5) / (count + 0.5)) for term, count in counts.items()}
    average = sum(candidate.frequency.total() for candidate in candidates) / total
    facet_queries = [_terms(facet.query) for facet in facets]

    def facet_score(candidate: _Candidate, index: int) -> float:
        return _bm25(facet_queries[index], candidate.frequency, idf, average) + _heading_bonus(candidate, facets[index])

    def score(candidate: _Candidate) -> float:
        literal = _bm25([_stem(term) for term in core], candidate.frequency, idf, average)
        return (
            literal + 0.45 * sum(facet_score(candidate, index) for index in range(len(facets))) + 20 * candidate.fusion
        )

    ordered = sorted(candidates, key=lambda candidate: (-score(candidate), candidate.hit.entry_id))
    # Multi-statement questions need evidence for each requested concept, not
    # twenty near-duplicates of whichever statement has the most query words.
    seeds: list[_Candidate] = []
    per_facet = min(4, limit // max(2 * len(facets), 1))
    for index in range(len(facets)):
        ranked = sorted(candidates, key=lambda candidate: (-facet_score(candidate, index), -score(candidate)))
        seeds.extend(candidate for candidate in ranked[:per_facet] if facet_score(candidate, index) > 0)
    seen: set[str] = set()
    result = []
    for candidate in [*seeds, *ordered]:
        if candidate.hit.entry_version_id not in seen:
            seen.add(candidate.hit.entry_version_id)
            result.append(candidate)
    return result


async def _collect(
    memory: PDFMemory, query: str, limit: int, candidates: dict[tuple[str, int, str, str], _Candidate]
) -> None:
    from powercontext.builtin.runtime.models import SearchMemoryRequest

    page = await memory.search(SearchMemoryRequest(query=query, mode="fts", limit=limit))
    for rank, hit in enumerate(page.hits, start=1):
        key = (hit.memory_ref.artifact_id, hit.memory_ref.revision, hit.entry_id, hit.entry_version_id)
        if key not in candidates:
            candidates[key] = _Candidate(hit=hit, frequency=Counter(_terms(hit.text)))
        candidates[key].fusion += 1.0 / (60 + rank)


async def search_pages(memory: PDFMemory, question: str, limit: int) -> tuple[MemoryCitation, ...]:
    """Rank scoped Memory hits, then validate and deduplicate their page sources."""

    from powercontext.builtin.artifacts.memory.models import MemoryCitation
    from powercontext.builtin.runtime.models import GetMemoryEntryRequest

    if limit < 0:
        raise ValueError("PDF search limit must not be negative")  # noqa: TRY003
    if limit == 0:
        return ()
    if not question.strip():
        raise ValueError("PDF search question must not be blank")  # noqa: TRY003
    core, facets, variants = _query_plan(question)
    candidates: dict[tuple[str, int, str, str], _Candidate] = {}
    candidate_limit = max(100, min(600, limit * 20))
    for query in variants:
        await _collect(memory, query, candidate_limit, candidates)
    # Document IDs are discovered from actual Memory text, never from an asset
    # list. Their exact lexical token also admits sparse statement/table pages
    # which contain few of the original question's words.
    for document in _matching_documents(list(candidates.values()), question):
        await _collect(memory, document, max(256, min(2048, limit * 64)), candidates)
    ordered = _rank(list(candidates.values()), question, core, facets, limit)
    citations: list[MemoryCitation] = []
    seen: set[str] = set()
    for candidate in ordered:
        hit = candidate.hit
        citation = MemoryCitation(
            memory_ref=hit.memory_ref, entry_id=hit.entry_id, entry_version_id=hit.entry_version_id
        )
        entry = (await memory.get(GetMemoryEntryRequest(citation=citation))).entry
        if len(entry.sources) != 1 or entry.sources[0].source_type != "pdf-page":
            continue
        source_id = entry.sources[0].source_id
        if source_id not in seen:
            seen.add(source_id)
            citations.append(citation)
            if len(citations) == limit:
                break
    return tuple(citations)
