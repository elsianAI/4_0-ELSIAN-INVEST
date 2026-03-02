"""Scope consistency: case.json period_scope must match expected.json periods.

If expected.json contains Q* or H* periods, case.json MUST have period_scope=FULL.
If expected.json only has FY* periods, period_scope must be ANNUAL_ONLY or absent.
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

    scope = case_data.get("period_scope", "ANNUAL_ONLY")
    has_non_fy = _has_non_annual_periods(expected_data)

    if has_non_fy:
        assert scope == "FULL", (
            f"{ticker}: expected.json has non-FY periods but "
            f"case.json period_scope is '{scope}' (should be 'FULL')"
        )
    else:
        assert scope in ("ANNUAL_ONLY", None), (
            f"{ticker}: expected.json only has FY periods but "
            f"case.json period_scope is '{scope}' (should be 'ANNUAL_ONLY' or absent)"
        )
