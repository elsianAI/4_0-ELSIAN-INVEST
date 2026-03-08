"""Tests for multi-filing merge logic ported from 3.0."""

from elsian.models.field import FieldResult, Provenance
from elsian.merge.merger import merge_extractions


def _make_fr(value, source="test.md"):
    return FieldResult(
        value=value,
        provenance=Provenance(source_filing=source),
    )


def test_merge_single_filing():
    filing = (
        "10-K",
        "10k.md",
        {"FY2024": {"ingresos": _make_fr(1000, "10k.md")}},
    )
    result = merge_extractions([filing], ticker="TEST")
    assert "FY2024" in result.periods
    assert result.periods["FY2024"].fields["ingresos"].value == 1000


def test_merge_priority_annual_over_quarterly():
    annual = (
        "10-K",
        "10k.md",
        {"FY2024": {"ingresos": _make_fr(1000, "10k.md")}},
    )
    quarterly = (
        "10-Q",
        "10q.md",
        {"FY2024": {"ingresos": _make_fr(999, "10q.md")}},
    )
    # Annual filed first, quarterly tries to override
    result = merge_extractions([annual, quarterly], ticker="TEST")
    assert result.periods["FY2024"].fields["ingresos"].value == 1000


def test_merge_multiple_periods():
    filing = (
        "10-K",
        "10k.md",
        {
            "FY2024": {"ingresos": _make_fr(1000)},
            "FY2023": {"ingresos": _make_fr(900)},
        },
    )
    result = merge_extractions([filing], ticker="TEST")
    assert len(result.periods) == 2
    assert result.periods["FY2024"].fields["ingresos"].value == 1000
    assert result.periods["FY2023"].fields["ingresos"].value == 900


def test_merge_audit_record():
    filing = (
        "10-K",
        "10k.md",
        {"FY2024": {"ingresos": _make_fr(1000)}},
    )
    result = merge_extractions([filing], ticker="TEST")
    assert result.audit.fields_extracted == 1


def test_merge_same_priority_prefers_better_affinity():
    comparative = _make_fr(25.2, "SRC_001_10-K_FY2025.clean.md")
    comparative._sort_key = (0, 1, 0, 0, ("SRC_001_10-K_FY2025.clean.md", -1, -11, 5))
    primary = _make_fr(232918.0, "SRC_002_10-K_FY2024.htm")
    primary._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))

    result = merge_extractions(
        [
            ("10-K", "SRC_001_10-K_FY2025.clean.md", {"FY2024": {"sga": comparative}}),
            ("10-K", "SRC_002_10-K_FY2024.htm", {"FY2024": {"sga": primary}}),
        ],
        ticker="TEST",
    )

    assert result.periods["FY2024"].fields["sga"].value == 232918.0


def test_merge_same_priority_replaces_penalized_existing_semantics():
    penalized = _make_fr(25.2, "SRC_001_10-K_FY2025.clean.md")
    penalized._sort_key = (0, 0, 0, 50, ("SRC_001_10-K_FY2025.clean.md", -1, -11, 5))
    better = _make_fr(232918.0, "SRC_002_10-K_FY2024.htm")
    better._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))

    result = merge_extractions(
        [
            ("10-K", "SRC_001_10-K_FY2025.clean.md", {"FY2024": {"sga": penalized}}),
            ("10-K", "SRC_002_10-K_FY2024.htm", {"FY2024": {"sga": better}}),
        ],
        ticker="TEST",
    )

    assert result.periods["FY2024"].fields["sga"].value == 232918.0


def test_merge_eps_keeps_close_newer_comparative_over_primary():
    newer_comparative = _make_fr(-3.43, "SRC_001_10-K_FY2025.htm")
    newer_comparative._sort_key = (0, 1, -1, -9999, ("", 0, 0, 0))
    primary = _make_fr(-3.39, "SRC_002_10-K_FY2024.htm")
    primary._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))

    result = merge_extractions(
        [
            ("10-K", "SRC_001_10-K_FY2025.htm", {"FY2023": {"eps_basic": newer_comparative}}),
            ("10-K", "SRC_002_10-K_FY2024.htm", {"FY2023": {"eps_basic": primary}}),
        ],
        ticker="TEST",
    )

    assert result.periods["FY2023"].fields["eps_basic"].value == -3.43


def test_merge_eps_replaces_large_drift_newer_comparative_with_primary():
    newer_comparative = _make_fr(0.18, "SRC_001_10-K_FY2025.htm")
    newer_comparative._sort_key = (0, 1, -1, -9999, ("", 0, 0, 0))
    primary = _make_fr(1.76, "SRC_002_10-K_FY2023.htm")
    primary._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))

    result = merge_extractions(
        [
            ("10-K", "SRC_001_10-K_FY2025.htm", {"FY2023": {"eps_basic": newer_comparative}}),
            ("10-K", "SRC_002_10-K_FY2023.htm", {"FY2023": {"eps_basic": primary}}),
        ],
        ticker="TEST",
    )

    assert result.periods["FY2023"].fields["eps_basic"].value == 1.76


def test_merge_eps_replaces_weighted_average_disclosure_with_primary():
    newer_disclosure = _make_fr(-0.15, "SRC_002_20-F_FY2024.clean.md")
    newer_disclosure.provenance.source_location = (
        "SRC_002_20-F_FY2024.clean.md:table:income_statement:"
        "weighted_average_number_of_ordinary_shares_used_to_calculate_"
        "basic_earnings_per_share:tbl32:row3:col2"
    )
    newer_disclosure._sort_key = (0, 0, 0, 0, ("", 0, 0, 0))
    primary = _make_fr(-0.3, "SRC_003_20-F_FY2023.clean.md")
    primary.provenance.source_location = (
        "SRC_003_20-F_FY2023.clean.md:table:income_statement:tbl1:row30:col1"
    )
    primary._sort_key = (0, 0, 0, 0, ("", 0, 0, 0))

    result = merge_extractions(
        [
            ("20-F", "SRC_002_20-F_FY2024.clean.md", {"FY2023": {"eps_basic": newer_disclosure}}),
            ("20-F", "SRC_003_20-F_FY2023.clean.md", {"FY2023": {"eps_basic": primary}}),
        ],
        ticker="TEST",
    )

    assert result.periods["FY2023"].fields["eps_basic"].value == -0.3


def test_merge_eps_prefers_explicit_restatement_candidate():
    primary = _make_fr(-0.44, "SRC_015_10-Q_Q1-2023.htm")
    primary._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))
    restated = _make_fr(-0.51, "SRC_010_10-Q_Q3-2024.htm")
    restated._sort_key = (0, 0, -1, -9999, ("", 0, 0, 0))
    restated._is_explicit_restatement = True

    result = merge_extractions(
        [
            ("10-Q", "SRC_015_10-Q_Q1-2023.htm", {"Q1-2023": {"eps_basic": primary}}),
            ("10-Q", "SRC_010_10-Q_Q3-2024.htm", {"Q1-2023": {"eps_basic": restated}}),
        ],
        ticker="TEST",
    )

    assert result.periods["Q1-2023"].fields["eps_basic"].value == -0.51
