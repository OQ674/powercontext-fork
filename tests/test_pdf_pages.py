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

"""PDF integrity and exact page provenance through the public Source protocol."""

from __future__ import annotations

import hashlib
import io
from typing import cast

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from powercontext.sources import SourceDefinitionRegistry, project_source_for_transport
from powercontext.sources.pdf_pages import (
    PDF_PAGE_SOURCE_DEFINITION,
    PDFDocumentInput,
    PDFPageInput,
    parse_pdf_document,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


def pdf_bytes(texts: tuple[str, ...], *, title: str = "Report", password: str | None = None) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if not text:
            continue
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        lines = ["BT /F1 9 Tf 36 750 Td"]
        for index, line in enumerate(text.splitlines()):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append(("0 -11 Td " if index else "") + "(" + escaped + ") Tj")
        stream = DecodedStreamObject()
        stream.set_data(("\n".join([*lines, "ET"])).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Title": title})
    if password is not None:
        writer.encrypt(password, owner_password="owner")  # noqa: S106
    data = io.BytesIO()
    writer.write(data)
    return data.getvalue()


def _write(writer: PdfWriter) -> bytes:
    data = io.BytesIO()
    writer.write(data)
    return data.getvalue()


@pytest.mark.parametrize("texts", [("",), ("First 125.00", "", "Last 731"), ("Same 42", "Same 42")])
def test_all_physical_pages_preserve_text_and_numbers(texts):
    raw = pdf_bytes(texts)
    parsed = parse_pdf_document(PDFDocumentInput(document_id="Example", content=raw))
    assert [page.page_number for page in parsed] == list(range(1, len(texts) + 1))
    assert [page.text.strip() for page in parsed] == list(texts)
    assert all(page.document_sha256 == hashlib.sha256(raw).hexdigest() for page in parsed)


@pytest.mark.parametrize("raw", [b"", b"not a PDF", b"%PDF-1.7\npartial"])
def test_invalid_files_fail_without_page_results(raw):
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="bad", content=raw))


def test_empty_password_permissions_are_legal_and_password_protection_fails():
    parsed = parse_pdf_document(
        PDFDocumentInput(document_id="permissions", content=pdf_bytes(("Readable 123",), password=""))
    )
    assert parsed[0].text.strip() == "Readable 123"
    with pytest.raises(ValueError):
        parse_pdf_document(
            PDFDocumentInput(document_id="locked", content=pdf_bytes(("Private 456",), password="secret"))  # noqa: S106
        )


@pytest.mark.parametrize(
    "damage", ["content_type", "content_array", "compressed", "tree", "unfinished_text", "font", "unicode_map"]
)
def test_unreadable_later_page_fails_atomically(damage):
    writer = PdfWriter(io.BytesIO(pdf_bytes(("Good 111", "Later 222"))))
    page = writer.pages[1]
    if damage == "content_type":
        page[NameObject("/Contents")] = NumberObject(8)
    elif damage == "content_array":
        page[NameObject("/Contents")] = ArrayObject([page.raw_get("/Contents"), NumberObject(8)])
    elif damage == "compressed":
        compressed = cast(DecodedStreamObject, page["/Contents"]).flate_encode()
        compressed._data = compressed._data[:-4]
        page[NameObject("/Contents")] = writer._add_object(compressed)
    elif damage == "tree":
        cast(DictionaryObject, writer.root_object["/Pages"])[NameObject("/Count")] = NumberObject(3)
    elif damage == "font":
        page[NameObject("/Resources")] = DictionaryObject()
    elif damage == "unicode_map":
        resources = cast(DictionaryObject, page["/Resources"])
        fonts = cast(DictionaryObject, resources["/Font"])
        cast(DictionaryObject, fonts["/F1"])[NameObject("/ToUnicode")] = NumberObject(42)
    else:
        cast(DecodedStreamObject, page["/Contents"]).set_data(b"BT /F1 9 Tf (unterminated")
    with pytest.raises(ValueError):
        parse_pdf_document(PDFDocumentInput(document_id="bad-page", content=_write(writer)))


def test_content_array_is_one_logical_stream():
    writer = PdfWriter(io.BytesIO(pdf_bytes(("Before",))))
    left, right = DecodedStreamObject(), DecodedStreamObject()
    left.set_data(b"BT /F1 9")
    right.set_data(b"Tf 36 750 Td (Continuation 991) Tj ET")
    writer.pages[0][NameObject("/Contents")] = ArrayObject([writer._add_object(left), writer._add_object(right)])
    page = parse_pdf_document(PDFDocumentInput(document_id="array", content=_write(writer)))[0]
    assert page.text.strip() == "Continuation 991"


def test_shared_form_inherits_each_callers_font_resources():
    writer = PdfWriter(io.BytesIO(pdf_bytes(("First", "Second"))))
    form = DecodedStreamObject()
    form.update({
        NameObject("/Type"): NameObject("/XObject"),
        NameObject("/Subtype"): NameObject("/Form"),
        NameObject("/BBox"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(100), NumberObject(100)]),
    })
    form.set_data(b"BT /F1 9 Tf 0 80 Td (A) Tj ET")
    form_ref = writer._add_object(form)
    for index, page in enumerate(writer.pages):
        resources = cast(DictionaryObject, page["/Resources"])
        fonts = cast(DictionaryObject, resources["/Font"])
        font = DictionaryObject(cast(DictionaryObject, fonts["/F1"]))
        cmap = DecodedStreamObject()
        cmap.set_data(
            (
                f"1 begincodespacerange <00> <FF> endcodespacerange\n1 beginbfchar <41> <00{88 + index:02x}> endbfchar"
            ).encode()
        )
        font[NameObject("/ToUnicode")] = writer._add_object(cmap)
        resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Shared"): form_ref})
        cast(DecodedStreamObject, page["/Contents"]).set_data(b"q /Shared Do Q")
    pages = parse_pdf_document(PDFDocumentInput(document_id="form", content=_write(writer)))
    assert [page.text.strip() for page in pages] == ["X", "Y"]


@pytest.mark.asyncio
async def test_source_identity_and_projection_preserve_revisions_and_unicode():
    registry = SourceDefinitionRegistry((PDF_PAGE_SOURCE_DEFINITION,))
    old = pdf_bytes(("Same body 123", "Same body 123"), title="old")
    new = pdf_bytes(("Same body 123", "Same body 123"), title="metadata-only revision")
    names = set()
    for identifier in ("Company 2024", "文档\n标识" * 200, "a:b", "a"):
        for raw in (old, new):
            for page in parse_pdf_document(PDFDocumentInput(document_id=identifier, content=raw)):
                source = await registry.resolve(page)
                assert source.name == (await registry.resolve(page)).name
                assert len(source.name) <= 256 and source.name not in names
                names.add(source.name)
                assert await registry.read(source) == page
                evidence = project_source_for_transport(registry, source).projection(TEXT_EVIDENCE_PROJECTION_KEY)
                assert isinstance(evidence, dict)
                assert evidence["content"] == identifier + "\n" + page.text
                assert evidence["metadata"] == {
                    "document_id": identifier,
                    "document_sha256": hashlib.sha256(raw).hexdigest(),
                    "page_number": page.page_number,
                }
    assert len(names) == 16


@pytest.mark.parametrize("identifier", ["", " \n\t"])
def test_document_id_cannot_be_blank(identifier):
    with pytest.raises(ValueError):
        PDFDocumentInput(document_id=identifier, content=b"")


def test_page_input_and_source_fields_have_required_types():
    with pytest.raises(ValueError):
        PDFPageInput(document_id="x", document_sha256="A" * 64, page_number=1, text="")
    with pytest.raises(ValueError):
        PDFPageInput(document_id="x", document_sha256="0" * 64, page_number=True, text="")


def test_plain_text_matches_standard_pypdf_without_ranking_normalization():
    raw = pdf_bytes(("Cash (net) 1,234.56\nRevenue 9,876.50", "Other 25"))
    expected = [page.extract_text(extraction_mode="plain") for page in PdfReader(io.BytesIO(raw)).pages]
    assert [page.text for page in parse_pdf_document(PDFDocumentInput(document_id="x", content=raw))] == expected
