"""Integration tests for the real ``elsian source-map`` CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = REPO_ROOT / "cases"


def _run_source_map(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "elsian.cli", "source-map", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _has_extraction_result(ticker: str) -> bool:
    return (CASES_DIR / ticker / "extraction_result.json").exists()


@pytest.fixture
def temp_case_dir() -> Generator[Path, None, None]:
    case_dir = CASES_DIR / "__SOURCE_MAP_TMP__"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    (case_dir / "filings").mkdir(parents=True)
    yield case_dir
    if case_dir.exists():
        shutil.rmtree(case_dir)


@pytest.mark.skipif(
    not _has_extraction_result("TZOO"),
    reason="TZOO extraction_result.json not found",
)
def test_cli_source_map_tzoo_builds_full_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "tzoo_source_map.json"

    result = _run_source_map("TZOO", "--output", str(output_path))

    assert result.returncode == 0, result.stderr
    assert "SourceMap_v1 FULL" in result.stdout
    assert output_path.exists()
    source_map = json.loads(output_path.read_text(encoding="utf-8"))
    assert source_map["schema_version"] == "SourceMap_v1"
    assert source_map["summary"]["resolved_fields"] == source_map["summary"]["total_fields"]


def test_cli_source_map_missing_extraction_result_has_clear_error(temp_case_dir: Path) -> None:
    result = _run_source_map(temp_case_dir.name)

    assert result.returncode != 0
    assert "extraction_result.json" in result.stderr
    assert "extract" in result.stderr or "run" in result.stderr
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


def test_cli_source_map_partial_uses_default_output_path(temp_case_dir: Path) -> None:
    (temp_case_dir / "filings" / "sample.txt").write_text(
        "Revenue 100 90\n",
        encoding="utf-8",
    )
    extraction_result = {
        "schema_version": "2.0",
        "ticker": temp_case_dir.name,
        "currency": "USD",
        "periods": {
            "FY2024": {
                "fecha_fin": "2024-12-31",
                "tipo_periodo": "annual",
                "fields": {
                    "ingresos": {
                        "value": 100.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:table:income_statement:tbl0:row1:col0",
                        "row_label": "Revenue",
                        "raw_text": "100",
                        "extraction_method": "table",
                    },
                    "net_income": {
                        "value": 12.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:char999",
                        "row_label": "Net income",
                        "raw_text": "12",
                        "extraction_method": "narrative",
                    },
                },
            }
        },
    }
    (temp_case_dir / "extraction_result.json").write_text(
        json.dumps(extraction_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = _run_source_map(temp_case_dir.name)

    assert result.returncode == 0, result.stderr
    assert "SourceMap_v1 PARTIAL" in result.stdout
    assert (temp_case_dir / "source_map.json").exists()


def test_cli_source_map_empty_returns_non_zero_and_writes_artifact(
    temp_case_dir: Path,
    tmp_path: Path,
) -> None:
    (temp_case_dir / "filings" / "sample.txt").write_text(
        "Revenue 100 90\n",
        encoding="utf-8",
    )
    extraction_result = {
        "schema_version": "2.0",
        "ticker": temp_case_dir.name,
        "currency": "USD",
        "periods": {
            "FY2024": {
                "fecha_fin": "2024-12-31",
                "tipo_periodo": "annual",
                "fields": {
                    "net_income": {
                        "value": 12.0,
                        "scale": "units",
                        "confidence": "high",
                        "source_filing": "sample.txt",
                        "source_location": "sample.txt:char999",
                        "row_label": "Net income",
                        "raw_text": "12",
                        "extraction_method": "narrative",
                    },
                },
            }
        },
    }
    (temp_case_dir / "extraction_result.json").write_text(
        json.dumps(extraction_result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "empty_source_map.json"

    result = _run_source_map(temp_case_dir.name, "--output", str(output_path))

    assert result.returncode != 0
    assert "SourceMap_v1 EMPTY" in result.stderr
    assert output_path.exists()
    source_map = json.loads(output_path.read_text(encoding="utf-8"))
    assert source_map["summary"]["resolved_fields"] == 0
