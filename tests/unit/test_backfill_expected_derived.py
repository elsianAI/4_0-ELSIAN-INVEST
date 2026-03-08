from __future__ import annotations

import json
from pathlib import Path

from scripts.backfill_expected_derived import backfill_cases


def _write_expected(path: Path, periods: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"periods": periods}, indent=2) + "\n", encoding="utf-8")


def test_backfill_adds_eligible_fields_and_is_idempotent(tmp_path: Path) -> None:
    expected_path = tmp_path / "cases" / "TEST" / "expected.json"
    _write_expected(
        expected_path,
        {
            "FY2024": {
                "fields": {
                    "ebit": {"value": 100},
                    "depreciation_amortization": {"value": 20},
                    "cfo": {"value": 90},
                    "capex": {"value": -30},
                }
            }
        },
    )

    first = backfill_cases(tmp_path / "cases", apply=True)
    assert first["fields"]["ebitda"]["added"] == 1
    assert first["fields"]["fcf"]["added"] == 1
    assert first["modified_files"] == ["cases/TEST/expected.json"]

    data = json.loads(expected_path.read_text())
    fy2024 = data["periods"]["FY2024"]["fields"]
    assert fy2024["ebitda"] == {"value": 120.0, "source_filing": "DERIVED"}
    assert fy2024["fcf"] == {"value": 60.0, "source_filing": "DERIVED"}

    second = backfill_cases(tmp_path / "cases", apply=True)
    assert second["fields"]["ebitda"]["added"] == 0
    assert second["fields"]["fcf"]["added"] == 0
    assert second["modified_files"] == []


def test_backfill_skips_existing_values(tmp_path: Path) -> None:
    expected_path = tmp_path / "cases" / "TEST" / "expected.json"
    _write_expected(
        expected_path,
        {
            "FY2024": {
                "fields": {
                    "ebit": {"value": 100},
                    "depreciation_amortization": {"value": 20},
                    "ebitda": {"value": 999, "source_filing": "SRC.md"},
                }
            }
        },
    )

    result = backfill_cases(tmp_path / "cases", apply=True)
    assert result["fields"]["ebitda"]["existing_preserved_before"] == 1
    assert result["fields"]["ebitda"]["added"] == 0

    data = json.loads(expected_path.read_text())
    assert data["periods"]["FY2024"]["fields"]["ebitda"]["value"] == 999


def test_backfill_skips_canonical_inconsistent_periods(tmp_path: Path) -> None:
    expected_path = tmp_path / "cases" / "ACLS" / "expected.json"
    _write_expected(
        expected_path,
        {
            "Q1-2024": {
                "fields": {
                    "ebit": {"value": 100},
                    "depreciation_amortization": {"value": 20},
                }
            }
        },
    )

    result = backfill_cases(tmp_path / "cases", apply=True)
    assert result["fields"]["ebitda"]["skipped_inconsistent_before"] == 1
    assert result["fields"]["ebitda"]["added"] == 0

    data = json.loads(expected_path.read_text())
    assert "ebitda" not in data["periods"]["Q1-2024"]["fields"]


def test_backfill_dry_run_reports_without_writing(tmp_path: Path) -> None:
    expected_path = tmp_path / "cases" / "TEST" / "expected.json"
    _write_expected(
        expected_path,
        {
            "FY2024": {
                "fields": {
                    "cfo": {"value": 90},
                    "capex": {"value": -30},
                }
            }
        },
    )

    result = backfill_cases(tmp_path / "cases", apply=False)
    assert result["fields"]["fcf"]["eligible_missing_before"] == 1
    assert result["fields"]["fcf"]["added"] == 0
    assert result["modified_files"] == []

    data = json.loads(expected_path.read_text())
    assert "fcf" not in data["periods"]["FY2024"]["fields"]
