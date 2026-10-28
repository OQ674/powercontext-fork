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

"""Complete physical PDF pages as revision-specific, captured evidence."""

from __future__ import annotations

import hashlib
import io
import json
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, field_validator
from pypdf import PageObject, PdfReader
from pypdf.generic import ArrayObject, NullObject, StreamObject

from powercontext.sources.definitions import SourceDefinition, SourceProjection
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence

if TYPE_CHECKING:
    from powercontext.builtin.artifacts.memory.models import MemoryCitation
    from powercontext.sources._pdf_retrieval import PDFMemory


def _document_id(value: str) -> str:
    if not value.strip():
        raise ValueError("PDF document_id must not be empty or blank")  # noqa: TRY003
    return value


class PDFDocumentInput(BaseModel):
    """The complete original PDF bytes and a caller-owned document identity."""

    document_id: str
    content: bytes

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        return _document_id(value)


class PDFPageInput(BaseModel):
    """The complete extractable text of one one-based physical PDF page."""

    document_id: str
    document_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    page_number: Annotated[int, Field(ge=1, strict=True)]
    text: str

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        return _document_id(value)


class PDFPageSource(Source):
    """Captured page content whose identity includes the original PDF revision."""

    document_id: str
    document_sha256: str
    page_number: int
    text: str


def _page_text(page: PageObject) -> str:
    contents = page.get("/Contents")
    if contents is not None:
        resolved = contents.get_object()
        streams = resolved if isinstance(resolved, ArrayObject) else (resolved,)
        if not isinstance(resolved, NullObject) and any(
            not isinstance(item.get_object(), StreamObject) for item in streams
        ):
            raise ValueError("Invalid PDF page content stream")  # noqa: TRY003
    return page.extract_text(extraction_mode="plain") or ""


def parse_pdf_document(value: PDFDocumentInput) -> tuple[PDFPageInput, ...]:
    """Extract every physical page, including blanks, or fail without any pages."""

    _document_id(value.document_id)
    digest = hashlib.sha256(value.content).hexdigest()
    try:
        with io.BytesIO(value.content) as stream:
            reader = PdfReader(stream, strict=True)
            if reader.is_encrypted and not reader.decrypt(""):
                raise ValueError("The PDF requires a nonempty password")  # noqa: TRY003, TRY301
            return tuple(
                PDFPageInput(
                    document_id=value.document_id,
                    document_sha256=digest,
                    page_number=index,
                    text=_page_text(page),
                )
                for index, page in enumerate(reader.pages, start=1)
            )
    except Exception as error:
        raise ValueError("Cannot completely parse the original PDF") from error  # noqa: TRY003


class PDFPageTextEvidenceProjection:
    """Preserve the full page and its exact physical location in a PDF revision."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class: type[PDFPageSource] = PDFPageSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: PDFPageSource, /) -> TextEvidence:
        return TextEvidence(
            source_type="pdf-page",
            source_id=source.name,
            content=f"{source.document_id}\n{source.text}",
            metadata={
                "document_id": source.document_id,
                "document_sha256": source.document_sha256,
                "page_number": source.page_number,
            },
        )


class PDFPageSourceDefinition:
    """Resolve and read complete immutable page evidence."""

    name = "pdf-page"
    version = "1"
    input_class: type[PDFPageInput] = PDFPageInput
    source_class: type[PDFPageSource] = PDFPageSource
    projections: tuple[SourceProjection[PDFPageSource], ...] = (PDFPageTextEvidenceProjection(),)

    async def resolve(self, value: PDFPageInput, /) -> PDFPageSource:
        identity = json.dumps(
            [value.document_id, value.document_sha256, value.page_number], ensure_ascii=False, separators=(",", ":")
        )
        name = "pdf:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return PDFPageSource(
            name=name,
            definition_version=self.version,
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: PDFPageSource, /) -> PDFPageInput:
        return PDFPageInput(
            document_id=source.document_id,
            document_sha256=source.document_sha256,
            page_number=source.page_number,
            text=source.text,
        )


PDF_PAGE_SOURCE_DEFINITION: SourceDefinition[PDFPageInput, PDFPageSource, PDFPageInput] = PDFPageSourceDefinition()


async def search_pdf_pages(memory: PDFMemory, question: str, limit: int = 10) -> tuple[MemoryCitation, ...]:
    """Retrieve distinct PDF pages using only real, scoped Memory citations."""

    from powercontext.sources._pdf_retrieval import search_pages

    return await search_pages(memory, question, limit)
