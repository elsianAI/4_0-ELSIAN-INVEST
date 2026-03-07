"""Helpers for building expected_draft.json from extraction outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from elsian.evaluate.validation import validate
from elsian.models.result import ExtractionResult
from elsian.normalize.aliases import AliasResolver


def _is_manual_field(field_data: dict[str, Any]) -> bool:
    location = field_data.get("source_location", "") or ""
    method = field_data.get("extraction_method", "") or ""
    confidence = field_data.get("confidence", "") or ""
    return (
        location.startswith("case.json:manual_overrides")
        or method == "manual"
        or confidence == "manual"
    )


def _coerce_result_dict(extraction_result: ExtractionResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(extraction_result, ExtractionResult):
        return extraction_result.to_dict()
    return extraction_result


def _build_gap_policy() -> dict[str, str]:
    return {
        "missing_canonicals": (
            "Canonical fields not auto-populated by the deterministic PDF/text draft "
            "for that period. They are gaps to review, not proof that the filing lacks them."
        ),
        "skipped_manual_fields": (
            "Fields intentionally excluded because their source is manual "
            "(case.json overrides or manual extraction)."
        ),
        "missing_expected_fields": (
            "Fields present in expected.json but absent from the draft for a common period."
        ),
        "extra_fields_vs_expected": (
            "Fields present in the draft but absent from expected.json for a common period."
        ),
    }


def _values_match(expected: Any, actual: Any, tolerance: float = 0.01) -> bool:
    if expected is None or actual is None:
        return False
    if expected == 0:
        return actual == 0
    try:
        return abs(actual - expected) / abs(expected) <= tolerance
    except TypeError:
        return False


def compare_draft_vs_expected(
    draft: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Summarise coverage and value agreement vs an existing expected.json."""

    exp_periods: dict[str, Any] = expected.get("periods", {})
    draft_periods: dict[str, Any] = draft.get("periods", {})

    common_periods = sorted(set(exp_periods) & set(draft_periods))
    missing_periods = sorted(set(exp_periods) - set(draft_periods))
    extra_periods = sorted(set(draft_periods) - set(exp_periods))

    total_expected = 0
    covered = 0
    matched = 0
    period_summaries: dict[str, Any] = {}

    for period_label in common_periods:
        exp_fields = exp_periods[period_label].get("fields", {})
        draft_fields = draft_periods[period_label].get("fields", {})
        missing_fields = sorted(set(exp_fields) - set(draft_fields))
        extra_fields = sorted(set(draft_fields) - set(exp_fields))

        matched_fields = 0
        for field_name, exp_data in exp_fields.items():
            total_expected += 1
            if field_name not in draft_fields:
                continue
            covered += 1
            exp_value = exp_data.get("value")
            draft_value = draft_fields[field_name].get("value")
            if _values_match(exp_value, draft_value):
                matched += 1
                matched_fields += 1

        period_summaries[period_label] = {
            "expected_fields": len(exp_fields),
            "draft_fields": len(draft_fields),
            "covered_fields": len(exp_fields) - len(missing_fields),
            "matched_fields": matched_fields,
            "missing_fields": missing_fields,
            "extra_fields": extra_fields,
        }

    coverage_pct = (covered / total_expected * 100) if total_expected else 0.0
    value_match_pct = (matched / total_expected * 100) if total_expected else 0.0

    return {
        "common_periods": common_periods,
        "missing_periods": missing_periods,
        "extra_periods": extra_periods,
        "coverage_fields": covered,
        "total_expected_fields": total_expected,
        "matched_fields": matched,
        "coverage_pct": round(coverage_pct, 2),
        "value_match_pct": round(value_match_pct, 2),
        "periods": period_summaries,
    }


def build_expected_draft_from_extraction(
    extraction_result: ExtractionResult | dict[str, Any],
    ticker: str,
    currency: str,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build expected_draft.json from the pipeline extraction result."""

    result_dict = _coerce_result_dict(extraction_result)
    canonical_fields = sorted(AliasResolver().get_all_canonical_names())
    validation = validate(result_dict)

    periods_out: dict[str, Any] = {}
    confidence_totals: dict[str, int] = {}
    for period_label in sorted(result_dict.get("periods", {})):
        period_data = result_dict["periods"][period_label]
        fields = period_data.get("fields", {})
        fields_out: dict[str, Any] = {}
        confidence_counts: dict[str, int] = {}
        non_high_fields: list[str] = []
        skipped_manual_fields: list[str] = []

        for field_name in sorted(fields):
            field_data = fields[field_name]
            if _is_manual_field(field_data):
                skipped_manual_fields.append(field_name)
                continue
            confidence = field_data.get("confidence", "unknown")
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
            confidence_totals[confidence] = confidence_totals.get(confidence, 0) + 1
            if confidence != "high":
                non_high_fields.append(field_name)

            entry: dict[str, Any] = {
                "value": field_data.get("value"),
                "source_filing": field_data.get("source_filing", ""),
                "confidence": confidence,
                "_source": "pipeline",
            }
            if field_data.get("extraction_method"):
                entry["extraction_method"] = field_data["extraction_method"]
            if field_data.get("scale"):
                entry["_scale"] = field_data["scale"]
            if field_data.get("source_location"):
                entry["_source_location"] = field_data["source_location"]
            fields_out[field_name] = entry

        missing_canonicals = [
            field_name for field_name in canonical_fields if field_name not in fields_out
        ]
        period_out: dict[str, Any] = {
            "fields": fields_out,
            "_confidence": {
                "field_counts": dict(sorted(confidence_counts.items())),
                "non_high_fields": sorted(non_high_fields),
            },
            "_gaps": {
                "missing_canonicals": missing_canonicals,
                "missing_count": len(missing_canonicals),
                "skipped_manual_fields": sorted(skipped_manual_fields),
            },
        }
        periods_out[period_label] = period_out

    if not periods_out:
        draft = {
            "version": "1.0",
            "ticker": ticker,
            "currency": currency,
            "scale": "mixed",
            "scale_notes": (
                "SKELETON — no deterministic non-iXBRL fields were extracted. "
                "Curate manually from PDF/other sources."
            ),
            "_generated_by": "elsian curate",
            "_generated_at": datetime.now().isoformat(timespec="seconds"),
            "_source_mode": "pipeline_non_sec",
            "_confidence_summary": {},
            "_gap_policy": _build_gap_policy(),
            "_validation": {
                "status": validation["status"],
                "confidence_score": validation["confidence_score"],
                "warnings": validation["warnings"],
                "limitaciones": validation["limitaciones"],
            },
            "periods": {},
        }
        if expected is not None:
            draft["_comparison_to_expected"] = compare_draft_vs_expected(draft, expected)
        return draft

    draft: dict[str, Any] = {
        "version": "1.0",
        "ticker": ticker,
        "currency": currency,
        "scale": "as_reported",
        "scale_notes": (
            "Values come from the deterministic extraction pipeline over PDF/text filings. "
            "Review gaps, confidence, and provenance before promoting to expected.json."
        ),
        "_generated_by": "elsian curate",
        "_generated_at": datetime.now().isoformat(timespec="seconds"),
        "_source_mode": "pipeline_non_sec",
        "_confidence_summary": dict(sorted(confidence_totals.items())),
        "_gap_policy": _build_gap_policy(),
        "_validation": {
            "status": validation["status"],
            "confidence_score": validation["confidence_score"],
            "warnings": validation["warnings"],
            "limitaciones": validation["limitaciones"],
        },
        "periods": periods_out,
    }

    if expected is not None:
        comparison = compare_draft_vs_expected(draft, expected)
        draft["_comparison_to_expected"] = comparison
        for period_label, period_summary in comparison["periods"].items():
            draft["periods"][period_label]["_gaps"]["missing_expected_fields"] = (
                period_summary["missing_fields"]
            )
            draft["periods"][period_label]["_gaps"]["extra_fields_vs_expected"] = (
                period_summary["extra_fields"]
            )

    return draft
