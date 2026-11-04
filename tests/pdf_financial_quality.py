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

"""Independently authored report fixtures; scoring data never enters product APIs."""

from __future__ import annotations

from dataclasses import dataclass

from powercontext.builtin.artifacts.memory import MemoryEntryInput
from powercontext.sources.projections import TEXT_EVIDENCE_PROJECTION_KEY


class PagePipeline:
    async def extract(self, request, /):
        return tuple(
            MemoryEntryInput(
                kind="source-evidence",
                text=source.projection(TEXT_EVIDENCE_PROJECTION_KEY)["content"],
                sources=(source,),
            )
            for source in request.sources
        )


@dataclass(frozen=True)
class Report:
    identifier: str
    pages: tuple[str, ...]


@dataclass(frozen=True)
class Question:
    text: str
    evidence: tuple[tuple[str, int], ...]


def reports(split: str) -> tuple[tuple[Report, ...], tuple[Question, ...]]:
    if split == "development":
        companies = [("Orion Packaging", "ORION_PACKAGING_2024_10K"), ("Cedar Logistics", "CEDAR_LOGISTICS_2023_10K")]
        locations = (13, 37, 52, 28, 58, 6)
        statements = (
            "Consolidated Statements of Income\nNet sales 9000 8200\nOperating income 1200 1050\nNet income 800 720\nRestructuring expense 0 0",
            "Consolidated Statements of Cash Flows\nNet income 800 720\nDepreciation and amortization 300 260\nCash provided by operating activities 1800 1600\nCapital expenditures 600 550",
            "Consolidated Balance Sheets\nCurrent assets 4100 3900\nTotal assets 12000 11000\nCurrent liabilities 2100 1900\nShareholders equity 7000 6500",
            "Legal Proceedings\nThe company is defending an ongoing material lawsuit over freight charges. The commitment is estimated at 250.",
            "Restructuring Programs\nPlant closures require severance costs of 95 and asset impairment of 20. These charges are discussed separately from the income statement.",
            "Business Overview\nThe geographic segments primarily operate in Canada and Norway. The international division serves those countries.",
        )
        prompts = (
            ("What unadjusted operating income is reported by {company}?", (0,)),
            (
                "Calculate unadjusted EBITDA less capex for {company}, using the income statement and statement of cash flows.",
                (0, 1),
            ),
            ("What is {company} current ratio using current assets and current liabilities?", (2,)),
            ("Has {company} disclosed ongoing materially important legal battles?", (3,)),
            ("What restructuring costs did {company} report separately from its income statement?", (0, 4)),
            ("In which geographies does {company} primarily operate?", (5,)),
        )
    else:
        companies = [("Harbor Mobility", "HMOB_ANNUAL2022"), ("Juniper Devices", "JDEV_ANNUAL2022")]
        locations = (55, 18, 43, 7, 31, 62)
        statements = (
            "Consolidated Statements of Operations\nRevenues 7600 7000\nCost of goods sold 4800 4400\nOperating profit 1400 1250\nNet earnings 910 840",
            "Statements of Cash Flows\nNet earnings 910 840\nDepreciation and amortization 270 260\nNet cash from operating activities 1500 1380\nPurchases of property plant and equipment 420 390",
            "Statements of Financial Position\nTotal assets 13000 12500\nCurrent assets 4200 4000\nCurrent liabilities 2200 2100\nStockholders equity 7200 6900",
            "Commitments and Contingencies\nLitigation concerning the supply contract remains pending. The unresolved claims could have a material adverse effect.",
            "Capital Investment\nCapital spending purchased property plant and equipment costing 420. This figure excludes business acquisitions.",
            "Geographical Information\nBusiness segments span Japan and Chile. Both countries are principal international markets.",
        )
        prompts = (
            ("What is the operating profit margin of {company}? Use revenue and the operating result.", (0,)),
            ("For {company}, determine EBITDA as operating profit plus depreciation and amortization.", (0, 1)),
            ("How much free cash flow does {company} generate after buying property plant and equipment?", (1, 4)),
            ("Compute the return on assets for {company} using net earnings and total assets.", (0, 2)),
            ("What material unresolved litigation faces {company}?", (3,)),
            ("Name the principal countries served by {company} business segments.", (5,)),
        )
    result = []
    questions = []
    for company, identifier in companies:
        pages = [
            f"{company} Annual Review\nSupplemental operating disclosures section {page}.\n"
            f"Historical revenue and income appear in discussion. Contract {page + 1000}. "
            "Product statistics, regulatory background and compensation policy are provided here."
            for page in range(1, 65)
        ]
        for location, statement in zip(locations, statements, strict=True):
            pages[location - 1] = company + "\n" + statement
        result.append(Report(identifier, tuple(pages)))
        questions.extend(
            Question(prompt.format(company=company), tuple((identifier, locations[index]) for index in expected))
            for prompt, expected in prompts
        )
    return tuple(result), tuple(questions)
