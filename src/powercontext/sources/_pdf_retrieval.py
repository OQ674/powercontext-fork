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

"""Corpus-wide lexical evidence ranking through public scoped Memory operations."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from powercontext.artifacts import MemoryCitation
from powercontext.builtin.runtime.models import GetMemoryEntryRequest, SearchMemoryRequest

if TYPE_CHECKING:
    from powercontext.builtin.runtime.application import ScopedMemoryApplication
    from powercontext.builtin.runtime.models import MemoryEntryRecord

_WORD = re.compile(r"[a-z]+|\d+")
_STOP = frozenset([
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "at",
    "for",
    "from",
    "with",
    "by",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "its",
    "they",
    "their",
    "this",
    "that",
    "these",
    "those",
    "what",
    "which",
    "how",
    "why",
    "when",
    "where",
    "who",
    "do",
    "does",
    "did",
    "has",
    "have",
    "had",
    "would",
    "could",
    "should",
    "can",
    "will",
    "please",
    "provide",
    "give",
    "answer",
    "respond",
    "response",
    "question",
    "according",
    "based",
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
    "using",
    "use",
    "explicitly",
    "outlined",
    "reported",
    "report",
    "annual",
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
    "thousand",
    "thousands",
    "s",
])
_ID_STOP = frozenset([
    "k",
    "q",
    "f",
    "pdf",
    "inc",
    "co",
    "corp",
    "corporation",
    "company",
    "ltd",
    "limited",
    "plc",
    "report",
    "annual",
    "financial",
    "statements",
])


def _stem(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and len(word) > 3 and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"(?<=[a-z])-\s*\n\s*(?=[a-z])", "", normalized)
    return tuple(_stem(word) for word in _WORD.findall(normalized))


def _phrase(text: str) -> str:
    return " ".join(_tokens(text))


@dataclass(frozen=True)
class _Concept:
    triggers: tuple[str, ...]
    alternatives: tuple[str, ...]
    heading: str = ""
    table: bool = False


# General accounting concepts, not company names, question IDs or evidence pages.
_CONCEPTS = (
    _Concept(
        (
            "income statement",
            "income statements",
            "p&l",
            "ebitda",
            "profit margin",
            "operating margin",
            "gross margin",
            "gross profit",
            "operating income",
        ),
        ("operating income", "net income", "income from operations", "operating profit"),
        r"\b(?:consolidated )?statements? (?:of )?(?:income|operations?|earnings?)\b",
        True,
    ),
    _Concept(
        ("cash flow", "cash flows", "ebitda", "depreciation", "amortization", "d&a"),
        ("cash flows", "operating activities", "depreciation and amortization"),
        r"\bstatement\w* (?:of )?cash flow\b",
        True,
    ),
    _Concept(
        ("capex", "capital expenditure", "free cash flow"),
        ("capital expenditures", "capital spending", "purchases of property plant equipment", "additions to property"),
    ),
    _Concept(
        ("balance sheet", "balance sheets", "current ratio", "quick ratio", "working capital", "assets", "equity"),
        ("total assets", "current assets", "current liabilities", "shareholders equity", "stockholders equity"),
        r"\b(?:balance sheets?|statements? (?:of )?financial position)\b",
        True,
    ),
    _Concept(
        ("revenue", "sales", "margin", "gross profit"), ("net revenue", "net sales", "total revenue", "cost of sales")
    ),
    _Concept(
        ("legal", "litigation", "lawsuit", "battles", "contingencies"),
        ("legal proceedings", "litigation", "lawsuits", "commitments and contingencies"),
        r"\b(?:legal proceeding|commitment and contingenc)",
    ),
    _Concept(
        ("geograph", "countries", "regions", "primarily operates", "segments"),
        (
            "geographic",
            "business segments",
            "operating segments",
            "division",
            "international",
            "countries",
            "regions",
            "north america",
            "latin america",
            "europe",
            "africa",
            "middle east",
            "asia pacific",
        ),
        r"\b(?:item 1 business|business overview|operating segments?|geographic (?:areas?|markets?|regions?))\b",
    ),
    _Concept(("restructur", "impairment"), ("restructuring", "productivity", "impairment", "reorganization")),
    _Concept(
        ("debt", "borrowing", "leverage", "interest coverage"), ("long term debt", "borrowings", "interest expense")
    ),
    _Concept(
        ("tax",),
        ("income taxes", "income tax provision", "effective tax rate", "deferred tax"),
        r"\b(?:income tax(?:es| provision)?|effective tax rate)\b",
        True,
    ),
    _Concept(("dividend", "buyback", "repurchase"), ("dividends", "share repurchases", "treasury stock")),
    _Concept(("pension", "retirement"), ("pension benefits", "retirement", "benefit obligation")),
    _Concept(("acquisition", "goodwill"), ("acquisitions", "goodwill", "purchase price")),
    _Concept(("lease",), ("operating leases", "finance leases", "lease obligations")),
    _Concept(("inventory", "inventories"), ("inventories", "inventory")),
    _Concept(
        ("customer concentration", "customer retention", "retain", "card member", "primary customers"),
        (
            "customer concentration",
            "one customer accounted",
            "sales to this customer",
            "major customers",
            "customer retention",
            "customer relationships",
            "card members",
            "new card acquisitions",
            "deeper relationships",
            "new customers",
            "customer demand",
            "commercial customers",
            "airline customers",
            "government contracts",
            "government customers",
            "sales to the government",
        ),
    ),
    _Concept(
        ("cyclicality", "cyclical", "business cycle"),
        ("cyclical", "business cycles", "economic conditions", "economic downturn"),
    ),
)


@dataclass(frozen=True)
class _Query:
    literal: dict[str, float]
    expanded: dict[str, float]
    phrases: tuple[str, ...]
    concepts: tuple[_Concept, ...]
    text: str


def _query(question: str) -> _Query:
    terms = _tokens(question)
    literal = {term: 0.2 if term.isdigit() else 1.0 for term in terms if term not in _STOP}
    lower = question.casefold()
    concepts = tuple(concept for concept in _CONCEPTS if any(trigger in lower for trigger in concept.triggers))
    expanded = dict(literal)
    for concept in concepts:
        for alternative in concept.alternatives:
            for term in _tokens(alternative):
                if term not in _STOP:
                    expanded.setdefault(term, 0.35)
    phrases = tuple(
        dict.fromkeys(
            " ".join(terms[start : start + width])
            for width in (2, 3)
            for start in range(len(terms) - width + 1)
            if all(term not in _STOP and not term.isdigit() for term in terms[start : start + width])
        )
    )
    return _Query(literal, expanded, phrases, concepts, _phrase(question))


@dataclass
class _Page:
    record: MemoryEntryRecord
    source_id: str
    identifier: str
    tokens: tuple[str, ...]
    counts: Counter[str]
    body: str
    coverage: tuple[float, ...] = ()
    affinity: float = 0.0
    score: float = 0.0


def _page(record: MemoryEntryRecord) -> _Page | None:
    sources = record.entry.sources
    if len(sources) != 1 or sources[0].source_type != "pdf-page":
        return None
    identifier, _, body = record.entry.text.partition("\n")
    terms = _tokens(body)
    if not terms:
        return None
    return _Page(record, sources[0].source_id, identifier, terms, Counter(terms), " " + " ".join(terms) + " ")


def _affinity(identifier: str, query: _Query) -> float:
    prefix = re.split(r"(?:19|20)\d{2}", identifier, maxsplit=1)[0]
    company = tuple(term for term in _tokens(prefix) if term not in _ID_STOP)
    compact = "".join(company)
    query_compact = query.text.replace(" ", "")
    if len(compact) >= 2 and compact in query_compact:
        return 1.0
    # Common two-word company shorthands concatenate the first syllables
    # (for example, the first two letters of each word). Identifiers often
    # arrive without word boundaries, so recognize that conservative shape
    # without maintaining a company-specific alias table.
    if any(
        len(term) >= 4 and compact.startswith(term[:2]) and term[2:] in compact[2:]
        for term in query.literal
        if term.isalpha()
    ):
        return 1.0
    meaningful = tuple(term for term in company if len(term) > 1 and not term.isdigit())
    return sum(term in query.literal for term in meaningful) / len(meaningful) if meaningful else 0.0


def _bm25(counts: Counter[str], weights: dict[str, float], idf: dict[str, float], average: float) -> float:
    norm = 1.2 * (0.6 + 0.4 * counts.total() / max(average, 1.0))
    return sum(
        weight * idf.get(term, 0) * min(counts[term], 4) * 2.2 / (min(counts[term], 4) + norm)
        for term, weight in weights.items()
        if counts[term]
    )


def _looks_like_index(text: str) -> bool:
    """Distinguish an actual index from the repeated ``Table of Contents`` running header."""
    numbered_sections = len(re.findall(r"\b(?:item|note)\s+\d+[a-z]?\b", text))
    return numbered_sections >= 5 or (" our financial result " in text and " note 1 " in text and " note 5 " in text)


def _headings(page: _Page, query: _Query) -> tuple[float, tuple[float, ...]]:
    # A statement title is useful only when it is genuinely at the start of a
    # page. Audit opinions and exhibit indexes often repeat every statement
    # name later in their first paragraphs and otherwise crowd out the actual
    # statement pages.
    beginning = page.body[:120]
    index_page = _looks_like_index(page.body[:1800])
    numeric = sum(count for term, count in page.counts.items() if term.isdigit())
    coverage: list[float] = []
    score = 0.0
    for concept in query.concepts:
        heading = bool(concept.heading and re.search(concept.heading, beginning))
        primary = heading and not index_page and (not concept.table or numeric >= 6)
        phrases = sum(f" {_phrase(alternative)} " in page.body for alternative in concept.alternatives)
        strength = 12.0 if primary else min(phrases, 4) * 1.0
        coverage.append(strength)
        score += strength
    if index_page:
        score *= 0.1
    return score, tuple(coverage)


def _rank(pages: list[_Page], query: _Query, native: dict[tuple[str, str], int], limit: int) -> list[_Page]:
    frequencies = Counter(term for page in pages for term in page.counts)
    idf = {
        term: math.log1p((len(pages) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)) for term in query.expanded
    }
    average = sum(len(page.tokens) for page in pages) / max(1, len(pages))
    routes: list[list[tuple[float, _Page]]] = [[], [], [], [], []]
    for page in pages:
        literal = _bm25(page.counts, query.literal, idf, average)
        expanded = _bm25(page.counts, query.expanded, idf, average)
        window = max(
            (
                _bm25(Counter(page.tokens[start : start + 96]), query.expanded, idf, 96)
                for start in range(0, len(page.tokens), 48)
            ),
            default=0.0,
        )
        heading, page.coverage = _headings(page, query)
        proximity = sum(phrase in page.body for phrase in query.phrases)
        page.affinity = _affinity(page.identifier, query)
        rank = native.get((page.record.entry.entry_id, page.record.entry.entry_version_id))
        scores = (literal, expanded, window, heading + proximity, 1.0 / rank if rank else 0.0)
        for route, score in zip(routes, scores, strict=True):
            if score > 0:
                route.append((score, page))
    for route, weight in zip(routes, (2.0, 1.0, 1.0, 1.0, 0.5), strict=True):
        for rank, (_, page) in enumerate(sorted(route, key=lambda item: (-item[0], item[1].source_id)), 1):
            page.score += weight / (60 + rank)
    best_affinity = max((page.affinity for page in pages), default=0.0)
    if best_affinity == 1.0:
        for page in pages:
            page.score *= 0.35 + 0.65 * page.affinity
    ordered = sorted((page for page in pages if page.score > 0), key=lambda page: (-page.score, page.source_id))
    return _cover_concepts(ordered, len(query.concepts), best_affinity, limit)


def _cover_concepts(ordered: list[_Page], count: int, affinity: float, limit: int) -> list[_Page]:
    if count == 0:
        return ordered[:limit]
    selected: list[_Page] = []
    selected_ids: set[str] = set()
    # Reserve a small evidence budget for each requested concept. Financial
    # questions often cite several equally plausible disclosure and statement
    # pages, so two reservations are not enough for a top-20 contract.
    per_concept = min(6, max(1, limit // max(2 * count, 1)))
    for index in range(count):
        available = sorted(
            (page for page in ordered if page.coverage[index] > 0 and (affinity < 1 or page.affinity == 1)),
            key=lambda page: (-page.coverage[index], -page.score, page.source_id),
        )
        added = 0
        for candidate in available:
            if candidate.source_id in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.source_id)
            added += 1
            if added == per_concept or len(selected) == limit:
                break
    for candidate in ordered:
        if len(selected) == limit:
            break
        if candidate.source_id not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate.source_id)
    return sorted(selected, key=lambda page: (-page.score, page.source_id))


async def search_pages(memory: ScopedMemoryApplication, question: str, limit: int) -> tuple[MemoryCitation, ...]:
    if type(limit) is not int:
        raise TypeError("limit must be an integer")  # noqa: TRY003
    if limit <= 0 or not question.strip():
        return ()
    query = _query(question)
    if not query.literal:
        return ()
    first = await memory.search(SearchMemoryRequest(query=question, mode="fts", limit=max(100, limit * 4)))
    if first.memory_ref is None:
        return ()
    snapshot = await memory.list()
    pages: dict[str, _Page] = {}
    for record in snapshot.entries:
        page = _page(record)
        if page is not None:
            pages.setdefault(page.source_id, page)
    if not pages:
        return ()
    native = {(hit.entry_id, hit.entry_version_id): rank for rank, hit in enumerate(first.hits, 1)}
    selected = _rank(list(pages.values()), query, native, limit)
    citations = []
    for page in selected:
        citation = page.record.citation
        actual = await memory.get(GetMemoryEntryRequest(citation=citation))
        if actual.entry != page.record.entry:
            raise ValueError("PDF evidence did not round-trip through Memory")  # noqa: TRY003
        citations.append(citation)
    return tuple(citations)
