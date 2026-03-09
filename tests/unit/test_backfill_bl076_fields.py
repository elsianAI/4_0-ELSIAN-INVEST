"""Tests dirigidos para BL-076: scripts/backfill_bl076_fields.py

Cubre:
    - No-overwrite: campos existentes en expected no se sobreescriben.
    - Idempotencia: segunda ejecucion no produce cambios.
    - Exclusion de campos fuera de scope.
    - total_debt como campo permitido (misma logica que el resto).
    - inventories solo se añade si filing-backed (ixbrl o pipeline con source_filing).
    - Campos derived no se backfillean.
    - Periodos en expected sin periodo equivalente en draft se registran como gap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.backfill_bl076_fields import (
    TARGET_FIELDS,
    _extract_source_filing,
    backfill_all,
    backfill_ticker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_expected(path: Path, periods: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": "1.0", "periods": periods}, indent=2) + "\n", encoding="utf-8")


def _write_draft(path: Path, periods: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": "1.0", "periods": periods}, indent=2) + "\n", encoding="utf-8")


def _ixbrl_field(value: float, filing: str) -> dict:
    return {
        "value": value,
        "_source": "ixbrl",
        "_concept": "us-gaap:SomeConcept",
        "_filing": filing,
        "_displayed": str(value),
        "_scale": 3,
    }


def _pipeline_field(value: float, filing: str) -> dict:
    return {
        "value": value,
        "source_filing": filing,
        "confidence": "high",
        "_source": "pipeline",
        "extraction_method": "table",
    }


def _derived_field(value: float) -> dict:
    return {
        "value": value,
        "_source": "derived",
    }


# ---------------------------------------------------------------------------
# TARGET_FIELDS contract
# ---------------------------------------------------------------------------

def test_target_fields_contains_exactly_seven() -> None:
    assert TARGET_FIELDS == frozenset({
        "cfi", "cff", "delta_cash",
        "accounts_receivable", "accounts_payable",
        "inventories", "total_debt",
    })


# ---------------------------------------------------------------------------
# _extract_source_filing
# ---------------------------------------------------------------------------

def test_extract_source_filing_ixbrl_returns_filing() -> None:
    fd = _ixbrl_field(100.0, "SRC_001_10-K.clean.md")
    assert _extract_source_filing(fd) == "SRC_001_10-K.clean.md"


def test_extract_source_filing_pipeline_returns_source_filing() -> None:
    fd = _pipeline_field(200.0, "SRC_002_10-Q.txt")
    assert _extract_source_filing(fd) == "SRC_002_10-Q.txt"


def test_extract_source_filing_derived_returns_none() -> None:
    fd = _derived_field(300.0)
    assert _extract_source_filing(fd) is None


def test_extract_source_filing_unknown_source_returns_none() -> None:
    fd = {"value": 50.0, "_source": "manual"}
    assert _extract_source_filing(fd) is None


# ---------------------------------------------------------------------------
# No-overwrite: campos existentes no se modifican
# ---------------------------------------------------------------------------

def test_no_overwrite_existing_field(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": {"value": 999.0, "source_filing": "ORIGINAL.md"},
                    "ingresos": {"value": 1000.0, "source_filing": "SRC.md"},
                }
            }
        },
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": _ixbrl_field(777.0, "DRAFT.md"),  # valor diferente
                }
            }
        },
    )

    backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    assert data["periods"]["FY2024"]["fields"]["cfi"]["value"] == 999.0
    assert data["periods"]["FY2024"]["fields"]["cfi"]["source_filing"] == "ORIGINAL.md"


def test_no_overwrite_skipped_exists_counter(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": {"value": 100.0, "source_filing": "SRC.md"},
                    "cff": {"value": 200.0, "source_filing": "SRC.md"},
                }
            }
        },
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": _ixbrl_field(111.0, "DRAFT.md"),
                    "cff": _ixbrl_field(222.0, "DRAFT.md"),
                    "delta_cash": _ixbrl_field(50.0, "DRAFT.md"),
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    assert r["fields_skipped_exists"] == 2
    assert r["fields_added"] == 1


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

def test_idempotent_second_run_no_changes(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {
            "FY2024": {
                "fields": {
                    "ingresos": {"value": 1000.0, "source_filing": "SRC.md"},
                }
            }
        },
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": _ixbrl_field(-500.0, "SRC_001.md"),
                    "cff": _ixbrl_field(-200.0, "SRC_001.md"),
                }
            }
        },
    )

    r1 = backfill_ticker("TICK", cases_dir, apply=True)
    assert r1["fields_added"] == 2

    content_after_first = (cases_dir / "TICK" / "expected.json").read_text()

    r2 = backfill_ticker("TICK", cases_dir, apply=True)
    assert r2["fields_added"] == 0
    assert r2["fields_skipped_exists"] == 2

    content_after_second = (cases_dir / "TICK" / "expected.json").read_text()
    assert content_after_first == content_after_second


def test_idempotent_backfill_all(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    for ticker in ["T1", "T2"]:
        _write_expected(
            cases_dir / ticker / "expected.json",
            {"FY2023": {"fields": {"ingresos": {"value": 100.0, "source_filing": "S.md"}}}},
        )
        _write_draft(
            cases_dir / ticker / "expected_draft.json",
            {"FY2023": {"fields": {"accounts_receivable": _ixbrl_field(50.0, "S.md")}}},
        )

    r1 = backfill_all(cases_dir, apply=True)
    assert r1["total_fields_added"] == 2

    r2 = backfill_all(cases_dir, apply=True)
    assert r2["total_fields_added"] == 0
    assert r2["modified_files"] == []


# ---------------------------------------------------------------------------
# Exclusion de campos fuera de scope
# ---------------------------------------------------------------------------

def test_out_of_scope_fields_not_added(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 1000.0, "source_filing": "SRC.md"}}}},
    )
    # Draft tiene ebitda y fcf (derivados) y campos conocidos fuera del TARGET_FIELDS
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "ebitda": _ixbrl_field(200.0, "SRC.md"),
                    "fcf": _ixbrl_field(150.0, "SRC.md"),
                    "gross_profit": _ixbrl_field(400.0, "SRC.md"),
                    "cfi": _ixbrl_field(-50.0, "SRC.md"),  # dentro de scope
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    fy2024_fields = data["periods"]["FY2024"]["fields"]

    # Solo cfi debe añadirse
    assert "cfi" in fy2024_fields
    assert "ebitda" not in fy2024_fields
    assert "fcf" not in fy2024_fields
    assert "gross_profit" not in fy2024_fields
    assert r["fields_added"] == 1


# ---------------------------------------------------------------------------
# total_debt como campo permitido
# ---------------------------------------------------------------------------

def test_total_debt_added_when_filing_backed_ixbrl(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 500.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "total_debt": _ixbrl_field(1000.0, "SRC_001_10-K.htm"),
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    td = data["periods"]["FY2024"]["fields"].get("total_debt")
    assert td is not None
    assert td["value"] == 1000.0
    assert td["source_filing"] == "SRC_001_10-K.htm"
    assert r["fields_added"] == 1


def test_total_debt_added_when_filing_backed_pipeline(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2023": {"fields": {"ingresos": {"value": 500.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2023": {
                "fields": {
                    "total_debt": _pipeline_field(800.0, "SRC_002_annual.txt"),
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    td = data["periods"]["FY2023"]["fields"].get("total_debt")
    assert td is not None
    assert td["value"] == 800.0
    assert td["source_filing"] == "SRC_002_annual.txt"
    assert r["fields_added"] == 1


def test_total_debt_not_added_when_derived(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2023": {"fields": {"ingresos": {"value": 500.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2023": {
                "fields": {
                    "total_debt": _derived_field(900.0),  # derivado, no filing-backed
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    assert "total_debt" not in data["periods"]["FY2023"]["fields"]
    assert r["fields_added"] == 0
    assert r["fields_skipped_not_filing_backed"] == 1


# ---------------------------------------------------------------------------
# inventories: solo filing-backed
# ---------------------------------------------------------------------------

def test_inventories_added_when_ixbrl(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 200.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "inventories": _ixbrl_field(75.0, "SRC_001.htm"),
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    assert data["periods"]["FY2024"]["fields"]["inventories"]["value"] == 75.0
    assert r["fields_added"] == 1


def test_inventories_not_added_when_derived(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 200.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "inventories": _derived_field(0.0),  # no se fabrica
                }
            }
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    data = json.loads((cases_dir / "TICK" / "expected.json").read_text())
    assert "inventories" not in data["periods"]["FY2024"]["fields"]
    assert r["fields_added"] == 0


# ---------------------------------------------------------------------------
# Gaps: periodos sin correspondencia en draft
# ---------------------------------------------------------------------------

def test_gap_registered_when_period_missing_in_draft(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {
            "FY2024": {"fields": {"ingresos": {"value": 100.0, "source_filing": "SRC.md"}}},
            "Q1-2024": {"fields": {"ingresos": {"value": 25.0, "source_filing": "SRC.md"}}},
        },
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": _ixbrl_field(-100.0, "SRC.md"),
                }
            }
            # Q1-2024 no presente en draft
        },
    )

    r = backfill_ticker("TICK", cases_dir, apply=True)

    assert r["fields_added"] == 1
    gap_periods = {g["period"] for g in r["gaps"]}
    assert "Q1-2024" in gap_periods


# ---------------------------------------------------------------------------
# Dry-run no escribe
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "TICK" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 100.0, "source_filing": "SRC.md"}}}},
    )
    _write_draft(
        cases_dir / "TICK" / "expected_draft.json",
        {
            "FY2024": {
                "fields": {
                    "cfi": _ixbrl_field(-50.0, "SRC.md"),
                }
            }
        },
    )

    content_before = (cases_dir / "TICK" / "expected.json").read_text()
    r = backfill_ticker("TICK", cases_dir, apply=False)
    content_after = (cases_dir / "TICK" / "expected.json").read_text()

    assert r["fields_added"] == 1  # cuenta como elegible incluso en dry-run
    assert content_before == content_after  # fichero no modificado


# ---------------------------------------------------------------------------
# backfill_all: multiple tickers
# ---------------------------------------------------------------------------

def test_backfill_all_aggregates_results(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    for ticker, field in [("T1", "cfi"), ("T2", "cff"), ("T3", "delta_cash")]:
        _write_expected(
            cases_dir / ticker / "expected.json",
            {"FY2023": {"fields": {"ingresos": {"value": 100.0, "source_filing": "S.md"}}}},
        )
        _write_draft(
            cases_dir / ticker / "expected_draft.json",
            {"FY2023": {"fields": {field: _ixbrl_field(10.0, "S.md")}}},
        )

    result = backfill_all(cases_dir, apply=True)

    assert result["total_fields_added"] == 3
    assert len(result["modified_files"]) == 3


def test_backfill_all_ticker_filter(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    for ticker in ["T1", "T2", "T3"]:
        _write_expected(
            cases_dir / ticker / "expected.json",
            {"FY2023": {"fields": {"ingresos": {"value": 100.0, "source_filing": "S.md"}}}},
        )
        _write_draft(
            cases_dir / ticker / "expected_draft.json",
            {"FY2023": {"fields": {"cfi": _ixbrl_field(10.0, "S.md")}}},
        )

    result = backfill_all(cases_dir, tickers=["T1", "T3"], apply=True)

    assert result["total_fields_added"] == 2
    assert "cases/T2/expected.json" not in result["modified_files"]


def test_backfill_all_missing_draft_reported_as_error(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    _write_expected(
        cases_dir / "NODRAFT" / "expected.json",
        {"FY2024": {"fields": {"ingresos": {"value": 100.0, "source_filing": "S.md"}}}},
    )
    # Sin expected_draft.json

    result = backfill_all(cases_dir, apply=True)

    ticker_result = next(r for r in result["results"] if r["ticker"] == "NODRAFT")
    assert "error" in ticker_result
    assert ticker_result["fields_added"] == 0
