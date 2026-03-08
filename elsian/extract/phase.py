"""ExtractPhase -- core extraction orchestrator.

Ported from 3.0 deterministic/src/pipeline.py extract() method.
Iterates filings, detects metadata, runs table + narrative extraction,
resolves aliases, applies scale cascade, handles collision resolution
and additive fields, applies sign convention, and post-processes results.

Adapted for 4.0 models: FieldResult wraps provenance in Provenance dataclass.
"""

from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from elsian.models.field import FieldResult, Provenance
from elsian.models.result import ExtractionResult, PeriodResult, PhaseResult
from elsian.extract.detect import analyze_filing
from elsian.analyze.preflight import preflight as _run_preflight, PreflightResult
from elsian.extract.html_tables import (
    extract_tables_from_clean_md,
    extract_tables_from_text,
    extract_shares_outstanding_from_text,
    TableField,
)
from elsian.extract.vertical import extract_vertical_bs
from elsian.extract.narrative import extract_from_narrative
from elsian.extract.pdf_tables import extract_tables_from_pdf
from elsian.normalize.aliases import AliasResolver
from elsian.normalize.scale import infer_scale_cascade, validate_scale_sanity
from elsian.normalize.audit import AuditLog
from elsian.merge.merger import merge_extractions
from elsian.context import PipelineContext
from elsian.pipeline import PipelinePhase
from elsian.extract.ixbrl_extractor import IxbrlExtractor, make_ixbrl_sort_key


# ── Sign normalisation ───────────────────────────────────────────────
_ALWAYS_POSITIVE_FIELDS = frozenset({
    "cost_of_revenue",
    "sga",
    "research_and_development",
    "depreciation_amortization",
    "interest_expense",
})

_BENEFIT_RE = re.compile(r"\bbenefit\b|\(income\)", re.IGNORECASE)
# Matches labels where "benefit" appears BEFORE "(expense)" — these labels use
# an inverted sign convention (positive=benefit, parens=expense) so we negate.
_BENEFIT_FIRST_RE = re.compile(r"\bbenefit\b.*\(expenses?\)", re.IGNORECASE)


# ── Field → financial statement section mapping ────────────────────────
# Used to select the correct preflight units_by_section scale per field.
_FIELD_SECTION_MAP: dict[str, str] = {
    # Income Statement
    "ingresos": "income_statement",
    "cost_of_revenue": "income_statement",
    "gross_profit": "income_statement",
    "ebitda": "income_statement",
    "ebit": "income_statement",
    "net_income": "income_statement",
    "eps_basic": "income_statement",
    "eps_diluted": "income_statement",
    "research_and_development": "income_statement",
    "sga": "income_statement",
    "depreciation_amortization": "income_statement",
    "interest_expense": "income_statement",
    "income_tax": "income_statement",
    # Balance Sheet
    "total_assets": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "total_equity": "balance_sheet",
    "cash_and_equivalents": "balance_sheet",
    "accounts_receivable": "balance_sheet",
    "inventories": "balance_sheet",
    "accounts_payable": "balance_sheet",
    "total_debt": "balance_sheet",
    # Cash Flow
    "cfo": "cash_flow",
    "capex": "cash_flow",
    "fcf": "cash_flow",
    "dividends_per_share": "cash_flow",
    "shares_outstanding": "cash_flow",
}

# Maps preflight unit_name keys → SCALE_FACTORS keys
_PREFLIGHT_UNIT_TO_SCALE: dict[str, str] = {
    "billions": "billions",
    "milliards": "billions",
    "millions": "millions",
    "millions_fr": "millions",
    "millions_sym": "millions",
    "eur_millions": "millions",
    "thousands": "thousands",
    "milliers": "thousands",
    "k_dollars": "thousands",
    "units": "raw",
}


def _normalize_sign(canonical: str, raw_label: str, value: float) -> float:
    """Ensure expense fields use the correct sign convention.

    Args:
        canonical: Canonical field name.
        raw_label: Raw label from the filing (used to detect benefit keywords).
        value: Parsed numeric value (may be negative from parenthetical or
            explicit minus-sign formatting).
    """
    if canonical in _ALWAYS_POSITIVE_FIELDS:
        return abs(value)
    if canonical == "income_tax":
        # "BENEFIT (EXPENSES)" label: positive=benefit→store negative;
        # parenthesized=expense→store positive.  Negate the parsed value.
        if _BENEFIT_FIRST_RE.search(raw_label):
            return -value
        if value < 0 and not _BENEFIT_RE.search(raw_label):
            return abs(value)
    return value


def _preflight_scale_for_field(
    canonical: str,
    pf: Optional["PreflightResult"],
    fallback: str,
) -> str:
    """Return the scale for *canonical* using preflight units_by_section.

    Priority:
    1. Section-specific scale (income_statement / balance_sheet / cash_flow)
    2. Global scale from preflight
    3. *fallback* (detect.py result)
    """
    if pf is None:
        return fallback
    section = _FIELD_SECTION_MAP.get(canonical)
    if section and section in pf.units_by_section:
        unit_name = pf.units_by_section[section].get("unit", "")
        mapped = _PREFLIGHT_UNIT_TO_SCALE.get(unit_name, "")
        if mapped:
            return mapped
    if pf.units_global:
        unit_name = pf.units_global.get("unit", "")
        mapped = _PREFLIGHT_UNIT_TO_SCALE.get(unit_name, "")
        if mapped:
            return mapped
    return fallback


# ── Dividend per share from equity statement ─────────────────────────
_DIVIDEND_PER_SHARE_RE = re.compile(
    r"Dividend\s+paid\s*\(\s*\$\s*([\d,.]+)\s*per\s+share\s*\)",
    re.IGNORECASE,
)
_BALANCE_DATE_RE = re.compile(
    r"Balance\s+at\s+December\s+31[,]?\s+(20\d{2})",
    re.IGNORECASE,
)
_FINANCIAL_HIGHLIGHTS_TITLE_RE = re.compile(
    r"^\s*FINANCIAL HIGHLIGHTS 2024\s*$",
    re.IGNORECASE,
)
_FINANCIAL_HIGHLIGHTS_DPS_HEADER_RE = re.compile(
    r"\bordinary\s+dividend\s+per\s+share\b",
    re.IGNORECASE,
)
_FINANCIAL_HIGHLIGHTS_DPS_ROW_RE = re.compile(
    r"^\s*(?P<year>20\d{2})\s+\d[\d,.]*m?\s+"
    r"(?P=year)\s+\d[\d,.]*m?\s+"
    r"(?P=year)\s+(?P<value>0?\.\d+)\s*$",
    re.IGNORECASE,
)


def _extract_dividends_per_share(
    text: str, source_filename: str
) -> List[Tuple[str, float, str]]:
    """Extract dividends_per_share from equity statement labels."""
    results: List[Tuple[str, float, str]] = []
    balance_positions: List[Tuple[int, int]] = []
    for m in _BALANCE_DATE_RE.finditer(text):
        balance_positions.append((m.start(), int(m.group(1))))

    for m in _DIVIDEND_PER_SHARE_RE.finditer(text):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        preceding_year = None
        for bpos, byear in reversed(balance_positions):
            if bpos < m.start():
                preceding_year = byear
                break
        if preceding_year is None:
            continue
        period_key = f"FY{preceding_year + 1}"
        loc = f"{source_filename}:equity_statement:char{m.start()}"
        results.append((period_key, value, loc))
    return results


def _extract_financial_highlights_dividends_per_share(
    text: str, source_filename: str
) -> List[TableField]:
    """Extract Somero annual-report DPS from the FY2024 highlights dashboard."""
    results: List[TableField] = []

    lines = text.splitlines()
    title_line_idx = next(
        (
            idx for idx, line in enumerate(lines)
            if _FINANCIAL_HIGHLIGHTS_TITLE_RE.search(line)
        ),
        None,
    )
    if title_line_idx is None:
        return results

    header_line_idx = next(
        (
            idx
            for idx in range(title_line_idx, min(len(lines), title_line_idx + 10))
            if _FINANCIAL_HIGHLIGHTS_DPS_HEADER_RE.search(lines[idx])
        ),
        None,
    )
    if header_line_idx is None:
        return results

    for line_idx in range(header_line_idx + 1, min(len(lines), header_line_idx + 8)):
        row_match = _FINANCIAL_HIGHLIGHTS_DPS_ROW_RE.match(lines[line_idx])
        if not row_match:
            continue
        try:
            value = float(row_match.group("value").replace(",", ""))
        except ValueError:
            continue
        if value <= 0 or value >= 1:
            continue
        year = row_match.group("year")
        results.append(
            TableField(
                label="Dividends per share",
                value=value,
                column_header=f"FY{year}",
                table_index=0,
                source_location=(
                    f"{source_filename}:table:financial_highlights_dps:"
                    f"line{line_idx + 1}"
                ),
                raw_text=lines[line_idx].strip(),
                col_label=f"FY{year}",
                table_title="financial_highlights_dps",
                row_idx=line_idx,
                col_idx=0,
            )
        )
    if {field.column_header for field in results} != {"FY2024", "FY2023"}:
        return []
    return results


# ── Section priority patterns ────────────────────────────────────────
_PRIMARY_IS_SECTION = re.compile(
    r":operating_income|:operating_profit|:consolidated_statements_of_operations"
    r"|:consolidated_statements_of_income"
    r"|:consolidated_balance_sheets|:consolidated_statements_of_comprehensive"
    # Require :tbl suffix to distinguish the *direct* consolidated IS table
    # (section_label ends in :income_from_operations:tblN) from sub-tables
    # such as brand/segment breakdowns (trailing colon → double :: before tbl)
    # or footnote-marked segments (_( suffix, e.g. income_from_operations_(1)).
    r"|:income_from_operations:tbl",
    re.I,
)
_DEPRIORITIZED_SECTION = re.compile(
    r":loss_from_operations"
    r"|:income.*from_operations"
    r"|discontinued_operations"
    r"|:discontinued"
    r"|:net_income_\(loss\)"
    r"|prepaid_income_taxes"
    r"|:income_tax_payable"
    r"|details_of_income_tax"
    r"|:income_taxes\b"
    r"|:income_tax\b"
    r"|components_of_income"
    r"|components_of_results"
    r"|net_income.*margin"
    r"|balance_sheet_data",
    re.I,
)
_STRONGLY_DEPRIORITIZED_SECTION = re.compile(
    r"federal_income_taxes"
    r"|statutory_rate"
    r"|:statements_of_operations:"
    r"|:balance_sheets:"
    r"|:statements_of_cash_flows:"
    r"|the_following_table_presents.*balance_sheet"
    r"|unremitted_earnings"
    r"|undistributed_earnings"
    # Equity-method investee sub-schedules — balance-sheet and income data
    # from the investee's financial statements are NOT parent company data.
    r"|:equity_method_investment"
    # Acquisition fair-value note tables (e.g. HEYDUDE acquisition summary in
    # CROX 10-K) — headed by a liabilities footnote like "Income taxes payable
    # (7)".  These show acquired-entity cash/assets at acquisition date, NOT
    # the parent company's consolidated balances.
    r"|:income_taxes_payable",
    re.I,
)

_TBL_RE = re.compile(r"tbl(\d+)")
_ROW_RE = re.compile(r"row(\d+)")
_COL_RE = re.compile(r"col(\d+)")


def _section_bonus(source_location: str, rules: Optional[Dict] = None,
                   canonical: Optional[str] = None) -> int:
    """Return a priority bonus based on the table's sub-section.

    When *canonical* is ``"total_equity"`` and the source is an
    income-statement section, applies a severe penalty (equity
    never belongs on the IS).

    The severe_penalty default is -300 (not -100) so that high
    label_priority scores (max ~100) cannot cancel the penalty.
    A candidate from a strongly-deprioritised section always
    produces semantic_rank > 0, enabling the merger's replacement
    path for deprioritised existing candidates.
    """
    bonus = 5
    penalty = -5
    severe_penalty = -300
    if rules and "section_weights" in rules:
        sw = rules["section_weights"]
        bonus = sw.get("primary_is_bonus", 5)
        penalty = sw.get("deprioritized_penalty", -5)
        severe_penalty = sw.get("strongly_deprioritized_penalty", -300)
    if _PRIMARY_IS_SECTION.search(source_location):
        base = bonus
    elif _STRONGLY_DEPRIORITIZED_SECTION.search(source_location):
        base = severe_penalty
    elif _DEPRIORITIZED_SECTION.search(source_location):
        base = penalty
    else:
        base = 0

    # total_equity from income-statement is always a misclassification
    # (typically par value or shares outstanding).
    if canonical == "total_equity":
        loc_lower = source_location.lower()
        if ":income_statement:" in loc_lower:
            base = min(base, severe_penalty)

    # Revenue (ingresos) extracted from an IS "net_income" sub-section is
    # always supplemental acquisition pro-forma data, never primary-IS
    # revenue.  Revenue appears at the top of the IS, not nested under a
    # "Net income" heading.
    if canonical == "ingresos":
        loc_lower = source_location.lower()
        if ":income_statement:" in loc_lower and ":net_income:" in loc_lower:
            base = min(base, severe_penalty)

    # Working-capital balance-sheet lines can also appear in "changes in
    # operating assets and liabilities" cash-flow tables nested under
    # a net-income heading. Those rows are movement components, not the
    # balance-sheet ending balances we want for canonical BS fields.
    if canonical in {"accounts_receivable", "inventories", "accounts_payable"}:
        loc_lower = source_location.lower()
        if ":income_statement:" in loc_lower and ":net_income:" in loc_lower:
            base = min(base, severe_penalty)

    # D&A should come from monetary income-statement rows, not from per-share
    # reconciliation tables where the same label can appear as a cents/share
    # add-back component (e.g. GCT 0.01 / 0.06 artifacts).
    if canonical == "depreciation_amortization":
        loc_lower = source_location.lower()
        if ":income_statement:" in loc_lower and any(
            token in loc_lower
            for token in (
                "per_share",
                "per_ordinary_share",
                "per_common_share",
                "per_ads",
            )
        ):
            base = min(base, severe_penalty)

    return base


def _is_balance_sheet_source(source_location: str) -> bool:
    """Return True for balance-sheet-like table/text sources."""
    loc_lower = source_location.lower()
    return ":balance_sheet:" in loc_lower or ":vertical_bs:" in loc_lower


def _source_anchor_prefix(source_location: str) -> str:
    """Return the stable table/section prefix for a source location."""
    return re.sub(r":row\d+(?::col\d+)?$", "", source_location)


def _source_section_prefix(source_location: str) -> str:
    """Return a broader section prefix shared by related balance-sheet tables."""
    if ":tbl" in source_location:
        return re.sub(r":tbl\d+.*$", "", source_location)
    return re.sub(r":[^:]+$", "", source_location)


def _pick_total_liabilities_bridge_components(
    raw_table_fields: List[TableField],
    period_key: str,
    identity_gap: float,
    base_liabilities_value: float,
    base_source_location: str,
) -> List[TableField]:
    """Pick the smallest bridge component set that closes the BS identity gap.

    Some filings present balance-sheet items outside "Total liabilities" but
    still above common equity, e.g. mezzanine equity or redeemable/non-
    controlling interests. When that happens, we keep "total_equity" on the
    face-of-statement basis and fold only the matching bridge component(s) into
    `total_liabilities`.
    """
    if identity_gap <= 0:
        return []

    tolerance = max(1.0, abs(identity_gap) * 0.001)
    component_priority = {
        "redeemable_nci": 0,
        "mezzanine_equity": 1,
        "non_controlling_interest": 2,
    }
    candidates: List[Tuple[str, TableField]] = []
    seen: set[Tuple[str, float, str]] = set()
    anchor_prefixes: set[str] = set()
    anchor_sections: set[str] = set()

    for rtf in raw_table_fields:
        if rtf.column_header != period_key:
            continue
        if re.fullmatch(r"total\s+liabilities", rtf.label.strip(), re.I):
            if abs(rtf.value - base_liabilities_value) <= max(1.0, abs(base_liabilities_value) * 0.001):
                anchor_prefix = _source_anchor_prefix(rtf.source_location)
                anchor_prefixes.add(anchor_prefix)
                anchor_sections.add(_source_section_prefix(anchor_prefix))

    if not anchor_prefixes and base_source_location:
        anchor_prefix = _source_anchor_prefix(base_source_location)
        anchor_prefixes.add(anchor_prefix)
        anchor_sections.add(_source_section_prefix(anchor_prefix))

    for rtf in raw_table_fields:
        if rtf.column_header != period_key:
            continue
        candidate_prefix = _source_anchor_prefix(rtf.source_location)
        candidate_section = _source_section_prefix(candidate_prefix)
        if anchor_prefixes and (
            candidate_prefix not in anchor_prefixes
            and candidate_section not in anchor_sections
        ):
            continue
        if not anchor_prefixes and not _is_balance_sheet_source(rtf.source_location):
            continue

        label_lower = rtf.label.lower()
        if (
            "stockholders" in label_lower or "shareholders" in label_lower
        ) and "equity" in label_lower:
            continue
        if "including portion attributable to noncontrolling interest" in label_lower:
            continue
        if "total liabilities" in label_lower and any(
            token in label_lower
            for token in ("equity", "stockholders", "shareholders")
        ):
            continue

        component_kind = ""
        if re.search(r"redeemable\s+non[- ]?controlling\s+interest", label_lower):
            component_kind = "redeemable_nci"
        elif re.search(r"\bmezzanine\s+equity\b", label_lower):
            component_kind = "mezzanine_equity"
        elif re.search(r"\bnon[- ]?controlling\s+interest\b", label_lower):
            component_kind = "non_controlling_interest"
        else:
            continue

        dedup_key = (component_kind, float(rtf.value), rtf.source_location)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        candidates.append((component_kind, rtf))

    if not candidates:
        return []

    best_combo: List[TableField] = []
    best_rank: Tuple[int, Tuple[int, ...]] | None = None
    max_size = min(3, len(candidates))

    for combo_size in range(1, max_size + 1):
        for combo in combinations(candidates, combo_size):
            combo_value = sum(rtf.value for _, rtf in combo)
            if abs(combo_value - identity_gap) > tolerance:
                continue
            combo_rank = (
                combo_size,
                tuple(sorted(component_priority[kind] for kind, _ in combo)),
            )
            if best_rank is None or combo_rank < best_rank:
                best_rank = combo_rank
                best_combo = [rtf for _, rtf in combo]

    return best_combo


_TOTAL_LIABILITIES_IDENTITY_TOTAL_RE = re.compile(
    r"^total\s+liabilities\b.*\bequity\b",
    re.I,
)


def _pick_total_liabilities_identity_total_row(
    raw_table_fields: List[TableField],
    period_key: str,
    *,
    assets_value: float | None = None,
) -> TableField | None:
    """Pick an explicit identity-total row for total-liabilities bridging.

    Some quarterlies expose the face-of-statement bridge as a total row like
    ``Total Liabilities and Equity`` or
    ``Total Liabilities, Redeemable Non-Controlling Interest and Equity``.
    This helper returns the best row for the requested period, preferring
    actual balance-sheet sections when available.
    """
    tolerance = max(1.0, abs(assets_value) * 0.001) if assets_value is not None else 1.0
    best_row: TableField | None = None
    best_rank: tuple[int, int, int, int] | None = None

    for rtf in raw_table_fields:
        if rtf.column_header != period_key:
            continue

        label_lower = rtf.label.strip().lower()
        if not _TOTAL_LIABILITIES_IDENTITY_TOTAL_RE.search(label_lower):
            continue
        if "including portion attributable to noncontrolling interest" in label_lower:
            continue
        if assets_value is not None and abs(rtf.value - assets_value) > tolerance:
            continue

        rank = (
            0 if _is_balance_sheet_source(rtf.source_location) else 1,
            0 if "redeemable non-controlling interest" in label_lower else 1,
            rtf.table_index if rtf.table_index >= 0 else 9999,
            rtf.row_idx if rtf.row_idx >= 0 else 9999,
        )
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best_row = rtf

    return best_row


def _has_total_liabilities_bridge_context(
    raw_table_fields: List[TableField],
    period_key: str,
    identity_total_row: TableField | None = None,
) -> bool:
    """Return True when the period exposes a bridge component above equity."""
    anchor_prefix = (
        _source_anchor_prefix(identity_total_row.source_location)
        if identity_total_row is not None
        else ""
    )
    anchor_section = (
        _source_section_prefix(anchor_prefix)
        if anchor_prefix
        else ""
    )

    for rtf in raw_table_fields:
        if rtf.column_header != period_key:
            continue

        if anchor_prefix:
            candidate_prefix = _source_anchor_prefix(rtf.source_location)
            candidate_section = _source_section_prefix(candidate_prefix)
            if (
                candidate_prefix != anchor_prefix
                and candidate_section != anchor_section
            ):
                continue

        label_lower = rtf.label.lower()
        if re.search(r"redeemable\s+non[- ]?controlling\s+interest", label_lower):
            return True
        if re.search(r"\bmezzanine\s+equity\b", label_lower):
            return True
        if (
            re.search(r"\bnon[- ]?controlling\s+interest\b", label_lower)
            and "including portion attributable" not in label_lower
        ):
            return True

    return False


def _filing_rank(period_key: str, filing_type: str,
                 rules: Optional[Dict] = None) -> int:
    """Rank a filing type for a given period (lower = better)."""
    if rules and "filing_priority_by_period" in rules:
        priorities = rules["filing_priority_by_period"]
        if period_key.startswith("FY"):
            period_type = "FY"
        elif period_key.startswith("H"):
            period_type = "H"
        else:
            period_type = "Q"
        plist = priorities.get(period_type, [])
        ft_upper = filing_type.upper()
        for idx, ft in enumerate(plist):
            if ft.upper() == ft_upper:
                return idx
        return len(plist)
    from elsian.merge.merger import _filing_priority
    return _filing_priority(filing_type)


def _source_type_rank(source_type: str,
                      rules: Optional[Dict] = None) -> int:
    """Rank a source type (lower = better). table < narrative."""
    if rules and "source_type_priority" in rules:
        plist = rules["source_type_priority"]
        try:
            return plist.index(source_type)
        except ValueError:
            return len(plist)
    return 0 if source_type == "table" else 1


def _parse_stable_order(source_filing: str, source_location: str,
                        rules: Optional[Dict] = None) -> Tuple:
    """Extract stable tiebreak key from filing coords."""
    tbl_m = _TBL_RE.search(source_location)
    row_m = _ROW_RE.search(source_location)
    col_m = _COL_RE.search(source_location)
    tbl_num = int(tbl_m.group(1)) if tbl_m else 0
    row_num = int(row_m.group(1)) if row_m else 0
    col_num = int(col_m.group(1)) if col_m else 0

    tbl_sign = -1
    row_sign = -1
    col_sign = 1
    if rules and "stable_tiebreaker" in rules:
        st = rules["stable_tiebreaker"]
        if st.get("tbl_order", "").startswith("ascending"):
            tbl_sign = 1
        if st.get("row_order", "").startswith("ascending"):
            row_sign = 1
        if st.get("col_order", "").startswith("descending"):
            col_sign = -1

    return (source_filing, tbl_sign * tbl_num, row_sign * row_num, col_sign * col_num)


# Fields that must prefer the PRIMARY filing (the one whose FY tag matches
# the period) to honour "as-reported" semantics. This bucket stays narrow:
# share counts, annual debt snapshots, and trade working-capital balances are
# the remaining point-in-time fields where newer comparative filings were
# still drifting to the wrong column even after source-quality filters.
_SPLIT_SENSITIVE_FIELDS: set = {
    "shares_outstanding",
    "total_debt",
    "accounts_receivable",
    "accounts_payable",
}


# IS fields that commonly appear in supplemental acquisition pro-forma notes
# (e.g. "Net income supplemental disclosure" in CROX 10-K FY2024 covering
# pre-acquisition FY2021 data).  For these fields the pipeline prefers the
# most recent filing that still covers the period in its standard 3-year
# comparative window (gap ≤ 2 years from the filing year).
_SUPPLEMENTAL_PRONE_FIELDS: frozenset = frozenset({"net_income"})

_FY_YEAR_RE = re.compile(r"FY(\d{4})")
_GENERIC_YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
_QUARTER_TOKEN_RE = re.compile(r"Q([1-4])(?:[-_](20\d{2}))?")
_STANDALONE_NET_RESULT_RE = re.compile(
    r"^net\s+(?:income|loss)(?:\s*\(loss\))?\s*$",
    re.I,
)
_PRIMARY_CFO_LABEL_RE = re.compile(
    r"^net\s+cash\s+(?:provided|used)\s+(?:by|in)(?:\s*\(\s*used\s+in\s*\))?\s+operating",
    re.I,
)
_PRIMARY_CAPEX_LABEL_RE = re.compile(
    r"^(?:purchases?|payments?)\s+(?:to\s+acquire\s+)?property,\s*plant\s+and\s+equipment\b",
    re.I,
)
_AUXILIARY_NOTE_MARKERS = (
    "results_of_operations",
    "profit_and_loss_transfer_agreement",
    "interest_and_dividend_income",
    "restructuring_expenses_included",
    "lease_expense",
)
_NOTE_SMALL_VALUE_FIELDS = frozenset({
    "cost_of_revenue",
    "gross_profit",
    "research_and_development",
    "sga",
})
_MONETARY_SCALES = frozenset({"thousands", "millions", "billions"})


def _extract_fy_year(s: str) -> int | None:
    """Parse the fiscal year from a string like 'FY2024' or a filename."""
    m = _FY_YEAR_RE.search(s)
    if m:
        return int(m.group(1))
    years = _GENERIC_YEAR_RE.findall(s)
    return int(years[-1]) if years else None


def _has_explicit_restatement_signal(pf: Optional[PreflightResult]) -> bool:
    """Return True only for explicit restatement / revision evidence."""
    if pf is None or not pf.restatement_detected:
        return False
    if any(
        signal.get("confidence") == "high"
        for signal in pf.restatement_signals
    ):
        return True
    medium_patterns = {
        signal.get("pattern", "")
        for signal in pf.restatement_signals
        if signal.get("confidence") == "medium"
    }
    return (
        any("previously\\s+reported" in pattern for pattern in medium_patterns)
        and any("reclassif" in pattern for pattern in medium_patterns)
    )


def _mark_explicit_restatement_candidate(
    fr: FieldResult,
    period_key: str,
    source_filing: str,
    *,
    restatement_detected: bool,
) -> None:
    """Annotate later comparative candidates from explicitly restated filings."""
    fr._is_explicit_restatement = bool(  # type: ignore[attr-defined]
        restatement_detected
        and period_key.startswith(("Q", "H"))
        and period_key not in source_filing
    )


def _candidate_allows_total_equity_restatement_affinity(
    canonical_field: str | None,
    period_key: str,
    source_filing: str,
    source_type: str,
    source_location: str,
    *,
    ixbrl_total_equity_context: str = "",
) -> bool:
    """Return whether a restated quarterly equity candidate may tie primary."""
    if canonical_field != "total_equity":
        return True
    if not period_key.startswith(("Q", "H")):
        return True
    if period_key in source_filing:
        return True
    if source_type == "ixbrl":
        return ixbrl_total_equity_context == "balance_sheet_restatement"
    if source_type == "narrative":
        return False
    return _is_balance_sheet_source(source_location)


def _candidate_restatement_detected(
    *,
    canonical_field: str | None,
    period_key: str,
    source_filing: str,
    source_type: str,
    source_location: str,
    preflight_result: Optional[PreflightResult],
    ixbrl_total_equity_context: str = "",
) -> bool:
    """Return whether explicit-restatement affinity should apply here."""
    if not _has_explicit_restatement_signal(preflight_result):
        return False
    return _candidate_allows_total_equity_restatement_affinity(
        canonical_field,
        period_key,
        source_filing,
        source_type,
        source_location,
        ixbrl_total_equity_context=ixbrl_total_equity_context,
    )


def _extract_quarter_token(s: str) -> int | None:
    """Parse the quarter number from a period key or filing stem."""
    m = _QUARTER_TOKEN_RE.search(s)
    if not m:
        return None
    return int(m.group(1))


def _period_affinity(period_key: str, source_filing: str,
                     canonical_field: str | None = None,
                     restatement_detected: bool = False) -> int:
    """Return 0 when the filing is the best source for *period_key*, else 1.

    **FY periods — split-sensitive fields** (shares, debt snapshots, trade
    working-capital balances): the primary filing is preferred (FY tag
    matches) so point-in-time values do not drift to a newer comparative
    column.

    **FY periods — supplemental-prone fields** (net_income): prefer the most
    recent filing whose standard 3-year window includes the period.  A filing
    that is 3+ years newer than the period likely only carries that period’s
    data in a supplemental acquisition note (pro-forma), not the primary IS.

    **FY periods — all other fields**: affinity is always 0. The tiebreaker
    becomes filing_rank (lower SRC number = newer filing), so implicit
    restatements / reclassifications in newer comparative columns are
    picked up automatically.

    **Quarterly periods**: prefer the primary filing by default.  However,
    when preflight has already detected an explicit restatement / revision in
    the later filing, allow that comparative to compete on equal affinity for
    prior-year values carried inside the next year's quarterly comparatives.
    ``net_income`` remains same-quarter-only because later Q3 filings can
    carry Q1/Q2 YTD net-income derivations that are not directly comparable to
    the original standalone quarter.
    """
    if period_key.startswith("FY"):
        if canonical_field and canonical_field not in _SPLIT_SENSITIVE_FIELDS:
            # Supplemental-prone fields: penalise filings that are 3+ years
            # newer than the period (standard 3-year look-back boundary).
            if canonical_field in _SUPPLEMENTAL_PRONE_FIELDS:
                period_year = _extract_fy_year(period_key)
                filing_year = _extract_fy_year(source_filing)
                if (
                    period_year is not None
                    and filing_year is not None
                    and filing_year - period_year > 2
                ):
                    return 1
            return 0
        # Split-sensitive (or unknown): prefer primary filing
        fy_tag = period_key
        if fy_tag in source_filing:
            return 0
        return 1
    # Quarterly: prefer primary filing unless the later filing explicitly
    # restates / revises the prior-year comparative.
    if period_key in source_filing:
        return 0
    if restatement_detected:
        period_year = _extract_fy_year(period_key)
        filing_year = _extract_fy_year(source_filing)
        if (
            period_year is not None
            and filing_year is not None
            and 0 < filing_year - period_year <= 1
        ):
            if canonical_field == "net_income":
                period_quarter = _extract_quarter_token(period_key)
                filing_quarter = _extract_quarter_token(source_filing)
                if (
                    period_quarter is not None
                    and filing_quarter is not None
                    and period_quarter != filing_quarter
                ):
                    return 1
            return 0
    return 1


def _candidate_context_bonus(
    canonical: str,
    raw_label: str,
    source_location: str,
    value: float,
    scale: str,
) -> int:
    """Return field-specific context adjustments for candidate ranking."""
    label_lower = raw_label.lower()
    loc_lower = source_location.lower()
    bonus = 0

    if (
        canonical in _NOTE_SMALL_VALUE_FIELDS
        and scale in _MONETARY_SCALES
        and abs(value) < 10000
        and any(marker in loc_lower for marker in _AUXILIARY_NOTE_MARKERS)
    ):
        bonus -= 300

    if canonical == "cfo":
        if "operating lease" in label_lower:
            bonus -= 300
        elif _PRIMARY_CFO_LABEL_RE.search(raw_label):
            bonus += 100
    elif canonical == "capex":
        if _PRIMARY_CAPEX_LABEL_RE.search(raw_label):
            bonus += 100
        if (
            "included in" in label_lower
            and any(
                token in label_lower
                for token in (
                    "accounts payable",
                    "other non-current liabilities",
                    "other current liabilities",
                    "liabilities",
                )
            )
        ):
            bonus -= 300
        if label_lower.lstrip().startswith("accrued "):
            bonus -= 300
    elif canonical == "net_income":
        if _STANDALONE_NET_RESULT_RE.fullmatch(raw_label.strip()):
            bonus += 100
        if any(
            token in label_lower
            for token in (
                "on disposal",
                "reclassification adjustment",
                "redeemable non-controlling",
                "non-controlling interest",
                "included in net income",
                "included in net (loss) income",
            )
        ):
            bonus -= 300
    elif canonical in {"eps_basic", "eps_diluted"}:
        if "weighted_average_number_of_ordinary_shares_used_to_calculate" in loc_lower:
            bonus -= 300
    elif canonical == "total_debt":
        if (
            ":cash_flow:" in loc_lower
            and re.search(r"\b(payment|payments|repayment|proceeds|receipt)\b", label_lower)
        ):
            bonus -= 300

    return bonus


def compute_sort_key(
    period_key: str,
    filing_type: str,
    source_type: str,
    label_priority: int,
    section_bonus_val: int,
    source_filing: str,
    source_location: str,
    rules: Optional[Dict] = None,
    canonical_field: str | None = None,
    restatement_detected: bool = False,
) -> Tuple:
    """Compute a comparable sort key for collision resolution.

    Lower key = better candidate. Comparison order:
    1. filing_rank
    2. period_affinity
    3. source_type_rank
    4. semantic_rank (negated label_priority + section_bonus)
    5. stable_order
    """
    fr = _filing_rank(period_key, filing_type, rules)
    affinity = _period_affinity(
        period_key,
        source_filing,
        canonical_field,
        restatement_detected=restatement_detected,
    )
    src_rank = _source_type_rank(source_type, rules)
    semantic_rank = -(label_priority + section_bonus_val)
    stable = _parse_stable_order(source_filing, source_location, rules)
    return (fr, affinity, src_rank, semantic_rank, stable)


def _make_field_result(
    value: float, scale: str, source_filing: str,
    source_location: str, confidence: str,
    *,
    table_index: int | None = None,
    table_title: str = "",
    row_label: str = "",
    col_label: str = "",
    row: int | None = None,
    col: int | None = None,
    raw_text: str = "",
    extraction_method: str = "",
) -> FieldResult:
    """Create a FieldResult with Provenance from flat args."""
    return FieldResult(
        value=value,
        provenance=Provenance(
            source_filing=source_filing,
            source_location=source_location,
            table_index=table_index,
            table_title=table_title,
            row_label=row_label,
            col_label=col_label,
            row=row,
            col=col,
            raw_text=raw_text,
            extraction_method=extraction_method,
        ),
        scale=scale,
        confidence=confidence,
    )


class ExtractPhase(PipelinePhase):
    """Core extraction orchestrator. Zero LLM calls."""

    def __init__(self, config_dir: str = "") -> None:
        if not config_dir:
            config_dir = str(Path(__file__).parent.parent.parent / "config")
        self._config_dir = config_dir
        self._alias_resolver = AliasResolver(
            str(Path(config_dir) / "field_aliases.json")
        )

    def run(self, context: PipelineContext) -> PhaseResult:
        """PipelinePhase interface: extract from filings in context.case.case_dir."""
        case_dir = context.case.case_dir
        if not case_dir:
            return PhaseResult(
                phase_name="ExtractPhase", success=False, message="No case_dir set",
            )
        result = self.extract(case_dir)

        # Post-extraction sanity checks (informational, non-blocking)
        from elsian.normalize.sanity import run_sanity_checks
        sanity_warnings = run_sanity_checks(result)
        if sanity_warnings:
            import logging as _logging
            _logging.getLogger(__name__).info(
                "%s: %d sanity warning(s) detected",
                result.ticker, len(sanity_warnings),
            )

        context.result = result
        total_fields = sum(len(pr.fields) for pr in result.periods.values())
        msg = (
            f"{result.ticker}: extracted {total_fields} fields across "
            f"{len(result.periods)} periods from {result.filings_used} filings"
        )
        return PhaseResult(phase_name="ExtractPhase", success=True, message=msg)

    def _load_selection_rules(self) -> Dict:
        """Load selection_rules.json from config dir."""
        path = Path(self._config_dir) / "selection_rules.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def extract(self, case_dir: str) -> ExtractionResult:
        """Extract financial data from filings in a case directory."""
        case_path = Path(case_dir)
        filings_dir = case_path / "filings"

        # Read case config
        case_json_path = case_path / "case.json"
        config: Dict = {}
        if case_json_path.exists():
            config = json.loads(case_json_path.read_text(encoding="utf-8"))

        ticker = config.get("ticker", case_path.name)
        currency = config.get("currency", "USD")
        fiscal_year_end_month = int(config.get("fiscal_year_end_month", 12))

        # Load selection rules
        rules = dict(self._load_selection_rules())
        case_overrides = config.get("selection_overrides")
        if case_overrides and isinstance(case_overrides, dict):
            rules.update(case_overrides)

        # Per-case additive_fields: temporarily promote specific canonical
        # fields to additive accumulation for this case only.  This allows
        # filings that report D&A as separate sub-components (PPE, ROU,
        # intangibles) to sum them to the total without changing the global
        # field_aliases.json setting (which would break tickers that have
        # a single D&A row from multiple filing sections).
        _case_additive = set(config.get("additive_fields", []))
        _orig_additive = set(self._alias_resolver._additive)
        if _case_additive:
            self._alias_resolver._additive = _orig_additive | _case_additive

        if not filings_dir.exists() or not any(filings_dir.iterdir()):
            if _case_additive:
                self._alias_resolver._additive = _orig_additive
            return ExtractionResult(ticker=ticker, currency=currency, filings_used=0)

        audit = AuditLog()
        filing_extractions: List[Tuple[str, str, Dict[str, Dict[str, FieldResult]]]] = []
        all_raw_table_fields: List[TableField] = []

        # Build a set of filing prefixes that have .clean.md versions.
        # When a .clean.md exists, narrative extraction from the .txt
        # counterpart is suppressed (the .clean.md has the same content
        # but superior HTML table parsing; narrative values like "$634.4
        # million" would compete incorrectly with exact table values).
        _clean_md_prefixes: set[str] = set()
        for fp in filings_dir.iterdir():
            if fp.name.endswith(".clean.md"):
                _clean_md_prefixes.add(fp.name.rsplit(".clean.md", 1)[0])

        for filing_path in sorted(filings_dir.iterdir()):
            if not filing_path.is_file():
                continue

            suffix = filing_path.suffix.lower()
            if suffix not in {".md", ".txt"}:
                if not filing_path.name.endswith(".clean.md"):
                    continue

            is_clean_md = filing_path.name.endswith(".clean.md")
            text = filing_path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                continue

            metadata = analyze_filing(filing_path.name, text)
            filing_scale = metadata.scale
            filing_scale_confidence = metadata.scale_confidence

            # Run preflight analysis — non-blocking, errors are silent.
            try:
                pf_result: Optional[PreflightResult] = _run_preflight(text)
            except Exception:
                pf_result = None

            period_fields: Dict[str, Dict[str, FieldResult]] = {}
            additive_labels: Dict[str, Dict[str, set]] = {}
            _raw_table_fields: list = []

            if is_clean_md:
                self._extract_from_clean_md(
                    text, filing_path, metadata, filing_scale,
                    filing_scale_confidence, rules, audit,
                    period_fields, additive_labels, _raw_table_fields,
                    preflight_result=pf_result,
                    fiscal_year_end_month=fiscal_year_end_month,
                )
            else:
                # Suppress narrative extraction when a .clean.md with
                # the same prefix exists — the .clean.md has exact table
                # values while narrative produces approximate ones.
                _suppress_narrative = (
                    suffix == ".txt"
                    and filing_path.stem in _clean_md_prefixes
                )
                self._extract_from_txt(
                    text, filing_path, metadata, filing_scale,
                    filing_scale_confidence, rules, audit,
                    period_fields, additive_labels, _raw_table_fields,
                    preflight_result=pf_result,
                    suppress_narrative=_suppress_narrative,
                )

            # Post-process: recover total_liabilities from sub-totals
            self._recover_total_liabilities(
                period_fields, _raw_table_fields, filing_path.name,
                filing_scale, filing_scale_confidence,
            )
            all_raw_table_fields.extend(_raw_table_fields)

            if period_fields:
                filing_extractions.append(
                    (metadata.filing_type, filing_path.name, period_fields)
                )

        # Post-process: EPS duplication (basic and diluted)
        for _ft, _fn, pf in filing_extractions:
            for _pk in pf:
                if "eps_basic" in pf[_pk] and "eps_diluted" not in pf[_pk]:
                    src = pf[_pk]["eps_basic"]
                    pf[_pk]["eps_diluted"] = _make_field_result(
                        src.value, src.scale,
                        src.provenance.source_filing,
                        src.provenance.source_location,
                        src.confidence,
                        table_index=src.provenance.table_index,
                        table_title=src.provenance.table_title,
                        row_label=src.provenance.row_label,
                        col_label=src.provenance.col_label,
                        row=src.provenance.row,
                        col=src.provenance.col,
                        raw_text=src.provenance.raw_text,
                        extraction_method=src.provenance.extraction_method,
                    )
                elif "eps_diluted" in pf[_pk] and "eps_basic" not in pf[_pk]:
                    src = pf[_pk]["eps_diluted"]
                    pf[_pk]["eps_basic"] = _make_field_result(
                        src.value, src.scale,
                        src.provenance.source_filing,
                        src.provenance.source_location,
                        src.confidence,
                        table_index=src.provenance.table_index,
                        table_title=src.provenance.table_title,
                        row_label=src.provenance.row_label,
                        col_label=src.provenance.col_label,
                        row=src.provenance.row,
                        col=src.provenance.col,
                        raw_text=src.provenance.raw_text,
                        extraction_method=src.provenance.extraction_method,
                    )

        # Merge all filing extractions
        result = merge_extractions(
            filing_extractions, ticker=ticker, currency=currency
        )

        # Inject manual_overrides from case.json — ONLY for fields that the
        # extractor could not find (e.g. corrupted PDF sources). If the
        # extractor already produced a value, it always wins.
        self._apply_manual_overrides(config, result)

        # Cross-filing BS bridge: some comparative filings provide the winning
        # liabilities/assets while equity still comes from another filing.
        self._bridge_total_liabilities_after_merge(result, all_raw_table_fields)

        # Restore the alias resolver's original additive set before returning
        # so that per-case additive_fields don't leak into subsequent cases.
        if _case_additive:
            self._alias_resolver._additive = _orig_additive

        # Update audit
        result.audit.fields_extracted += audit.accepted_count
        result.audit.fields_discarded += audit.discarded_count
        result.audit.discarded_reasons.extend(audit.discard_reasons)
        result.audit.discarded_reasons = list(set(result.audit.discarded_reasons))

        return result

    # ── Clean MD extraction ──────────────────────────────────────────

    def _extract_from_clean_md(
        self,
        text: str,
        filing_path: Path,
        metadata: object,
        filing_scale: str,
        filing_scale_confidence: str,
        rules: Dict,
        audit: AuditLog,
        period_fields: Dict[str, Dict[str, FieldResult]],
        additive_labels: Dict[str, Dict[str, set]],
        raw_table_fields: list,
        preflight_result: Optional[PreflightResult] = None,
        fiscal_year_end_month: int = 12,
    ) -> None:
        """Extract from .clean.md files (markdown tables).

        When an iXBRL ``.htm`` sibling exists (same base name), runs
        ``IxbrlExtractor`` first to populate *period_fields* with
        high-confidence iXBRL results.  The subsequent HTML-table extraction
        pass will not overwrite those results because the iXBRL sort key
        (``IXBRL_SRC_TYPE_RANK`` / ``IXBRL_SEMANTIC_RANK``) is always lower
        (higher priority) than any table or narrative sort key.
        """
        # ── iXBRL extraction (primary source where available) ──────────────
        _base = filing_path.name.removesuffix(".clean.md")
        _htm_path = filing_path.parent / (_base + ".htm")
        if _htm_path.exists() and IxbrlExtractor.has_ixbrl(_htm_path):
            _ixbrl_ext = IxbrlExtractor()
            _ixbrl_results = _ixbrl_ext.extract(_htm_path, fiscal_year_end_month)
            for _period, _fields in _ixbrl_results.items():
                if _period not in period_fields:
                    period_fields[_period] = {}
                _fr_rank = _filing_rank(_period, metadata.filing_type, rules)
                for _field_name, _fr in _fields.items():
                    _was_rescaled = getattr(_fr, "_ixbrl_was_rescaled", False)
                    _candidate_restated = _candidate_restatement_detected(
                        canonical_field=_field_name,
                        period_key=_period,
                        source_filing=_htm_path.stem,
                        source_type="ixbrl",
                        source_location=getattr(
                            _fr.provenance,
                            "source_location",
                            "",
                        ),
                        preflight_result=preflight_result,
                        ixbrl_total_equity_context=getattr(
                            _fr,
                            "_ixbrl_total_equity_context",
                            "",
                        ),
                    )
                    _affinity_override = _period_affinity(
                        _period,
                        _htm_path.stem,
                        _field_name,
                        restatement_detected=_candidate_restated,
                    )
                    _ixbrl_sk = make_ixbrl_sort_key(
                        _period, _htm_path.stem, _fr_rank,
                        affinity_override=_affinity_override,
                        was_rescaled=_was_rescaled,
                    )
                    _fr._sort_key = _ixbrl_sk  # type: ignore[attr-defined]
                    _mark_explicit_restatement_candidate(
                        _fr,
                        _period,
                        _htm_path.stem,
                        restatement_detected=_candidate_restated,
                    )
                    period_fields[_period][_field_name] = _fr
                    audit.accept(
                        field_name=_field_name,
                        period=_period,
                        source_filing=_htm_path.name,
                        raw_label=_fr.provenance.row_label,
                        raw_value=_fr.value,
                        scale=_fr.scale,
                    )

        # ── HTML table extraction (fills gaps not covered by iXBRL) ────────
        table_fields = extract_tables_from_clean_md(
            text, source_filename=filing_path.name,
            filing_type=metadata.filing_type,
        )
        raw_table_fields.extend(table_fields)

        for tf in table_fields:
            self._process_table_field(
                tf, filing_path, metadata, filing_scale,
                filing_scale_confidence, rules, audit,
                period_fields, additive_labels,
                source_type="table",
                use_section_bonus=True,
                preflight_result=preflight_result,
            )

        # Dedicated shares_outstanding extraction — the main table extractor
        # often assigns col='unknown' to shares rows in EPS-note tables
        # (column headers are non-standard). The dedicated regex extractor
        # scans the full text and uses year-context headers to assign the
        # correct period, picking up values the table extractor misses.
        for tf in extract_shares_outstanding_from_text(
            text, source_filename=filing_path.name,
        ):
            self._process_table_field(
                tf, filing_path, metadata, filing_scale,
                filing_scale_confidence, rules, audit,
                period_fields, additive_labels,
                source_type="table",
                use_section_bonus=False,
                preflight_result=preflight_result,
            )

        # Dividend per share from equity statement
        for dps_period, dps_value, dps_loc in _extract_dividends_per_share(
            text, filing_path.name
        ):
            if dps_period not in period_fields:
                period_fields[dps_period] = {}
            if "dividends_per_share" not in period_fields[dps_period]:
                fr = _make_field_result(
                    dps_value, "raw", filing_path.name, dps_loc, "high",
                    table_index=0,
                    table_title="equity_statement",
                    row_label="Dividend paid ($ per share)",
                    col_label=dps_period,
                    row=0,
                    col=0,
                    raw_text=str(dps_value),
                    extraction_method="table",
                )
                period_fields[dps_period]["dividends_per_share"] = fr
                audit.accept(
                    field_name="dividends_per_share",
                    period=dps_period,
                    source_filing=filing_path.name,
                    raw_label="Dividend paid ($ per share)",
                    raw_value=dps_value,
                    scale="raw",
                )

    # ── TXT extraction ───────────────────────────────────────────────

    def _extract_from_txt(
        self,
        text: str,
        filing_path: Path,
        metadata: object,
        filing_scale: str,
        filing_scale_confidence: str,
        rules: Dict,
        audit: AuditLog,
        period_fields: Dict[str, Dict[str, FieldResult]],
        additive_labels: Dict[str, Dict[str, set]],
        raw_table_fields: list,
        preflight_result: Optional[PreflightResult] = None,
        suppress_narrative: bool = False,
    ) -> None:
        """Extract from .txt files (space-aligned tables + narrative).

        Args:
            suppress_narrative: When True, skip the narrative extraction
                pass.  Used when a .clean.md counterpart exists for the
                same filing — the .clean.md already produced exact table
                values and narrative would introduce approximate duplicates.
        """
        txt_table_fields = extract_tables_from_text(
            text, source_filename=filing_path.name,
        )
        raw_table_fields.extend(txt_table_fields)

        for tf in txt_table_fields:
            self._process_table_field(
                tf, filing_path, metadata, filing_scale,
                filing_scale_confidence, rules, audit,
                period_fields, additive_labels,
                source_type="table",
                use_section_bonus=False,
                preflight_result=preflight_result,
            )

        for tf in _extract_financial_highlights_dividends_per_share(
            text, source_filename=filing_path.name
        ):
            self._process_table_field(
                tf, filing_path, metadata, filing_scale,
                filing_scale_confidence, rules, audit,
                period_fields, additive_labels,
                source_type="table",
                use_section_bonus=False,
                preflight_result=preflight_result,
            )

        # ── Dedicated shares_outstanding extraction ──────
        # Shares data often lives in Notes sections, beyond the
        # 120-line section cap.  A dedicated regex extractor
        # searches the full text for weighted-average share counts.
        for tf in extract_shares_outstanding_from_text(
            text, source_filename=filing_path.name,
        ):
            self._process_table_field(
                tf, filing_path, metadata, filing_scale,
                filing_scale_confidence, rules, audit,
                period_fields, additive_labels,
                source_type="table",
                use_section_bonus=False,
                preflight_result=preflight_result,
            )

        # ── Vertical-format consolidated BS extraction ───
        # EDGAR .txt may have the consolidated BS in a vertical
        # layout (one label per line) that the space-aligned
        # parser cannot handle.  This targeted extractor pulls
        # key BS totals directly.  A high section_bonus (+20)
        # ensures these authoritative consolidated values beat
        # Schedule I / parent-only values from other sources.
        _VERTICAL_BS_BONUS = 20
        vertical_bs_fields = extract_vertical_bs(
            text, source_filename=filing_path.name,
        )
        raw_table_fields.extend(vertical_bs_fields)
        for tf in vertical_bs_fields:
            canonical = self._alias_resolver.resolve(tf.label)
            if canonical is None:
                # Synthetic labels (e.g. "Total debt (current +
                # long-term)") may not resolve via aliases.
                # The source_location encodes the canonical name.
                loc = tf.source_location
                if ":total_debt" in loc:
                    canonical = "total_debt"
                elif ":total_assets" in loc:
                    canonical = "total_assets"
                elif ":total_liabilities" in loc:
                    canonical = "total_liabilities"
                elif ":total_equity" in loc:
                    canonical = "total_equity"
                elif ":cash_and_equivalents" in loc:
                    canonical = "cash_and_equivalents"
            if canonical is None:
                continue

            field_mult = self._alias_resolver.get_multiplier(canonical)
            pf_scale = _preflight_scale_for_field(canonical, preflight_result, metadata.scale)
            scale, confidence = infer_scale_cascade(
                filing_scale, "", pf_scale, field_mult
            )

            if not validate_scale_sanity(tf.value, canonical, scale):
                audit.discard(
                    field_name=canonical,
                    period=tf.column_header,
                    reason="scale_uncertain",
                    source_filing=filing_path.name,
                    raw_label=tf.label,
                    raw_value=tf.value,
                )
                continue

            period_key = tf.column_header
            if not period_key or not period_key.startswith("FY"):
                continue

            label_pri = self._alias_resolver.label_priority(
                canonical, tf.label
            )
            vertical_bonus = (
                _VERTICAL_BS_BONUS
                if canonical in {"total_assets", "total_liabilities", "total_equity"}
                else 0
            )
            candidate_restated = _candidate_restatement_detected(
                canonical_field=canonical,
                period_key=period_key,
                source_filing=filing_path.name,
                source_type="table",
                source_location=tf.source_location,
                preflight_result=preflight_result,
            )

            new_sort_key = compute_sort_key(
                period_key=period_key,
                filing_type=metadata.filing_type,
                source_type="table",
                label_priority=label_pri,
                section_bonus_val=vertical_bonus,
                source_filing=filing_path.name,
                source_location=tf.source_location,
                rules=rules,
                canonical_field=canonical,
                restatement_detected=candidate_restated,
            )

            if period_key not in period_fields:
                period_fields[period_key] = {}

            if canonical in period_fields[period_key]:
                existing = period_fields[period_key][canonical]
                old_sort_key = getattr(
                    existing, "_sort_key",
                    (999, 999, 999, 999, (999,)),
                )
                if new_sort_key >= old_sort_key:
                    audit.discard(
                        field_name=canonical,
                        period=period_key,
                        reason="lower_priority_duplicate",
                        source_filing=filing_path.name,
                        raw_label=tf.label,
                        raw_value=tf.value,
                        scale=scale,
                    )
                    continue

            fr = _make_field_result(
                _normalize_sign(canonical, tf.label, tf.value),
                scale, filing_path.name, tf.source_location, confidence,
                table_index=tf.table_index if tf.table_index >= 0 else None,
                table_title=tf.table_title,
                row_label=tf.label,
                col_label=tf.col_label,
                row=tf.row_idx if tf.row_idx >= 0 else None,
                col=tf.col_idx if tf.col_idx >= 0 else None,
                raw_text=tf.raw_text,
                extraction_method="table",
            )
            fr._sort_key = new_sort_key  # type: ignore[attr-defined]
            _mark_explicit_restatement_candidate(
                fr,
                period_key,
                filing_path.name,
                restatement_detected=candidate_restated,
            )
            period_fields[period_key][canonical] = fr
            audit.accept(
                field_name=canonical,
                period=period_key,
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )

        # ── PDF structured table extraction ────────────────────
        # If a .pdf sibling exists for this .txt, run the PDF table
        # extractor for structured data.  Results feed into the same
        # _process_table_field pipeline — additive to text extraction.
        pdf_sibling = filing_path.with_suffix(".pdf")
        if pdf_sibling.exists():
            pdf_table_fields = extract_tables_from_pdf(
                str(pdf_sibling), filing_source_id=filing_path.name,
            )
            for tf in pdf_table_fields:
                # Override extraction_method via raw_text prefix for
                # provenance tracking — the TableField itself only
                # carries data; the _process_table_field path sets
                # extraction_method="table".  We'll patch provenance
                # after creation.
                self._process_table_field(
                    tf, filing_path, metadata, filing_scale,
                    filing_scale_confidence, rules, audit,
                    period_fields, additive_labels,
                    source_type="table",
                    use_section_bonus=False,
                    preflight_result=preflight_result,
                )

        # Narrative extraction — skipped when a .clean.md counterpart
        # already provided table-parsed values for this filing.
        if suppress_narrative:
            return

        narrative_fields = extract_from_narrative(
            text, source_filename=filing_path.name
        )
        for nf in narrative_fields:
            canonical = self._alias_resolver.resolve(nf.label)
            if canonical is None:
                audit.discard(
                    field_name=nf.label,
                    period=nf.period_hint,
                    reason="label_ambiguous",
                    source_filing=filing_path.name,
                    raw_label=nf.label,
                    raw_value=nf.value,
                )
                continue

            scale = nf.scale if nf.scale != "raw" else filing_scale
            confidence = "medium" if nf.scale != "raw" else filing_scale_confidence
            period_key = nf.period_hint
            if not period_key:
                audit.discard(
                    field_name=canonical, period="unknown",
                    reason="period_unknown",
                    source_filing=filing_path.name,
                    raw_label=nf.label, raw_value=nf.value, scale=scale,
                )
                continue

            if period_key not in period_fields:
                period_fields[period_key] = {}

            new_lp = self._alias_resolver.label_priority(canonical, nf.label)
            candidate_restated = _candidate_restatement_detected(
                canonical_field=canonical,
                period_key=period_key,
                source_filing=filing_path.name,
                source_type="narrative",
                source_location=nf.source_location,
                preflight_result=preflight_result,
            )
            new_sk = compute_sort_key(
                period_key=period_key,
                filing_type=metadata.filing_type,
                source_type="narrative",
                label_priority=new_lp,
                section_bonus_val=0,
                source_filing=filing_path.name,
                source_location=nf.source_location,
                rules=rules,
                canonical_field=canonical,
                restatement_detected=candidate_restated,
            )
            if canonical in period_fields[period_key]:
                existing = period_fields[period_key][canonical]
                old_sk = getattr(existing, "_sort_key", (999, 999, 0, ("", 0, 0, 0)))
                if new_sk >= old_sk:
                    audit.discard(
                        field_name=canonical, period=period_key,
                        reason="lower_priority_duplicate",
                        source_filing=filing_path.name,
                        raw_label=nf.label, raw_value=nf.value, scale=scale,
                    )
                    continue

            fr = _make_field_result(
                _normalize_sign(canonical, nf.label, nf.value),
                scale, filing_path.name, nf.source_location, confidence,
                raw_text=nf.label,
                extraction_method="narrative",
            )
            fr._sort_key = new_sk  # type: ignore[attr-defined]
            _mark_explicit_restatement_candidate(
                fr,
                period_key,
                filing_path.name,
                restatement_detected=candidate_restated,
            )
            period_fields[period_key][canonical] = fr
            audit.accept(
                field_name=canonical, period=period_key,
                source_filing=filing_path.name,
                raw_label=nf.label, raw_value=nf.value, scale=scale,
            )

    # ── Common table field processing ────────────────────────────────

    def _process_table_field(
        self,
        tf: TableField,
        filing_path: Path,
        metadata: object,
        filing_scale: str,
        filing_scale_confidence: str,
        rules: Dict,
        audit: AuditLog,
        period_fields: Dict[str, Dict[str, FieldResult]],
        additive_labels: Dict[str, Dict[str, set]],
        source_type: str = "table",
        use_section_bonus: bool = True,
        preflight_result: Optional[PreflightResult] = None,
    ) -> None:
        """Process a single TableField through alias resolution, scale, and collision handling."""
        canonical = self._alias_resolver.resolve(tf.label)
        if canonical is None:
            audit.discard(
                field_name=tf.label, period=tf.column_header,
                reason="label_ambiguous",
                source_filing=filing_path.name,
                raw_label=tf.label, raw_value=tf.value,
            )
            return

        field_mult = self._alias_resolver.get_multiplier(canonical)
        pf_scale = _preflight_scale_for_field(canonical, preflight_result, metadata.scale)
        scale, confidence = infer_scale_cascade(
            filing_scale, "", pf_scale, field_mult
        )

        if not validate_scale_sanity(tf.value, canonical, scale):
            audit.discard(
                field_name=canonical, period=tf.column_header,
                reason="scale_uncertain",
                source_filing=filing_path.name,
                raw_label=tf.label, raw_value=tf.value, scale=scale,
            )
            return

        # Reject negative total_debt from IS sections — on
        # the income statement, negative values matching the
        # total_debt alias are always something else (e.g.
        # "Loss on extinguishment of debt").
        if (canonical == "total_debt"
                and tf.value < 0
                and ":income_statement:" in tf.source_location.lower()):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="negative_debt_in_IS",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if canonical == "total_debt" and ":cash_flow:" in tf.source_location.lower():
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="cashflow_debt_movement_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical in {"accounts_receivable", "accounts_payable"}
            and ":cash_flow:" in tf.source_location.lower()
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="cashflow_working_capital_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical in {"accounts_receivable", "accounts_payable"}
            and any(
                marker in tf.source_location.lower()
                for marker in (
                    ":income_statement:net_income:",
                    ":income_statement:net_(loss)_income:",
                    ":income_statement:deferred_income_taxes:",
                    ":income_statement:prepaid_income_taxes:",
                )
            )
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="income_statement_working_capital_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical == "accounts_payable"
            and "included in accounts payable" in tf.label.lower()
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="accounts_payable_component_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical == "total_liabilities"
            and ":income_statement:" in tf.source_location.lower()
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="income_statement_liabilities_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical == "total_liabilities"
            and any(
                token in tf.label.lower()
                for token in ("equity", "stockholders", "shareholders")
            )
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="liabilities_plus_equity_total_not_liabilities",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return
        if (
            canonical == "total_liabilities"
            and any(
                marker in tf.source_location.lower()
                for marker in (
                    ":income_statement:accumulated_other_comprehensive_income:",
                    ":income_statement:less:_net_income_attributable_to_non-controlling_interest:",
                )
            )
        ):
            audit.discard(
                field_name=canonical,
                period=tf.column_header,
                reason="income_statement_total_liabilities_not_balance",
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )
            return

        period_key = tf.column_header
        if not period_key or period_key == "unknown":
            audit.discard(
                field_name=canonical, period="unknown",
                reason="period_unknown",
                source_filing=filing_path.name,
                raw_label=tf.label, raw_value=tf.value, scale=scale,
            )
            return

        if period_key not in period_fields:
            period_fields[period_key] = {}

        new_lp = self._alias_resolver.label_priority(canonical, tf.label)
        sec_bonus = _section_bonus(tf.source_location, rules, canonical=canonical) if use_section_bonus else 0
        if not use_section_bonus:
            loc_lower = tf.source_location.lower()
            if any(s in loc_lower for s in ("income_statement", "balance_sheet", "cash_flow")):
                sec_bonus = 3 if "income_statement" in loc_lower else 1
            # Always enforce canonical-specific section penalties even for
            # .txt extraction.  Without this, the +3 income_statement
            # fallback above would give acquisition-note tables (e.g.
            # income_taxes_payable) or supplemental sections (e.g.
            # net_income sub-section in a pro-forma note) an inflated score
            # that beats the correct primary-IS candidate from another
            # filing in the merger.  Apply only when the override is a
            # penalty (< 0) so that neutral sections (returning 0) do not
            # inadvertently reduce the +3 income_statement fallback.
            _canonical_override = _section_bonus(
                tf.source_location, rules, canonical=canonical
            )
            if _canonical_override < 0:
                sec_bonus = min(sec_bonus, _canonical_override)
        sec_bonus += _candidate_context_bonus(
            canonical,
            tf.label,
            tf.source_location,
            tf.value,
            scale,
        )
        candidate_restated = _candidate_restatement_detected(
            canonical_field=canonical,
            period_key=period_key,
            source_filing=filing_path.name,
            source_type=source_type,
            source_location=tf.source_location,
            preflight_result=preflight_result,
        )
        new_sk = compute_sort_key(
            period_key=period_key,
            filing_type=metadata.filing_type,
            source_type=source_type,
            label_priority=new_lp,
            section_bonus_val=sec_bonus,
            source_filing=filing_path.name,
            source_location=tf.source_location,
            rules=rules,
            canonical_field=canonical,
            restatement_detected=candidate_restated,
        )

        if canonical in period_fields[period_key]:
            existing = period_fields[period_key][canonical]
            norm_lbl = self._alias_resolver._normalize(tf.label)

            # Additive fields
            if self._alias_resolver.is_additive(canonical):
                # If the existing slot was filled by iXBRL, skip additive
                # accumulation.  iXBRL provides complete totals (e.g.
                # us-gaap:Liabilities = total liabilities), not individual
                # components.  Summation would double-count them.
                # Fall through to normal sort-key collision resolution.
                _existing_method = getattr(
                    existing.provenance, "extraction_method", ""
                )
                if _existing_method != "ixbrl":
                    seen = additive_labels.get(period_key, {}).get(canonical, set())
                    if use_section_bonus:
                        is_new = not any(s in norm_lbl or norm_lbl in s for s in seen)
                    else:
                        dedup_key = norm_lbl + "|" + tf.source_location
                        is_new = dedup_key not in seen

                    if is_new:
                        combined_value = existing.value + _normalize_sign(
                            canonical, tf.label, tf.value
                        )
                        ep = existing.provenance
                        fr = _make_field_result(
                            combined_value, existing.scale,
                            ep.source_filing,
                            ep.source_location,
                            existing.confidence,
                            table_index=ep.table_index,
                            table_title=ep.table_title,
                            row_label=ep.row_label,
                            col_label=ep.col_label,
                            row=ep.row,
                            col=ep.col,
                            raw_text=ep.raw_text,
                            extraction_method=ep.extraction_method or "table",
                        )
                        fr._sort_key = existing._sort_key  # type: ignore[attr-defined]
                        period_fields[period_key][canonical] = fr
                        if use_section_bonus:
                            additive_labels.setdefault(period_key, {}).setdefault(canonical, set()).add(norm_lbl)
                        else:
                            additive_labels.setdefault(period_key, {}).setdefault(canonical, set()).add(dedup_key)
                        audit.accept(
                            field_name=canonical, period=period_key,
                            source_filing=filing_path.name,
                            raw_label=tf.label, raw_value=tf.value, scale=scale,
                        )
                        return
                    if len(seen) == 1:
                        # Allow duplicate replacement only while the field is
                        # still a single constituent; once multiple additive
                        # labels have been merged, replacing the aggregate with
                        # a later duplicate would collapse the total back to a
                        # single component.
                        pass
                    else:
                        audit.discard(
                            field_name=canonical, period=period_key,
                            reason="additive_duplicate_constituent",
                            source_filing=filing_path.name,
                            raw_label=tf.label, raw_value=tf.value, scale=scale,
                        )
                        return
                # else: existing is iXBRL → fall through to normal collision resolution

            # Normal collision resolution
            old_sk = getattr(existing, "_sort_key", (999, 999, 0, ("", 0, 0, 0)))
            if new_sk >= old_sk:
                audit.discard(
                    field_name=canonical, period=period_key,
                    reason="lower_priority_duplicate",
                    source_filing=filing_path.name,
                    raw_label=tf.label, raw_value=tf.value, scale=scale,
                )
                return

        # Determine extraction_method: "pdf_table" when the source_location
        # contains "pdf_tbl" (set by extract_tables_from_pdf), else "table".
        _ext_method = "pdf_table" if "pdf_tbl" in tf.source_location else "table"

        fr = _make_field_result(
            _normalize_sign(canonical, tf.label, tf.value),
            scale, filing_path.name, tf.source_location, confidence,
            table_index=tf.table_index if tf.table_index >= 0 else None,
            table_title=tf.table_title,
            row_label=tf.label,
            col_label=tf.col_label,
            row=tf.row_idx if tf.row_idx >= 0 else None,
            col=tf.col_idx if tf.col_idx >= 0 else None,
            raw_text=tf.raw_text,
            extraction_method=_ext_method,
        )
        fr._sort_key = new_sk  # type: ignore[attr-defined]
        _mark_explicit_restatement_candidate(
            fr,
            period_key,
            filing_path.name,
            restatement_detected=candidate_restated,
        )

        # Populate preflight metadata on provenance
        if preflight_result is not None:
            fr.provenance.preflight_currency = preflight_result.currency or ""
            fr.provenance.preflight_standard = preflight_result.accounting_standard or ""
            section = _FIELD_SECTION_MAP.get(canonical)
            if section and section in preflight_result.units_by_section:
                fr.provenance.preflight_units_hint = (
                    preflight_result.units_by_section[section].get("unit", "")
                )
            elif preflight_result.units_global:
                fr.provenance.preflight_units_hint = (
                    preflight_result.units_global.get("unit", "")
                )

        period_fields[period_key][canonical] = fr

        if self._alias_resolver.is_additive(canonical):
            norm_lbl = self._alias_resolver._normalize(tf.label)
            if use_section_bonus:
                additive_labels.setdefault(period_key, {}).setdefault(canonical, set()).add(norm_lbl)
            else:
                dedup_seed = norm_lbl + "|" + tf.source_location
                additive_labels.setdefault(period_key, {}).setdefault(canonical, set()).add(dedup_seed)

        audit.accept(
            field_name=canonical, period=period_key,
            source_filing=filing_path.name,
            raw_label=tf.label, raw_value=tf.value, scale=scale,
        )

    # ── Post-processing ──────────────────────────────────────────────

    @staticmethod
    def _recover_total_liabilities(
        period_fields: Dict[str, Dict[str, FieldResult]],
        raw_table_fields: list,
        source_filename: str,
        filing_scale: str,
        filing_scale_confidence: str,
    ) -> None:
        """Recover or bridge total_liabilities from BS sub-totals/components."""
        _NC_LIAB_RE = re.compile(r"total\s+non[- ]?current\s+liabilities", re.I)
        _C_LIAB_RE = re.compile(r"total\s+current\s+liabilities", re.I)

        for pk in list(period_fields.keys()):
            if "total_liabilities" not in period_fields[pk]:
                nc_val = None
                c_val = None
                nc_loc = ""
                nc_rtf = None
                for rtf in raw_table_fields:
                    if rtf.column_header != pk:
                        continue
                    if _NC_LIAB_RE.search(rtf.label):
                        nc_val = rtf.value
                        nc_loc = rtf.source_location
                        nc_rtf = rtf
                    elif _C_LIAB_RE.search(rtf.label):
                        c_val = rtf.value
                if nc_val is not None and c_val is not None:
                    period_fields[pk]["total_liabilities"] = _make_field_result(
                        nc_val + c_val, filing_scale,
                        source_filename, nc_loc,
                        filing_scale_confidence,
                        table_index=nc_rtf.table_index if nc_rtf and nc_rtf.table_index >= 0 else None,
                        table_title=nc_rtf.table_title if nc_rtf else "",
                        row_label="total_liabilities (computed: non-current + current)",
                        col_label=nc_rtf.col_label if nc_rtf else "",
                        row=nc_rtf.row_idx if nc_rtf and nc_rtf.row_idx >= 0 else None,
                        col=nc_rtf.col_idx if nc_rtf and nc_rtf.col_idx >= 0 else None,
                        raw_text=f"{nc_val} + {c_val}",
                        extraction_method="table",
                    )

            assets = period_fields[pk].get("total_assets")
            liabilities = period_fields[pk].get("total_liabilities")
            equity = period_fields[pk].get("total_equity")
            identity_total_row = (
                _pick_total_liabilities_identity_total_row(
                    raw_table_fields,
                    pk,
                    assets_value=assets.value if assets else None,
                )
                if equity
                else None
            )

            if equity and liabilities is None and identity_total_row:
                identity_total_tolerance = max(
                    1.0,
                    abs(identity_total_row.value) * 0.001,
                )
                derived_total_liabilities = identity_total_row.value - equity.value
                should_use_identity_total = _has_total_liabilities_bridge_context(
                    raw_table_fields,
                    pk,
                    identity_total_row,
                )

                if should_use_identity_total and derived_total_liabilities > 0:
                    base_field = equity
                    base_prov = base_field.provenance
                    adjusted = _make_field_result(
                        derived_total_liabilities,
                        base_field.scale,
                        source_filename,
                        f"{identity_total_row.source_location}:bs_identity_bridge",
                        base_field.confidence,
                        table_index=identity_total_row.table_index
                        if identity_total_row.table_index >= 0
                        else None,
                        table_title=identity_total_row.table_title,
                        row_label=(
                            "total_liabilities "
                            "(computed: total liabilities and equity - total equity)"
                        ),
                        col_label=identity_total_row.col_label,
                        row=identity_total_row.row_idx
                        if identity_total_row.row_idx >= 0
                        else None,
                        col=identity_total_row.col_idx
                        if identity_total_row.col_idx >= 0
                        else None,
                        raw_text=f"{identity_total_row.value} - {equity.value}",
                        extraction_method="table",
                    )
                    adjusted.provenance.preflight_currency = (
                        base_prov.preflight_currency
                    )
                    adjusted.provenance.preflight_standard = (
                        base_prov.preflight_standard
                    )
                    adjusted.provenance.preflight_units_hint = (
                        base_prov.preflight_units_hint
                    )
                    adjusted._sort_key = getattr(equity, "_sort_key", None)  # type: ignore[attr-defined]
                    period_fields[pk]["total_liabilities"] = adjusted
                    liabilities = adjusted

            if not assets or not liabilities or not equity:
                continue

            identity_gap = assets.value - (liabilities.value + equity.value)
            tolerance = max(1.0, abs(assets.value) * 0.001)
            if identity_gap <= tolerance:
                continue

            bridge_fields = _pick_total_liabilities_bridge_components(
                raw_table_fields,
                pk,
                identity_gap,
                liabilities.value,
                liabilities.provenance.source_location,
            )
            bridge_value = sum(field.value for field in bridge_fields)
            same_filing_identity_bridge = (
                assets.provenance.source_filing
                and assets.provenance.source_filing == liabilities.provenance.source_filing
                and liabilities.provenance.source_filing == equity.provenance.source_filing
                and _has_total_liabilities_bridge_context(raw_table_fields, pk)
            )
            if not bridge_fields and not same_filing_identity_bridge:
                continue

            existing = liabilities
            existing_prov = existing.provenance
            row_label = existing_prov.row_label or "Total liabilities"
            if bridge_fields and abs(bridge_value - identity_gap) <= tolerance:
                adjusted_value = existing.value + bridge_value
                bridge_labels = ", ".join(field.label for field in bridge_fields)
                raw_text = f"{existing.value} + ({' + '.join(str(field.value) for field in bridge_fields)})"
                adjusted_row_label = f"{row_label} (+ {bridge_labels})"
            elif same_filing_identity_bridge:
                adjusted_value = assets.value - equity.value
                raw_text = f"{assets.value} - {equity.value}"
                adjusted_row_label = (
                    f"{row_label} "
                    "(computed: total assets - total equity with explicit bridge)"
                )
            else:
                continue

            adjusted = _make_field_result(
                adjusted_value,
                existing.scale,
                existing_prov.source_filing or source_filename,
                f"{existing_prov.source_location}:bs_identity_bridge",
                existing.confidence,
                table_index=existing_prov.table_index,
                table_title=existing_prov.table_title,
                row_label=adjusted_row_label,
                col_label=existing_prov.col_label,
                row=existing_prov.row,
                col=existing_prov.col,
                raw_text=raw_text,
                extraction_method=existing_prov.extraction_method or "table",
            )
            adjusted.provenance.preflight_currency = (
                existing_prov.preflight_currency
            )
            adjusted.provenance.preflight_standard = (
                existing_prov.preflight_standard
            )
            adjusted.provenance.preflight_units_hint = (
                existing_prov.preflight_units_hint
            )
            adjusted._sort_key = getattr(existing, "_sort_key", None)  # type: ignore[attr-defined]
            period_fields[pk]["total_liabilities"] = adjusted

    @staticmethod
    def _bridge_total_liabilities_after_merge(
        result: ExtractionResult,
        raw_table_fields: List[TableField],
    ) -> None:
        """Apply the same BS-identity bridge on merged results.

        Needed when the winning liabilities/assets come from a comparative
        filing while the winning equity comes from a different filing.
        """
        for pk, period_result in result.periods.items():
            assets = period_result.fields.get("total_assets")
            liabilities = period_result.fields.get("total_liabilities")
            equity = period_result.fields.get("total_equity")
            if not assets or not liabilities or not equity:
                continue

            identity_gap = assets.value - (liabilities.value + equity.value)
            tolerance = max(1.0, abs(assets.value) * 0.001)
            if identity_gap <= tolerance:
                continue

            bridge_fields = _pick_total_liabilities_bridge_components(
                raw_table_fields,
                pk,
                identity_gap,
                liabilities.value,
                liabilities.provenance.source_location,
            )
            bridge_value = sum(field.value for field in bridge_fields)
            same_filing_identity_bridge = (
                assets.provenance.source_filing
                and assets.provenance.source_filing == liabilities.provenance.source_filing
                and liabilities.provenance.source_filing == equity.provenance.source_filing
                and _has_total_liabilities_bridge_context(raw_table_fields, pk)
            )
            if not bridge_fields and not same_filing_identity_bridge:
                continue

            existing = liabilities
            existing_prov = existing.provenance
            row_label = existing_prov.row_label or "Total liabilities"
            if bridge_fields and abs(bridge_value - identity_gap) <= tolerance:
                adjusted_value = existing.value + bridge_value
                bridge_labels = ", ".join(field.label for field in bridge_fields)
                raw_text = f"{existing.value} + ({' + '.join(str(field.value) for field in bridge_fields)})"
                adjusted_row_label = f"{row_label} (+ {bridge_labels})"
            elif same_filing_identity_bridge:
                adjusted_value = assets.value - equity.value
                raw_text = f"{assets.value} - {equity.value}"
                adjusted_row_label = (
                    f"{row_label} "
                    "(computed: total assets - total equity with explicit bridge)"
                )
            else:
                continue

            adjusted = _make_field_result(
                adjusted_value,
                existing.scale,
                existing_prov.source_filing,
                f"{existing_prov.source_location}:bs_identity_bridge",
                existing.confidence,
                table_index=existing_prov.table_index,
                table_title=existing_prov.table_title,
                row_label=adjusted_row_label,
                col_label=existing_prov.col_label,
                row=existing_prov.row,
                col=existing_prov.col,
                raw_text=raw_text,
                extraction_method=existing_prov.extraction_method or "table",
            )
            adjusted.provenance.preflight_currency = (
                existing_prov.preflight_currency
            )
            adjusted.provenance.preflight_standard = (
                existing_prov.preflight_standard
            )
            adjusted.provenance.preflight_units_hint = (
                existing_prov.preflight_units_hint
            )
            period_result.fields["total_liabilities"] = adjusted

    # ── MANUAL OVERRIDES ─────────────────────────────────────────────

    @staticmethod
    def _apply_manual_overrides(
        config: Dict,
        result: ExtractionResult,
    ) -> None:
        """Inject manual_overrides from case.json only for missing fields.

        A field is considered missing if the extractor produced no value for
        that period+field combination after merging all filings.  If the
        extractor found anything — even with low confidence — it always wins
        and the override is silently skipped.
        """
        overrides = config.get("manual_overrides")
        if not overrides or not isinstance(overrides, dict):
            return

        for period_key, fields in overrides.items():
            if not isinstance(fields, dict):
                continue

            # Pre-validate specs: only consider dict entries with a numeric value.
            valid_specs = {
                fn: spec
                for fn, spec in fields.items()
                if isinstance(spec, dict) and "value" in spec
            }
            if not valid_specs:
                continue

            # Create the period entry if the extractor found nothing at all.
            if period_key not in result.periods:
                fecha_fin = ""
                m = re.match(r"FY(\d{4})$", period_key)
                if m:
                    fecha_fin = f"{m.group(1)}-12-31"
                result.periods[period_key] = PeriodResult(
                    fecha_fin=fecha_fin,
                    tipo_periodo="anual",
                )

            period_result = result.periods[period_key]

            for field_name, spec in valid_specs.items():
                # Extractor wins: skip if any value already present.
                if field_name in period_result.fields:
                    continue

                try:
                    value = float(spec["value"])
                except (TypeError, ValueError):
                    continue

                note = spec.get("note", "")
                loc = (
                    f"case.json:manual_overrides:{period_key}:{field_name}"
                    + (f":{note}" if note else "")
                )
                fr = _make_field_result(
                    value, "raw", "manual_override", loc, "manual",
                    extraction_method="manual",
                )
                period_result.fields[field_name] = fr
                result.audit.fields_extracted += 1
