"""Scope consistency: case.json period_scope must always be FULL (DEC-031).

ANNUAL_ONLY has been eliminated. All tickers must have period_scope=FULL.
"""

import json
from pathlib import Path

import pytest

from tests.integration.test_regression import VALIDATED_TICKERS

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _has_non_annual_periods(expected: dict) -> bool:
    """Return True if expected.json contains any non-FY period."""
    periods = expected.get("periods", {})
    return any(not k.startswith("FY") for k in periods)


@pytest.mark.parametrize("ticker", VALIDATED_TICKERS)
def test_period_scope_matches_expected(ticker: str) -> None:
    """period_scope in case.json must be coherent with periods in expected.json."""
    case_dir = CASES_DIR / ticker
    case_path = case_dir / "case.json"
    expected_path = case_dir / "expected.json"

    if not case_path.exists() or not expected_path.exists():
        pytest.skip(f"Missing case.json or expected.json for {ticker}")

    case_data = _load_json(case_path)
    expected_data = _load_json(expected_path)

    scope = case_data.get("period_scope", "FULL")

    # DEC-031: ANNUAL_ONLY eliminated — period_scope must always be FULL
    assert scope == "FULL", (
        f"{ticker}: case.json period_scope is '{scope}' but must be 'FULL' "
        f"(DEC-031: ANNUAL_ONLY eliminated)"
    )
