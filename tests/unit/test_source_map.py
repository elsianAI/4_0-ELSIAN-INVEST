"""Unit tests for SourceMapBuilder (BL-053)."""

from __future__ import annotations

import json
from pathlib import Path

from elsian.assemble.source_map import SourceMapBuilder


def _write_case(case_dir: Path) -> None:
    filings_dir = case_dir / "filings"
    filings_dir.mkdir(parents=True, exist_ok=True)

    (filings_dir / "sample.clean.md").write_text(
        "\n".join(
            [
                "## Income statement",
                "",
                "|  | 2024 |",
                "| --- | --- |",
                "| Revenues | 51,991 |",
                "| Net income | 5,100 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (filings_dir / "sample.htm").write_text(
        (
            "<html>\n"
            "<body>\n"
            '<ix:nonFraction contextRef="ctx-fy2024" '
            'name="us-gaap:StockholdersEquity" id="fact-1">1,891</ix:nonFraction>\n'
            "</body>\n"
            "</html>\n"
        ),
        encoding="utf-8",
    )

    (filings_dir / "sample.txt").write_text(
        "\n".join(
            [
                "Consolidated Balance Sheets",
                "Cash and cash equivalents",
                "Total assets",
                "Total liabilities",
                "Total stockholders' equity",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    extraction_result = {
        "schema_version": "2.0",
        "ticker": "TEST",
        "currency": "USD",
        "periods": {
            "FY2024": {
                "fecha_fin": "2024-12-31",
                "tipo_periodo": "annual",
                "fields": {
                    "ingresos": {
                        "value": 51991.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.clean.md",
                        "source_location": "sample.clean.md:table:income_statement:tbl0:row1:col1",
                        "row_label": "Revenues",
                        "raw_text": "51,991",
                        "extraction_method": "table",
                    },
                    "total_equity": {
                        "value": 1891.0,
                        "scale": "thousands",
                        "confidence": "high",
                        "source_filing": "sample.htm",
                        "source_location": "sample.htm:ixbrl:ctx-fy2024:us-gaap:StockholdersEquity",
                        "row_label": "us-gaap:StockholdersEquity",
                        "col_label": "FY2024",
                        "raw_text": "1,891",
                        "extraction_method": "ixbrl",
                    },
                    "cash_and_equivalents": {
                        "value": 1200.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:vertical_bs:consolidated:cash_and_equivalents",
                        "extraction_method": "table",
                    },
                },
            }
        },
    }
    (case_dir / "extraction_result.json").write_text(
        json.dumps(extraction_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def test_source_map_builder_writes_output(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    builder = SourceMapBuilder()
    source_map = builder.build(case_dir)

    output_path = case_dir / "source_map.json"
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == source_map
    assert source_map["schema_version"] == "SourceMap_v1"
    assert source_map["summary"]["total_fields"] == 3
    assert source_map["summary"]["resolved_fields"] == 3


def test_table_pointer_resolves_clean_md_line(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["ingresos"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["original_path"] == "filings/sample.htm"
    assert field_entry["clean_path"] == "filings/sample.clean.md"
    assert field_entry["raw_text"] == "51,991"
    assert field_entry["pointer"]["kind"] == "clean_md_table"
    assert field_entry["pointer"]["path"] == "filings/sample.clean.md"
    assert field_entry["pointer"]["line_start"] == 5
    assert "Revenues" in field_entry["pointer"]["snippet"]
    assert field_entry["click_target"] == "filings/sample.clean.md#L5"


def test_ixbrl_pointer_resolves_html_anchor(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["total_equity"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["original_path"] == "filings/sample.htm"
    assert field_entry["clean_path"] == "filings/sample.clean.md"
    assert field_entry["raw_text"] == "1,891"
    assert field_entry["pointer"]["kind"] == "html_ixbrl"
    assert field_entry["pointer"]["path"] == "filings/sample.htm"
    assert field_entry["pointer"]["element_id"] == "fact-1"
    assert field_entry["click_target"] == "filings/sample.htm#fact-1"
    assert "StockholdersEquity" in field_entry["pointer"]["snippet"]


def test_vertical_bs_pointer_resolves_text_line(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["cash_and_equivalents"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["pointer"]["kind"] == "text_label"
    assert field_entry["pointer"]["path"] == "filings/sample.txt"
    assert field_entry["pointer"]["line_start"] == 2
    assert field_entry["click_target"] == "filings/sample.txt#L2"
