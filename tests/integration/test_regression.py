"""Regression tests: every ticker with curated expected.json must score 100%.

Parametrized: runs extract + eval on each ticker with filings.
Skips tickers whose expected.json or filings are missing.
"""

import os
from pathlib import Path

import pytest

from elsian.extract.phase import ExtractPhase
from elsian.evaluate.evaluator import evaluate

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"

# Tickers expected to score 100% (curated and validated in 3.0)
VALIDATED_TICKERS = ["TZOO", "GCT", "IOSP", "NEXN", "SONO", "TEP", "TALO", "NVDA", "KAR", "PR", "ACLS", "INMD", "CROX", "SOM", "0327"]

# Tickers with known issues pending recertification
PENDING_RECERT_TICKERS: list[str] = []

# Tickers still being curated (expected to fail, not blocking)
WIP_TICKERS: list[str] = []


def _has_case(ticker: str) -> bool:
    """Check if a ticker has case.json, expected.json, and filings."""
    d = CASES_DIR / ticker
    return (
        d.exists()
        and (d / "case.json").exists()
        and (d / "expected.json").exists()
        and (d / "filings").is_dir()
        and any((d / "filings").iterdir())
    )


@pytest.mark.parametrize("ticker", VALIDATED_TICKERS)
def test_regression_100_percent(ticker: str) -> None:
    """Validated tickers must score exactly 100%."""
    if not _has_case(ticker):
        pytest.skip(f"No case data for {ticker}")

    phase = ExtractPhase()
    result = phase.extract(str(CASES_DIR / ticker))
    report = evaluate(result, str(CASES_DIR / ticker / "expected.json"))

    assert report.score == 100.0, (
        f"{ticker}: score={report.score}% "
        f"(matched={report.matched}, wrong={report.wrong}, missed={report.missed})"
    )


@pytest.mark.parametrize("ticker", PENDING_RECERT_TICKERS)
@pytest.mark.skip(reason="KAR recertification pending — BL-001 + BL-008")
def test_regression_pending_recert(ticker: str) -> None:
    """Pending recert tickers remain visible but do not block CI."""
    if not _has_case(ticker):
        pytest.skip(f"No case data for {ticker}")


@pytest.mark.parametrize("ticker", WIP_TICKERS)
def test_regression_wip(ticker: str) -> None:
    """WIP tickers: extraction runs without error (score not asserted)."""
    if not _has_case(ticker):
        pytest.skip(f"No case data for {ticker}")

    phase = ExtractPhase()
    result = phase.extract(str(CASES_DIR / ticker))
    report = evaluate(result, str(CASES_DIR / ticker / "expected.json"))

    # Just log the score — don't assert 100%
    print(f"\n  {ticker}: {report.score}% ({report.matched}/{report.total_expected})")
