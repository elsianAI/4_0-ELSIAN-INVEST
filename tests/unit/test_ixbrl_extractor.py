"""Unit tests for IxbrlExtractor (elsian.extract.ixbrl_extractor).

Tests cover:
- IxbrlExtractor.has_ixbrl()  — file sniffing
- IxbrlExtractor.extract()    — conversion to FieldResult
- _normalize_sign()           — sign convention for expense fields
- _map_scale()                — iXBRL scale → string
- make_ixbrl_sort_key()       — sort key tuple for collision resolution
- Calendar-quarter fix        — period labels for non-December FYE companies
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from elsian.extract.ixbrl_extractor import (
    IXBRL_SEMANTIC_RANK,
    IXBRL_SRC_TYPE_RANK,
    IxbrlExtractor,
    _map_scale,
    _normalize_sign,
    make_ixbrl_sort_key,
)
from elsian.models.field import FieldResult

# ---------------------------------------------------------------------------
# Shared iXBRL HTML fixture (calendar-year company, December FYE)
# ---------------------------------------------------------------------------

_MINIMAL_IXBRL = textwrap.dedent("""\
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
    <xbrli:context id="c-annual">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2024-01-01</xbrli:startDate>
        <xbrli:endDate>2024-12-31</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    <xbrli:context id="c-instant">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001234567</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:instant>2024-12-31</xbrli:instant>
      </xbrli:period>
    </xbrli:context>
    </ix:resources>
    </ix:header>
    </div>
    <p>
    Revenue: <ix:nonFraction unitRef="usd" contextRef="c-annual" decimals="-3"
        name="us-gaap:Revenues" scale="3" id="f-1">83,902</ix:nonFraction>
    Net Income: <ix:nonFraction unitRef="usd" contextRef="c-annual" decimals="-3"
        name="us-gaap:NetIncomeLoss" scale="3" id="f-2">13,564</ix:nonFraction>
    EPS: <ix:nonFraction unitRef="usdPerShare" contextRef="c-annual" decimals="2"
        name="us-gaap:EarningsPerShareBasic" scale="0" id="f-3">1.08</ix:nonFraction>
    R&amp;D (expense — should stay positive): <ix:nonFraction unitRef="usd"
        contextRef="c-annual" decimals="-3"
        name="us-gaap:ResearchAndDevelopmentExpense" scale="3"
        sign="-" id="f-4">5,000</ix:nonFraction>
    Assets: <ix:nonFraction unitRef="usd" contextRef="c-instant" decimals="-3"
        name="us-gaap:Assets" scale="3" id="f-5">54,722</ix:nonFraction>
    </p>
    </body>
    </html>
""")

# iXBRL fixture with a January-FYE quarterly period (NVDA-style)
_NVDA_STYLE_IXBRL = textwrap.dedent("""\
    <?xml version='1.0' encoding='ASCII'?>
    <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
          xmlns:xbrli="http://www.xbrl.org/2003/instance"
          xmlns:us-gaap="http://fasb.org/us-gaap/2024"
          xml:lang="en-US">
    <head><title>NVDA-style Q1 FY2023</title></head>
    <body>
    <div style="display:none">
    <ix:header>
    <ix:resources>
    <xbrli:context id="c-current">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2022-01-31</xbrli:startDate>
        <xbrli:endDate>2022-05-01</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    <xbrli:context id="c-prior">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0001045810</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2021-02-01</xbrli:startDate>
        <xbrli:endDate>2021-05-02</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    </ix:resources>
    </ix:header>
    </div>
    <p>
    Current Revenue: <ix:nonFraction unitRef="usd" contextRef="c-current"
        decimals="-6" name="us-gaap:Revenues" scale="6" id="f-1">8,288</ix:nonFraction>
    Prior Year Revenue: <ix:nonFraction unitRef="usd" contextRef="c-prior"
        decimals="-6" name="us-gaap:Revenues" scale="6" id="f-2">5,661</ix:nonFraction>
    </p>
    </body>
    </html>
""")

_MIXED_SCALE_DA_IXBRL = textwrap.dedent("""\
    <?xml version='1.0' encoding='ASCII'?>
    <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
          xmlns:xbrli="http://www.xbrl.org/2003/instance"
          xmlns:us-gaap="http://fasb.org/us-gaap/2024"
          xml:lang="en-US">
    <head><title>Mixed-scale D&A</title></head>
    <body>
    <div style="display:none">
    <ix:header>
    <ix:resources>
    <xbrli:context id="c-current">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0000000000</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2025-04-01</xbrli:startDate>
        <xbrli:endDate>2025-06-30</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    </ix:resources>
    </ix:header>
    </div>
    <p>
    Revenue: <ix:nonFraction unitRef="usd" contextRef="c-current" decimals="-3"
        name="us-gaap:Revenues" scale="3" id="f-1">144,732</ix:nonFraction>
    D&amp;A: <ix:nonFraction unitRef="usd" contextRef="c-current" decimals="-5"
        name="us-gaap:DepreciationAndAmortization" scale="6" id="f-2">7.6</ix:nonFraction>
    </p>
    </body>
    </html>
""")

_MIXED_SCALE_DURATION_DA_IXBRL = textwrap.dedent("""\
    <?xml version='1.0' encoding='ASCII'?>
    <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
          xmlns:xbrli="http://www.xbrl.org/2003/instance"
          xmlns:us-gaap="http://fasb.org/us-gaap/2024"
          xml:lang="en-US">
    <head><title>Mixed-scale duration D&A</title></head>
    <body>
    <div style="display:none">
    <ix:header>
    <ix:resources>
    <xbrli:context id="Duration_4_1_2025_To_6_30_2025_ctx">
      <xbrli:entity>
        <xbrli:identifier scheme="http://www.sec.gov/CIK">0000000000</xbrli:identifier>
      </xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>2025-04-01</xbrli:startDate>
        <xbrli:endDate>2025-06-30</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>
    </ix:resources>
    </ix:header>
    </div>
    <p>
    Revenue: <ix:nonFraction unitRef="usd" contextRef="Duration_4_1_2025_To_6_30_2025_ctx" decimals="-3"
        name="us-gaap:Revenues" scale="3" id="f-1">144,732</ix:nonFraction>
    D&amp;A: <ix:nonFraction unitRef="usd" contextRef="Duration_4_1_2025_To_6_30_2025_ctx" decimals="-5"
        name="us-gaap:DepreciationAndAmortization" scale="6" id="f-2">7.6</ix:nonFraction>
    </p>
    </body>
    </html>
""")

PLAIN_HTML = "<html><head></head><body><p>No iXBRL here</p></body></html>"


@pytest.fixture
def ixbrl_file(tmp_path: Path) -> Path:
    fp = tmp_path / "SRC_001_10-K_FY2024.htm"
    fp.write_text(_MINIMAL_IXBRL, encoding="utf-8")
    return fp


@pytest.fixture
def nvda_q1_file(tmp_path: Path) -> Path:
    """Simulates NVDA's Q1 FY2023 10-Q (period ending May 1, 2022)."""
    fp = tmp_path / "SRC_018_10-Q_Q2-2022.htm"
    fp.write_text(_NVDA_STYLE_IXBRL, encoding="utf-8")
    return fp


@pytest.fixture
def mixed_scale_da_file(tmp_path: Path) -> Path:
    fp = tmp_path / "SRC_008_10-Q_Q2-2025.htm"
    fp.write_text(_MIXED_SCALE_DA_IXBRL, encoding="utf-8")
    return fp


@pytest.fixture
def mixed_scale_duration_da_file(tmp_path: Path) -> Path:
    fp = tmp_path / "SRC_008_10-Q_Q2-2025.htm"
    fp.write_text(_MIXED_SCALE_DURATION_DA_IXBRL, encoding="utf-8")
    return fp


@pytest.fixture
def plain_html_file(tmp_path: Path) -> Path:
    fp = tmp_path / "plain.htm"
    fp.write_text(PLAIN_HTML, encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# IxbrlExtractor.has_ixbrl()
# ---------------------------------------------------------------------------


class TestHasIxbrl:
    def test_detects_ixbrl_namespace(self, tmp_path: Path):
        f = tmp_path / "with_ns.htm"
        f.write_text('<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">', encoding="utf-8")
        assert IxbrlExtractor.has_ixbrl(f) is True

    def test_detects_ix_header_tag(self, tmp_path: Path):
        f = tmp_path / "with_header.htm"
        f.write_text("<html><body><ix:header><ix:resources/></ix:header></body></html>", encoding="utf-8")
        assert IxbrlExtractor.has_ixbrl(f) is True

    def test_rejects_plain_html(self, plain_html_file: Path):
        assert IxbrlExtractor.has_ixbrl(plain_html_file) is False

    def test_returns_false_on_missing_file(self, tmp_path: Path):
        assert IxbrlExtractor.has_ixbrl(tmp_path / "nonexistent.htm") is False

    def test_case_insensitive(self, tmp_path: Path):
        f = tmp_path / "upper.htm"
        f.write_text('<html XMLNS:IX="http://www.xbrl.org/2013/inlineXBRL">', encoding="utf-8")
        assert IxbrlExtractor.has_ixbrl(f) is True

    def test_reads_only_first_chunk(self, tmp_path: Path):
        """has_ixbrl should not require reading the entire file."""
        f = tmp_path / "large.htm"
        # Namespace in first 8KB; very large tail with no iXBRL
        content = 'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" ' + "x" * 100_000
        f.write_text(content, encoding="utf-8")
        assert IxbrlExtractor.has_ixbrl(f) is True


# ---------------------------------------------------------------------------
# IxbrlExtractor.extract()
# ---------------------------------------------------------------------------


class TestIxbrlExtractorExtract:
    def test_returns_dict(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        assert isinstance(result, dict)

    def test_period_keys_are_strings(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        for period in result:
            assert isinstance(period, str)

    def test_fy2024_present(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        assert "FY2024" in result

    def test_ingresos_fy2024(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["ingresos"]
        assert isinstance(fr, FieldResult)
        assert fr.value == 83902.0

    def test_extraction_method_is_ixbrl(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["ingresos"]
        assert fr.provenance.extraction_method == "ixbrl"

    def test_confidence_is_high(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["ingresos"]
        assert fr.confidence == "high"

    def test_scale_thousands(self, ixbrl_file: Path):
        """Revenue uses scale=3 → 'thousands'."""
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["ingresos"]
        assert fr.scale == "thousands"

    def test_scale_raw_for_eps(self, ixbrl_file: Path):
        """EPS uses scale=0 → 'raw'."""
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["eps_basic"]
        assert fr.scale == "raw"
        assert fr.value == pytest.approx(1.08)

    def test_sign_normalized_for_rd(self, ixbrl_file: Path):
        """R&D tagged with sign='-' must be stored as positive."""
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["research_and_development"]
        assert fr.value > 0, f"Expected positive R&D, got {fr.value}"
        assert fr.value == 5000.0

    def test_balance_sheet_instant_period(self, ixbrl_file: Path):
        """Assets from instant context (2024-12-31) → FY2024."""
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        assert "total_assets" in result.get("FY2024", {})
        assert result["FY2024"]["total_assets"].value == 54722.0

    def test_returns_empty_on_plain_html(self, plain_html_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(plain_html_file, fiscal_year_end_month=12)
        assert result == {}

    def test_source_filing_in_provenance(self, ixbrl_file: Path):
        ext = IxbrlExtractor()
        result = ext.extract(ixbrl_file, fiscal_year_end_month=12)
        fr = result["FY2024"]["ingresos"]
        assert fr.provenance.source_filing == ixbrl_file.name

    def test_nonexistent_file_returns_empty(self, tmp_path: Path):
        ext = IxbrlExtractor()
        result = ext.extract(tmp_path / "missing.htm", fiscal_year_end_month=12)
        assert result == {}


# ---------------------------------------------------------------------------
# Calendar-quarter period resolution (NVDA-style, January FYE)
# ---------------------------------------------------------------------------


class TestCalendarQuarterPeriodResolution:
    """Regression tests for the calendar-quarter fix (ixbrl.py).

    Before the fix, a period ending 2022-05-01 with fiscal_year_end_month=1
    was labelled Q2-2023 (fiscal quarter 2 of fiscal year 2023).
    After the fix it is correctly labelled Q2-2022 (calendar Q2 of 2022).
    """

    def test_may_2022_period_labelled_q2_2022(self, nvda_q1_file: Path):
        """Period ending 2022-05-01 → Q2-2022 (calendar Q2 of 2022)."""
        ext = IxbrlExtractor()
        result = ext.extract(nvda_q1_file, fiscal_year_end_month=1)
        assert "Q2-2022" in result, f"Got periods: {sorted(result)}"

    def test_may_2021_prior_year_labelled_q2_2021(self, nvda_q1_file: Path):
        """Prior-year comparative period ending 2021-05-02 → Q2-2021."""
        ext = IxbrlExtractor()
        result = ext.extract(nvda_q1_file, fiscal_year_end_month=1)
        assert "Q2-2021" in result, f"Got periods: {sorted(result)}"

    def test_q2_2022_has_correct_revenue(self, nvda_q1_file: Path):
        """Current-period revenue (8288M) must be in Q2-2022, NOT Q2-2023."""
        ext = IxbrlExtractor()
        result = ext.extract(nvda_q1_file, fiscal_year_end_month=1)
        assert result["Q2-2022"]["ingresos"].value == pytest.approx(8288.0)

    def test_no_fiscal_year_label_for_quarterly_period(self, nvda_q1_file: Path):
        """The quarterly period ending May 2022 must NOT appear as FY2023."""
        ext = IxbrlExtractor()
        result = ext.extract(nvda_q1_file, fiscal_year_end_month=1)
        assert "FY2023" not in result

    def test_preserves_million_scale_for_decimal_quarterly_da(
        self,
        mixed_scale_da_file: Path,
    ):
        ext = IxbrlExtractor()
        result = ext.extract(mixed_scale_da_file, fiscal_year_end_month=12)
        fr = result["Q2-2025"]["depreciation_amortization"]

        assert fr.value == pytest.approx(7.6)
        assert fr.scale == "millions"
        assert getattr(fr, "_ixbrl_was_rescaled", False) is False

    def test_rescales_duration_context_quarterly_da_to_dominant_scale(
        self,
        mixed_scale_duration_da_file: Path,
    ):
        ext = IxbrlExtractor()
        result = ext.extract(mixed_scale_duration_da_file, fiscal_year_end_month=12)
        fr = result["Q2-2025"]["depreciation_amortization"]

        assert fr.value == pytest.approx(7600.0)
        assert fr.scale == "thousands"
        assert getattr(fr, "_ixbrl_was_rescaled", False) is True


# ---------------------------------------------------------------------------
# _normalize_sign()
# ---------------------------------------------------------------------------


class TestNormalizeSign:
    def test_always_positive_field_positive_input(self):
        assert _normalize_sign("cost_of_revenue", 1000.0) == 1000.0

    def test_always_positive_field_negative_input(self):
        assert _normalize_sign("cost_of_revenue", -1000.0) == 1000.0

    def test_always_positive_research_and_development(self):
        assert _normalize_sign("research_and_development", -500.0) == 500.0

    def test_always_positive_sga(self):
        assert _normalize_sign("sga", -200.0) == 200.0

    def test_always_positive_depreciation(self):
        assert _normalize_sign("depreciation_amortization", -150.0) == 150.0

    def test_always_positive_interest_expense(self):
        assert _normalize_sign("interest_expense", -30.0) == 30.0

    def test_net_income_preserves_negative(self):
        """net_income is NOT in _ALWAYS_POSITIVE — loss should stay negative."""
        assert _normalize_sign("net_income", -5000.0) == -5000.0

    def test_ebit_preserves_negative(self):
        assert _normalize_sign("ebit", -100.0) == -100.0

    def test_income_tax_preserves_negative(self):
        """income_tax can be negative (tax benefit) — must preserve sign."""
        assert _normalize_sign("income_tax", -50.0) == -50.0


# ---------------------------------------------------------------------------
# _map_scale()
# ---------------------------------------------------------------------------


class TestMapScale:
    def test_scale_0_is_raw(self):
        assert _map_scale(0) == "raw"

    def test_scale_3_is_thousands(self):
        assert _map_scale(3) == "thousands"

    def test_scale_6_is_millions(self):
        assert _map_scale(6) == "millions"

    def test_scale_9_is_billions(self):
        assert _map_scale(9) == "billions"

    def test_unknown_scale_defaults_to_raw(self):
        assert _map_scale(12) == "raw"

    def test_negative_scale_defaults_to_raw(self):
        assert _map_scale(-3) == "raw"


# ---------------------------------------------------------------------------
# make_ixbrl_sort_key()
# ---------------------------------------------------------------------------


class TestMakeIxbrlSortKey:
    def test_returns_tuple(self):
        sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", 1)
        assert isinstance(sk, tuple)

    def test_primary_filing_affinity_is_zero(self):
        """When the period label appears in the filing stem → affinity = 0."""
        sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", 1)
        assert sk[1] == 0

    def test_comparative_filing_affinity_is_one(self):
        """When the period does NOT appear in the filing stem → affinity = 1."""
        sk = make_ixbrl_sort_key("FY2023", "SRC_001_10-K_FY2024", 1)
        assert sk[1] == 1

    def test_affinity_override_wins_over_filename_heuristic(self):
        sk = make_ixbrl_sort_key(
            "FY2023",
            "SRC_001_10-K_FY2024",
            1,
            affinity_override=0,
        )
        assert sk[1] == 0

    def test_filing_rank_is_preserved(self):
        for rank in (1, 2, 3):
            sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", rank)
            assert sk[0] == rank

    def test_src_type_rank_is_ixbrl_constant(self):
        sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", 1)
        assert sk[2] == IXBRL_SRC_TYPE_RANK

    def test_semantic_rank_is_ixbrl_constant(self):
        sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", 1)
        assert sk[3] == IXBRL_SEMANTIC_RANK

    def test_ixbrl_beats_table_src_type(self):
        """iXBRL sort key (src_type=-1) must sort before table (src_type=0)."""
        ixbrl_sk = make_ixbrl_sort_key("FY2024", "SRC_001_10-K_FY2024", 1)
        # Table sort key: same filing_rank + affinity, src_type_rank=0
        table_sk = (1, 0, 0, 100, ("net_income", 3, 0, 1))
        assert ixbrl_sk < table_sk
