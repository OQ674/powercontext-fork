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

"""CSV fidelity, validation and portable row-evidence regressions."""

from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest

from powercontext.sources import SourceDefinitionRegistry, SourceMaterialization, TextEvidence
from powercontext.sources.csv_rows import (
    CSV_ROW_SOURCE_DEFINITION,
    CSVDocumentInput,
    CSVRowInput,
    CSVRowSource,
    csv_row_source_id,
    parse_csv_document,
)
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


@pytest.mark.parametrize(
    "content",
    [
        b"\n",
        b'""\n',
        b"id,name\n1,valid\n2,too,many\n",
        b"id,name\n1,valid\n \t,blank-key\n",
        b"id,name\n1,valid\n1,duplicate\n",
        b'id\n1\n""\n',
        b'id,name\n1,valid\n2,"closed"junk\n',
        b'id,name\n1,valid\n2,"unfinished',
        b"id,name\n1,valid\n2,\xc0\xaf\n",
        b"id,name\n1,valid\n2,\xed\xa0\x80\n",
        b"id,name\n1,valid\n2,\xe2\x82",
    ],
)
def test_invalid_trailing_records_reject_the_entire_document(content: bytes) -> None:
    with pytest.raises(ValueError):
        parse_csv_document(CSVDocumentInput(document_id="records", primary_key="id", content=content))


@pytest.mark.parametrize("line_ending", ["\n", "\r\n", "\r"])
def test_unicode_strings_empty_fields_and_quoted_line_endings_round_trip(line_ending: str) -> None:
    columns = ("编号", " id ", "number", "boolean", "empty", "note")
    records = [
        ("北京", " 001 ", "00012.00", "false", "", f'第一行{line_ending}第二行,"原文"'),
        ("东京", "001 ", "1e10", "NULL", "", "\ufeff内嵌 BOM"),
        ("巴黎", "001", "-0", "true", "", ""),
    ]
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator=line_ending)
    writer.writerow(columns)
    writer.writerows(records)
    content = b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
    rows = parse_csv_document(CSVDocumentInput(document_id="国际:表/1", primary_key=" id ", content=content))
    assert [row.values for row in rows] == records
    registry = SourceDefinitionRegistry((CSV_ROW_SOURCE_DEFINITION,))
    for row in rows:
        source = asyncio.run(registry.resolve(row))
        assert isinstance(source, CSVRowSource)
        assert source.materialization == SourceMaterialization.CAPTURED
        assert source.definition_version == "1"
        restored = CSVRowSource.model_validate_json(source.model_dump_json())
        assert asyncio.run(registry.read(restored)) == row
        evidence = TextEvidence.model_validate(registry.project(restored, TEXT_EVIDENCE_PROJECTION_KEY))
        expected = dict(zip(columns, row.values, strict=True))
        assert evidence.content == json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
        assert evidence.metadata == {
            "document_id": "国际:表/1",
            "primary_key": " id ",
            "primary_key_value": row.primary_key_value,
            "columns": list(columns),
            "row": expected,
        }
        assert evidence.source_id == source.source_id == source.name


def test_identity_limit_counts_encoded_characters_and_avoids_component_collisions() -> None:
    assert len(csv_row_source_id("d", "x" * 250)) == 256
    with pytest.raises(ValueError):
        csv_row_source_id("d", "x" * 251)
    assert len(csv_row_source_id("d", "界" * 27 + "x" * 7)) == 256
    with pytest.raises(ValueError):
        csv_row_source_id("d", "界" * 28)
    assert csv_row_source_id("a:b", "c") != csv_row_source_id("a", "b:c")
    assert csv_row_source_id("a%3Ab", "c") != csv_row_source_id("a:b", "c")
    with pytest.raises(ValueError):
        parse_csv_document(CSVDocumentInput(document_id="d", primary_key="id", content=b"id\n" + b"x" * 251))


@pytest.mark.parametrize("document_id", ["", " ", "\tname", "name\n", "\u3000name"])
def test_document_identity_rejects_blank_or_padded_values(document_id: str) -> None:
    with pytest.raises(ValueError):
        csv_row_source_id(document_id, "1")


def test_header_names_and_primary_key_values_are_compared_exactly() -> None:
    rows = parse_csv_document(
        CSVDocumentInput(document_id="exact", primary_key=" id ", content=b"id, id ,ID\n1, 1 ,01\n")
    )
    assert rows[0].primary_key_value == " 1 "
    assert rows[0].columns == ("id", " id ", "ID")
    with pytest.raises(ValueError):
        parse_csv_document(CSVDocumentInput(document_id="exact", primary_key="id", content=b" id \n1\n"))
    assert parse_csv_document(CSVDocumentInput(document_id="exact", primary_key="id", content=b"id\n\n\n")) == ()


@pytest.mark.parametrize(
    "updates",
    [
        {"columns": ("id", "id")},
        {"columns": ("id", " ")},
        {"values": ("1",)},
        {"primary_key": "missing"},
        {"primary_key_value": "2"},
        {"primary_key_value": " "},
    ],
)
def test_direct_row_inputs_obey_the_same_record_contract(updates: dict[str, object]) -> None:
    payload = {
        "document_id": "direct",
        "primary_key": "id",
        "primary_key_value": "1",
        "columns": ("id", "name"),
        "values": ("1", "row"),
    }
    with pytest.raises(ValueError):
        CSVRowInput.model_validate(payload | updates)
