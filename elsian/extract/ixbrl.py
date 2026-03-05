"""iXBRL parser for SEC inline XBRL filings.

Extracts structured financial data from ix:nonFraction tags embedded in
.htm filing files. This is a standalone QA/development tool — NOT part
of the production extraction pipeline.

Usage:
    facts = parse_ixbrl_filing("path/to/filing.htm", fiscal_year_end_month=12)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ContextInfo:
    """Resolved xbrli:context information."""

    context_id: str
    start_date: date | None = None
    end_date: date | None = None
    instant_date: date | None = None
    has_segment: bool = False

    @property
    def is_duration(self) -> bool:
        return self.start_date is not None and self.end_date is not None

    @property
    def is_instant(self) -> bool:
        return self.instant_date is not None

    @property
    def period_end(self) -> date | None:
        if self.is_instant:
            return self.instant_date
        if self.is_duration:
            return self.end_date
        return None

    @property
    def duration_days(self) -> int | None:
        if self.is_duration and self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None


@dataclass
class IxbrlFact:
    """A single extracted iXBRL fact with provenance."""

    concept: str
    field: str | None
    period: str
    value: float
    displayed_value: str
    scale: int
    decimals: str
    unit_ref: str
    context_ref: str
    tag_id: str
    source_filing: str
    is_negated: bool = False


# ---------------------------------------------------------------------------
# Concept map loader
# ---------------------------------------------------------------------------

_concept_map_cache: dict[str, str] | None = None
_sign_overrides_cache: dict[str, str] | None = None
_preferred_concepts_cache: dict[str, list[str]] | None = None


def _load_concept_map() -> tuple[dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Load and cache the ixbrl_concept_map.json."""
    global _concept_map_cache, _sign_overrides_cache, _preferred_concepts_cache
    if _concept_map_cache is not None:
        assert _sign_overrides_cache is not None
        assert _preferred_concepts_cache is not None
        return _concept_map_cache, _sign_overrides_cache, _preferred_concepts_cache

    map_path = CONFIG_DIR / "ixbrl_concept_map.json"
    if not map_path.exists():
        logger.warning("ixbrl_concept_map.json not found at %s", map_path)
        _concept_map_cache = {}
        _sign_overrides_cache = {}
        _preferred_concepts_cache = {}
        return _concept_map_cache, _sign_overrides_cache, _preferred_concepts_cache

    data = json.loads(map_path.read_text(encoding="utf-8"))
    _concept_map_cache = data.get("mapping", {})
    raw_sign = data.get("sign_override", {})
    _sign_overrides_cache = {k: v for k, v in raw_sign.items() if not k.startswith("_")}
    raw_pref = data.get("preferred_concepts", {})
    _preferred_concepts_cache = {k: v for k, v in raw_pref.items() if not k.startswith("_")}
    return _concept_map_cache, _sign_overrides_cache, _preferred_concepts_cache


def map_concept(concept: str) -> str | None:
    """Map a GAAP concept to a canonical field name, or None."""
    mapping, _, _ = _load_concept_map()
    return mapping.get(concept)


# ---------------------------------------------------------------------------
# Context parsing
# ---------------------------------------------------------------------------

def _parse_date(text: str) -> date | None:
    """Parse YYYY-MM-DD date string."""
    text = text.strip()
    try:
        parts = text.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def parse_contexts(soup: BeautifulSoup) -> dict[str, ContextInfo]:
    """Parse all xbrli:context elements into a context_id → ContextInfo map."""
    contexts: dict[str, ContextInfo] = {}
    for ctx_tag in soup.find_all("xbrli:context"):
        ctx_id = ctx_tag.get("id", "")
        if not ctx_id:
            continue

        has_segment = ctx_tag.find("xbrli:segment") is not None

        period_tag = ctx_tag.find("xbrli:period")
        if not period_tag:
            continue

        start_date = None
        end_date = None
        instant_date = None

        start_tag = period_tag.find("xbrli:startdate")
        end_tag = period_tag.find("xbrli:enddate")
        instant_tag = period_tag.find("xbrli:instant")

        if start_tag and end_tag:
            start_date = _parse_date(start_tag.get_text())
            end_date = _parse_date(end_tag.get_text())
        elif instant_tag:
            instant_date = _parse_date(instant_tag.get_text())

        contexts[ctx_id] = ContextInfo(
            context_id=ctx_id,
            start_date=start_date,
            end_date=end_date,
            instant_date=instant_date,
            has_segment=has_segment,
        )

    return contexts


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------

def resolve_period_label(
    ctx: ContextInfo,
    fiscal_year_end_month: int = 12,
) -> str | None:
    """Determine the period label (FY2024, Q3-2024, etc.) from a context.

    Returns None if the context cannot be mapped to a standard period.
    """
    if ctx.has_segment:
        return None

    if ctx.is_duration:
        return _resolve_duration_period(ctx, fiscal_year_end_month)
    if ctx.is_instant:
        return _resolve_instant_period(ctx, fiscal_year_end_month)

    return None


def _fiscal_year_for_date(d: date, fiscal_year_end_month: int) -> int:
    """Determine the fiscal year number for a given date.

    For calendar year companies (end_month=12): Dec 31, 2024 → FY2024
    For non-standard (end_month=1): Jan 25, 2026 → FY2026
    For Oct year end (end_month=9): Sep 30, 2024 → FY2024
    """
    if d.month <= fiscal_year_end_month:
        return d.year
    return d.year + 1


def _resolve_duration_period(
    ctx: ContextInfo,
    fiscal_year_end_month: int,
) -> str | None:
    """Resolve a duration context to a period label."""
    assert ctx.start_date and ctx.end_date
    days = (ctx.end_date - ctx.start_date).days

    fy = _fiscal_year_for_date(ctx.end_date, fiscal_year_end_month)

    # Annual: ~335-400 days
    if 335 <= days <= 400:
        return f"FY{fy}"

    # Quarterly: ~80-100 days
    # Use calendar quarter + calendar year of the end date so that period labels
    # match the expected.json convention (Q#-CALENDAR_YEAR, independent of FYE).
    if 80 <= days <= 100:
        cal_q = (ctx.end_date.month - 1) // 3 + 1
        return f"Q{cal_q}-{ctx.end_date.year}"

    # Semi-annual: ~175-195 days
    if 175 <= days <= 195:
        half = _half_for_date(ctx.end_date, fiscal_year_end_month)
        if half:
            return f"H{half}-{fy}"
        return None

    # YTD periods (6 or 9 months) — skip, not standard periods
    return None


def _quarter_for_date(end_date: date, fiscal_year_end_month: int) -> int | None:
    """Determine which fiscal quarter ends on this date.

    For calendar year (end_month=12):
      Q1 ends Mar 31, Q2 ends Jun 30, Q3 ends Sep 30, Q4 ends Dec 31
    For NVDA (end_month=1):
      Q1 ends ~Apr, Q2 ends ~Jul, Q3 ends ~Oct, Q4 ends ~Jan
    """
    # Calculate month offset from fiscal year start
    fy_start_month = (fiscal_year_end_month % 12) + 1  # month after FY end
    month_in_fy = (end_date.month - fy_start_month) % 12
    quarter = (month_in_fy // 3) + 1
    if 1 <= quarter <= 4:
        return quarter
    return None


def _half_for_date(end_date: date, fiscal_year_end_month: int) -> int | None:
    """Determine which fiscal half ends on this date."""
    fy_start_month = (fiscal_year_end_month % 12) + 1
    month_in_fy = (end_date.month - fy_start_month) % 12
    if month_in_fy < 6:
        return 1
    return 2


def _resolve_instant_period(
    ctx: ContextInfo,
    fiscal_year_end_month: int,
) -> str | None:
    """Resolve an instant context to a period label for balance sheet items.

    The instant date is the balance sheet date. We determine the fiscal
    period it belongs to based on the date.
    """
    assert ctx.instant_date
    d = ctx.instant_date

    fy = _fiscal_year_for_date(d, fiscal_year_end_month)

    # Check if this is a fiscal year end date (within ±7 days of expected FY end)
    expected_fy_end_month = fiscal_year_end_month
    # Try matching the month
    if d.month == expected_fy_end_month:
        return f"FY{fy}"

    # Otherwise resolve to calendar quarter + calendar year of the balance-sheet date.
    # (Annual FY-end dates are already caught above by the month-match check.)
    cal_q = (d.month - 1) // 3 + 1
    return f"Q{cal_q}-{d.year}"


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

def parse_displayed_value(text: str) -> float | None:
    """Parse the displayed text of an ix:nonFraction tag into a number.

    Handles:
    - Comma-separated thousands: "83,902" → 83902.0
    - Decimals: "1.08" → 1.08
    - Negative in parentheses: "(5,404)" → -5404.0
    - Em-dash or en-dash for zero: "—" / "–" → 0.0
    - Whitespace and nbsp
    """
    text = text.strip()
    # Replace nbsp and other whitespace
    text = text.replace("\u00a0", "").replace("\xa0", "").strip()

    if not text or text in ("—", "–", "−", "-"):
        return 0.0

    # Check for parentheses (negative in accounting)
    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()

    # Remove thousand separators (commas)
    text = text.replace(",", "")

    # Remove dollar signs, percent signs
    text = text.replace("$", "").replace("%", "").strip()

    if not text:
        return 0.0

    try:
        val = float(text)
        return -val if is_negative else val
    except ValueError:
        logger.debug("Could not parse iXBRL value: %r", text)
        return None


def compute_actual_value(displayed: float, scale: int) -> float:
    """Compute actual value: displayed × 10^scale."""
    return displayed * (10 ** scale)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_ixbrl_filing(
    filepath: str | Path,
    fiscal_year_end_month: int = 12,
    concept_map: dict[str, str] | None = None,
) -> list[IxbrlFact]:
    """Parse an iXBRL .htm filing and return extracted facts.

    Args:
        filepath: Path to the .htm filing file.
        fiscal_year_end_month: Month number (1-12) when the fiscal year ends.
        concept_map: Optional override of concept→field mapping.
            If None, loads from config/ixbrl_concept_map.json.

    Returns:
        List of IxbrlFact objects for all parseable ix:nonFraction tags
        that belong to non-dimensional contexts and mapped periods.
    """
    filepath = Path(filepath)
    if concept_map is None:
        mapping, sign_overrides, preferred = _load_concept_map()
    else:
        mapping = concept_map
        sign_overrides = {}
        preferred = {}

    logger.info("Parsing iXBRL: %s", filepath.name)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    contexts = parse_contexts(soup)
    source_filing = filepath.name

    # Pre-resolve period labels for non-dimensional contexts
    period_map: dict[str, str] = {}
    for ctx_id, ctx in contexts.items():
        if ctx.has_segment:
            continue
        label = resolve_period_label(ctx, fiscal_year_end_month)
        if label:
            period_map[ctx_id] = label

    facts: list[IxbrlFact] = []

    for tag in soup.find_all("ix:nonfraction"):
        concept = tag.get("name", "")
        if not concept:
            continue

        ctx_ref = tag.get("contextref", "")
        if ctx_ref not in period_map:
            continue  # Skip dimensional or unmapped contexts

        period_label = period_map[ctx_ref]
        canonical_field = mapping.get(concept)

        # Parse value
        raw_text = tag.get_text()
        displayed = parse_displayed_value(raw_text)
        if displayed is None:
            continue

        scale_str = tag.get("scale", "0")
        try:
            scale_val = int(scale_str)
        except (ValueError, TypeError):
            scale_val = 0

        decimals_str = tag.get("decimals", "0") or "0"

        # Handle sign attribute
        sign_attr = tag.get("sign", "")
        is_negated = sign_attr == "-"
        if is_negated:
            displayed = -displayed

        unit_ref = tag.get("unitref", "")
        tag_id = tag.get("id", "")

        # Apply sign override from config (e.g., capex → negate)
        value_for_draft = displayed
        if canonical_field and canonical_field in sign_overrides:
            if sign_overrides[canonical_field] == "negate":
                value_for_draft = -abs(displayed)

        facts.append(IxbrlFact(
            concept=concept,
            field=canonical_field,
            period=period_label,
            value=value_for_draft,
            displayed_value=raw_text.strip(),
            scale=scale_val,
            decimals=decimals_str,
            unit_ref=unit_ref,
            context_ref=ctx_ref,
            tag_id=tag_id,
            source_filing=source_filing,
            is_negated=is_negated,
        ))

    logger.info(
        "Parsed %d facts (%d mapped) from %s",
        len(facts),
        sum(1 for f in facts if f.field),
        filepath.name,
    )
    return facts


# ---------------------------------------------------------------------------
# Aggregation helpers (used by curate command)
# ---------------------------------------------------------------------------

def deduplicate_facts(
    facts: list[IxbrlFact],
    preferred_concepts: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, IxbrlFact]]:
    """Aggregate facts into period → field → best fact.

    When the same field+period has multiple values (from different concepts
    or repeated tags), prefer based on:
    1. Preferred concept order from config
    2. First occurrence
    """
    if preferred_concepts is None:
        _, _, preferred_concepts = _load_concept_map()

    result: dict[str, dict[str, IxbrlFact]] = {}

    for fact in facts:
        if fact.field is None:
            continue

        period = fact.period
        field_name = fact.field

        if period not in result:
            result[period] = {}

        existing = result[period].get(field_name)
        if existing is None:
            result[period][field_name] = fact
        else:
            # Check preferred concept order
            pref_list = preferred_concepts.get(field_name, [])
            existing_rank = _concept_rank(existing.concept, pref_list)
            new_rank = _concept_rank(fact.concept, pref_list)
            if new_rank < existing_rank:
                result[period][field_name] = fact

    return result


def _concept_rank(concept: str, preferred: list[str]) -> int:
    """Return the rank of a concept in the preferred list (lower = better)."""
    try:
        return preferred.index(concept)
    except ValueError:
        return 999


def generate_expected_draft(
    facts_by_period: dict[str, dict[str, IxbrlFact]],
    ticker: str,
    currency: str,
) -> dict[str, Any]:
    """Generate an expected_draft.json structure from deduplicated facts."""
    from datetime import datetime

    periods_out: dict[str, Any] = {}
    for period_label in sorted(facts_by_period.keys()):
        fields = facts_by_period[period_label]
        fields_out: dict[str, Any] = {}
        for fname in sorted(fields.keys()):
            fact = fields[fname]
            entry: dict[str, Any] = {"value": fact.value}
            entry["_source"] = "ixbrl"
            entry["_concept"] = fact.concept
            entry["_filing"] = fact.source_filing
            entry["_displayed"] = fact.displayed_value
            entry["_scale"] = fact.scale
            fields_out[fname] = entry
        periods_out[period_label] = {"fields": fields_out}

    return {
        "version": "1.0",
        "ticker": ticker,
        "currency": currency,
        "scale": "as_reported",
        "scale_notes": (
            "Values are displayed values from iXBRL tags (as shown in filing tables). "
            "Generated by elsian curate — review and adjust before using as ground truth."
        ),
        "_generated_by": "elsian curate",
        "_generated_at": datetime.now().isoformat(timespec="seconds"),
        "periods": periods_out,
    }


def run_sanity_checks(
    draft: dict[str, Any],
) -> list[str]:
    """Run basic sanity checks on the generated draft.

    Returns list of warning messages (empty = all good).
    """
    warnings: list[str] = []
    periods = draft.get("periods", {})

    for plabel, pdata in periods.items():
        fields = pdata.get("fields", {})

        # Check: revenue should be positive
        rev = fields.get("ingresos", {}).get("value")
        if rev is not None and rev <= 0:
            warnings.append(f"{plabel}: ingresos={rev} (expected positive)")

        # Check: A ≈ L + E (±5%)
        assets = fields.get("total_assets", {}).get("value")
        liab = fields.get("total_liabilities", {}).get("value")
        equity = fields.get("total_equity", {}).get("value")
        if assets is not None and liab is not None and equity is not None:
            expected_sum = liab + equity
            if expected_sum != 0:
                deviation = abs(assets - expected_sum) / abs(expected_sum)
                if deviation > 0.05:
                    warnings.append(
                        f"{plabel}: A≠L+E — assets={assets}, "
                        f"liab+equity={expected_sum} (dev={deviation:.1%})"
                    )

        # Check: net_income sign matches EPS sign
        ni = fields.get("net_income", {}).get("value")
        eps = fields.get("eps_basic", {}).get("value")
        if ni is not None and eps is not None:
            if (ni > 0 and eps < 0) or (ni < 0 and eps > 0):
                warnings.append(
                    f"{plabel}: net_income and eps_basic have opposite signs "
                    f"(ni={ni}, eps={eps})"
                )

    return warnings
