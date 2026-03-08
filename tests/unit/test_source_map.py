"""Unit tests for SourceMapBuilder (BL-053 hardening)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
                "Income statement",
                "2024 2023",
                "Revenue                                       51,991 49,100",
                "Gross profit                                  15,000 14,200",
                "",
                "Consolidated Balance Sheets",
                "Cash and cash equivalents                     1,200 1,050",
                "Total debt (current + long-term)              800 750",
                "Total stockholdersʼ equity                    1,891 1,700",
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
                    "ingresos_txt": {
                        "value": 51991.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:table:income_statement:tbl0:row1:col0",
                        "row_label": "Revenue",
                        "raw_text": "51,991",
                        "extraction_method": "table",
                    },
                    "equity_ixbrl": {
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
                    "total_debt": {
                        "value": 800.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:vertical_bs:consolidated:total_debt",
                        "extraction_method": "table",
                    },
                    "total_equity": {
                        "value": 1891.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:vertical_bs:consolidated:total_equity",
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
    assert source_map["summary"]["total_fields"] == 6
    assert source_map["summary"]["resolved_fields"] == 6


def test_table_pointer_resolves_clean_md_line(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["ingresos"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["original_path"] == "filings/sample.htm"
    assert field_entry["clean_path"] == "filings/sample.clean.md"
    assert field_entry["pointer"]["kind"] == "clean_md_table"
    assert field_entry["pointer"]["path"] == "filings/sample.clean.md"
    assert field_entry["pointer"]["line_start"] == 5
    assert field_entry["click_target"] == "filings/sample.clean.md#L5"


def test_text_table_pointer_resolves_txt_table_line(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["ingresos_txt"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["original_path"] == "filings/sample.htm"
    assert field_entry["pointer"]["kind"] == "text_table"
    assert field_entry["pointer"]["path"] == "filings/sample.txt"
    assert field_entry["pointer"]["line_start"] == 3
    assert field_entry["click_target"] == "filings/sample.txt#L3"


def test_ixbrl_pointer_resolves_html_anchor(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["equity_ixbrl"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["original_path"] == "filings/sample.htm"
    assert field_entry["clean_path"] == "filings/sample.clean.md"
    assert field_entry["pointer"]["kind"] == "html_ixbrl"
    assert field_entry["pointer"]["path"] == "filings/sample.htm"
    assert field_entry["pointer"]["element_id"] == "fact-1"
    assert field_entry["click_target"] == "filings/sample.htm#fact-1"


def test_ixbrl_pointer_resolves_bridge_suffix_to_base_fact(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    extraction_result_path = case_dir / "extraction_result.json"
    extraction_result = json.loads(extraction_result_path.read_text(encoding="utf-8"))
    extraction_result["periods"]["FY2024"]["fields"]["total_equity_bridge"] = {
        "value": 1991.0,
        "scale": "thousands",
        "confidence": "high",
        "source_filing": "sample.htm",
        "source_location": "sample.htm:ixbrl:ctx-fy2024:us-gaap:StockholdersEquity:bs_identity_bridge",
        "row_label": "us-gaap:StockholdersEquity (+ Non-controlling interest)",
        "col_label": "FY2024",
        "raw_text": "1,891 + (100)",
        "extraction_method": "ixbrl",
    }
    extraction_result_path.write_text(
        json.dumps(extraction_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["total_equity_bridge"]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["pointer"]["kind"] == "html_ixbrl"
    assert field_entry["pointer"]["element_id"] == "fact-1"
    assert field_entry["click_target"] == "filings/sample.htm#fact-1"


@pytest.mark.parametrize(
    ("field_name", "expected_line"),
    [
        ("cash_and_equivalents", 7),
        ("total_debt", 8),
        ("total_equity", 9),
    ],
)
def test_vertical_bs_pointer_resolves_expected_line(
    tmp_path: Path,
    field_name: str,
    expected_line: int,
) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"][field_name]

    assert field_entry["resolution_status"] == "resolved"
    assert field_entry["pointer"]["kind"] == "text_label"
    assert field_entry["pointer"]["path"] == "filings/sample.txt"
    assert field_entry["pointer"]["line_start"] == expected_line
    assert field_entry["click_target"] == f"filings/sample.txt#L{expected_line}"


def test_source_map_builder_accepts_relative_case_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_dir = tmp_path / "cases" / "TEST"
    case_dir.mkdir(parents=True)
    _write_case(case_dir)
    monkeypatch.chdir(tmp_path)

    source_map = SourceMapBuilder().build(Path("cases/TEST"))

    assert source_map["summary"]["resolved_fields"] == 6
    assert (case_dir / "source_map.json").exists()


def test_source_map_builder_rejects_paths_outside_case_dir(tmp_path: Path) -> None:
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    _write_case(case_dir)

    outside = tmp_path / "outside.txt"
    outside.write_text("sneaky\n", encoding="utf-8")

    extraction_result = json.loads(
        (case_dir / "extraction_result.json").read_text(encoding="utf-8")
    )
    extraction_result["periods"]["FY2024"]["fields"]["sneaky"] = {
        "value": 1.0,
        "scale": "raw",
        "confidence": "high",
        "source_filing": "../outside.txt",
        "source_location": "../outside.txt:char0",
        "raw_text": "sneaky",
        "extraction_method": "narrative",
    }
    (case_dir / "extraction_result.json").write_text(
        json.dumps(extraction_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    source_map = SourceMapBuilder().build(case_dir)
    field_entry = source_map["periods"]["FY2024"]["fields"]["sneaky"]

    assert field_entry["resolution_status"] == "unresolved"
    assert field_entry["original_path"] is None
    assert field_entry["clean_path"] is None
