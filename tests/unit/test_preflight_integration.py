"""Tests for WP-4: Preflight integration in ExtractPhase.

Tests verify:
1. Mixed-units filing: section-specific scale is used (IS=millions, BS=thousands)
2. No units detected: falls back to detect.py metadata.scale
3. Empty text: PreflightResult has empty units_by_section
4. Provenance.to_dict() serialises preflight fields only when non-empty
"""

from __future__ import annotations
import pytest
from elsian.analyze.preflight import PreflightResult, preflight
from elsian.extract.phase import _FIELD_SECTION_MAP, _PREFLIGHT_UNIT_TO_SCALE, _preflight_scale_for_field
from elsian.models.field import Provenance


def _mixed_units_pf() -> PreflightResult:
    pf = PreflightResult()
    pf.units_by_section = {
        "income_statement": {"unit": "millions", "multiplier": 1_000_000},
        "balance_sheet": {"unit": "thousands", "multiplier": 1_000},
    }
    pf.currency = "USD"
    pf.accounting_standard = "US-GAAP"
    return pf


class TestPreflightScaleForField:
    def test_income_statement_field_uses_is_scale(self) -> None:
        pf = _mixed_units_pf()
        assert _preflight_scale_for_field("ingresos", pf, "raw") == "millions"

    def test_balance_sheet_field_uses_bs_scale(self) -> None:
        pf = _mixed_units_pf()
        assert _preflight_scale_for_field("total_assets", pf, "raw") == "thousands"

    def test_cash_flow_uses_global_when_section_absent(self) -> None:
        pf = _mixed_units_pf()
        pf.units_global = {"unit": "millions", "multiplier": 1_000_000}
        assert _preflight_scale_for_field("cfo", pf, "raw") == "millions"

    def test_all_is_fields_use_is_scale(self) -> None:
        pf = _mixed_units_pf()
        is_fields = ["ingresos", "cost_of_revenue", "gross_profit", "ebitda", "ebit",
            "net_income", "eps_basic", "eps_diluted", "research_and_development",
            "sga", "depreciation_amortization", "interest_expense", "income_tax"]
        for f in is_fields:
            assert _preflight_scale_for_field(f, pf, "raw") == "millions", f

    def test_all_bs_fields_use_bs_scale(self) -> None:
        pf = _mixed_units_pf()
        bs_fields = ["total_assets", "total_liabilities", "total_equity", "cash_and_equivalents", "total_debt"]
        for f in bs_fields:
            assert _preflight_scale_for_field(f, pf, "raw") == "thousands", f


class TestNoUnitsDetected:
    def test_empty_units_returns_fallback(self) -> None:
        pf = PreflightResult()
        assert _preflight_scale_for_field("ingresos", pf, "thousands") == "thousands"

    def test_none_preflight_returns_fallback(self) -> None:
        assert _preflight_scale_for_field("ingresos", None, "millions") == "millions"

    def test_unknown_field_with_global_uses_global(self) -> None:
        pf = PreflightResult()
        pf.units_global = {"unit": "thousands", "multiplier": 1_000}
        assert _preflight_scale_for_field("unknown_field", pf, "raw") == "thousands"


class TestPreflightRobustness:
    def test_empty_text_returns_safe_defaults(self) -> None:
        result = preflight("")
        assert isinstance(result, PreflightResult)
        assert result.units_by_section == {}
        assert result.units_global is None
        assert result.currency is None

    def test_whitespace_only_text_returns_safe_defaults(self) -> None:
        result = preflight("    ")
        assert isinstance(result, PreflightResult)
        assert result.units_by_section == {}

    def test_actual_mixed_units_text_detected(self) -> None:
        # Sections must be far apart (> 200 chars) so boundary trimming works
        is_header = "Consolidated Statements of Operations\n(in millions, except per share amounts)\n"
        is_padding = ("Net revenues: 1,000\nCost of revenues: 400\nGross profit: 600\n"
                      "Operating income: 200\n" * 10)
        bs_part = "\n\nConsolidated Balance Sheets\n(in thousands)\nTotal assets: 500,000\n"
        text = is_header + is_padding + bs_part

        result = preflight(text)
        assert "income_statement" in result.sections_detected
        assert "balance_sheet" in result.sections_detected
        assert "income_statement" in result.units_by_section
        assert result.units_by_section["income_statement"]["unit"] == "millions"
        assert "balance_sheet" in result.units_by_section
        assert result.units_by_section["balance_sheet"]["unit"] == "thousands"


class TestProvenanceSerialisation:
    def test_empty_preflight_fields_excluded(self) -> None:
        prov = Provenance(source_filing="SRC_001.clean.md")
        d = prov.to_dict()
        assert "preflight_currency" not in d
        assert "preflight_standard" not in d
        assert "preflight_units_hint" not in d

    def test_populated_preflight_fields_included(self) -> None:
        prov = Provenance(source_filing="SRC_001.clean.md",
            preflight_currency="USD", preflight_standard="US-GAAP", preflight_units_hint="thousands")
        d = prov.to_dict()
        assert d["preflight_currency"] == "USD"
        assert d["preflight_standard"] == "US-GAAP"
        assert d["preflight_units_hint"] == "thousands"

    def test_partial_preflight_fields(self) -> None:
        prov = Provenance(source_filing="SRC_001.clean.md", preflight_currency="EUR")
        d = prov.to_dict()
        assert d["preflight_currency"] == "EUR"
        assert "preflight_standard" not in d

    def test_source_filing_always_present(self) -> None:
        prov = Provenance(source_filing="SRC_002.clean.md", preflight_currency="GBP",
            preflight_standard="IFRS", preflight_units_hint="millions")
        d = prov.to_dict()
        assert d["source_filing"] == "SRC_002.clean.md"


class TestUnitToScaleMapping:
    VALID_SCALES = {"raw", "thousands", "millions", "billions"}

    def test_all_mappings_are_valid_scales(self) -> None:
        for unit_name, scale in _PREFLIGHT_UNIT_TO_SCALE.items():
            assert scale in self.VALID_SCALES

    def test_french_unit_aliases(self) -> None:
        assert _PREFLIGHT_UNIT_TO_SCALE["milliards"] == "billions"
        assert _PREFLIGHT_UNIT_TO_SCALE["millions_fr"] == "millions"
        assert _PREFLIGHT_UNIT_TO_SCALE["milliers"] == "thousands"

    def test_all_canonical_fields_have_section_mapping(self) -> None:
        expected_fields = {
            "ingresos", "cost_of_revenue", "gross_profit", "ebitda", "ebit",
            "net_income", "eps_basic", "eps_diluted", "research_and_development",
            "sga", "depreciation_amortization", "interest_expense", "income_tax",
            "total_assets", "total_liabilities", "total_equity",
            "cash_and_equivalents", "total_debt",
            "cfo", "capex", "fcf", "dividends_per_share", "shares_outstanding",
        }
        missing = expected_fields - set(_FIELD_SECTION_MAP.keys())
        assert not missing, f"Fields missing from _FIELD_SECTION_MAP: {missing}"
