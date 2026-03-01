"""Filing pre-flight metadata extractor.

Ported from 3_0-ELSIAN-INVEST/scripts/runners/filing_preflight.py (319 lines).
100% deterministic, <1ms per filing, 0 LLM tokens.

Detects: language, accounting standard, currency, fiscal year, financial
sections, units per section, restatement signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Language detection ────────────────────────────────────────────────

_LANG_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("en", re.compile(r"\b(?:total\s+(?:assets|liabilities|equity)|net\s+income|revenue|cash\s+flow)\b", re.I), "high"),
    ("fr", re.compile(r"\b(?:r[eé]sultat\s+net|chiffre\s+d['\u2019]affaires|total\s+(?:de\s+l['\u2019]actif|du\s+passif)|flux\s+de\s+tr[eé]sorerie)\b", re.I), "high"),
    ("es", re.compile(r"\b(?:ingresos\s+totales|resultado\s+neto|flujo\s+de\s+(?:caja|efectivo))\b", re.I), "high"),
    ("de", re.compile(r"\b(?:Gesamtverm[oö]gen|Eigenkapital|Jahres[uü]berschuss|Umsatzerl[oö]se)\b", re.I), "medium"),
]


# ── Accounting standard detection ─────────────────────────────────────

_STANDARD_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("IFRS", re.compile(r"\bIFRS\b"), "high"),
    ("IFRS", re.compile(r"\bInternational\s+Financial\s+Reporting\s+Standards\b", re.I), "high"),
    ("US-GAAP", re.compile(r"\bU\.?S\.?\s*GAAP\b", re.I), "high"),
    ("US-GAAP", re.compile(r"\bGenerally\s+Accepted\s+Accounting\s+Principles\b", re.I), "medium"),
    ("FR-GAAP", re.compile(r"\bPlan\s+Comptable\s+G[eé]n[eé]ral\b", re.I), "medium"),
]


# ── Currency detection ────────────────────────────────────────────────

_CURRENCY_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("USD", re.compile(r"\b(?:United\s+States\s+dollars?|US\s*\$|USD)\b", re.I), "high"),
    ("EUR", re.compile(r"\b(?:euros?|EUR|€)\b", re.I), "high"),
    ("GBP", re.compile(r"\b(?:pounds?\s+sterling|GBP|£)\b", re.I), "high"),
    ("CAD", re.compile(r"\b(?:Canadian\s+dollars?|CAD|C\$)\b", re.I), "high"),
    ("AUD", re.compile(r"\b(?:Australian\s+dollars?|AUD|A\$)\b", re.I), "high"),
    ("JPY", re.compile(r"\b(?:Japanese\s+yen|JPY|¥)\b", re.I), "medium"),
    ("CHF", re.compile(r"\b(?:Swiss\s+francs?|CHF)\b", re.I), "medium"),
    ("CNY", re.compile(r"\b(?:Chinese\s+(?:yuan|renminbi)|CNY|RMB)\b", re.I), "medium"),
    ("HKD", re.compile(r"\b(?:Hong\s+Kong\s+dollars?|HKD|HK\$)\b", re.I), "medium"),
]


# ── Section detection ─────────────────────────────────────────────────

_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("income_statement", re.compile(r"\b(?:income\s+statements?|statements?\s+of\s+(?:income|operations|profit|earnings)|compte\s+de\s+r[eé]sultat|profit\s+(?:and|or|&)\s+loss)\b", re.I)),
    ("balance_sheet", re.compile(r"\b(?:balance\s+sheets?|statements?\s+of\s+financial\s+position|bilan\s+consolid[eé]?)\b", re.I)),
    ("cash_flow", re.compile(r"\b(?:cash\s+flows?|statements?\s+of\s+cash\s+flows?|flux\s+de\s+tr[eé]sorerie|tableau\s+des\s+flux)\b", re.I)),
    ("equity", re.compile(r"\b(?:statement\s+of\s+(?:stockholders|shareholders)['\u2019]?\s+equity|variation\s+des\s+capitaux\s+propres)\b", re.I)),
    ("notes", re.compile(r"\b(?:notes\s+to\s+(?:the\s+)?(?:consolidated\s+)?financial\s+statements|notes\s+annexes)\b", re.I)),
    ("mda", re.compile(r"\b(?:management['\u2019]?s?\s+discussion|MD&A|rapport\s+de\s+gestion)\b", re.I)),
]


# ── Units per section detection ───────────────────────────────────────

_UNIT_PATTERNS: list[tuple[str, int, re.Pattern[str]]] = [
    ("billions", 1_000_000_000, re.compile(r"\bin\s+billions?\b", re.I)),
    ("milliards", 1_000_000_000, re.compile(r"\ben\s+milliards?\b", re.I)),
    ("millions", 1_000_000, re.compile(r"\bin\s+millions?\b", re.I)),
    ("millions_fr", 1_000_000, re.compile(r"\ben\s+millions?\s+d['\u2019](?:euros?|dollars?|USD|EUR)\b", re.I)),
    ("millions_sym", 1_000_000, re.compile(r"(?:\$|€|£)\s*millions?\b", re.I)),
    ("eur_millions", 1_000_000, re.compile(r"€\s*(?:M|millions?)\b", re.I)),
    ("thousands", 1_000, re.compile(r"\bin\s+thousands?\b", re.I)),
    ("milliers", 1_000, re.compile(r"\ben\s+milliers?\b", re.I)),
    ("k_dollars", 1_000, re.compile(r"(?:\$|€|£)\s*(?:000s?|thousands?)\b", re.I)),
    ("units", 1, re.compile(r"\bin\s+(?:USD|EUR|GBP)\b", re.I)),
]


# ── Restatement detection ─────────────────────────────────────────────

_RESTATEMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bhave\s+been\s+restated\b", re.I), "high"),
    (re.compile(r"\brestatement\s+of\b", re.I), "high"),
    (re.compile(r"\brestated\s+(?:financial\s+)?(?:statements?|figures?|results?)\b", re.I), "high"),
    (re.compile(r"\bas\s+restated\b", re.I), "high"),
    (re.compile(r"\br[eé]exprim[eé](?:s|es?)?\b", re.I), "high"),
    (re.compile(r"\bretrait[eé](?:s|[eé]es?)?\b", re.I), "medium"),
    (re.compile(r"\*\s*restated\b", re.I), "medium"),
    (re.compile(r"\bpreviously\s+reported\b", re.I), "medium"),
    (re.compile(r"\breclassif(?:ied|ication)\b", re.I), "medium"),
]


# ── Fiscal year detection ─────────────────────────────────────────────

_FY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bfiscal\s+year\s+(?:ended?\s+)?(?:(?:December|June|March|September)\s+\d{1,2},?\s+)?(\d{4})\b", re.I), "high"),
    (re.compile(r"\byear\s+ended?\s+(?:(?:December|June|March|September)\s+\d{1,2},?\s+)?(\d{4})\b", re.I), "high"),
    (re.compile(r"\bFY\s*(\d{4})\b", re.I), "high"),
    (re.compile(r"\bexercice\s+(?:clos\s+le\s+)?(?:\d{1,2}\s+\w+\s+)?(\d{4})\b", re.I), "high"),
    (re.compile(r"\b(?:for\s+the\s+)?(?:twelve|six)\s+months?\s+ended?\b.*?(\d{4})\b", re.I), "medium"),
]


# ── Result dataclass ──────────────────────────────────────────────────

@dataclass
class PreflightResult:
    """Result of filing pre-flight analysis."""

    language: Optional[str] = None
    language_confidence: Optional[str] = None
    accounting_standard: Optional[str] = None
    accounting_standard_confidence: Optional[str] = None
    currency: Optional[str] = None
    currency_confidence: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_year_confidence: Optional[str] = None
    sections_detected: list[str] = field(default_factory=list)
    units_by_section: dict[str, dict[str, Any]] = field(default_factory=dict)
    units_global: Optional[dict[str, Any]] = None
    restatement_detected: bool = False
    restatement_signals: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_confidence": self.language_confidence,
            "accounting_standard": self.accounting_standard,
            "accounting_standard_confidence": self.accounting_standard_confidence,
            "currency": self.currency,
            "currency_confidence": self.currency_confidence,
            "fiscal_year": self.fiscal_year,
            "fiscal_year_confidence": self.fiscal_year_confidence,
            "sections_detected": self.sections_detected,
            "units_by_section": self.units_by_section,
            "units_global": self.units_global,
            "restatement_detected": self.restatement_detected,
            "restatement_signals": self.restatement_signals,
        }


# ── Internal helpers ──────────────────────────────────────────────────

def _find_section_boundaries(text: str) -> list[tuple[str, int, int]]:
    """Find approximate boundaries of financial sections in text."""
    boundaries: list[tuple[str, int, int]] = []
    for section_name, pattern in _SECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 200)
            end = min(len(text), match.start() + 50_000)
            boundaries.append((section_name, start, end))

    boundaries.sort(key=lambda x: x[1])

    # Trim overlapping ends
    for i in range(len(boundaries) - 1):
        if boundaries[i][2] > boundaries[i + 1][1]:
            boundaries[i] = (boundaries[i][0], boundaries[i][1], boundaries[i + 1][1])

    return boundaries


# ── Main preflight function ──────────────────────────────────────────

def preflight(text: str) -> PreflightResult:
    """Run deterministic pre-flight analysis on filing text.

    Args:
        text: The clean.md or raw text of a filing.

    Returns:
        PreflightResult with detected metadata signals.
    """
    result = PreflightResult()

    if not text:
        return result

    # Only analyze first 100K chars for performance
    text_sample = text[:100_000]

    # ── Language ──
    lang_scores: dict[str, int] = {}
    for lang, pattern, _confidence in _LANG_PATTERNS:
        matches = pattern.findall(text_sample)
        if matches:
            lang_scores[lang] = lang_scores.get(lang, 0) + len(matches)
    if lang_scores:
        best_lang = max(lang_scores, key=lang_scores.get)  # type: ignore[arg-type]
        result.language = best_lang
        result.language_confidence = "high" if lang_scores[best_lang] >= 3 else "medium"

    # ── Accounting standard ──
    for standard, pattern, confidence in _STANDARD_PATTERNS:
        if pattern.search(text_sample):
            result.accounting_standard = standard
            result.accounting_standard_confidence = confidence
            break

    # ── Currency ──
    currency_scores: dict[str, int] = {}
    currency_conf: dict[str, str] = {}
    for currency, pattern, confidence in _CURRENCY_PATTERNS:
        matches = pattern.findall(text_sample)
        if matches:
            currency_scores[currency] = currency_scores.get(currency, 0) + len(matches)
            if currency not in currency_conf or confidence == "high":
                currency_conf[currency] = confidence
    if currency_scores:
        best_currency = max(currency_scores, key=currency_scores.get)  # type: ignore[arg-type]
        result.currency = best_currency
        result.currency_confidence = currency_conf.get(best_currency, "medium")

    # ── Fiscal year ──
    for pattern, confidence in _FY_PATTERNS:
        match = pattern.search(text_sample)
        if match:
            year_str = match.group(1)
            try:
                year = int(year_str)
                if 1990 <= year <= 2040:
                    result.fiscal_year = year
                    result.fiscal_year_confidence = confidence
                    break
            except ValueError:
                continue

    # ── Sections ──
    for section_name, pattern in _SECTION_PATTERNS:
        if pattern.search(text_sample):
            result.sections_detected.append(section_name)

    # ── Units by section ──
    section_boundaries = _find_section_boundaries(text_sample)
    for section_name, start, end in section_boundaries:
        section_text = text_sample[start:end]
        for unit_name, multiplier, pattern in _UNIT_PATTERNS:
            if pattern.search(section_text[:2000]):  # Check only header area
                result.units_by_section[section_name] = {
                    "unit": unit_name,
                    "multiplier": multiplier,
                }
                break

    # Global unit: most common unit in first 5K chars
    header_text = text_sample[:5000]
    global_unit_count = 0
    for unit_name, multiplier, pattern in _UNIT_PATTERNS:
        matches = pattern.findall(header_text)
        if matches and len(matches) > global_unit_count:
            result.units_global = {"unit": unit_name, "multiplier": multiplier}
            global_unit_count = len(matches)

    # ── Restatement ──
    for pattern, confidence in _RESTATEMENT_PATTERNS:
        matches = list(pattern.finditer(text_sample))
        if matches:
            signal = {
                "pattern": pattern.pattern[:60],
                "confidence": confidence,
                "count": len(matches),
                "sample": matches[0].group(0)[:80],
            }
            result.restatement_signals.append(signal)
    if result.restatement_signals:
        result.restatement_detected = True

    return result
