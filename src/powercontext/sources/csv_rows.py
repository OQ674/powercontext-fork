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

"""Offline CSV records captured as stable, individually readable evidence."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Self
from urllib.parse import quote

from pydantic import BaseModel, Field, field_validator, model_validator

from powercontext.limits import MAX_SOURCE_ID_LENGTH
from powercontext.sources.definitions import SourceDefinition, SourceProjection
from powercontext.sources.models import Source, SourceMaterialization
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY, TextEvidence


def _validate_document_id(document_id: str) -> str:
    if not document_id or document_id != document_id.strip():
        raise ValueError("document_id must be nonempty without surrounding whitespace")  # noqa: TRY003
    return document_id


def _primary_key_index(columns: tuple[str, ...], primary_key: str) -> int:
    if not columns or any(not column.strip() for column in columns):
        raise ValueError("CSV column names must be nonempty and not blank")  # noqa: TRY003
    if len(set(columns)) != len(columns):
        raise ValueError("CSV column names must be unique")  # noqa: TRY003
    if not primary_key or primary_key not in columns:
        raise ValueError("primary_key must exactly match a CSV column name")  # noqa: TRY003
    return columns.index(primary_key)


def csv_row_source_id(document_id: str, primary_key_value: str) -> str:
    """Encode document and raw primary-key value into a bounded row identity."""

    _validate_document_id(document_id)
    if not primary_key_value.strip():
        raise ValueError("CSV primary-key values must be nonempty and not blank")  # noqa: TRY003
    identity = f"csv:{quote(document_id, safe='')}:{quote(primary_key_value, safe='')}"
    if len(identity) > MAX_SOURCE_ID_LENGTH:
        raise ValueError("CSV row identity exceeds the Source ID length limit")  # noqa: TRY003
    return identity


class CSVDocumentInput(BaseModel):
    """A complete UTF-8 CSV document and its exact primary-key column name."""

    document_id: str
    primary_key: Annotated[str, Field(min_length=1)]
    content: bytes

    @field_validator("document_id")
    @classmethod
    def validate_document_id(cls, value: str) -> str:
        return _validate_document_id(value)


class CSVRowInput(BaseModel):
    """One full record, preserving raw strings and the original column order."""

    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]

    @model_validator(mode="after")
    def validate_row(self) -> Self:
        csv_row_source_id(self.document_id, self.primary_key_value)
        key_index = _primary_key_index(self.columns, self.primary_key)
        if len(self.values) != len(self.columns):
            raise ValueError("CSV record width must equal the header width")  # noqa: TRY003
        if self.values[key_index] != self.primary_key_value:
            raise ValueError("primary_key_value must match the raw primary-key field")  # noqa: TRY003
        return self


class CSVRowSource(Source):
    """Captured row evidence with a stable document-and-key identity."""

    source_id: str
    document_id: str
    primary_key: str
    primary_key_value: str
    columns: tuple[str, ...]
    values: tuple[str, ...]


def parse_csv_document(value: CSVDocumentInput) -> tuple[CSVRowInput, ...]:
    """Validate the entire document before returning any of its captured rows."""

    _validate_document_id(value.document_id)
    try:
        text = value.content.decode("utf-8-sig", errors="strict")
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=",", quotechar='"', doublequote=True, strict=True)
        columns = tuple(next(reader, ()))
        key_index = _primary_key_index(columns, value.primary_key)
        rows: list[CSVRowInput] = []
        seen: set[str] = set()
        for fields in reader:
            if not fields:
                continue
            if len(fields) != len(columns):
                raise ValueError("CSV record width must equal the header width")  # noqa: TRY003
            key = fields[key_index]
            if key in seen:
                raise ValueError("CSV primary-key values must be unique within a document")  # noqa: TRY003
            rows.append(
                CSVRowInput(
                    document_id=value.document_id,
                    primary_key=value.primary_key,
                    primary_key_value=key,
                    columns=columns,
                    values=tuple(fields),
                )
            )
            seen.add(key)
        return tuple(rows)
    except (UnicodeError, csv.Error) as error:
        raise ValueError("Invalid UTF-8 CSV document") from error  # noqa: TRY003


class CSVRowTextEvidenceProjection:
    """Expose complete row JSON through the standard text-evidence capability."""

    name = TEXT_EVIDENCE_PROJECTION_KEY.name
    version = TEXT_EVIDENCE_PROJECTION_KEY.version
    source_class: type[CSVRowSource] = CSVRowSource
    output_class: type[BaseModel] = TextEvidence

    def project(self, source: CSVRowSource, /) -> TextEvidence:
        row = dict(zip(source.columns, source.values, strict=True))
        return TextEvidence(
            source_type="csv-row",
            source_id=source.source_id,
            content=json.dumps(row, ensure_ascii=False, separators=(",", ":")),
            metadata={
                "document_id": source.document_id,
                "primary_key": source.primary_key,
                "primary_key_value": source.primary_key_value,
                "columns": list(source.columns),
                "row": row,
            },
        )


class CSVRowSourceDefinition:
    """Resolve captured rows and read their complete original records."""

    input_class: type[CSVRowInput] = CSVRowInput
    name = "csv-row"
    source_class: type[CSVRowSource] = CSVRowSource
    version = "1"
    projections: tuple[SourceProjection[CSVRowSource], ...] = (CSVRowTextEvidenceProjection(),)

    async def resolve(self, value: CSVRowInput, /) -> CSVRowSource:
        identity = csv_row_source_id(value.document_id, value.primary_key_value)
        return CSVRowSource(
            name=identity,
            source_id=identity,
            definition_version=self.version,
            materialization=SourceMaterialization.CAPTURED,
            **value.model_dump(),
        )

    async def read(self, source: CSVRowSource, /) -> CSVRowInput:
        return CSVRowInput(
            document_id=source.document_id,
            primary_key=source.primary_key,
            primary_key_value=source.primary_key_value,
            columns=source.columns,
            values=source.values,
        )


CSV_ROW_SOURCE_DEFINITION: SourceDefinition[CSVRowInput, CSVRowSource, CSVRowInput] = CSVRowSourceDefinition()
