"""Post-extraction sanity checks.

Ported from 3.0 ``scripts/runners/tp_normalizer.py``
(``_sanity_check_entry`` and ``_sanity_check_yoy``).

These checks run **after** extraction and merge to catch common data
anomalies.  Warnings are informational (logged, never blocking).
The only auto-fix is flipping positive CAPEX to negative.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

from elsian.models.result import ExtractionResult

logger = logging.getLogger(__name__)

# Fields checked for YoY jumps >10×
_YOY_FIELDS: tuple[str, ...] = ("ingresos", "ebit", "net_income")

# Regex to extract the fiscal year from a period key like "FY2024"
_FY_RE = re.compile(r"FY(\d{4})")


@dataclass
class SanityWarning:
    """A single sanity-check finding."""

    period: str
    field: str
    warning_type: str  # capex_positive | revenue_negative | gp_gt_revenue | yoy_jump
    message: str


# ── Per-period checks ────────────────────────────────────────────────


def _check_period(period_key: str, fields: dict) -> list[SanityWarning]:
    """Run per-period sanity checks and return warnings.

    Auto-fix: if capex is positive, flip its sign in-place.
    """
    warnings: list[SanityWarning] = []

    # 1. CAPEX positive → warning + auto-fix
    capex_fr = fields.get("capex")
    if capex_fr is not None and capex_fr.value > 0:
        warnings.append(
            SanityWarning(
                period=period_key,
                field="capex",
                warning_type="capex_positive",
                message=(
                    f"{period_key}: CAPEX positive ({capex_fr.value}), "
                    f"sign flipped to {-capex_fr.value}"
                ),
            )
        )
        capex_fr.value = -capex_fr.value

    # 2. Revenue negative → warning
    revenue_fr = fields.get("ingresos")
    if revenue_fr is not None and revenue_fr.value < 0:
        warnings.append(
            SanityWarning(
                period=period_key,
                field="ingresos",
                warning_type="revenue_negative",
                message=f"{period_key}: Revenue negative ({revenue_fr.value})",
            )
        )

    # 3. gross_profit > revenue → warning
    gp_fr = fields.get("gross_profit")
    if (
        revenue_fr is not None
        and gp_fr is not None
        and revenue_fr.value > 0
        and gp_fr.value > revenue_fr.value
    ):
        warnings.append(
            SanityWarning(
                period=period_key,
                field="gross_profit",
                warning_type="gp_gt_revenue",
                message=(
                    f"{period_key}: gross_profit ({gp_fr.value}) > "
                    f"revenue ({revenue_fr.value})"
                ),
            )
        )

    return warnings


# ── YoY checks ───────────────────────────────────────────────────────


def _check_yoy(result: ExtractionResult) -> list[SanityWarning]:
    """Detect >10× year-over-year jumps in key metrics.

    Only annual periods (FYxxxx) are compared, sorted chronologically.
    """
    warnings: list[SanityWarning] = []

    # Collect annual periods sorted by year
    annual: list[tuple[int, str]] = []
    for pk in result.periods:
        m = _FY_RE.match(pk)
        if m:
            annual.append((int(m.group(1)), pk))
    annual.sort()

    for i in range(1, len(annual)):
        prev_year, prev_pk = annual[i - 1]
        curr_year, curr_pk = annual[i]
        prev_fields = result.periods[prev_pk].fields
        curr_fields = result.periods[curr_pk].fields

        for field_name in _YOY_FIELDS:
            prev_fr = prev_fields.get(field_name)
            curr_fr = curr_fields.get(field_name)
            if prev_fr is None or curr_fr is None:
                continue
            if prev_fr.value == 0:
                continue
            ratio = abs(curr_fr.value / prev_fr.value)
            if ratio > 10:
                warnings.append(
                    SanityWarning(
                        period=curr_pk,
                        field=field_name,
                        warning_type="yoy_jump",
                        message=(
                            f"{field_name}: {prev_pk}→{curr_pk} "
                            f"ratio={ratio:.1f}x (>10x)"
                        ),
                    )
                )

    return warnings


# ── Public entry point ───────────────────────────────────────────────


def run_sanity_checks(result: ExtractionResult) -> list[SanityWarning]:
    """Run all sanity checks on an ExtractionResult.

    Returns a list of SanityWarning objects.  The only mutation is
    flipping positive CAPEX to negative (auto-fix).

    Args:
        result: The full extraction result to validate.

    Returns:
        List of warnings (empty if everything is clean).
    """
    warnings: list[SanityWarning] = []

    # Per-period checks
    for period_key, period in result.periods.items():
        warnings.extend(_check_period(period_key, period.fields))

    # Cross-period YoY checks
    warnings.extend(_check_yoy(result))

    # Log warnings
    for w in warnings:
        logger.warning("Sanity check: %s", w.message)

    return warnings
