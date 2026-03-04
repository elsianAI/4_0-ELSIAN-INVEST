"""Tests for ExtractPhase sign normalization and helper functions."""

from elsian.extract.phase import (
    _normalize_sign,
    _section_bonus,
    _filing_rank,
    _source_type_rank,
    _period_affinity,
    compute_sort_key,
    _make_field_result,
)


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
    """Split-sensitive field: FY2024 data from FY2024 filing → affinity 0."""
    assert _period_affinity("FY2024", "SRC_003_10-K_FY2024.clean.md", "eps_basic") == 0


def test_period_affinity_split_sensitive_comparative():
    """Split-sensitive field: FY2024 data from a LATER filing → affinity 1."""
    assert _period_affinity("FY2024", "SRC_001_10-K_FY2026.clean.md", "eps_diluted") == 1


def test_period_affinity_non_split_always_zero():
    """Non-split fields: always affinity 0 regardless of filing, so newer filing wins."""
    assert _period_affinity("FY2019", "SRC_006_10-K_FY2019.clean.md", "ingresos") == 0
    assert _period_affinity("FY2019", "SRC_005_10-K_FY2020.clean.md", "ingresos") == 0


def test_period_affinity_fy_no_tag():
    """FY period from a file without FY tag → affinity 1 for split-sensitive,
    0 for non-split (newer file wins)."""
    assert _period_affinity("FY2024", "anything.clean.md", "eps_basic") == 1
    assert _period_affinity("FY2024", "anything.clean.md", "ingresos") == 0


def test_period_affinity_q_primary():
    """Q periods always prefer primary filing regardless of field."""
    assert _period_affinity("Q1-2024", "SRC_010_10-Q_Q1-2024.clean.md", "eps_basic") == 0
    assert _period_affinity("Q1-2024", "SRC_010_10-Q_Q1-2024.clean.md", "ingresos") == 0


def test_period_affinity_q_comparative():
    """Q periods: comparative filing → affinity 1 for ALL fields."""
    assert _period_affinity("Q1-2024", "SRC_012_10-Q_Q3-2024.clean.md", "eps_basic") == 1
    assert _period_affinity("Q1-2024", "SRC_012_10-Q_Q3-2024.clean.md", "ingresos") == 1


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