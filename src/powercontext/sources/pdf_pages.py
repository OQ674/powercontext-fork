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

"""Complete physical pages of immutable PDF revisions, with scoped retrieval."""

from __future__ import annotations

import hashlib
import io
import json
import zlib
from copy import copy
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator
from pypdf import PdfReader
from pypdf.filters import decode_stream_data
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, NameObject, NullObject, StreamObject

from powercontext.artifacts import MemoryCitation
from powercontext.sources.definitions import SourceDefinition, SourceProjection
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence

if TYPE_CHECKING:
    from powercontext.builtin.runtime.application import ScopedMemoryApplication


class PDFDocumentInput(BaseModel):
    """Original PDF bytes, never a pre-extracted substitute."""

    document_id: str
    content: bytes

    @field_validator("document_id")
    @classmethod
    def nonblank_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("document_id must contain non-whitespace text")  # noqa: TRY003
        return value


class PDFPageInput(BaseModel):
    """One complete page in the physical order of an exact input file."""

    document_id: str
    document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_number: int = Field(gt=0, strict=True)
    text: str

    _nonblank_id = field_validator("document_id")(PDFDocumentInput.nonblank_id.__func__)


class _UnreadablePDF(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Cannot completely read PDF: {detail}")


def _object(value):
    return value.get_object() if hasattr(value, "get_object") else value


def _page_count(node, ancestors: frozenset[int] = frozenset()) -> int:
    node = _object(node)
    if not isinstance(node, DictionaryObject) or id(node) in ancestors:
        raise _UnreadablePDF("invalid-or-cyclic-page-tree")
    kind = _object(node.get("/Type"))
    if kind == "/Page":
        return 1
    children = _object(node.get("/Kids"))
    if kind != "/Pages" or not isinstance(children, ArrayObject):
        raise _UnreadablePDF("unreadable-page-tree-children")
    actual = sum(_page_count(child, ancestors | {id(node)}) for child in children)
    if _object(node.get("/Count")) != actual:
        raise _UnreadablePDF("page-tree-count-mismatch")
    return actual


def _check_stream(stream: StreamObject) -> None:
    filters = _object(stream.get("/Filter"))
    if filters is None:
        stream.get_data()
        return
    filters = filters if isinstance(filters, ArrayObject) else (filters,)
    parameters = _object(stream.get("/DecodeParms"))
    parameters = parameters if isinstance(parameters, ArrayObject) else (parameters,) * len(filters)
    payload = stream._data
    for index, filter_name in enumerate(filters):
        filter_name = _object(filter_name)
        if filter_name in {"/FlateDecode", "/Fl"}:
            decoder = zlib.decompressobj()
            decoder.decompress(payload)
            if not decoder.eof:
                raise _UnreadablePDF("truncated-compressed-text-stream")
        stage = copy(stream)
        stage._data = payload
        stage[NameObject("/Filter")] = filter_name
        stage.pop("/DecodeParms", None)
        parameter = _object(parameters[index]) if index < len(parameters) else None
        if parameter is not None:
            stage[NameObject("/DecodeParms")] = parameter
        payload = decode_stream_data(stage)


def _content(value, reader: PdfReader) -> ContentStream:
    value = _object(value)
    if value is None or isinstance(value, NullObject):
        return ContentStream(None, reader)
    streams = value if isinstance(value, ArrayObject) else (value,)
    for stream in streams:
        stream = _object(stream)
        if not isinstance(stream, StreamObject):
            raise _UnreadablePDF("non-stream-page-content")
        _check_stream(stream)
    parsed = ContentStream(value, reader)
    # pypdf parses operators lazily. Force every stream before accepting a page.
    _ = parsed.operations
    return parsed


def _font(resources: DictionaryObject, name) -> None:
    fonts = _object(resources.get("/Font"))
    font = _object(fonts.get(name)) if isinstance(fonts, DictionaryObject) else None
    if not isinstance(font, DictionaryObject):
        raise _UnreadablePDF("missing-font")
    cmap = _object(font.get("/ToUnicode"))
    if cmap is not None and not isinstance(cmap, NullObject):
        if not isinstance(cmap, StreamObject):
            raise _UnreadablePDF("non-stream-font-unicode-map")
        _check_stream(cmap)


def _resources_for_content(
    content: ContentStream,
    resources: DictionaryObject,
    reader: PdfReader,
    forms: frozenset[int] = frozenset(),
    inherited_font: bool = False,
) -> DictionaryObject:
    """Validate used resources and give Forms their caller's inherited resources.

    Only extraction copies are changed. A shared Form used by two pages must
    resolve fonts in each caller's context, rather than retaining the first one.
    """
    result = DictionaryObject(resources)
    objects = _object(resources.get("/XObject"))
    objects = DictionaryObject(objects) if isinstance(objects, DictionaryObject) else DictionaryObject()
    has_font = inherited_font
    stack: list[bool] = []
    for operands, operator in content.operations:
        if operator == b"q":
            stack.append(has_font)
        elif operator == b"Q" and stack:
            has_font = stack.pop()
        elif operator == b"Tf":
            _font(resources, operands[0])
            has_font = True
        elif operator in {b"Tj", b"TJ", b"'", b'"'} and not has_font:
            raise _UnreadablePDF("text-without-readable-font")
        elif operator == b"Do":
            _prepare_form(operands[0], objects, resources, reader, forms, has_font)
    if objects:
        result[NameObject("/XObject")] = objects
    return result


def _prepare_form(name, objects, resources, reader, forms, has_font) -> None:
    original = _object(objects.get(name))
    if not isinstance(original, StreamObject):
        raise _UnreadablePDF("missing-external-object")
    if _object(original.get("/Subtype")) != "/Form":
        return
    if id(original) in forms:
        raise _UnreadablePDF("cyclic-text-form")
    content = _content(original, reader)
    form_resources = _object(original.get("/Resources"))
    if form_resources is None:
        form_resources = resources
    if not isinstance(form_resources, DictionaryObject):
        raise _UnreadablePDF("invalid-form-resources")
    form = copy(original)
    form[NameObject("/Resources")] = _resources_for_content(
        content,
        form_resources,
        reader,
        forms | {id(original)},
        has_font,
    )
    objects[name] = form


def _extract(page, reader: PdfReader) -> str:
    content = _content(page.get("/Contents"), reader)
    resources = _object(page.get("/Resources"))
    resources = resources if isinstance(resources, DictionaryObject) else DictionaryObject()
    prepared = copy(page)
    prepared[NameObject("/Resources")] = _resources_for_content(content, resources, reader)
    return prepared.extract_text(extraction_mode="plain") or ""


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Return all physical pages atomically; preserve pypdf's plain page text."""
    digest = hashlib.sha256(value.content).hexdigest()
    try:
        with io.BytesIO(value.content) as stream:
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted and not reader.decrypt(""):
                raise _UnreadablePDF("nonempty-password-required")  # noqa: TRY301
            expected = _page_count(reader.root_object["/Pages"])
            pages = tuple(
                PDFPageInput(
                    document_id=value.document_id,
                    document_sha256=digest,
                    page_number=number,
                    text=_extract(page, reader),
                )
                for number, page in enumerate(reader.pages, 1)
            )
            if len(pages) != expected:
                raise _UnreadablePDF("incomplete-physical-page-traversal")  # noqa: TRY301
            return pages
    except Exception as error:
        raise ValueError("The original PDF cannot be completely parsed") from error  # noqa: TRY003


class _PageSource(Source):
    page: PDFPageInput


class _PageText:
    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class: type[_PageSource] = _PageSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: _PageSource, /) -> TextEvidence:
        page = source.page
        return TextEvidence(
            source_type="pdf-page",
            source_id=source.name,
            content=f"{page.document_id}\n{page.text}",
            metadata={
                "document_id": page.document_id,
                "document_sha256": page.document_sha256,
                "page_number": page.page_number,
            },
        )


class _PageDefinition:
    name = "pdf-page"
    version = "1"
    input_class: type[PDFPageInput] = PDFPageInput
    source_class: type[_PageSource] = _PageSource
    projections: tuple[SourceProjection[_PageSource], ...] = (_PageText(),)

    async def resolve(self, value: PDFPageInput, /) -> _PageSource:
        canonical = json.dumps(
            [value.document_id, value.document_sha256, value.page_number], ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return _PageSource(
            name="pdf-page:" + hashlib.sha256(canonical).hexdigest(),
            definition_version="1",
            materialization=SourceMaterialization.CAPTURED,
            page=value.model_copy(deep=True),
        )

    async def read(self, source: _PageSource, /) -> PDFPageInput:
        return source.page.model_copy(deep=True)


PDF_PAGE_SOURCE_DEFINITION: SourceDefinition[PDFPageInput, _PageSource, PDFPageInput] = _PageDefinition()


async def search_pdf_pages(
    memory: ScopedMemoryApplication,
    question: str,
    limit: int = 10,
) -> tuple[MemoryCitation, ...]:
    """Find distinct page citations in the caller's real, current scoped Memory."""
    from powercontext.sources._pdf_retrieval import search_pages

    return await search_pages(memory, question, limit)
