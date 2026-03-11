"""Evaluate extraction results against expected.json.

Compares field by field, period by period. Tolerance: +/-1% for numerics.
"""

from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any

from elsian.expected_derived import derive_missing_fields
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


def _compute_provenance_coverage(extraction: ExtractionResult, expected_periods: dict[str, Any]) -> float:
    """Provenance coverage: pct of extracted expected fields with source_filing AND extraction_method set."""
    fields_with_value = 0
    fields_with_full_provenance = 0
    for period_key, period_data in expected_periods.items():
        if period_key not in extraction.periods:
            continue
        period = extraction.periods[period_key]
        for field_name, field_info in period_data.get("fields", {}).items():
            if field_info.get("value") is None:
                continue
            if field_name not in period.fields:
                continue
            fields_with_value += 1
            fr = period.fields[field_name]
            if fr.provenance.source_filing and fr.provenance.extraction_method:
                fields_with_full_provenance += 1
    if fields_with_value == 0:
        return 0.0
    return round(fields_with_full_provenance / fields_with_value * 100.0, 2)


def _compute_validator_confidence(extraction: ExtractionResult) -> float:
    """Run the autonomous truth-pack validator and return its confidence score (0-100)."""
    try:
        from elsian.evaluate.validation import validate
        result = validate(extraction.to_dict())
        return float(result.get("confidence_score", 0.0))
    except Exception:
        logger.debug("validator_confidence could not be computed", exc_info=True)
        return 0.0


def _compute_readiness(
    score: float,
    required_fields_coverage_pct: float,
    validator_confidence_score: float,
    provenance_coverage_pct: float,
    extra: int,
    total_expected: int,
) -> tuple[float, float]:
    """Compute readiness v1 using fixed formula.

    Returns:
        (readiness_score, extra_penalty)
    """
    readiness_base = (
        0.40 * score
        + 0.20 * required_fields_coverage_pct
        + 0.20 * validator_confidence_score
        + 0.20 * provenance_coverage_pct
    )
    extra_penalty = min(15.0, extra / max(total_expected, 1) * 100.0)
    readiness_score = max(0.0, round(readiness_base - extra_penalty, 2))
    return readiness_score, round(extra_penalty, 2)


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
                expected_is_derived = field_info.get("source_filing") == "DERIVED"
                if expected_is_derived:
                    derived_actual = derive_missing_fields(
                        ticker=extraction.ticker,
                        period_key=period_key,
                        fields={name: {"value": fr.value} for name, fr in period.fields.items()},
                        existing_field_names={name for name in period.fields if name != field_name},
                    )
                    if field_name in derived_actual:
                        actual_value = derived_actual[field_name]
                        fields_with_value += 1
                if actual_value is None:
                    if field_name in period.fields:
                        actual_value = period.fields[field_name].value
                        fields_with_value += 1
                    else:
                        derived_actual = derive_missing_fields(
                            ticker=extraction.ticker,
                            period_key=period_key,
                            fields={name: {"value": fr.value} for name, fr in period.fields.items()},
                            existing_field_names=set(period.fields),
                        )
                        if field_name in derived_actual:
                            actual_value = derived_actual[field_name]
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

    # Readiness v1 (BL-064)
    provenance_coverage_pct = _compute_provenance_coverage(extraction, expected_periods)
    validator_confidence_score = _compute_validator_confidence(extraction)
    readiness_score, extra_penalty = _compute_readiness(
        score=score,
        required_fields_coverage_pct=req_coverage,
        validator_confidence_score=validator_confidence_score,
        provenance_coverage_pct=provenance_coverage_pct,
        extra=extra,
        total_expected=total_expected,
    )

    return EvalReport(
        ticker=extraction.ticker,
        total_expected=total_expected,
        matched=matched,
        wrong=wrong,
        missed=missed,
        extra=extra,
        score=round(score, 2),
        required_fields_coverage_pct=round(req_coverage, 2),
        readiness_score=readiness_score,
        validator_confidence_score=round(validator_confidence_score, 2),
        provenance_coverage_pct=provenance_coverage_pct,
        extra_penalty=extra_penalty,
        details=details,
    )
