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

"""Full PDF page fidelity, atomic failure and revision-specific identities."""

from __future__ import annotations

import asyncio
import hashlib
import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, TextStringObject

from powercontext.sources import SourceDefinitionRegistry, SourceMaterialization, TextEvidence
from powercontext.sources.pdf_pages import (
    PDF_PAGE_SOURCE_DEFINITION,
    PDFDocumentInput,
    PDFPageInput,
    PDFPageSource,
    parse_pdf_document,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


def make_pdf(
    texts: tuple[str, ...], *, title: str = "original", password: str | None = None, corrupt_last: bool = False
) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=600, height=800)
        if not text:
            continue
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        stream = DecodedStreamObject()
        lines = ["BT /F1 10 Tf 20 780 Td"]
        for line in text.split("\n"):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append(f"({escaped}) Tj 0 -12 Td")
        lines.append("ET")
        stream.set_data("\n".join(lines).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if corrupt_last:
        writer.pages[-1][NameObject("/Contents")] = TextStringObject("invalid content-stream object")
    writer.add_metadata({"/Title": title})
    if password is not None:
        writer.encrypt(user_password=password, owner_password="owner")  # noqa: S106
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_full_pages_blank_page_order_numbers_and_exact_projection() -> None:
    raw = make_pdf(("Revenue 00123.00\nCost (45)\nPrinted page 99", "", "Balance sheet\nAssets 9876\nPrinted page i"))
    pages = parse_pdf_document(PDFDocumentInput(document_id="财报: 2023/修订", content=raw))
    assert [page.page_number for page in pages] == [1, 2, 3]
    assert pages[1].text == ""
    assert "00123.00" in pages[0].text and "(45)" in pages[0].text
    assert "9876" in pages[2].text and "Revenue" not in pages[2].text
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    names = set()
    for page in pages:
        assert page.document_sha256 == hashlib.sha256(raw).hexdigest()
        source = asyncio.run(registry.resolve(page))
        assert isinstance(source, PDFPageSource)
        assert source.materialization == SourceMaterialization.CAPTURED
        names.add(source.name)
        restored = PDFPageSource.model_validate_json(source.model_dump_json())
        assert asyncio.run(registry.read(restored)) == page
        evidence = TextEvidence.model_validate(registry.project(restored, TEXT_EVIDENCE_PROJECTION_KEY))
        assert evidence.source_type == "pdf-page" and evidence.source_id == source.name
        assert evidence.content == f"{page.document_id}\n{page.text}"
        assert evidence.metadata == {
            "document_id": page.document_id,
            "document_sha256": page.document_sha256,
            "page_number": page.page_number,
        }
    assert len(names) == 3


def test_revision_document_and_physical_page_all_affect_identity() -> None:
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    identities = set()
    for document in ("report:a", "report%3Aa", "报告" * 300):
        for title in ("original", "revised"):
            raw = make_pdf(("same text", "same text"), title=title)
            pages = parse_pdf_document(PDFDocumentInput(document_id=document, content=raw))
            for page in pages:
                source = asyncio.run(registry.resolve(page))
                assert source.name == asyncio.run(registry.resolve(page)).name
                assert len(source.name) <= 256
                identities.add(source.name)
    assert len(identities) == 12


@pytest.mark.parametrize("document_id", ["", " ", "\t\r\n", "\u3000"])
def test_document_id_must_not_be_blank(document_id: str) -> None:
    with pytest.raises(ValueError):
        PDFDocumentInput(document_id=document_id, content=make_pdf(("text",)))


def test_late_page_corruption_and_password_failure_are_atomic() -> None:
    with pytest.raises(ValueError):
        parse_pdf_document(
            PDFDocumentInput(document_id="broken", content=make_pdf(("valid first", "valid second"), corrupt_last=True))
        )
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="private", content=make_pdf(("text",), password="password")))  # noqa: S106
    readable = parse_pdf_document(
        PDFDocumentInput(document_id="permissions", content=make_pdf(("text", ""), password=""))
    )
    assert len(readable) == 2 and "text" in readable[0].text and readable[1].text == ""


@pytest.mark.parametrize(
    "updates",
    [
        {"page_number": 0},
        {"page_number": -1},
        {"page_number": True},
        {"document_sha256": "A" * 64},
        {"document_sha256": "0" * 63},
    ],
)
def test_direct_page_input_validates_physical_location_and_digest(updates: dict[str, object]) -> None:
    values = {"document_id": "report", "document_sha256": "0" * 64, "page_number": 1, "text": ""}
    with pytest.raises(ValueError):
        PDFPageInput.model_validate(values | updates)
