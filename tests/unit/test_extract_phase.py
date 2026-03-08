"""Tests for ExtractPhase sign normalization and helper functions."""

from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from elsian.extract.html_tables import TableField
from elsian.extract.phase import (
    ExtractPhase,
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

    assert fy2023.value == 0.2319
    assert fy2023.provenance.source_filing == "SRC_001_ANNUAL_REPORT_FY2024.txt"
    assert fy2023.provenance.extraction_method == "table"
    assert "financial_highlights_dps" in fy2023.provenance.source_location
    assert {fy2024.value, fy2023.value}.isdisjoint({4.1, 7.4, 16.9, 23.0})


def test_extract_phase_gct_prefers_monetary_da_over_per_share_artifact():
    result = _case_extract("GCT")

    assert result.periods["Q2-2023"].fields["depreciation_amortization"].value == 380.0
    assert result.periods["Q3-2023"].fields["depreciation_amortization"].value == 390.0
    assert result.periods["Q2-2025"].fields["depreciation_amortization"].value == 2140.0
    assert result.periods["Q3-2025"].fields["depreciation_amortization"].value == 2115.0


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
