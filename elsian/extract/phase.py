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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from elsian.models.field import FieldResult, Provenance
from elsian.models.result import ExtractionResult, PeriodResult, AuditRecord, PhaseResult
from elsian.extract.detect import analyze_filing
from elsian.analyze.preflight import preflight as _run_preflight, PreflightResult
from elsian.extract.html_tables import (
    extract_tables_from_clean_md,
    extract_tables_from_text,
    extract_shares_outstanding_from_text,
    TableField,
)
from elsian.extract.vertical import extract_vertical_bs
from elsian.extract.narrative import extract_from_narrative, NarrativeField
from elsian.normalize.aliases import AliasResolver
from elsian.normalize.scale import infer_scale_cascade, validate_scale_sanity
from elsian.normalize.audit import AuditLog
from elsian.merge.merger import merge_extractions
from elsian.context import PipelineContext
from elsian.pipeline import PipelinePhase


# ── Sign normalisation ───────────────────────────────────────────────
_ALWAYS_POSITIVE_FIELDS = frozenset({
    "cost_of_revenue",
    "sga",
    "research_and_development",
    "depreciation_amortization",
    "interest_expense",
})

_BENEFIT_RE = re.compile(r"\bbenefit\b", re.IGNORECASE)


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
    """Ensure expense fields use the correct sign convention."""
    if canonical in _ALWAYS_POSITIVE_FIELDS:
        return abs(value)
    if canonical == "income_tax" and value < 0:
        if not _BENEFIT_RE.search(raw_label):
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


# ── Section priority patterns ────────────────────────────────────────
_PRIMARY_IS_SECTION = re.compile(
    r":operating_income|:operating_profit|:consolidated_statements_of_operations"
    r"|:consolidated_statements_of_income"
    r"|:consolidated_balance_sheets|:consolidated_statements_of_comprehensive",
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
    r"|:equity_method_investment",
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
    """
    bonus = 5
    penalty = -5
    severe_penalty = -100
    if rules and "section_weights" in rules:
        sw = rules["section_weights"]
        bonus = sw.get("primary_is_bonus", 5)
        penalty = sw.get("deprioritized_penalty", -5)
        severe_penalty = sw.get("strongly_deprioritized_penalty", -100)
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

    return base


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


# Fields where stock-splits / reverse-splits cause the SAME line item to
# change value across filings.  For these, prefer the PRIMARY filing
# (the one whose FY tag matches the period) to honour "as-reported".
# For all other fields, prefer the NEWEST filing (lowest SRC number) so
# that implicit restatements / reclassifications are picked up.
_SPLIT_SENSITIVE_FIELDS: set = {
    "eps_basic", "eps_diluted", "shares_outstanding", "dividends_per_share",
}


def _period_affinity(period_key: str, source_filing: str,
                     canonical_field: str | None = None) -> int:
    """Return 0 when the filing is the best source for *period_key*, else 1.

    **FY periods — split-sensitive fields** (EPS, shares, DPS): the primary
    filing is preferred (FY tag matches) so as-reported pre-split values win.

    **FY periods — all other fields**: affinity is always 0. The tiebreaker
    becomes filing_rank (lower SRC number = newer filing), so implicit
    restatements / reclassifications in newer comparative columns are
    picked up automatically.

    **Quarterly periods**: always prefer the primary filing regardless of
    field, because quarterly values vary across filings (3-month vs YTD
    cumulative in 10-Q comparatives).
    """
    if period_key.startswith("FY"):
        # Non-split FY fields: no preference → newer filing wins
        if canonical_field and canonical_field not in _SPLIT_SENSITIVE_FIELDS:
            return 0
        # Split-sensitive (or unknown): prefer primary filing
        fy_tag = period_key
        if fy_tag in source_filing:
            return 0
        return 1
    # Quarterly: always prefer primary filing
    if period_key in source_filing:
        return 0
    return 1


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
    affinity = _period_affinity(period_key, source_filing, canonical_field)
    src_rank = _source_type_rank(source_type, rules)
    semantic_rank = -(label_priority + section_bonus_val)
    stable = _parse_stable_order(source_filing, source_location, rules)
    return (fr, affinity, src_rank, semantic_rank, stable)


def _make_field_result(
    value: float, scale: str, source_filing: str,
    source_location: str, confidence: str,
) -> FieldResult:
    """Create a FieldResult with Provenance from flat args."""
    return FieldResult(
        value=value,
        provenance=Provenance(
            source_filing=source_filing,
            source_location=source_location,
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

        # Load selection rules
        rules = dict(self._load_selection_rules())
        case_overrides = config.get("selection_overrides")
        if case_overrides and isinstance(case_overrides, dict):
            rules.update(case_overrides)

        if not filings_dir.exists() or not any(filings_dir.iterdir()):
            return ExtractionResult(ticker=ticker, currency=currency, filings_used=0)

        audit = AuditLog()
        filing_extractions: List[Tuple[str, str, Dict[str, Dict[str, FieldResult]]]] = []

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
                )
            else:
                self._extract_from_txt(
                    text, filing_path, metadata, filing_scale,
                    filing_scale_confidence, rules, audit,
                    period_fields, additive_labels, _raw_table_fields,
                    preflight_result=pf_result,
                )

            # Post-process: recover total_liabilities from sub-totals
            self._recover_total_liabilities(
                period_fields, _raw_table_fields, filing_path.name,
                filing_scale, filing_scale_confidence,
            )

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
                    )
                elif "eps_diluted" in pf[_pk] and "eps_basic" not in pf[_pk]:
                    src = pf[_pk]["eps_diluted"]
                    pf[_pk]["eps_basic"] = _make_field_result(
                        src.value, src.scale,
                        src.provenance.source_filing,
                        src.provenance.source_location,
                        src.confidence,
                    )

        # Merge all filing extractions
        result = merge_extractions(
            filing_extractions, ticker=ticker, currency=currency
        )

        # Inject manual_overrides from case.json — ONLY for fields that the
        # extractor could not find (e.g. corrupted PDF sources). If the
        # extractor already produced a value, it always wins.
        self._apply_manual_overrides(config, result)

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
    ) -> None:
        """Extract from .clean.md files (markdown tables)."""
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
                    dps_value, "raw", filing_path.name, dps_loc, "high"
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
    ) -> None:
        """Extract from .txt files (space-aligned tables + narrative)."""
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
        for tf in extract_vertical_bs(
            text, source_filename=filing_path.name,
        ):
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
            new_sort_key = compute_sort_key(
                period_key=period_key,
                filing_type=metadata.filing_type,
                source_type="table",
                label_priority=label_pri,
                section_bonus_val=_VERTICAL_BS_BONUS,
                source_filing=filing_path.name,
                source_location=tf.source_location,
                rules=rules,
                canonical_field=canonical,
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
            )
            fr._sort_key = new_sort_key  # type: ignore[attr-defined]
            period_fields[period_key][canonical] = fr
            audit.accept(
                field_name=canonical,
                period=period_key,
                source_filing=filing_path.name,
                raw_label=tf.label,
                raw_value=tf.value,
                scale=scale,
            )

        # Narrative extraction
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
            )
            fr._sort_key = new_sk  # type: ignore[attr-defined]
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
        )

        if canonical in period_fields[period_key]:
            existing = period_fields[period_key][canonical]
            norm_lbl = self._alias_resolver._normalize(tf.label)

            # Additive fields
            if self._alias_resolver.is_additive(canonical):
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
                    fr = _make_field_result(
                        combined_value, existing.scale,
                        existing.provenance.source_filing,
                        existing.provenance.source_location,
                        existing.confidence,
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
                else:
                    audit.discard(
                        field_name=canonical, period=period_key,
                        reason="additive_duplicate_constituent",
                        source_filing=filing_path.name,
                        raw_label=tf.label, raw_value=tf.value, scale=scale,
                    )
                    return

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

        fr = _make_field_result(
            _normalize_sign(canonical, tf.label, tf.value),
            scale, filing_path.name, tf.source_location, confidence,
        )
        fr._sort_key = new_sk  # type: ignore[attr-defined]

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
        """Recover total_liabilities from non-current + current sub-totals."""
        _NC_LIAB_RE = re.compile(r"total\s+non[- ]?current\s+liabilities", re.I)
        _C_LIAB_RE = re.compile(r"total\s+current\s+liabilities", re.I)

        for pk in list(period_fields.keys()):
            if "total_liabilities" not in period_fields[pk]:
                nc_val = None
                c_val = None
                nc_loc = ""
                for rtf in raw_table_fields:
                    if rtf.column_header != pk:
                        continue
                    if _NC_LIAB_RE.search(rtf.label):
                        nc_val = rtf.value
                        nc_loc = rtf.source_location
                    elif _C_LIAB_RE.search(rtf.label):
                        c_val = rtf.value
                if nc_val is not None and c_val is not None:
                    period_fields[pk]["total_liabilities"] = _make_field_result(
                        nc_val + c_val, filing_scale,
                        source_filename, nc_loc,
                        filing_scale_confidence,
                    )

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
                )
                period_result.fields[field_name] = fr
                result.audit.fields_extracted += 1
