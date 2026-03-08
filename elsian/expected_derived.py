"""Deterministic derived-field helpers for expected.json workflows."""

from __future__ import annotations

from typing import Any, Mapping

DERIVED_COMPONENTS: dict[str, tuple[str, ...]] = {
    "ebitda": ("ebit", "depreciation_amortization"),
    "fcf": ("cfo", "capex"),
}

# Canonical exclusions for BL-075, grounded in DEC-027 + AUDIT_EXPECTED_JSON.md.
DERIVED_INCONSISTENT_PERIODS: dict[tuple[str, str], set[str]] = {
    ("ACLS", "ebitda"): {
        "Q1-2024",
        "Q2-2024",
        "Q3-2024",
        "Q1-2025",
        "Q2-2025",
        "Q3-2025",
    },
    ("GCT", "ebitda"): {
        "FY2020",
        "FY2021",
        "FY2022",
        "FY2023",
        "FY2024",
        "FY2025",
    },
}


def is_period_excluded(ticker: str, period_key: str, field_name: str) -> bool:
    """Return True when a canonical inconsistent period must not be auto-derived."""
    return period_key in DERIVED_INCONSISTENT_PERIODS.get((ticker, field_name), set())


def _numeric_value(field_data: Any) -> float | None:
    """Extract a numeric field value from expected/extraction dictionaries."""
    if isinstance(field_data, Mapping):
        field_data = field_data.get("value")
    if isinstance(field_data, bool):
        return None
    if isinstance(field_data, (int, float)):
        return float(field_data)
    return None


def derive_field_value(field_name: str, fields: Mapping[str, Any]) -> float | None:
    """Compute a supported deterministic derived field from a field mapping."""
    if field_name == "ebitda":
        ebit = _numeric_value(fields.get("ebit"))
        depreciation = _numeric_value(fields.get("depreciation_amortization"))
        if ebit is None or depreciation is None:
            return None
        return ebit + depreciation

    if field_name == "fcf":
        cfo = _numeric_value(fields.get("cfo"))
        capex = _numeric_value(fields.get("capex"))
        if cfo is None or capex is None:
            return None
        return cfo - abs(capex)

    return None


def derive_missing_fields(
    *,
    ticker: str,
    period_key: str,
    fields: Mapping[str, Any],
    existing_field_names: set[str] | None = None,
) -> dict[str, float]:
    """Return missing eligible deterministic derived fields for a period."""
    existing = existing_field_names or set()
    out: dict[str, float] = {}
    for field_name in DERIVED_COMPONENTS:
        if field_name in existing:
            continue
        if is_period_excluded(ticker, period_key, field_name):
            continue
        value = derive_field_value(field_name, fields)
        if value is not None:
            out[field_name] = value
    return out
