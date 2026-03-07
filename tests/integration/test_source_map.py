"""Integration tests for ``elsian source-map`` (BL-053)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from elsian.cli import CASES_DIR, cmd_source_map


def _has_extraction_result(ticker: str) -> bool:
    return (CASES_DIR / ticker / "extraction_result.json").exists()


@pytest.mark.skipif(
    not _has_extraction_result("TZOO"),
    reason="TZOO extraction_result.json not found",
)
def test_cmd_source_map_tzoo_builds_resolved_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "tzoo_source_map.json"

    cmd_source_map(
        argparse.Namespace(
            ticker="TZOO",
            output=str(output_path),
        )
    )

    assert output_path.exists()
    source_map = json.loads(output_path.read_text(encoding="utf-8"))

    assert source_map["schema_version"] == "SourceMap_v1"
    assert source_map["ticker"] == "TZOO"
    assert source_map["summary"]["total_fields"] > 0
    assert source_map["summary"]["resolved_fields"] == source_map["summary"]["total_fields"]
    assert "html_ixbrl" in source_map["summary"]["by_pointer_kind"]
    assert "clean_md_table" in source_map["summary"]["by_pointer_kind"]

    ixbrl_entry = source_map["periods"]["FY2020"]["fields"]["total_equity"]
    assert ixbrl_entry["original_path"] == "filings/SRC_005_10-K_FY2020.htm"
    assert ixbrl_entry["clean_path"] == "filings/SRC_005_10-K_FY2020.clean.md"
    assert ixbrl_entry["pointer"]["kind"] == "html_ixbrl"
    assert ixbrl_entry["click_target"].startswith("filings/SRC_005_10-K_FY2020.htm#")

    table_entry = source_map["periods"]["9M-2022"]["fields"]["ingresos"]
    assert table_entry["original_path"] == "filings/SRC_013_10-Q_Q3-2023.htm"
    assert table_entry["clean_path"] == "filings/SRC_013_10-Q_Q3-2023.clean.md"
    assert table_entry["pointer"]["kind"] == "clean_md_table"
    assert table_entry["click_target"].startswith(
        "filings/SRC_013_10-Q_Q3-2023.clean.md#L"
    )
    assert "Revenues" in table_entry["pointer"]["snippet"]
