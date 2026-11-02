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

"""Query-driven literal passages with citation-inclusive byte-budget selection."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

from powercontext.builtin.runtime.prepared_text import TRUST_POLICY

if TYPE_CHECKING:
    from powercontext.builtin.runtime.prepared_context import MemoryEntryAddress

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
    "for",
    "from",
    "with",
    "by",
    "as",
    "at",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "their",
    "they",
    "them",
    "we",
    "our",
    "you",
    "your",
    "which",
    "who",
    "whom",
    "can",
    "could",
    "may",
    "might",
    "will",
    "would",
    "shall",
    "should",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "than",
    "then",
    "also",
    "both",
    "each",
    "such",
    "through",
    "during",
    "into",
    "between",
    "among",
    "upon",
    "show",
    "shows",
    "shown",
    "study",
    "studies",
    "using",
    "use",
    "used",
    "via",
])
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_BREAK = re.compile(r"[.!?][\"')\]]*(?:\s+|$)|[。！？][\"'”’）]*\s*|\n+")  # noqa: RUF001
_ABBREVIATION = re.compile(r"(?:\b(?:e\.g|i\.e|et al|vs|fig|dr|mr|mrs|no))\.$", re.IGNORECASE)
_RESULT = re.compile(r"\b(?:found|demonstrat\w*|observ\w*|significant\w*|conclu\w*|results?|reveal\w*)\b", re.I)


@dataclass(frozen=True)
class PreparedEvidenceFragment:
    """A literal half-open Python character range in one exact Memory version."""

    address: MemoryEntryAddress
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class EvidenceDocument:
    """One recalled entry, retaining its full cross-scope citation identity."""

    address: MemoryEntryAddress
    text: str


@dataclass(frozen=True)
class _Sentence:
    start: int
    end: int
    terms: Counter[str]


@dataclass(frozen=True)
class _Plan:
    fragments: tuple[PreparedEvidenceFragment, ...] = ()
    cost: int = 0
    utility: float = 0.0


def _stem(word: str) -> str:
    # Lightweight morphology needs no model, vocabulary download or corpus.
    if not word.isascii() or not word.isalpha() or len(word) < 4:
        return word
    if word.endswith("ies"):
        word = word[:-3] + "y"
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix, replacement in (("ation", "ate"), ("ion", ""), ("ing", ""), ("ed", ""), ("ive", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)] + replacement
            break
    if len(word) > 4 and word[-1] == word[-2] and word[-1] not in "slz":
        word = word[:-1]
    return word[:-1] if len(word) > 4 and word.endswith("e") else word


def _terms(text: str) -> Counter[str]:
    words: list[str] = []
    for match in _WORDS.finditer(text.casefold()):
        word = match.group()
        if word in _STOP:
            continue
        if len(word) > 1 and all("\u3400" <= char <= "\u9fff" for char in word):
            words.extend(word[index : index + 2] for index in range(len(word) - 1))
        else:
            words.append(_stem(word))
    return Counter(words)


def _sentences(text: str) -> tuple[_Sentence, ...]:
    boundaries = [0]
    for match in _BREAK.finditer(text):
        if match.group().lstrip().startswith(".") and _ABBREVIATION.search(text[boundaries[-1] : match.end()].strip()):
            continue
        boundaries.append(match.end())
    boundaries.append(len(text))
    result: list[_Sentence] = []
    for start, end in pairwise(boundaries):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            result.append(_Sentence(start, end, _terms(text[start:end])))
    return tuple(result)


def _relevance(
    sentences: Sequence[_Sentence],
    query: Counter[str],
    weights: dict[str, float],
    mean_length: float,
) -> list[float]:
    scores: list[float] = []
    for sentence in sentences:
        length = sum(sentence.terms.values())
        score = 0.0
        coverage = 0
        for term in query:
            frequency = sentence.terms[term]
            if frequency:
                coverage += 1
                score += weights[term] * frequency * 2.2 / (frequency + 1.2 * (0.5 + 0.5 * length / mean_length))
        scores.append(score * (0.65 + 0.35 * coverage / max(1, len(query))))
    return scores


def _item(fragment: PreparedEvidenceFragment) -> dict[str, object]:
    address = fragment.address
    return {
        "citation": {
            "scope_id": address.memory.scope_id,
            "memory_ref": address.memory.artifact.model_dump(mode="json"),
            "entry_id": address.entry_id,
            "entry_version_id": address.entry_version_id,
        },
        "content": fragment.text,
        "start": fragment.start,
        "end": fragment.end,
    }


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_evidence(fragments: Sequence[PreparedEvidenceFragment]) -> str:
    """Keep evidence inert inside the ordinary prepared-context trust envelope."""
    encoded = _json({"trust": "untrusted_history", "items": [_item(fragment) for fragment in fragments]})
    return (
        TRUST_POLICY
        + "\n\nBEGIN_POWERCONTEXT_PREPARED_CONTEXT_V1\n"
        + encoded
        + "\nEND_POWERCONTEXT_PREPARED_CONTEXT_V1"
    )


def _fragment(document: EvidenceDocument, start: int, end: int) -> PreparedEvidenceFragment:
    return PreparedEvidenceFragment(document.address, start, end, document.text[start:end])


def _plan(fragments: tuple[PreparedEvidenceFragment, ...], utility: float) -> _Plan:
    # Each item contributes its JSON plus one comma. For nonempty selections
    # the fixed envelope budget accounts for the one comma that is absent.
    return _Plan(fragments, sum(len(_json(_item(fragment)).encode("utf-8")) + 1 for fragment in fragments), utility)


def _frontier(plans: Sequence[_Plan], capacity: int) -> list[_Plan]:
    # A more expensive plan with no greater utility cannot improve any later
    # selection. Keeping the Pareto frontier bounds the multiple-choice DP.
    result: list[_Plan] = []
    best = -1.0
    for plan in sorted((plan for plan in plans if plan.cost <= capacity), key=lambda plan: (plan.cost, -plan.utility)):
        if plan.utility > best + 1e-9:
            result.append(plan)
            best = plan.utility
    return result


def _passage_plans(
    document: EvidenceDocument,
    sentences: Sequence[_Sentence],
    scores: Sequence[float],
    capacity: int,
) -> list[_Plan]:
    candidates: list[_Plan] = [_Plan()]
    if sentences and sum(scores) > 0:
        candidates.append(
            _plan(
                (_fragment(document, sentences[0].start, sentences[-1].end),),
                sum(scores) + 0.04 * max(scores) * (len(sentences) - 1),
            )
        )
    # A few adjacent sentences preserve explanations and co-reference while
    # sharing one citation. Wider passages remain choices when they fit.
    for first, sentence in enumerate(sentences):
        for last in range(first, min(len(sentences), first + 6)):
            utility = sum(scores[first : last + 1])
            if utility <= 0:
                continue
            utility += 0.04 * max(scores[first : last + 1]) * (last - first)
            fragment = _fragment(document, sentence.start, sentences[last].end)
            candidate = _plan((fragment,), utility)
            if candidate.cost <= capacity:
                candidates.append(candidate)
    return candidates


def _distant_plans(document: EvidenceDocument, sentences: Sequence[_Sentence], scores: Sequence[float]) -> list[_Plan]:
    # Distant supporting statements can share a plan without shipping the
    # irrelevant middle. Their two citations are charged in full.
    candidates: list[_Plan] = []
    ranked = sorted(range(len(sentences)), key=lambda index: (-scores[index], index))[:8]
    for offset, left in enumerate(ranked):
        for right in ranked[offset + 1 :]:
            first, last = sorted((left, right))
            if last <= first + 1 or min(scores[first], scores[last]) <= 0:
                continue
            candidates.append(
                _plan(
                    tuple(_fragment(document, sentences[index].start, sentences[index].end) for index in (first, last)),
                    scores[first] + scores[last],
                )
            )
    return candidates


def _window_centers(text: str, query: Counter[str]) -> list[int]:
    centers: list[int] = []
    for match in _WORDS.finditer(text):
        if all("\u3400" <= char <= "\u9fff" for char in match.group()):
            centers.extend(
                match.start() + offset
                for offset in range(len(match.group()) - 1)
                if match.group()[offset : offset + 2] in query
            )
        elif _terms(match.group()).keys() & query.keys():
            centers.append(match.start())
    centers.sort(key=lambda center: -len(_terms(text[max(0, center - 100) : center + 200]).keys() & query.keys()))
    return centers[:24]


def _word_window(text: str, sentence: _Sentence, center: int, width: int) -> tuple[int, int]:
    start = max(sentence.start, sentence.start + center - width // 3)
    end = min(sentence.end, start + width)
    while start > sentence.start and start < end and text[start - 1].isascii() and not text[start - 1].isspace():
        start += 1
    while end < sentence.end and end > start and text[end].isascii() and not text[end].isspace():
        end -= 1
    return start, end


def _window_plans(
    document: EvidenceDocument,
    sentences: Sequence[_Sentence],
    scores: Sequence[float],
    query: Counter[str],
    capacity: int,
) -> list[_Plan]:
    # A sentence can itself exceed the entire budget. In that case use literal
    # word-aligned windows around matching terms, never an unrelated prefix.
    candidates: list[_Plan] = []
    for sentence, score in zip(sentences, scores, strict=True):
        if score <= 0 or _plan((_fragment(document, sentence.start, sentence.end),), score).cost <= capacity:
            continue
        text = document.text[sentence.start : sentence.end]
        for center in _window_centers(text, query):
            for width in (128, 256, 384, 512, 768, 1024, 1536):
                start, end = _word_window(document.text, sentence, center, width)
                if start < end:
                    fragment = _fragment(document, start, end)
                    coverage = len(_terms(fragment.text).keys() & query.keys()) / max(
                        1, len(sentence.terms.keys() & query.keys())
                    )
                    candidate = _plan((fragment,), score * coverage * ((end - start) / len(text)) ** 0.5)
                    if candidate.cost <= capacity:
                        candidates.append(candidate)
    return candidates


def _document_plans(
    document: EvidenceDocument,
    sentences: Sequence[_Sentence],
    scores: Sequence[float],
    query: Counter[str],
    capacity: int,
) -> list[_Plan]:
    return _frontier(
        [
            *_passage_plans(document, sentences, scores, capacity),
            *_distant_plans(document, sentences, scores),
            *_window_plans(document, sentences, scores, query, capacity),
        ],
        capacity,
    )


def select_evidence(
    query: str,
    documents: Sequence[EvidenceDocument],
    max_bytes: int,
) -> tuple[PreparedEvidenceFragment, ...]:
    """Choose source spans using only the query, recalled text and wire budget."""
    capacity = max_bytes - len(render_evidence(()).encode("utf-8")) + 1
    if capacity <= 0:
        return ()
    groups = tuple(_sentences(document.text) for document in documents)
    all_sentences = tuple(sentence for group in groups for sentence in group)
    terms = _terms(query)
    if not terms or not all_sentences:
        return ()
    frequency = Counter(term for sentence in all_sentences for term in sentence.terms)
    weights = {term: math.log1p((len(all_sentences) + 0.5) / (frequency[term] + 0.5)) for term in terms}
    mean_length = max(1.0, sum(sum(sentence.terms.values()) for sentence in all_sentences) / len(all_sentences))
    raw_scores = [_relevance(group, terms, weights, mean_length) for group in groups]
    maximum = max((score for scores in raw_scores for score in scores), default=0.0)
    if maximum <= 0:
        return ()
    selections = [_Plan()]
    for document, sentences, raw in zip(documents, groups, raw_scores, strict=True):
        scores = [
            (score / maximum) ** 1.5 * (1.08 if _RESULT.search(document.text[sentence.start : sentence.end]) else 1.0)
            for sentence, score in zip(sentences, raw, strict=True)
        ]
        plans = _document_plans(document, sentences, scores, terms, capacity)
        selections = _frontier(
            [
                _Plan(previous.fragments + plan.fragments, previous.cost + plan.cost, previous.utility + plan.utility)
                for previous in selections
                for plan in plans
                if previous.cost + plan.cost <= capacity
            ],
            capacity,
        )
    selected = max(selections, key=lambda plan: (plan.utility, -plan.cost)).fragments
    return selected
