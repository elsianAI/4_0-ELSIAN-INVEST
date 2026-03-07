"""Narrative extraction from prose financial text.

Ported from 3.0 deterministic/src/extract/narrative.py (303 lines).
Extracts financial data from narrative/prose sections of filings.
Patterns: "revenue amounted to EUR10,280M", "net income of $523 million",
comparative "versus $8,345M in FY2023".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class NarrativeField:
    """A single field extracted from narrative text."""

    label: str
    value: float
    currency: str = ""
    scale: str = "raw"  # raw | thousands | millions | billions
    period_hint: str = ""  # e.g. "FY2024", "2024"
    source_location: str = ""
    confidence: str = "medium"


# ── Scale keywords ───────────────────────────────────────────────────

_SCALE_WORDS = {
    "billion": "billions",
    "billions": "billions",
    "bn": "billions",
    "b": "billions",
    "million": "millions",
    "millions": "millions",
    "mn": "millions",
    "m": "millions",
    "thousand": "thousands",
    "thousands": "thousands",
    "k": "thousands",
}

_CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "CHF": "CHF",
    "HK$": "HKD",
}


def _parse_narrative_number(text: str) -> Optional[float]:
    """Parse a number from narrative context."""
    text = text.strip()
    if not text:
        return None

    is_negative = False
    if text.startswith("(") and text.endswith(")"):
        is_negative = True
        text = text[1:-1].strip()
    elif text.startswith("-") or text.startswith("−"):
        is_negative = True
        text = text[1:].strip()

    text = re.sub(r"[$€£¥]", "", text).strip()
    text = text.replace(",", "")

    try:
        value = float(text)
        return -value if is_negative else value
    except ValueError:
        return None


# ── Main Extraction Patterns ────────────────────────────────────────

# Pattern 1: "{label} {verb} {currency}{value} {scale}"
# e.g. "Revenue amounted to €10,280 million"
_PATTERN_LABEL_VERB_VALUE = re.compile(
    r"(?P<label>"
    r"(?:total\s+)?(?:net\s+)?"
    r"(?:revenue|revenues|sales|turnover|"
    r"(?:operating\s+)?(?:income|profit|loss|earnings)|"
    r"ebitda|ebit|"
    r"(?:net\s+)?(?:income|profit|loss|earnings)|"
    r"gross\s+(?:profit|margin)|"
    r"(?:operating\s+)?cash\s+flow|"
    r"(?:capital\s+)?expenditure|capex|"
    r"free\s+cash\s+flow|"
    r"total\s+(?:assets|liabilities|equity|debt)|"
    r"(?:cash\s+and\s+)?(?:cash\s+)?equivalents|"
    r"chiffre\s+d['\u2019]affaires|"
    r"r[ée]sultat\s+(?:net|op[ée]rationnel)|"
    r"b[ée]n[ée]fice\s+(?:net|brut)|"
    r"ingresos|beneficio\s+neto|resultado)"
    r")"
    r"\s+"
    r"(?:amounted?\s+to|(?:was|were|is|are|of|reached?|totale?d?|stood\s+at)\s*)"
    r"\s*"
    r"(?P<currency>[$€£¥]|(?:USD|EUR|GBP|HKD|CHF)\s*)?"
    r"(?P<value>[\-\(]?[\d,]+\.?\d*\)?)"
    r"\s*"
    r"(?P<scale>billion|billions|bn|million|millions|mn|thousand|thousands)?",
    re.IGNORECASE,
)

# Pattern 2: Comparative "versus {currency}{value} {scale} in {period}"
# e.g. "versus €8,345M in 2023"
_PATTERN_COMPARATIVE = re.compile(
    r"(?:versus|compared\s+(?:to|with)|vs\.?|from)\s+"
    r"(?P<currency>[$€£¥]|(?:USD|EUR|GBP|HKD|CHF)\s*)?"
    r"(?P<value>[\-\(]?[\d,]+\.?\d*\)?)"
    r"\s*"
    r"(?P<scale>billion|billions|bn|million|millions|mn|thousand|thousands|[MBK])?"
    r"\s*"
    r"(?:in\s+)?(?P<period>(?:FY\s?)?20\d{2}|Q[1-4][\s-]?20\d{2}|[HS][12][\s-]?20\d{2})?",
    re.IGNORECASE,
)

# Pattern 3: "{currency}{value} {scale} {label}" (reversed)
# e.g. "$185.2 million in revenue"
_PATTERN_VALUE_LABEL = re.compile(
    r"(?P<currency>[$€£¥]|(?:USD|EUR|GBP|HKD|CHF)\s*)"
    r"(?P<value>[\-\(]?[\d,]+\.?\d*\)?)"
    r"\s*"
    r"(?P<scale>billion|billions|bn|million|millions|mn|thousand|thousands)?"
    r"\s+(?:in|of)\s+"
    r"(?P<label>"
    r"(?:total\s+)?(?:net\s+)?"
    r"(?:revenue|revenues|sales|turnover|"
    r"(?:operating\s+)?(?:income|profit|loss)|"
    r"ebitda|ebit|"
    r"(?:net\s+)?(?:income|profit|loss)|"
    r"gross\s+(?:profit|margin)|"
    r"(?:operating\s+)?cash\s+flow|"
    r"(?:capital\s+)?expenditure|capex|"
    r"free\s+cash\s+flow|"
    r"total\s+(?:assets|liabilities|equity|debt))"
    r")",
    re.IGNORECASE,
)


def _resolve_scale(scale_text: str) -> str:
    """Resolve a scale keyword to canonical scale name."""
    if not scale_text:
        return "raw"
    low = scale_text.strip().lower()
    return _SCALE_WORDS.get(low, "raw")


def _resolve_currency(currency_text: str) -> str:
    """Resolve a currency symbol/code to ISO code."""
    if not currency_text:
        return ""
    text = currency_text.strip()
    return _CURRENCY_SYMBOLS.get(text, text.upper())


def _detect_surrounding_period(text: str, match_start: int) -> str:
    """Try to detect a period from text surrounding a match.

    Trims the suffix at the first comparative keyword so that periods
    from comparative clauses (e.g. "compared to $18M in 2023") are not
    attributed to the primary value.
    """
    prefix = text[max(0, match_start - 200):match_start]
    suffix = text[match_start:match_start + 200]

    # Trim suffix at the first comparative keyword to avoid picking up
    # the comparative period (e.g. "compared to $18M in 2023")
    comp_match = _COMPARATIVE_CONTEXT.search(suffix)
    if comp_match:
        suffix = suffix[:comp_match.start()]

    window = prefix + suffix

    # FY pattern
    m = re.search(r"\bFY\s?(\d{4})\b", window, re.IGNORECASE)
    if m:
        return f"FY{m.group(1)}"

    # "in 2024" or "for 2024"
    m = re.search(r"(?:in|for)\s+(20\d{2})\b", window, re.IGNORECASE)
    if m:
        return f"FY{m.group(1)}"

    # Quarter
    m = re.search(r"Q([1-4])[\s-]?(20\d{2})", window, re.IGNORECASE)
    if m:
        return f"Q{m.group(1)}-{m.group(2)}"

    return ""


_NON_GAAP_CONTEXT = re.compile(
    r"non[\s-]?gaap|adjusted|pro\s*forma|\bsegment\b|constant\s+currency",
    re.IGNORECASE,
)

_COMPARATIVE_CONTEXT = re.compile(
    r"compared\s+to|versus|vs\.?\s|prior[\s-]year|year[\s-]ago|from\s+\$",
    re.IGNORECASE,
)


_FILING_YEAR_RE = re.compile(
    r"(?:ANNUAL_REPORT_|annual-report-)(20\d{2})",
    re.IGNORECASE,
)

_YEAR_HEADER_RE = re.compile(r"^\s*((?:20\d{2}\s+){3,}20\d{2})\s*$", re.MULTILINE)

_HISTORICAL_REVENUE_ROW_RE = re.compile(
    r"^\s*Revenues?\s+\(as\s+reported[^)]*\)\s+"
    r"(?P<values>(?:\d[\d,]*\s+){3,}\d[\d,]*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_DIVIDEND_HISTORY_HEADER_RE = re.compile(
    r"Dividend\s+for\s+financial\s+year\*?\s+Gross\s+dividend\s+per\s+share",
    re.IGNORECASE,
)

_DIVIDEND_HISTORY_ROW_RE = re.compile(
    r"^\s*(?P<year>20\d{2})\s+€?\s*(?P<value>[\d.,]+)",
    re.MULTILINE,
)

_FCF_BULLET_RE = re.compile(
    r"[•\-\u2022]\s*"
    r"(?P<currency>[$€£¥])\s*"
    r"(?P<value>[\d,.]+)\s*"
    r"(?P<scale>billion|billions|bn|million|millions|mn|thousand|thousands|[MBK])"
    r"\s*"
    r"(?P<label>Net\s+Free\s+cash\s+flow|Free\s+cash\s+flow)\b",
    re.IGNORECASE,
)


def _default_period_from_source(source_filename: str) -> str:
    """Infer FY period from annual-report style filenames."""
    m = _FILING_YEAR_RE.search(source_filename or "")
    if m:
        return f"FY{m.group(1)}"
    return ""


def _extract_historical_revenue_table(
    text: str, source_filename: str = "",
) -> List[NarrativeField]:
    """Extract multi-year revenue rows from historical performance tables."""
    results: List[NarrativeField] = []

    for year_match in _YEAR_HEADER_RE.finditer(text):
        years = re.findall(r"20\d{2}", year_match.group(1))
        if len(years) < 4:
            continue

        block = text[year_match.end():year_match.end() + 600]
        row_match = _HISTORICAL_REVENUE_ROW_RE.search(block)
        if not row_match:
            continue

        values = re.findall(r"\d[\d,]*", row_match.group("values"))
        if len(values) < len(years):
            continue

        for year, raw_value in zip(years, values):
            value = _parse_narrative_number(raw_value)
            if value is None:
                continue
            results.append(
                NarrativeField(
                    label="Revenues",
                    value=value,
                    currency="EUR",
                    scale="millions",
                    period_hint=f"FY{year}",
                    source_location=(
                        f"{source_filename}:historical_revenue_table:char"
                        f"{year_match.start()}"
                    ),
                    confidence="high",
                )
            )
        break

    return results


def _extract_dividend_history_table(
    text: str, source_filename: str = "",
) -> List[NarrativeField]:
    """Extract dividend-per-share rows from historical dividend tables."""
    results: List[NarrativeField] = []

    header_match = _DIVIDEND_HISTORY_HEADER_RE.search(text)
    if not header_match:
        return results

    block = text[header_match.end():header_match.end() + 800]
    for row_match in _DIVIDEND_HISTORY_ROW_RE.finditer(block):
        value = _parse_narrative_number(row_match.group("value"))
        if value is None:
            continue
        year = row_match.group("year")
        results.append(
            NarrativeField(
                label="Gross dividend per share",
                value=value,
                currency="EUR",
                scale="raw",
                period_hint=f"FY{year}",
                source_location=(
                    f"{source_filename}:dividend_history_table:char"
                    f"{header_match.start()}"
                ),
                confidence="high",
            )
        )

    return results


def _extract_fcf_bullets(
    text: str, source_filename: str = "",
) -> List[NarrativeField]:
    """Extract cover-style FCF KPIs from annual-report bullets."""
    results: List[NarrativeField] = []
    default_period = _default_period_from_source(source_filename)

    for match in _FCF_BULLET_RE.finditer(text):
        value = _parse_narrative_number(match.group("value"))
        if value is None:
            continue

        period = _detect_surrounding_period(text, match.start()) or default_period
        if not period:
            continue

        results.append(
            NarrativeField(
                label=match.group("label").strip(),
                value=value,
                currency=_resolve_currency(match.group("currency") or ""),
                scale=_resolve_scale(match.group("scale") or ""),
                period_hint=period,
                source_location=f"{source_filename}:fcf_bullet:char{match.start()}",
                confidence="high",
            )
        )

    return results


def extract_from_narrative(
    text: str, source_filename: str = ""
) -> List[NarrativeField]:
    """Extract financial fields from narrative/prose text.

    Returns list of NarrativeField with label, value, currency, scale, period.
    """
    results: List[NarrativeField] = []

    # Pattern 1: label verb value
    for m in _PATTERN_LABEL_VERB_VALUE.finditer(text):
        value = _parse_narrative_number(m.group("value"))
        if value is None:
            continue
        context = text[max(0, m.start() - 100):m.end() + 100]
        if _NON_GAAP_CONTEXT.search(context):
            continue
        prefix = text[max(0, m.start() - 60):m.start()]
        if _COMPARATIVE_CONTEXT.search(prefix):
            continue
        period = _detect_surrounding_period(text, m.start())
        results.append(
            NarrativeField(
                label=m.group("label").strip(),
                value=value,
                currency=_resolve_currency(m.group("currency") or ""),
                scale=_resolve_scale(m.group("scale") or ""),
                period_hint=period,
                source_location=f"{source_filename}:narrative:char{m.start()}",
                confidence="medium",
            )
        )

    # Pattern 3: value label (reversed order)
    for m in _PATTERN_VALUE_LABEL.finditer(text):
        value = _parse_narrative_number(m.group("value"))
        if value is None:
            continue
        context = text[max(0, m.start() - 100):m.end() + 100]
        if _NON_GAAP_CONTEXT.search(context):
            continue
        prefix = text[max(0, m.start() - 60):m.start()]
        if _COMPARATIVE_CONTEXT.search(prefix):
            continue
        period = _detect_surrounding_period(text, m.start())
        results.append(
            NarrativeField(
                label=m.group("label").strip(),
                value=value,
                currency=_resolve_currency(m.group("currency") or ""),
                scale=_resolve_scale(m.group("scale") or ""),
                period_hint=period,
                source_location=f"{source_filename}:narrative:char{m.start()}",
                confidence="medium",
            )
        )

    results.extend(_extract_historical_revenue_table(text, source_filename))
    results.extend(_extract_dividend_history_table(text, source_filename))
    results.extend(_extract_fcf_bullets(text, source_filename))

    return results


def extract_comparatives(
    text: str, context_label: str = "", source_filename: str = ""
) -> List[NarrativeField]:
    """Extract comparative values ("versus X in Y") from narrative text."""
    results: List[NarrativeField] = []

    for m in _PATTERN_COMPARATIVE.finditer(text):
        value = _parse_narrative_number(m.group("value"))
        if value is None:
            continue

        period = ""
        if m.group("period"):
            raw_period = m.group("period").strip()
            # Normalize period
            pm = re.match(r"(?:FY\s?)?(\d{4})$", raw_period, re.IGNORECASE)
            if pm:
                period = f"FY{pm.group(1)}"
            else:
                period = raw_period.replace(" ", "-")

        results.append(
            NarrativeField(
                label=context_label or "comparative",
                value=value,
                currency=_resolve_currency(m.group("currency") or ""),
                scale=_resolve_scale(m.group("scale") or ""),
                period_hint=period,
                source_location=f"{source_filename}:comparative:char{m.start()}",
                confidence="low",
            )
        )

    return results
