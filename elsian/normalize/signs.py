"""SignConvention enforcer -- ensures extracted values follow the sign policy."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_ALWAYS_POSITIVE_IS: set[str] = {
    "ingresos", "gross_profit",
    "cost_of_revenue", "research_and_development", "sga",
    "depreciation_amortization", "interest_expense",
    "shares_outstanding",
}

_ALWAYS_POSITIVE_BS: set[str] = {
    "total_assets", "total_liabilities",
    "cash_and_equivalents", "total_debt",
}

_ALWAYS_NEGATIVE: set[str] = {"capex"}


def enforce_sign(field_name: str, value: float) -> float:
    """Enforce the sign convention for a given canonical field."""
    if field_name in _ALWAYS_POSITIVE_IS or field_name in _ALWAYS_POSITIVE_BS:
        return abs(value)
    if field_name in _ALWAYS_NEGATIVE:
        return -abs(value)
    return value
