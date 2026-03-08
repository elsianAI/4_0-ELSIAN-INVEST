"""Merge extractions from multiple filings into a single ExtractionResult.

Ported from 3.0 deterministic/src/merge.py.
Priority: annual > quarterly > earnings.
When multiple filings report the same field for the same period,
take the value from the highest-priority source.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from elsian.models.field import FieldResult
from elsian.models.result import (
    ExtractionResult,
    PeriodResult,
    AuditRecord,
)


# Filing type priority (lower = higher priority)
_TYPE_PRIORITY = {
    "10-K": 1,
    "20-F": 1,
    "40-F": 1,
    "annual_report": 1,
    "10-Q": 2,
    "6-K": 2,
    "interim_report": 2,
    "8-K": 3,
    "earnings": 3,
    "unknown": 4,
}

_EPS_FIELDS = {"eps_basic", "eps_diluted"}


def _filing_priority(filing_type: str) -> int:
    """Get priority for a filing type (lower = better)."""
    return _TYPE_PRIORITY.get(filing_type, 4)


def _should_keep_existing_eps_comparative(
    field_name: str,
    existing: FieldResult,
    field_result: FieldResult,
) -> bool:
    """Keep near-identical newer EPS comparatives over older primaries.

    Some issuers restate annual EPS in the next one or two filings without a
    structural share-count rebasing event. In those cases the newer comparative
    is a small numeric refinement and should stay. When the delta is large, the
    newer comparative is more likely a stock-split / rebasing artifact and the
    primary filing should replace it.
    """
    if field_name not in _EPS_FIELDS:
        return False
    existing_value = existing.value
    new_value = field_result.value
    if existing_value == 0 or new_value == 0:
        return False
    if existing_value * new_value < 0:
        return False
    relative_delta = abs(existing_value - new_value) / max(
        abs(existing_value), abs(new_value)
    )
    return relative_delta <= 0.05


def _eps_relative_delta(existing: FieldResult, field_result: FieldResult) -> float | None:
    existing_value = existing.value
    new_value = field_result.value
    if existing_value == 0 or new_value == 0:
        return None
    return abs(existing_value - new_value) / max(
        abs(existing_value), abs(new_value)
    )


def _prefer_eps_candidate(
    period_key: str,
    existing: FieldResult,
    field_result: FieldResult,
) -> str | None:
    """Resolve same-priority EPS conflicts using source semantics."""
    existing_restated = getattr(existing, "_is_explicit_restatement", False)
    new_restated = getattr(field_result, "_is_explicit_restatement", False)
    if existing_restated != new_restated:
        return "new" if new_restated else "existing"

    existing_filing = getattr(existing.provenance, "source_filing", "")
    new_filing = getattr(field_result.provenance, "source_filing", "")
    existing_loc = getattr(existing.provenance, "source_location", "").lower()
    new_loc = getattr(field_result.provenance, "source_location", "").lower()
    existing_primary = period_key in existing_filing
    new_primary = period_key in new_filing
    existing_weighted = (
        "weighted_average_number_of_ordinary_shares_used_to_calculate" in existing_loc
    )
    new_weighted = (
        "weighted_average_number_of_ordinary_shares_used_to_calculate" in new_loc
    )

    if existing_weighted != new_weighted:
        return "new" if existing_weighted else "existing"

    if _should_keep_existing_eps_comparative("eps_basic", existing, field_result):
        return "existing"

    relative_delta = _eps_relative_delta(existing, field_result)
    if relative_delta is None:
        return None

    if existing_primary != new_primary and relative_delta >= 0.25:
        if not existing_primary and (
            ":ixbrl:" in existing_loc or existing_weighted
        ):
            return "new"
        if not new_primary and (
            ":ixbrl:" in new_loc or new_weighted
        ):
            return "existing"

    return None


def merge_extractions(
    filing_extractions: List[
        Tuple[str, str, Dict[str, Dict[str, FieldResult]]]
    ],
    ticker: str = "",
    currency: str = "USD",
) -> ExtractionResult:
    """Merge field extractions from multiple filings.

    Args:
        filing_extractions: List of (filing_type, filename, {period: {field: FieldResult}})
        ticker: Ticker symbol
        currency: Currency code

    Returns:
        Merged ExtractionResult
    """
    # Sort by priority (annual first)
    sorted_filings = sorted(
        filing_extractions, key=lambda x: _filing_priority(x[0])
    )

    merged_periods: Dict[str, Dict[str, FieldResult]] = {}
    fields_extracted = 0
    fields_discarded = 0
    discard_reasons: list[str] = []

    for filing_type, filename, periods_data in sorted_filings:
        for period_key, fields in periods_data.items():
            if period_key not in merged_periods:
                merged_periods[period_key] = {}

            for field_name, field_result in fields.items():
                if field_name not in merged_periods[period_key]:
                    # First time seeing this field for this period
                    merged_periods[period_key][field_name] = field_result
                    fields_extracted += 1
                else:
                    # Already have a value - check if we should update
                    existing = merged_periods[period_key][field_name]
                    existing_priority = _filing_priority(
                        _guess_type_from_source(existing.provenance.source_filing)
                    )
                    new_priority = _filing_priority(filing_type)

                    if new_priority < existing_priority:
                        # New source has higher priority
                        merged_periods[period_key][field_name] = field_result
                        fields_discarded += 1
                        discard_reasons.append("duplicate_conflict")
                    elif new_priority == existing_priority:
                        # Same filing-type priority.
                        # sort_key layout: (filing_rank, affinity,
                        #                   src_rank, semantic_rank,
                        #                   stable_order)
                        existing_sk = getattr(existing, "_sort_key", None)
                        new_sk = getattr(field_result, "_sort_key", None)
                        if (
                            existing_sk is not None
                            and new_sk is not None
                            and len(existing_sk) > 3
                            and len(new_sk) > 3
                        ):
                            handled_eps = False
                            if field_name in _EPS_FIELDS:
                                eps_preference = _prefer_eps_candidate(
                                    period_key, existing, field_result
                                )
                                if eps_preference == "new":
                                    merged_periods[period_key][
                                        field_name
                                    ] = field_result
                                    handled_eps = True
                                elif eps_preference == "existing":
                                    handled_eps = True
                                # Else fall through to the generic sort-key
                                # policy below.
                            if not handled_eps and new_sk[1] < existing_sk[1]:
                                # 1) Affinity wins: primary filing beats
                                #    comparative (affinity 0 < 1).
                                if _should_keep_existing_eps_comparative(
                                    field_name, existing, field_result
                                ):
                                    pass
                                else:
                                    merged_periods[period_key][
                                        field_name
                                    ] = field_result
                            elif (
                                not handled_eps
                                and
                                new_sk[1] == existing_sk[1]
                                and existing_sk[3] > 0
                                and new_sk[3] < existing_sk[3]
                            ):
                                # 2) Same affinity, but existing comes from a
                                #    deprioritized section (semantic_rank > 0
                                #    implies section_bonus < 0).  Allow a
                                #    better-quality candidate to replace it.
                                merged_periods[period_key][
                                    field_name
                                ] = field_result
                        # Else keep existing (first-seen-wins when both
                        # quality signals are equal or absent).
                        fields_discarded += 1
                        discard_reasons.append("duplicate_conflict")
                    else:
                        # Normally keep existing (higher filing-type priority wins).
                        # Exception: if existing is a rescaled iXBRL value (low precision,
                        # e.g. 3.9M tag in a thousands-denominated filing → 3,900K) while
                        # the new candidate is an exact (non-rescaled) value from a table or
                        # narrative source, prefer the exact value even though it comes from a
                        # lower-priority filing type (e.g. 8-K earnings table vs 10-Q iXBRL).
                        existing_rescaled = getattr(
                            existing, "_ixbrl_was_rescaled", False
                        )
                        new_rescaled = getattr(
                            field_result, "_ixbrl_was_rescaled", False
                        )
                        if existing_rescaled and not new_rescaled:
                            merged_periods[period_key][field_name] = field_result
                            fields_discarded += 1
                            discard_reasons.append("quality_override_rescaled")
                        else:
                            fields_discarded += 1
                            discard_reasons.append("duplicate_conflict")

    # Build result
    result = ExtractionResult(
        ticker=ticker,
        currency=currency,
        filings_used=len(filing_extractions),
    )

    for period_key, fields in sorted(merged_periods.items()):
        period = PeriodResult(
            fecha_fin=_infer_fecha_fin(period_key),
            tipo_periodo=_infer_tipo_periodo(period_key),
            fields=fields,
        )
        result.periods[period_key] = period

    result.audit = AuditRecord(
        fields_extracted=fields_extracted,
        fields_discarded=fields_discarded,
        discarded_reasons=list(set(discard_reasons)),
    )

    return result


def _guess_type_from_source(source_filing: str) -> str:
    """Guess filing type from source filename."""
    low = source_filing.lower()
    if "10-k" in low or "10k" in low:
        return "10-K"
    if "10-q" in low or "10q" in low:
        return "10-Q"
    if "20-f" in low or "20f" in low:
        return "20-F"
    if "8-k" in low or "8k" in low:
        return "8-K"
    if "6-k" in low or "6k" in low:
        return "6-K"
    return "unknown"


def _infer_fecha_fin(period_key: str) -> str:
    """Infer period end date from period key."""
    import re

    # FY2024 -> 2024-12-31
    m = re.match(r"FY(\d{4})", period_key)
    if m:
        return f"{m.group(1)}-12-31"

    # Q1-2024 -> 2024-03-31, Q2->06-30, Q3->09-30, Q4->12-31
    m = re.match(r"Q(\d)-(\d{4})", period_key)
    if m:
        q = int(m.group(1))
        year = m.group(2)
        ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
        return f"{year}-{ends.get(q, '12-31')}"

    # H1-2024 -> 2024-06-30, H2->12-31
    m = re.match(r"H(\d)-(\d{4})", period_key)
    if m:
        h = int(m.group(1))
        year = m.group(2)
        return f"{year}-{'06-30' if h == 1 else '12-31'}"

    return ""


def _infer_tipo_periodo(period_key: str) -> str:
    """Infer period type from period key."""
    if period_key.startswith("FY"):
        return "anual"
    if period_key.startswith("Q"):
        return "trimestral"
    if period_key.startswith("H"):
        return "semestral"
    return "unknown"
