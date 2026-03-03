"""Evaluate extraction results against expected.json.

Compares field by field, period by period. Tolerance: +/-1% for numerics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from elsian.evaluate.validate_expected import validate_expected
from elsian.models.result import EvalMatch, EvalReport, ExtractionResult

logger = logging.getLogger(__name__)

TOLERANCE_PCT = 1.0


def _values_match(expected: float, actual: float) -> bool:
    """Check if two values match within tolerance."""
    if expected == 0 and actual == 0:
        return True
    if expected == 0:
        return abs(actual) < 0.01
    pct_diff = abs(actual - expected) / abs(expected) * 100
    return pct_diff <= TOLERANCE_PCT


def evaluate(extraction: ExtractionResult, expected_path: str | Path) -> EvalReport:
    """Compare ExtractionResult against expected.json."""
    expected_file = Path(expected_path)
    if not expected_file.exists():
        return EvalReport(ticker=extraction.ticker, total_expected=0, score=0.0)

    # Pre-check: validate expected.json structure (informational only)
    validation_issues = validate_expected(str(expected_file))
    for issue in validation_issues:
        logger.warning("validate_expected [%s]: %s", extraction.ticker, issue)

    expected_data = json.loads(expected_file.read_text(encoding="utf-8"))
    expected_periods: dict[str, Any] = expected_data.get("periods", {})

    details: list[EvalMatch] = []
    matched = 0
    wrong = 0
    missed = 0
    extra = 0
    total_expected = 0
    fields_with_value = 0

    for period_key, period_data in expected_periods.items():
        expected_fields = period_data.get("fields", {})

        for field_name, field_info in expected_fields.items():
            expected_value = field_info.get("value")
            if expected_value is None:
                continue
            total_expected += 1

            actual_value = None
            if period_key in extraction.periods:
                period = extraction.periods[period_key]
                if field_name in period.fields:
                    actual_value = period.fields[field_name].value
                    fields_with_value += 1

            if actual_value is None:
                missed += 1
                details.append(EvalMatch(
                    field_name=field_name, period=period_key,
                    expected=expected_value, actual=None, status="missed",
                ))
            elif _values_match(expected_value, actual_value):
                matched += 1
                details.append(EvalMatch(
                    field_name=field_name, period=period_key,
                    expected=expected_value, actual=actual_value, status="matched",
                ))
            else:
                wrong += 1
                details.append(EvalMatch(
                    field_name=field_name, period=period_key,
                    expected=expected_value, actual=actual_value, status="wrong",
                ))

    for period_key, period in extraction.periods.items():
        for field_name in period.fields:
            is_expected = (
                period_key in expected_periods
                and field_name in expected_periods[period_key].get("fields", {})
            )
            if not is_expected:
                extra += 1

    score = (matched / total_expected * 100.0) if total_expected > 0 else 0.0
    req_coverage = (fields_with_value / total_expected * 100.0) if total_expected > 0 else 0.0

    return EvalReport(
        ticker=extraction.ticker,
        total_expected=total_expected,
        matched=matched,
        wrong=wrong,
        missed=missed,
        extra=extra,
        score=round(score, 2),
        required_fields_coverage_pct=round(req_coverage, 2),
        details=details,
    )
