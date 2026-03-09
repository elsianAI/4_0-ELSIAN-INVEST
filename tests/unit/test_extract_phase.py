"""Tests for ExtractPhase sign normalization and helper functions."""

import json
from functools import lru_cache
from pathlib import Path
import shutil
from types import SimpleNamespace

from elsian.extract.html_tables import TableField
from elsian.extract.phase import (
    ExtractPhase,
    _candidate_allows_total_equity_restatement_affinity,
    _has_explicit_restatement_signal,
    _normalize_sign,
    _section_bonus,
    _filing_rank,
    _source_type_rank,
    _period_affinity,
    compute_sort_key,
    _make_field_result,
    _extract_financial_highlights_dividends_per_share,
    _pick_total_liabilities_bridge_components,
)
from elsian.normalize.audit import AuditLog

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _som_filing_text(filename: str) -> str:
    return (_REPO_ROOT / "cases" / "SOM" / "filings" / filename).read_text()


@lru_cache(maxsize=None)
def _case_extract(ticker: str):
    return ExtractPhase().extract(str(_REPO_ROOT / "cases" / ticker))


# ── Sign normalization ───────────────────────────────────────────────

def test_normalize_sign_expense_positive():
    """Expense fields should always be positive."""
    assert _normalize_sign("cost_of_revenue", "Cost of revenue", -500) == 500
    assert _normalize_sign("sga", "SGA expense", -100) == 100


def test_normalize_sign_income_tax_benefit():
    """income_tax with 'benefit' label stays negative."""
    assert _normalize_sign("income_tax", "Benefit from income taxes", -50) == -50


def test_normalize_sign_income_tax_annotated_benefit():
    """income_tax with pdf_tables.py-annotated '(benefit)' label stays negative (SOM case)."""
    # pdf_tables._extract_wide_historical_fields appends " (benefit)" to the label
    # when a tax row has a negative value in a historical wide table.
    assert _normalize_sign("income_tax", "Tax (benefit)", -2100) == -2100
    assert _normalize_sign("income_tax", "Income tax (benefit)", -200) == -200


def test_normalize_sign_income_tax_no_benefit():
    """income_tax without 'benefit' becomes positive (TEP/IFRS convention)."""
    assert _normalize_sign("income_tax", "Provision for income taxes", -50) == 50
    # TEP (Teleperformance, IFRS): filing presents income tax expense with explicit '-'
    # This is IFRS presentation convention, NOT a tax benefit → must be flipped to positive.
    assert _normalize_sign("income_tax", "Income tax", -346) == 346
    assert _normalize_sign("income_tax", "Income tax", -228) == 228



def test_normalize_sign_net_income_preserves():
    """net_income preserves its sign."""
    assert _normalize_sign("net_income", "Net income", -200) == -200
    assert _normalize_sign("net_income", "Net income", 300) == 300


# ── Section bonus ────────────────────────────────────────────────────

def test_section_bonus_primary_is():
    assert _section_bonus("filing:consolidated_statements_of_operations:tbl1") > 0


def test_section_bonus_deprioritized():
    assert _section_bonus("filing:discontinued_operations:tbl1") < 0


def test_section_bonus_strongly_deprioritized():
    assert _section_bonus("filing:federal_income_taxes:tbl1") < -10


def test_section_bonus_neutral():
    assert _section_bonus("filing:some_other_section:tbl1") == 0


def test_section_bonus_strongly_penalizes_da_from_per_share_sections():
    assert _section_bonus(
        "filing:income_statement:net_income_per_ordinary_share_–_diluted:tbl14",
        canonical="depreciation_amortization",
    ) < -10


def test_pick_total_liabilities_bridge_components_prefers_smallest_matching_subset():
    fields = [
        TableField(
            label="Total liabilities",
            value=621525.0,
            column_header="FY2024",
            source_location="filing:table:balance_sheet:tbl1:row0",
            raw_text="Total liabilities 621,525",
            col_label="FY2024",
            table_title="balance_sheet",
            row_idx=0,
            col_idx=1,
            table_index=1,
        ),
        TableField(
            label="Redeemable Non-Controlling Interest",
            value=442152.0,
            column_header="FY2024",
            source_location="filing:table:balance_sheet:tbl1:row1",
            raw_text="Redeemable Non-Controlling Interest 442,152",
            col_label="FY2024",
            table_title="balance_sheet",
            row_idx=1,
            col_idx=1,
            table_index=1,
        ),
        TableField(
            label="Non-controlling interest",
            value=316415.0,
            column_header="FY2024",
            source_location="filing:table:balance_sheet:tbl1:row2",
            raw_text="Non-controlling interest 316,415",
            col_label="FY2024",
            table_title="balance_sheet",
            row_idx=2,
            col_idx=1,
            table_index=1,
        ),
    ]

    picked = _pick_total_liabilities_bridge_components(
        fields,
        "FY2024",
        442152.0,
        621525.0,
        "filing:table:balance_sheet:tbl1:row0",
    )

    assert [field.label for field in picked] == [
        "Redeemable Non-Controlling Interest",
    ]


def test_pick_total_liabilities_bridge_components_ignores_total_equity_with_nci_label():
    fields = [
        TableField(
            label="Total liabilities",
            value=675765.0,
            column_header="Q1-2023",
            source_location="filing:table:balance_sheet:tbl1:row0",
            raw_text="Total liabilities 675,765",
            col_label="Q1-2023",
            table_title="balance_sheet",
            row_idx=0,
            col_idx=1,
            table_index=1,
        ),
        TableField(
            label="Stockholders' equity including portion attributable to noncontrolling interest",
            value=442668.0,
            column_header="Q1-2023",
            source_location="filing:table:balance_sheet:tbl1:row1",
            raw_text="Stockholders' equity including portion attributable to noncontrolling interest 442,668",
            col_label="Q1-2023",
            table_title="balance_sheet",
            row_idx=1,
            col_idx=1,
            table_index=1,
        ),
    ]

    picked = _pick_total_liabilities_bridge_components(
        fields,
        "Q1-2023",
        442668.0,
        675765.0,
        "filing:table:balance_sheet:tbl1:row0",
    )

    assert picked == []


# ── Filing rank ──────────────────────────────────────────────────────

def test_filing_rank_with_rules():
    rules = {
        "filing_priority_by_period": {
            "FY": ["10-K", "20-F", "10-Q", "8-K"],
        }
    }
    assert _filing_rank("FY2024", "10-K", rules) == 0
    assert _filing_rank("FY2024", "10-Q", rules) == 2
    assert _filing_rank("FY2024", "8-K", rules) == 3


# ── Source type rank ─────────────────────────────────────────────────

def test_source_type_rank_table_wins():
    assert _source_type_rank("table") < _source_type_rank("narrative")


# ── Period affinity ──────────────────────────────────────────────────

def test_period_affinity_split_sensitive_primary():
    """Weighted-average shares stay primary-filing sensitive for FY periods."""
    assert _period_affinity("FY2024", "SRC_003_10-K_FY2024.clean.md", "shares_outstanding") == 0


def test_period_affinity_split_sensitive_comparative():
    """Later annual share-count comparatives stay affinity=1."""
    assert _period_affinity("FY2024", "SRC_001_10-K_FY2026.clean.md", "shares_outstanding") == 1


def test_period_affinity_eps_allows_later_annual_comparatives():
    """Annual EPS uses merge-time heuristics rather than primary-only affinity."""
    assert _period_affinity("FY2024", "SRC_001_10-K_FY2026.clean.md", "eps_basic") == 0
    assert _period_affinity("FY2024", "SRC_001_REGULATORY_FILING_2025-02-27.clean.md", "eps_basic") == 0


def test_period_affinity_total_debt_prefers_primary_filing():
    """Annual debt snapshots should not drift to newer comparative filings."""
    assert _period_affinity("FY2024", "SRC_001_10-K_FY2026.clean.md", "total_debt") == 1


def test_period_affinity_working_capital_allows_later_annual_comparatives():
    """Inventories can use later comparative annual filings when they rank better."""
    assert _period_affinity("FY2024", "SRC_001_10-K_FY2026.clean.md", "inventories") == 0


def test_period_affinity_non_split_always_zero():
    """Non-split fields: always affinity 0 regardless of filing, so newer filing wins."""
    assert _period_affinity("FY2019", "SRC_006_10-K_FY2019.clean.md", "ingresos") == 0
    assert _period_affinity("FY2019", "SRC_005_10-K_FY2020.clean.md", "ingresos") == 0


def test_period_affinity_fy_no_tag():
    """FY period from a file without FY tag → affinity 1 for split-sensitive,
    0 for non-split (newer file wins)."""
    assert _period_affinity("FY2024", "anything.clean.md", "shares_outstanding") == 1
    assert _period_affinity("FY2024", "anything.clean.md", "eps_basic") == 0
    assert _period_affinity("FY2024", "anything.clean.md", "ingresos") == 0


def test_period_affinity_q_primary():
    """Q periods always prefer primary filing regardless of field."""
    assert _period_affinity("Q1-2024", "SRC_010_10-Q_Q1-2024.clean.md", "eps_basic") == 0
    assert _period_affinity("Q1-2024", "SRC_010_10-Q_Q1-2024.clean.md", "ingresos") == 0


def test_period_affinity_q_comparative():
    """Q periods: comparative filing → affinity 1 for ALL fields."""
    assert _period_affinity("Q1-2024", "SRC_012_10-Q_Q3-2024.clean.md", "eps_basic") == 1
    assert _period_affinity("Q1-2024", "SRC_012_10-Q_Q3-2024.clean.md", "ingresos") == 1


def test_period_affinity_q_restatement_comparative_can_tie_primary():
    """Restated quarterlies can tie on affinity; source-aware filters decide."""
    assert _period_affinity(
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "accounts_receivable",
        restatement_detected=True,
    ) == 0
    assert _period_affinity(
        "Q1-2023",
        "SRC_010_10-Q_Q3-2024.clean.md",
        "eps_basic",
        restatement_detected=True,
    ) == 0
    assert _period_affinity(
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "total_equity",
        restatement_detected=True,
    ) == 0


def test_has_explicit_restatement_signal_requires_high_or_paired_medium_markers():
    assert _has_explicit_restatement_signal(
        SimpleNamespace(
            restatement_detected=True,
            restatement_signals=[
                {"confidence": "medium", "pattern": r"\bpreviously\s+reported\b"},
            ],
        )
    ) is False
    assert _has_explicit_restatement_signal(
        SimpleNamespace(
            restatement_detected=True,
            restatement_signals=[
                {"confidence": "medium", "pattern": r"\bpreviously\s+reported\b"},
                {"confidence": "medium", "pattern": r"\breclassif(?:ied|ication)\b"},
            ],
        )
    ) is True


def test_period_affinity_q_restatement_net_income_requires_same_quarter():
    assert _period_affinity(
        "Q1-2023",
        "SRC_010_10-Q_Q3-2024.clean.md",
        "net_income",
        restatement_detected=True,
    ) == 1
    assert _period_affinity(
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "net_income",
        restatement_detected=True,
    ) == 0


def test_total_equity_restatement_affinity_requires_balance_sheet_context():
    assert _candidate_allows_total_equity_restatement_affinity(
        "total_equity",
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "table",
        "SRC_009_10-Q_Q1-2025.clean.md:table:balance_sheet:condensed_consolidated_balance_sheets:tbl2:row20:col3",
    ) is True
    assert _candidate_allows_total_equity_restatement_affinity(
        "total_equity",
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "table",
        "SRC_009_10-Q_Q1-2025.clean.md:table:equity:condensed_consolidated_statements_of_stockholders_equity:tbl7:row20:col3",
    ) is False
    assert _candidate_allows_total_equity_restatement_affinity(
        "total_equity",
        "Q1-2024",
        "SRC_009_10-Q_Q1-2025.clean.md",
        "narrative",
        "SRC_009_10-Q_Q1-2025.clean.md:narrative:char1200",
    ) is False


def test_additive_duplicate_candidate_can_replace_worse_existing_one():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-K", scale="thousands", scale_confidence="high")
    filing_path = _REPO_ROOT / "cases" / "ADTN" / "filings" / "SRC_001_10-K_FY2025.clean.md"
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"FY2024": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    weaker = TableField(
        label="Selling, general and administrative expenses",
        value=25.2,
        column_header="FY2024",
        source_location="filing:table:income_statement:results_of_operations:tbl1:row11:col5",
        raw_text="25.2",
        col_label="FY2024",
        table_title="income_statement:results_of_operations",
        row_idx=11,
        col_idx=5,
        table_index=1,
    )
    stronger = TableField(
        label="Selling, general and administrative expenses",
        value=232918.0,
        column_header="FY2024",
        source_location="filing:table:income_statement:interest_and_dividend_income:tbl4:row11:col5",
        raw_text="232,918",
        col_label="FY2024",
        table_title="income_statement:interest_and_dividend_income",
        row_idx=11,
        col_idx=5,
        table_index=4,
    )

    phase._process_table_field(
        weaker,
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )
    phase._process_table_field(
        stronger,
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    picked = period_fields["FY2024"]["sga"]
    assert picked.value == 232918.0
    assert "interest_and_dividend_income" in picked.provenance.source_location


def test_additive_duplicate_cannot_replace_aggregate_once_multiple_labels_exist():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-K", scale="thousands", scale_confidence="high")
    filing_path = _REPO_ROOT / "cases" / "ADTN" / "filings" / "SRC_001_10-K_FY2025.clean.md"
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"FY2024": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    phase._process_table_field(
        TableField(
            label="Sales and marketing",
            value=272124.0,
            column_header="FY2024",
            source_location="filing:table:income_statement:operating_income:tbl1:row5:col4",
            raw_text="272,124",
            col_label="FY2024",
            table_title="income_statement:operating_income",
            row_idx=5,
            col_idx=4,
            table_index=1,
        ),
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )
    phase._process_table_field(
        TableField(
            label="General and administrative",
            value=152828.0,
            column_header="FY2024",
            source_location="filing:table:income_statement:operating_income:tbl1:row6:col4",
            raw_text="152,828",
            col_label="FY2024",
            table_title="income_statement:operating_income",
            row_idx=6,
            col_idx=4,
            table_index=1,
        ),
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )
    phase._process_table_field(
        TableField(
            label="General and administrative",
            value=152828.0,
            column_header="FY2024",
            source_location="filing:table:income_statement:operating_income_(loss):tbl6:row7:col1",
            raw_text="152,828",
            col_label="FY2024",
            table_title="income_statement:operating_income_(loss)",
            row_idx=7,
            col_idx=1,
            table_index=6,
        ),
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    picked = period_fields["FY2024"]["sga"]
    assert picked.value == 424952.0


def test_process_table_field_restated_total_equity_invalid_table_keeps_primary():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-Q", scale="thousands", scale_confidence="high")
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"Q1-2024": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    primary_filing = Path("SRC_012_10-Q_Q1-2024.clean.md")
    phase._process_table_field(
        TableField(
            label="Total Equity",
            value=260849.0,
            column_header="Q1-2024",
            source_location="SRC_012_10-Q_Q1-2024.clean.md:table:balance_sheet:condensed_consolidated_balance_sheets:tbl1:row41:col2",
            raw_text="260,849",
            col_label="Q1-2024",
            table_title="balance_sheet:condensed_consolidated_balance_sheets",
            row_idx=41,
            col_idx=2,
            table_index=1,
        ),
        primary_filing,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    phase._process_table_field(
        TableField(
            label="Total stockholders' equity",
            value=265783.0,
            column_header="Q1-2024",
            source_location="SRC_009_10-Q_Q1-2025.clean.md:table:equity:condensed_consolidated_statements_of_stockholders_equity:tbl7:row20:col3",
            raw_text="265,783",
            col_label="Q1-2024",
            table_title="equity:condensed_consolidated_statements_of_stockholders_equity",
            row_idx=20,
            col_idx=3,
            table_index=7,
        ),
        Path("SRC_009_10-Q_Q1-2025.clean.md"),
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
        preflight_result=SimpleNamespace(
            restatement_detected=True,
            restatement_signals=[{"confidence": "high", "pattern": r"\brestated\b"}],
            currency="USD",
            accounting_standard="US_GAAP",
            units_by_section={},
            units_global={},
        ),
    )

    picked = period_fields["Q1-2024"]["total_equity"]
    assert picked.value == 260849.0
    assert picked.provenance.source_filing == "SRC_012_10-Q_Q1-2024.clean.md"


def test_process_table_field_restated_total_equity_balance_sheet_table_can_replace_primary():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-Q", scale="thousands", scale_confidence="high")
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"Q1-2024": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    primary_filing = Path("SRC_012_10-Q_Q1-2024.clean.md")
    phase._process_table_field(
        TableField(
            label="Total Equity",
            value=265783.0,
            column_header="Q1-2024",
            source_location="SRC_012_10-Q_Q1-2024.clean.md:table:balance_sheet:condensed_consolidated_balance_sheets:tbl1:row41:col2",
            raw_text="265,783",
            col_label="Q1-2024",
            table_title="balance_sheet:condensed_consolidated_balance_sheets",
            row_idx=41,
            col_idx=2,
            table_index=1,
        ),
        primary_filing,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    phase._process_table_field(
        TableField(
            label="Total Equity",
            value=260849.0,
            column_header="Q1-2024",
            source_location="SRC_009_10-Q_Q1-2025.clean.md:table:balance_sheet:condensed_consolidated_balance_sheets:tbl2:row41:col4",
            raw_text="260,849",
            col_label="Q1-2024",
            table_title="balance_sheet:condensed_consolidated_balance_sheets",
            row_idx=41,
            col_idx=4,
            table_index=2,
        ),
        Path("SRC_009_10-Q_Q1-2025.clean.md"),
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
        preflight_result=SimpleNamespace(
            restatement_detected=True,
            restatement_signals=[{"confidence": "high", "pattern": r"\brestated\b"}],
            currency="USD",
            accounting_standard="US_GAAP",
            units_by_section={},
            units_global={},
        ),
    )

    picked = period_fields["Q1-2024"]["total_equity"]
    assert picked.value == 260849.0
    assert picked.provenance.source_filing == "SRC_009_10-Q_Q1-2025.clean.md"
    assert getattr(picked, "_is_explicit_restatement", False) is True


def test_total_debt_discards_cash_flow_candidates():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-Q", scale="thousands", scale_confidence="high")
    filing_path = _REPO_ROOT / "cases" / "TALO" / "filings" / "SRC_018_10-Q_Q1-2022.clean.md"
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"Q1-2022": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    phase._process_table_field(
        TableField(
            label="Redemption of senior notes and other long-term debt",
            value=0.0,
            column_header="Q1-2022",
            source_location="SRC_018_10-Q_Q1-2022.clean.md:table:cash_flow:condensed_consolidated_statements_of_cash_flows:tbl19:row28:col1",
            raw_text="0",
            col_label="Q1-2022",
            table_title="cash_flow",
            row_idx=28,
            col_idx=1,
            table_index=19,
        ),
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    assert "total_debt" not in period_fields["Q1-2022"]


def test_working_capital_discards_income_statement_candidates():
    phase = ExtractPhase()
    metadata = SimpleNamespace(filing_type="10-K", scale="thousands", scale_confidence="high")
    filing_path = _REPO_ROOT / "cases" / "ADTN" / "filings" / "SRC_005_10-K_FY2021.clean.md"
    rules = phase._load_selection_rules()
    audit = AuditLog()
    period_fields = {"FY2019": {}}
    additive_labels: dict[str, dict[str, set]] = {}

    phase._process_table_field(
        TableField(
            label="Purchases of property, plant and equipment included in accounts payable",
            value=90.0,
            column_header="FY2019",
            source_location="SRC_005_10-K_FY2021.clean.md:table:income_statement:net_(loss)_income:tbl11:row49:col10",
            raw_text="90",
            col_label="FY2019",
            table_title="income_statement:net_(loss)_income",
            row_idx=49,
            col_idx=10,
            table_index=11,
        ),
        filing_path,
        metadata,
        metadata.scale,
        metadata.scale_confidence,
        rules,
        audit,
        period_fields,
        additive_labels,
    )

    assert "accounts_payable" not in period_fields["FY2019"]


# ── Sort key ─────────────────────────────────────────────────────────

def test_sort_key_filing_rank_wins():
    """Better filing rank should produce lower sort key."""
    sk_10k = compute_sort_key("FY2024", "10-K", "table", 5, 0, "f.md", "tbl1:row1")
    sk_8k = compute_sort_key("FY2024", "8-K", "table", 5, 0, "f.md", "tbl1:row1")
    assert sk_10k < sk_8k


def test_sort_key_table_beats_narrative():
    sk_tbl = compute_sort_key("FY2024", "10-K", "table", 5, 0, "f.md", "tbl1:row1")
    sk_narr = compute_sort_key("FY2024", "10-K", "narrative", 5, 0, "f.md", "tbl1:row1")
    assert sk_tbl < sk_narr


# ── make_field_result ────────────────────────────────────────────────

def test_make_field_result_provenance():
    fr = _make_field_result(100.0, "thousands", "file.md", "tbl1:row3", "high")
    assert fr.value == 100.0
    assert fr.provenance.source_filing == "file.md"
    assert fr.provenance.source_location == "tbl1:row3"
    assert fr.scale == "thousands"
    assert fr.confidence == "high"


def test_extract_financial_highlights_dividends_per_share():
    fields = _extract_financial_highlights_dividends_per_share(
        _som_filing_text("SRC_001_ANNUAL_REPORT_FY2024.txt"),
        source_filename="SRC_001_ANNUAL_REPORT_FY2024.txt",
    )

    assert [(field.column_header, field.value) for field in fields] == [
        ("FY2024", 0.169),
        ("FY2023", 0.2319),
    ]
    assert [field.source_location for field in fields] == [
        "SRC_001_ANNUAL_REPORT_FY2024.txt:table:financial_highlights_dps:line141",
        "SRC_001_ANNUAL_REPORT_FY2024.txt:table:financial_highlights_dps:line142",
    ]
    assert [field.table_index for field in fields] == [0, 0]


def test_adtn_regression_prefers_primary_statement_candidates():
    result = _case_extract("ADTN")

    assert result.periods["FY2019"].fields["cost_of_revenue"].value == 310894.0
    assert result.periods["FY2019"].fields["gross_profit"].value == 219167.0
    assert result.periods["FY2019"].fields["research_and_development"].value == 126200.0
    assert result.periods["FY2019"].fields["total_debt"].value == 24600.0
    assert result.periods["FY2022"].fields["dividends_per_share"].value == 0.09
    assert result.periods["FY2024"].fields["cfo"].value == 103571.0
    assert result.periods["FY2024"].fields["capex"].value == -34501.0
    assert result.periods["FY2024"].fields["inventories"].value == 261557.0
    assert result.periods["FY2024"].fields["eps_basic"].value == -5.79
    assert result.periods["FY2024"].fields["eps_diluted"].value == -5.79


def test_extract_financial_highlights_dividends_per_share_accepts_auto_discovered_filename():
    fields = _extract_financial_highlights_dividends_per_share(
        _som_filing_text("SRC_001_ANNUAL_REPORT_FY2024.txt"),
        source_filename="annual-report-2024.txt",
    )

    assert [(field.column_header, field.value) for field in fields] == [
        ("FY2024", 0.169),
        ("FY2023", 0.2319),
    ]
    assert [field.source_location for field in fields] == [
        "annual-report-2024.txt:table:financial_highlights_dps:line141",
        "annual-report-2024.txt:table:financial_highlights_dps:line142",
    ]


def test_extract_financial_highlights_dividends_per_share_ignores_presentation_cents():
    fields = _extract_financial_highlights_dividends_per_share(
        _som_filing_text("SRC_002_RESULTS_PRESENTATION_FY2024.txt"),
        source_filename="SRC_002_RESULTS_PRESENTATION_FY2024.txt",
    )

    assert fields == []


def test_extract_phase_som_dividends_per_share_from_annual_report():
    result = _case_extract("SOM")

    fy2024 = result.periods["FY2024"].fields["dividends_per_share"]
    fy2023 = result.periods["FY2023"].fields["dividends_per_share"]

    assert fy2024.value == 0.169
    assert fy2024.provenance.source_filing == "SRC_001_ANNUAL_REPORT_FY2024.txt"
    assert fy2024.provenance.extraction_method == "table"
    assert "financial_highlights_dps" in fy2024.provenance.source_location
    assert fy2024.provenance.table_index == 0
    assert fy2024.provenance.row is not None
    assert fy2024.provenance.col is not None

    assert fy2023.value == 0.2319
    assert fy2023.provenance.source_filing == "SRC_001_ANNUAL_REPORT_FY2024.txt"
    assert fy2023.provenance.extraction_method == "table"
    assert "financial_highlights_dps" in fy2023.provenance.source_location
    assert fy2023.provenance.table_index == 0
    assert fy2023.provenance.row is not None
    assert fy2023.provenance.col is not None
    assert {fy2024.value, fy2023.value}.isdisjoint({4.1, 7.4, 16.9, 23.0})


def test_extract_phase_gct_prefers_monetary_da_over_per_share_artifact():
    result = _case_extract("GCT")

    assert result.periods["Q2-2023"].fields["depreciation_amortization"].value == 380.0
    assert result.periods["Q3-2023"].fields["depreciation_amortization"].value == 390.0
    assert result.periods["Q2-2025"].fields["depreciation_amortization"].value == 2140.0
    assert result.periods["Q3-2025"].fields["depreciation_amortization"].value == 2115.0


def test_extract_phase_0327_h1_interim_reports_are_shared_core_extractor_backed():
    result = _case_extract("0327")

    h1_2025 = result.periods["H1-2025"].fields
    h1_2024 = result.periods["H1-2024"].fields
    h1_2023 = result.periods["H1-2023"].fields

    assert h1_2025["ingresos"].value == 2716164.0
    assert h1_2025["eps_basic"].value == 0.369
    assert h1_2025["shares_outstanding"].value == 1060685.0
    assert h1_2025["accounts_receivable"].value == 2753840.0
    assert h1_2025["capex"].value == -43004.0
    assert h1_2025["total_debt"].value == 0.0
    assert h1_2025["shares_outstanding"].provenance.source_filing == "SRC_004_IR_H12025.txt"
    assert "hkex_interim_compact" in h1_2025["ingresos"].provenance.source_location

    assert h1_2024["ingresos"].value == 3013241.0
    assert h1_2024["shares_outstanding"].value == 1070525.0
    assert h1_2024["dividends_per_share"].value == 0.24

    assert h1_2023["ingresos"].value == 3568564.0
    assert h1_2023["shares_outstanding"].value == 1078240.0


def test_extract_phase_adtn_keeps_q1_q2_2023_net_income_on_same_quarter_sources():
    result = _case_extract("ADTN")

    assert result.periods["Q1-2023"].fields["net_income"].value == -40453.0
    assert result.periods["Q2-2023"].fields["net_income"].value == -36215.0


def test_extract_phase_adtn_promoted_quarters_total_liabilities_use_identity_bridge():
    result = _case_extract("ADTN")

    q1_2023 = result.periods["Q1-2023"].fields["total_liabilities"]
    q1_2024 = result.periods["Q1-2024"].fields["total_liabilities"]
    q1_2025 = result.periods["Q1-2025"].fields["total_liabilities"]

    assert q1_2023.value == 1117657.0
    assert q1_2023.provenance.source_filing == "SRC_010_10-Q_Q3-2024.clean.md"
    assert q1_2023.provenance.source_location.endswith(":bs_identity_bridge")

    assert q1_2024.value == 1066092.0
    assert q1_2024.provenance.source_filing == "SRC_009_10-Q_Q1-2025.htm"
    assert q1_2024.provenance.source_location.endswith(":bs_identity_bridge")

    assert q1_2025.value == 1054346.0
    assert q1_2025.provenance.source_filing == "SRC_009_10-Q_Q1-2025.htm"
    assert q1_2025.provenance.source_location.endswith(":bs_identity_bridge")


def test_extract_phase_gct_total_liabilities_absorbs_mezzanine_equity():
    result = _case_extract("GCT")

    assert result.periods["FY2021"].fields["total_liabilities"].value == 87597.0


def test_extract_phase_tzoo_total_liabilities_absorbs_non_controlling_interest():
    result = _case_extract("TZOO")

    assert result.periods["FY2020"].fields["total_liabilities"].value == 100509.0
    assert result.periods["FY2021"].fields["total_liabilities"].value == 103959.0
    assert result.periods["Q1-2022"].fields["total_liabilities"].value == 94352.0
    assert result.periods["Q2-2022"].fields["total_liabilities"].value == 77049.0
    assert result.periods["Q3-2022"].fields["total_liabilities"].value == 67704.0
    assert result.periods["Q1-2023"].fields["total_liabilities"].value == 58048.0


def test_extract_phase_tzoo_keeps_primary_total_equity_over_restated_rollforward():
    result = _case_extract("TZOO")

    assert result.periods["Q1-2022"].fields["total_equity"].value == -1469.0
    assert result.periods["Q2-2022"].fields["total_equity"].value == 1431.0
    assert result.periods["Q3-2022"].fields["total_equity"].value == 616.0


def test_extract_phase_adtn_full_prefers_restated_quarters_and_preserves_da_scale(
    tmp_path: Path,
):
    src = _REPO_ROOT / "cases" / "ADTN"
    dst = tmp_path / "ADTN"
    shutil.copytree(src, dst)

    case_config = json.loads((dst / "case.json").read_text(encoding="utf-8"))
    case_config["period_scope"] = "FULL"
    (dst / "case.json").write_text(
        json.dumps(case_config, indent=2) + "\n",
        encoding="utf-8",
    )

    result = ExtractPhase().extract(str(dst))

    assert result.periods["Q1-2023"].fields["eps_basic"].value == -0.51
    assert result.periods["Q1-2024"].fields["accounts_receivable"].value == 191052.0
    assert result.periods["Q3-2023"].fields["total_equity"].value == 675651.0
    assert result.periods["Q1-2024"].fields["total_equity"].value == 260849.0
    assert result.periods["Q2-2024"].fields["total_equity"].value == 213628.0
    assert result.periods["Q3-2024"].fields["total_equity"].value == 205578.0
    assert result.periods["Q3-2024"].fields["total_liabilities"].value == 1061487.0
    assert result.periods["Q2-2025"].fields["depreciation_amortization"].value == 7.6


# ── BL-084 / DEC-028: Finance lease fallback total_debt synthesis ─────────────

def _make_simple_tf(
    label: str,
    value: float,
    period: str,
    source_location: str = "",
    *,
    table_index: int = 0,
    row_idx: int = 0,
    col_idx: int = 0,
) -> TableField:
    """Helper: build a minimal TableField for BL-084 unit tests."""
    return TableField(
        label=label,
        value=value,
        column_header=period,
        source_location=source_location or f"SRC_test.clean.md:balance_sheet:tbl0:row{row_idx}:col{col_idx}",
        raw_text=str(value),
        col_label=period,
        table_title="balance_sheet",
        row_idx=row_idx,
        col_idx=col_idx,
        table_index=table_index,
    )


def _run_fl_synthesis(
    raw_fields: list,
    existing_total_debt=None,  # float or None
    filing_scale: str = "thousands",
    period: str = "FY2025",
):
    """Run _synthesize_finance_lease_fallback_debt and return total_debt result."""
    from types import SimpleNamespace
    from elsian.extract.phase import ExtractPhase

    phase = ExtractPhase()
    period_fields: dict = {}
    if existing_total_debt is not None:
        period_fields[period] = {
            "total_debt": _make_field_result(
                existing_total_debt,
                "thousands",
                "SRC_test.clean.md",
                "SRC_test.clean.md:balance_sheet:tbl0:row1:col1",
                "high",
            )
        }

    meta = SimpleNamespace(filing_type="10-K", scale="thousands")
    from pathlib import Path
    phase._synthesize_finance_lease_fallback_debt(
        period_fields=period_fields,
        raw_table_fields=raw_fields,
        filing_path=Path("SRC_test.clean.md"),
        filing_type="10-K",
        filing_scale=filing_scale,
        filing_scale_confidence="high",
        metadata_scale="thousands",
        rules={},
        preflight_result=None,
    )
    return period_fields.get(period, {}).get("total_debt")


def test_bl084_synthesizes_from_both_finance_lease_components():
    """Positive: both current + long-term → total_debt fallback is created."""
    fields = [
        _make_simple_tf("Current portion of finance lease obligation", 1575.0, "FY2025"),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    assert result is not None, "Expected finance lease fallback to synthesise total_debt"
    assert abs(result.value - 42329.0) < 1.0


def test_bl084_requires_both_components_missing_longterm():
    """Negative: only current component present → no synthesis."""
    fields = [
        _make_simple_tf("Current portion of finance lease obligation", 1575.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    assert result is None, "Should not synthesise with only current component"


def test_bl084_requires_both_components_missing_current():
    """Negative: only long-term component present → no synthesis."""
    fields = [
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    assert result is None, "Should not synthesise with only long-term component"


def test_bl084_explicit_aggregate_blocks_synthesis():
    """Precedence rule: existing explicit total_debt blocks finance lease synthesis."""
    fields = [
        _make_simple_tf("Current portion of finance lease obligation", 1575.0, "FY2025"),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    explicit_debt = 85000.0
    result = _run_fl_synthesis(fields, existing_total_debt=explicit_debt)
    # Must return the EXPLICIT value, not the synthesised one.
    assert result is not None
    assert abs(result.value - explicit_debt) < 1.0, (
        f"Explicit total_debt ({explicit_debt}) should win; got {result.value}"
    )


def test_bl084_no_duplication_when_explicit_and_components_coexist():
    """No duplication: synthesis skipped when explicit total_debt already present."""
    fields = [
        _make_simple_tf("Current portion of finance lease obligation", 1575.0, "FY2025"),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    explicit_debt = 120000.0
    result = _run_fl_synthesis(fields, existing_total_debt=explicit_debt)
    assert result is not None
    assert result.value != 42329.0, "Synthesis must not overwrite explicit aggregate"
    assert abs(result.value - explicit_debt) < 1.0


def test_bl084_operating_lease_excluded():
    """Negative: operating lease liabilities are excluded from synthesis."""
    fields = [
        _make_simple_tf("Operating lease liabilities, current", 2000.0, "FY2025"),
        _make_simple_tf("Operating lease liabilities, non-current", 8000.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    assert result is None, "Operating lease liabilities must not enter total_debt"


def test_bl084_lease_expense_excluded():
    """Negative: lease expense label must not contribute to total_debt."""
    fields = [
        _make_simple_tf("Finance lease expense", 500.0, "FY2025"),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    # Finance lease expense must not match _FINANCE_LEASE_CURR_RE; only one
    # component (long-term) is found → synthesis must not activate.
    assert result is None, "lease expense must not be treated as current component"


def test_bl084_principal_payments_excluded():
    """Negative: principal payments on finance lease (cash flow) must be excluded."""
    fields = [
        _make_simple_tf(
            "Principal payments on finance lease obligation",
            1357.0,
            "FY2025",
            source_location="SRC_test.clean.md:cash_flow:tbl0:row5:col1",
        ),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    # Principal payments label must not match current-component pattern; only
    # long-term found → no synthesis.
    assert result is None, "Principal payments must not be treated as current component"


def test_bl084_cash_flow_context_excluded():
    """Negative: finance lease components from :cash_flow: source are excluded."""
    fields = [
        _make_simple_tf(
            "Current portion of finance lease obligation",
            1575.0,
            "FY2025",
            source_location="SRC_test.clean.md:cash_flow:tbl1:row3:col1",
        ),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, "FY2025"),
    ]
    result = _run_fl_synthesis(fields)
    # Current component is from cash-flow section → excluded → only long-term
    # remains → synthesis must not activate.
    assert result is None, "Cash-flow-sourced current component must be excluded"


def test_bl084_total_debt_from_cashflow_existing_guardrail():
    """Regression: _candidate_context_bonus still penalises total_debt from CF."""
    from elsian.extract.phase import _candidate_context_bonus
    bonus = _candidate_context_bonus(
        "total_debt",
        "Repayment of long-term debt",
        "SRC.clean.md:cash_flow:tbl1:row5:col1",
        5000.0,
        "thousands",
    )
    assert bonus <= -300, "Cash-flow repayment of debt must be heavily penalised"


def test_bl084_negative_total_debt_in_IS_discarded_via_process_table_field(tmp_path):
    """Regression: negative total_debt from income-statement is discarded."""
    import shutil
    src = _REPO_ROOT / "cases" / "ACLS"
    dst = tmp_path / "ACLS"
    shutil.copytree(src, dst)
    result = ExtractPhase().extract(str(dst))
    # total_debt must never be negative (IS sign convention guard).
    for pk, pr in result.periods.items():
        if "total_debt" in pr.fields:
            assert pr.fields["total_debt"].value >= 0, (
                f"total_debt for {pk} is negative: {pr.fields['total_debt'].value}"
            )


def test_bl084_fallback_synthesis_sort_key_loses_to_neutral_explicit():
    """Sort key of fallback synthesis is strictly worse than neutral explicit signal."""
    fallback_sk = compute_sort_key(
        period_key="FY2025",
        filing_type="10-K",
        source_type="table",
        label_priority=0,
        section_bonus_val=-1,          # fallback uses -1
        source_filing="SRC_001.clean.md",
        source_location="SRC_001.clean.md:balance_sheet:tbl0:row10:col1:finance_lease_fallback",
        rules={},
        canonical_field="total_debt",
        restatement_detected=False,
    )
    explicit_sk = compute_sort_key(
        period_key="FY2025",
        filing_type="10-K",
        source_type="table",
        label_priority=0,
        section_bonus_val=0,           # neutral explicit signal
        source_filing="SRC_001.clean.md",
        source_location="SRC_001.clean.md:balance_sheet:tbl0:row5:col1",
        rules={},
        canonical_field="total_debt",
        restatement_detected=False,
    )
    assert explicit_sk < fallback_sk, (
        "Explicit debt signal sort key must be strictly better (lower) than "
        "finance lease fallback sort key within the same filing"
    )


# ── BL-084 auditor fix: vertical.py/TXT path precedence alignment ─────────────

def test_bl084_vertical_finance_lease_fallback_carries_sentinel():
    """extract_vertical_bs finance lease fallback must carry :finance_lease_fallback
    sentinel in source_location so phase.py assigns section_bonus_val=-1 (DEC-028).
    """
    from elsian.extract.vertical import extract_vertical_bs

    # Minimal vertical-format .txt snippet with only finance lease labels
    # (no explicit current portion of long-term debt / long-term debt)
    # so the finance lease fallback path in Step 4b activates.
    text = """\
CONSOLIDATED BALANCE SHEETS
    2025   2024
ASSETS
Cash and cash equivalents
     1000
      900
Current portion of finance lease obligation
      200
      150
Long-term finance lease obligation
      800
      600
Total assets
    10000
     9000
See accompanying notes
"""
    results = extract_vertical_bs(text, source_filename="SRC_001.txt")
    fallback_fields = [
        tf for tf in results
        if "finance_lease_fallback" in tf.source_location
    ]
    assert fallback_fields, (
        "extract_vertical_bs must emit at least one finance lease fallback "
        "field with ':finance_lease_fallback' in source_location"
    )
    for tf in fallback_fields:
        assert ":total_debt:finance_lease_fallback" in tf.source_location, (
            f"source_location must include ':total_debt:finance_lease_fallback', got: "
            f"{tf.source_location!r}"
        )


def test_bl084_vertical_finance_lease_fallback_sort_key_loses_to_neutral_explicit():
    """Sort key of vertical.py finance lease fallback must be strictly worse
    than a neutral explicit total_debt signal (DEC-028 cross-filing guarantee).

    The sentinel ':finance_lease_fallback' in source_location causes phase.py to
    assign section_bonus_val=-1; an explicit signal gets section_bonus_val=0.
    A lower sort key wins, so the explicit signal must have a strictly lower key.
    """
    # Sort key that phase.py would assign to the vertical finance lease fallback
    # after the BL-084 auditor fix (section_bonus_val=-1 from the sentinel).
    fallback_sk = compute_sort_key(
        period_key="FY2025",
        filing_type="10-K",
        source_type="table",
        label_priority=0,
        section_bonus_val=-1,          # assigned by phase.py via :finance_lease_fallback
        source_filing="SRC_001.txt",
        source_location="SRC_001.txt:vertical_bs:consolidated:total_debt:finance_lease_fallback",
        rules={},
        canonical_field="total_debt",
        restatement_detected=False,
    )
    # Sort key of a neutral explicit total_debt signal from any other filing
    # (section_bonus_val=0, same period, same filing_type).
    explicit_sk = compute_sort_key(
        period_key="FY2025",
        filing_type="10-K",
        source_type="table",
        label_priority=0,
        section_bonus_val=0,           # neutral explicit signal
        source_filing="SRC_002.txt",
        source_location="SRC_002.txt:vertical_bs:consolidated:total_debt",
        rules={},
        canonical_field="total_debt",
        restatement_detected=False,
    )
    assert explicit_sk < fallback_sk, (
        "Neutral explicit total_debt sort key must be strictly better (lower) "
        "than vertical finance lease fallback sort key (DEC-028 guarantee)"
    )


# ── BL-084 shared-core fix: cross-filing isolation of synthesis block ─────────

def test_bl084_crossfiling_total_debt_does_not_block_filing_local_synthesis():
    """DEC-028 regression: cross-filing total_debt from a prior filing must not
    prevent the current filing from synthesising its own finance-lease fallback.

    Multi-filing scenario:
    - Filing A (SRC_A.clean.md) already produced total_debt = 95000.
    - Filing B (SRC_B.clean.md) has ONLY finance-lease components, no explicit debt.
    - After the BL-084 shared-core fix, synthesis for filing B must proceed
      regardless of filing A's contribution to period_fields.
    - The fallback sort key (section_bonus_val=-1) must remain strictly worse
      than filing A's explicit signal so the merge phase still prefers filing A.
    """
    from pathlib import Path

    cross_filing_debt = 95000.0
    period = "FY2025"

    # Simulate period_fields contaminated with filing A's total_debt.
    # SRC_A ≠ SRC_B → cross-filing signal that must NOT block synthesis.
    period_fields_b: dict = {
        period: {
            "total_debt": _make_field_result(
                cross_filing_debt,
                "thousands",
                "SRC_A.clean.md",
                "SRC_A.clean.md:balance_sheet:tbl0:row1:col1",
                "high",
            )
        }
    }

    raw_fields_b = [
        _make_simple_tf("Current portion of finance lease obligation", 1575.0, period),
        _make_simple_tf("Long-term finance lease obligation", 40754.0, period),
    ]

    phase = ExtractPhase()
    phase._synthesize_finance_lease_fallback_debt(
        period_fields=period_fields_b,
        raw_table_fields=raw_fields_b,
        filing_path=Path("SRC_B.clean.md"),
        filing_type="10-K",
        filing_scale="thousands",
        filing_scale_confidence="high",
        metadata_scale="thousands",
        rules={},
        preflight_result=None,
    )

    result = period_fields_b.get(period, {}).get("total_debt")

    # After fix: synthesis must have run for filing B, overwriting the
    # cross-filing placeholder in this isolated dict with the fallback.
    assert result is not None
    assert abs(result.value - 42329.0) < 1.0, (
        f"Filing B must synthesise its own fallback (42329.0); got {result.value}. "
        "Cross-filing total_debt from filing A must not suppress local synthesis."
    )
    assert ":finance_lease_fallback" in result.provenance.source_location, (
        "Synthesised fallback must carry the :finance_lease_fallback sentinel "
        "so that phase.py assigns section_bonus_val=-1 in cross-filing merge."
    )

    # The fallback sort key must be strictly worse than filing A's explicit
    # signal, so the real merge phase still selects filing A's value overall.
    fallback_sk = getattr(result, "_sort_key", None)
    assert fallback_sk is not None, "Synthesised fallback must carry a _sort_key."
    explicit_sk = compute_sort_key(
        period_key=period,
        filing_type="10-K",
        source_type="table",
        label_priority=0,
        section_bonus_val=0,
        source_filing="SRC_A.clean.md",
        source_location="SRC_A.clean.md:balance_sheet:tbl0:row1:col1",
        rules={},
        canonical_field="total_debt",
        restatement_detected=False,
    )
    assert explicit_sk < fallback_sk, (
        "Filing A explicit sort key must be strictly better (lower) than "
        "filing B finance-lease fallback sort key (DEC-028 cross-filing guarantee)."
    )
