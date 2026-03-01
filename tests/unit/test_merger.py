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
