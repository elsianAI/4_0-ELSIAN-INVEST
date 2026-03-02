"""Unit tests for the iXBRL parser (elsian.extract.ixbrl)."""

from __future__ import annotations

import json
import textwrap
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from elsian.extract.ixbrl import (
    ContextInfo,
    IxbrlFact,
    compute_actual_value,
    deduplicate_facts,
    generate_expected_draft,
    map_concept,
    parse_contexts,
    parse_displayed_value,
    parse_ixbrl_filing,
    resolve_period_label,
    run_sanity_checks,
    _fiscal_year_for_date,
    _quarter_for_date,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_IXBRL = textwrap.dedent("""\
    <?xml version='1.0' encoding='ASCII'?>
    <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
          xmlns:xbrli="http://www.xbrl.org/2003/instance"
          xmlns:us-gaap="http://fasb.org/us-gaap/2024"
          xml:lang="en-US">
    <head><title>Test</title></head>
    <body>
    <div style="display:none">
    <ix:header>
    <ix:resources>
    <xbrli:context id="c-1">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2024-01-01</xbrli:startDate>
        <xbrli:endDate>2024-12-31</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    <xbrli:context id="c-2">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:instant>2024-12-31</xbrli:instant>
      </xbrli:period>
    </xbrli:context>
    <xbrli:context id="c-3">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
        <xbrli:segment>
          <xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">test:SegmentA</xbrldi:explicitMember>
        </xbrli:segment>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2024-01-01</xbrli:startDate>
        <xbrli:endDate>2024-12-31</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    <xbrli:context id="c-q3">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2024-07-01</xbrli:startDate>
        <xbrli:endDate>2024-09-30</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    </ix:resources>
    </ix:header>
    </div>
    <p>
    Revenue: <ix:nonFraction unitRef="usd" contextRef="c-1" decimals="-3" name="us-gaap:Revenues" format="ixt:num-dot-decimal" scale="3" id="f-1">83,902</ix:nonFraction>
    Net Income: <ix:nonFraction unitRef="usd" contextRef="c-1" decimals="-3" name="us-gaap:NetIncomeLoss" format="ixt:num-dot-decimal" scale="3" id="f-2">13,564</ix:nonFraction>
    EPS: <ix:nonFraction unitRef="usdPerShare" contextRef="c-1" decimals="2" name="us-gaap:EarningsPerShareBasic" scale="0" id="f-3">1.08</ix:nonFraction>
    Assets: <ix:nonFraction unitRef="usd" contextRef="c-2" decimals="-3" name="us-gaap:Assets" format="ixt:num-dot-decimal" scale="3" id="f-4">54,722</ix:nonFraction>
    Segment Revenue: <ix:nonFraction unitRef="usd" contextRef="c-3" decimals="-3" name="us-gaap:Revenues" format="ixt:num-dot-decimal" scale="3" id="f-5">24,113</ix:nonFraction>
    Q3 Revenue: <ix:nonFraction unitRef="usd" contextRef="c-q3" decimals="-3" name="us-gaap:Revenues" format="ixt:num-dot-decimal" scale="3" id="f-6">21,000</ix:nonFraction>
    Capex: <ix:nonFraction unitRef="usd" contextRef="c-1" decimals="-3" name="us-gaap:PaymentsToAcquirePropertyPlantAndEquipment" format="ixt:num-dot-decimal" scale="3" id="f-7">177</ix:nonFraction>
    Unknown: <ix:nonFraction unitRef="usd" contextRef="c-1" decimals="-3" name="us-gaap:SomethingUnknown" scale="3" id="f-8">999</ix:nonFraction>
    Negative: <ix:nonFraction unitRef="usd" contextRef="c-1" decimals="-3" name="us-gaap:NetIncomeLoss" format="ixt:num-dot-decimal" scale="3" sign="-" id="f-9">500</ix:nonFraction>
    </p>
    </body>
    </html>
""")


@pytest.fixture
def ixbrl_file(tmp_path: Path) -> Path:
    """Create a temporary iXBRL file for testing."""
    fp = tmp_path / "test_filing.htm"
    fp.write_text(MINIMAL_IXBRL, encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# parse_displayed_value tests
# ---------------------------------------------------------------------------

class TestParseDisplayedValue:
    def test_simple_integer(self):
        assert parse_displayed_value("83902") == 83902.0

    def test_comma_separated(self):
        assert parse_displayed_value("83,902") == 83902.0

    def test_decimal(self):
        assert parse_displayed_value("1.08") == 1.08

    def test_parentheses_negative(self):
        assert parse_displayed_value("(5,404)") == -5404.0

    def test_em_dash_zero(self):
        assert parse_displayed_value("—") == 0.0

    def test_en_dash_zero(self):
        assert parse_displayed_value("–") == 0.0

    def test_empty_string(self):
        assert parse_displayed_value("") == 0.0

    def test_whitespace(self):
        assert parse_displayed_value("  83,902  ") == 83902.0

    def test_nbsp(self):
        assert parse_displayed_value("\u00a083,902\u00a0") == 83902.0

    def test_dollar_sign(self):
        assert parse_displayed_value("$1,234") == 1234.0

    def test_zero(self):
        assert parse_displayed_value("0") == 0.0

    def test_small_decimal(self):
        assert parse_displayed_value("0.016") == 0.016

    def test_large_number(self):
        assert parse_displayed_value("215,938") == 215938.0


# ---------------------------------------------------------------------------
# compute_actual_value tests
# ---------------------------------------------------------------------------

class TestComputeActualValue:
    def test_scale_zero(self):
        assert compute_actual_value(1.08, 0) == 1.08

    def test_scale_three(self):
        assert compute_actual_value(83902, 3) == 83902000.0

    def test_scale_six(self):
        assert compute_actual_value(215938, 6) == 215938000000.0

    def test_scale_nine(self):
        assert compute_actual_value(24.3, 9) == 24300000000.0

    def test_scale_twelve(self):
        assert compute_actual_value(4.0, 12) == 4000000000000.0


# ---------------------------------------------------------------------------
# Context and period resolution tests
# ---------------------------------------------------------------------------

class TestFiscalYearForDate:
    def test_calendar_year(self):
        assert _fiscal_year_for_date(date(2024, 12, 31), 12) == 2024

    def test_january_fy(self):
        """NVDA: FY ends January → Jan 25, 2026 is FY2026."""
        assert _fiscal_year_for_date(date(2026, 1, 25), 1) == 2026

    def test_october_fy(self):
        """SONO: FY ends September → Sep 30, 2024 is FY2024."""
        assert _fiscal_year_for_date(date(2024, 9, 30), 9) == 2024

    def test_mid_year(self):
        """June 30 with FY ending December is still FY2024."""
        assert _fiscal_year_for_date(date(2024, 6, 30), 12) == 2024


class TestQuarterForDate:
    def test_calendar_q1(self):
        assert _quarter_for_date(date(2024, 3, 31), 12) == 1

    def test_calendar_q2(self):
        assert _quarter_for_date(date(2024, 6, 30), 12) == 2

    def test_calendar_q3(self):
        assert _quarter_for_date(date(2024, 9, 30), 12) == 3

    def test_calendar_q4(self):
        assert _quarter_for_date(date(2024, 12, 31), 12) == 4

    def test_nvda_q1(self):
        """NVDA FY ends January. Q1 ends ~April."""
        assert _quarter_for_date(date(2025, 4, 27), 1) == 1

    def test_nvda_q2(self):
        """NVDA Q2 ends ~July."""
        assert _quarter_for_date(date(2025, 7, 27), 1) == 2

    def test_nvda_q3(self):
        """NVDA Q3 ends ~October."""
        assert _quarter_for_date(date(2025, 10, 26), 1) == 3


class TestResolvePeriodLabel:
    def test_annual_duration(self):
        ctx = ContextInfo("c-1", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        assert resolve_period_label(ctx, 12) == "FY2024"

    def test_quarterly_duration(self):
        ctx = ContextInfo("c-5", start_date=date(2024, 7, 1), end_date=date(2024, 9, 30))
        assert resolve_period_label(ctx, 12) == "Q3-2024"

    def test_instant_fy_end(self):
        ctx = ContextInfo("c-4", instant_date=date(2024, 12, 31))
        assert resolve_period_label(ctx, 12) == "FY2024"

    def test_instant_q3_end(self):
        ctx = ContextInfo("c-3", instant_date=date(2024, 9, 30))
        assert resolve_period_label(ctx, 12) == "Q3-2024"

    def test_segment_context_returns_none(self):
        ctx = ContextInfo("c-seg", start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), has_segment=True)
        assert resolve_period_label(ctx, 12) is None

    def test_ytd_9_months_returns_none(self):
        """9-month YTD periods should not map to a standard period."""
        ctx = ContextInfo("c-ytd", start_date=date(2024, 1, 1), end_date=date(2024, 9, 30))
        assert resolve_period_label(ctx, 12) is None

    def test_nvda_annual(self):
        ctx = ContextInfo("c-1", start_date=date(2025, 1, 27), end_date=date(2026, 1, 25))
        assert resolve_period_label(ctx, 1) == "FY2026"

    def test_nvda_instant_fy_end(self):
        ctx = ContextInfo("c-2", instant_date=date(2026, 1, 25))
        assert resolve_period_label(ctx, 1) == "FY2026"


# ---------------------------------------------------------------------------
# Concept mapping tests
# ---------------------------------------------------------------------------

class TestConceptMapping:
    def test_revenue_maps(self):
        assert map_concept("us-gaap:Revenues") == "ingresos"

    def test_revenue_variant_maps(self):
        assert map_concept("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax") == "ingresos"

    def test_net_income_maps(self):
        assert map_concept("us-gaap:NetIncomeLoss") == "net_income"

    def test_unknown_returns_none(self):
        assert map_concept("us-gaap:SomethingUnknown") is None

    def test_capex_maps(self):
        assert map_concept("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment") == "capex"

    def test_equity_inclusive(self):
        result = map_concept("us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
        assert result == "total_equity"


# ---------------------------------------------------------------------------
# Full parser tests (using fixture file)
# ---------------------------------------------------------------------------

class TestParseIxbrlFiling:
    def test_parses_facts_from_fixture(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        assert len(facts) > 0

    def test_filters_dimensional_contexts(self, ixbrl_file: Path):
        """Segment revenue (c-3) should NOT appear in results."""
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        segment_facts = [f for f in facts if f.context_ref == "c-3"]
        assert len(segment_facts) == 0

    def test_maps_revenue(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        rev_facts = [f for f in facts if f.field == "ingresos" and f.period == "FY2024"]
        assert len(rev_facts) >= 1
        assert rev_facts[0].value == 83902.0

    def test_maps_eps(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        eps_facts = [f for f in facts if f.field == "eps_basic" and f.period == "FY2024"]
        assert len(eps_facts) >= 1
        assert eps_facts[0].value == 1.08

    def test_maps_assets_from_instant(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        asset_facts = [f for f in facts if f.field == "total_assets" and f.period == "FY2024"]
        assert len(asset_facts) >= 1
        assert asset_facts[0].value == 54722.0

    def test_capex_is_negated(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        capex_facts = [f for f in facts if f.field == "capex" and f.period == "FY2024"]
        assert len(capex_facts) >= 1
        assert capex_facts[0].value == -177.0

    def test_unmapped_concept_returns_none_field(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        unknown_facts = [f for f in facts if f.concept == "us-gaap:SomethingUnknown"]
        assert len(unknown_facts) >= 1
        assert unknown_facts[0].field is None

    def test_sign_attribute_negates(self, ixbrl_file: Path):
        """Tag with sign='-' should have negated value."""
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        neg_facts = [f for f in facts if f.tag_id == "f-9"]
        assert len(neg_facts) == 1
        assert neg_facts[0].value == -500.0
        assert neg_facts[0].is_negated

    def test_quarterly_period_resolved(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        q3_facts = [f for f in facts if f.period == "Q3-2024"]
        assert len(q3_facts) >= 1

    def test_provenance_fields(self, ixbrl_file: Path):
        facts = parse_ixbrl_filing(ixbrl_file, fiscal_year_end_month=12)
        fact = facts[0]
        assert fact.source_filing == "test_filing.htm"
        assert fact.concept
        assert fact.context_ref
        assert fact.tag_id


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

class TestDeduplicateFacts:
    def test_basic_dedup(self):
        facts = [
            IxbrlFact("us-gaap:Revenues", "ingresos", "FY2024", 83902, "83,902", 3, "-3", "usd", "c-1", "f-1", "test.htm"),
            IxbrlFact("us-gaap:Revenues", "ingresos", "FY2024", 83902, "83,902", 3, "-3", "usd", "c-1", "f-2", "test.htm"),
        ]
        result = deduplicate_facts(facts)
        assert len(result["FY2024"]) == 1
        assert result["FY2024"]["ingresos"].value == 83902

    def test_preferred_concept_wins(self):
        facts = [
            IxbrlFact("us-gaap:StockholdersEquity", "total_equity", "FY2024", 462, "462", 3, "-3", "usd", "c-1", "f-1", "test.htm"),
            IxbrlFact("us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "total_equity", "FY2024", 4353, "4,353", 3, "-3", "usd", "c-1", "f-2", "test.htm"),
        ]
        preferred = {"total_equity": [
            "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            "us-gaap:StockholdersEquity",
        ]}
        result = deduplicate_facts(facts, preferred_concepts=preferred)
        assert result["FY2024"]["total_equity"].value == 4353

    def test_unmapped_fields_excluded(self):
        facts = [
            IxbrlFact("us-gaap:Unknown", None, "FY2024", 999, "999", 3, "-3", "usd", "c-1", "f-1", "test.htm"),
        ]
        result = deduplicate_facts(facts)
        assert "FY2024" not in result


# ---------------------------------------------------------------------------
# Sanity check tests
# ---------------------------------------------------------------------------

class TestSanityChecks:
    def test_no_warnings_on_valid(self):
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "ingresos": {"value": 100},
                        "total_assets": {"value": 500},
                        "total_liabilities": {"value": 300},
                        "total_equity": {"value": 200},
                        "net_income": {"value": 50},
                        "eps_basic": {"value": 2.5},
                    }
                }
            }
        }
        assert run_sanity_checks(draft) == []

    def test_negative_revenue_warning(self):
        draft = {"periods": {"FY2024": {"fields": {"ingresos": {"value": -100}}}}}
        warnings = run_sanity_checks(draft)
        assert any("ingresos" in w for w in warnings)

    def test_balance_sheet_mismatch_warning(self):
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "total_assets": {"value": 1000},
                        "total_liabilities": {"value": 300},
                        "total_equity": {"value": 200},  # 300+200=500 ≠ 1000
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert any("A≠L+E" in w for w in warnings)

    def test_ni_eps_sign_mismatch(self):
        draft = {
            "periods": {
                "FY2024": {
                    "fields": {
                        "net_income": {"value": -100},
                        "eps_basic": {"value": 0.5},
                    }
                }
            }
        }
        warnings = run_sanity_checks(draft)
        assert any("opposite signs" in w for w in warnings)


# ---------------------------------------------------------------------------
# generate_expected_draft tests
# ---------------------------------------------------------------------------

class TestGenerateExpectedDraft:
    def test_basic_structure(self):
        facts = {
            "FY2024": {
                "ingresos": IxbrlFact("us-gaap:Revenues", "ingresos", "FY2024", 83902, "83,902", 3, "-3", "usd", "c-1", "f-1", "test.htm"),
            }
        }
        draft = generate_expected_draft(facts, "TEST", "USD")
        assert draft["ticker"] == "TEST"
        assert draft["currency"] == "USD"
        assert "FY2024" in draft["periods"]
        assert "ingresos" in draft["periods"]["FY2024"]["fields"]
        field = draft["periods"]["FY2024"]["fields"]["ingresos"]
        assert field["value"] == 83902
        assert field["_source"] == "ixbrl"
        assert field["_concept"] == "us-gaap:Revenues"


# ---------------------------------------------------------------------------
# Context parsing tests
# ---------------------------------------------------------------------------

class TestParseContexts:
    def test_parses_duration_and_instant(self, ixbrl_file: Path):
        from bs4 import BeautifulSoup
        with open(ixbrl_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        contexts = parse_contexts(soup)
        assert "c-1" in contexts
        assert contexts["c-1"].is_duration
        assert contexts["c-1"].start_date == date(2024, 1, 1)
        assert contexts["c-1"].end_date == date(2024, 12, 31)

        assert "c-2" in contexts
        assert contexts["c-2"].is_instant
        assert contexts["c-2"].instant_date == date(2024, 12, 31)

    def test_segment_flag(self, ixbrl_file: Path):
        from bs4 import BeautifulSoup
        with open(ixbrl_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        contexts = parse_contexts(soup)
        assert contexts["c-3"].has_segment is True
        assert contexts["c-1"].has_segment is False
