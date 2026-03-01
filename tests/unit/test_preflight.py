"""Tests for elsian.analyze.preflight — filing pre-flight metadata extractor."""

import pytest

from elsian.analyze.preflight import (
    PreflightResult,
    _find_section_boundaries,
    preflight,
)


# ── Fixtures ──────────────────────────────────────────────────────────

US_GAAP_TEXT = """
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K

TRAVELZOO
Annual Report pursuant to Section 13

Consolidated Statements of Operations
(in thousands, except per share amounts)
Year Ended December 31, 2024

Net revenues: $83,902
Cost of revenue: 23,456
Total assets: 180,000
Total liabilities: 95,000
Net income: 14,500

The financial statements have been prepared in accordance with U.S. GAAP.
United States dollars (USD).

Consolidated Balance Sheets
(in thousands)
Total assets: $180,000

Consolidated Statements of Cash Flows
(in thousands)
Cash provided by operating activities: 20,000
"""

IFRS_EUR_TEXT = """
TELEPERFORMANCE SE
Document d'enregistrement universel 2024
Exercice clos le 31 décembre 2024

Compte de résultat consolidé
(en millions d'euros)
Chiffre d'affaires: 8,345
Résultat net: 612
Total de l'actif: 22,500
Flux de trésorerie: 1,200

Les états financiers consolidés ont été préparés conformément aux IFRS.

Bilan consolidé
(en millions d'euros)
Total de l'actif: 22,500

Tableau des flux de trésorerie
(en millions d'euros)
"""

IFRS_AUD_TEXT = """
KAR AUCTION SERVICES PTY LTD
Annual Report for the fiscal year ended June 30, 2024

Consolidated Statement of Profit or Loss
(in Australian dollars, AUD thousands)
Revenue: A$1,245,000
Net income: 89,000
Total assets: 3,200,000
Total liabilities: 1,800,000

The Group prepares its financial statements in accordance with IFRS
as adopted by the Australian Accounting Standards Board.

Consolidated Balance Sheets
(in AUD thousands)
Total assets: 3,200,000

Consolidated Statements of Cash Flows
(in AUD thousands)
Cash flow from operations: 150,000
"""

RESTATED_TEXT = """
Consolidated Statements of Operations
(in millions)
Year Ended December 31, 2023

Revenue: $5,000
Net income: $500

Note: Certain prior year amounts have been restated to conform with
the current year presentation. The 2022 figures as restated reflect
the reclassification of discontinued operations.
Previously reported revenue for 2022 was $4,800.
"""


# ── Empty / minimal input ────────────────────────────────────────────

class TestPreflightEmpty:
    def test_empty_string(self) -> None:
        result = preflight("")
        assert result.language is None
        assert result.accounting_standard is None
        assert result.currency is None
        assert result.sections_detected == []
        assert not result.restatement_detected

    def test_nonsense_text(self) -> None:
        result = preflight("lorem ipsum dolor sit amet 123 456")
        assert result.language is None


# ── US-GAAP / USD ──────────────────────────────────────────────────────

class TestPreflightUSGAAP:
    def test_language_english(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert result.language == "en"
        assert result.language_confidence in ("high", "medium")

    def test_standard_us_gaap(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert result.accounting_standard == "US-GAAP"
        assert result.accounting_standard_confidence == "high"

    def test_currency_usd(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert result.currency == "USD"

    def test_fiscal_year(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert result.fiscal_year == 2024

    def test_sections_detected(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert "income_statement" in result.sections_detected
        assert "balance_sheet" in result.sections_detected
        assert "cash_flow" in result.sections_detected

    def test_units_thousands(self) -> None:
        result = preflight(US_GAAP_TEXT)
        # Global unit from "in thousands" in header area
        assert result.units_global is not None
        assert result.units_global["multiplier"] == 1_000

    def test_no_restatement(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert not result.restatement_detected


# ── IFRS / EUR ─────────────────────────────────────────────────────────

class TestPreflightIFRSEUR:
    def test_language_french(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert result.language == "fr"

    def test_standard_ifrs(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert result.accounting_standard == "IFRS"

    def test_currency_eur(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert result.currency == "EUR"

    def test_fiscal_year(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert result.fiscal_year == 2024

    def test_sections_fr(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert "income_statement" in result.sections_detected
        assert "balance_sheet" in result.sections_detected
        assert "cash_flow" in result.sections_detected

    def test_units_millions(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert result.units_global is not None
        assert result.units_global["multiplier"] == 1_000_000


# ── IFRS / AUD ─────────────────────────────────────────────────────────

class TestPreflightIFRSAUD:
    def test_language_english(self) -> None:
        result = preflight(IFRS_AUD_TEXT)
        assert result.language == "en"

    def test_standard_ifrs(self) -> None:
        result = preflight(IFRS_AUD_TEXT)
        assert result.accounting_standard == "IFRS"

    def test_currency_aud(self) -> None:
        result = preflight(IFRS_AUD_TEXT)
        assert result.currency == "AUD"

    def test_fiscal_year_june(self) -> None:
        result = preflight(IFRS_AUD_TEXT)
        assert result.fiscal_year == 2024

    def test_sections_detected(self) -> None:
        result = preflight(IFRS_AUD_TEXT)
        assert "income_statement" in result.sections_detected
        assert "balance_sheet" in result.sections_detected
        assert "cash_flow" in result.sections_detected


# ── Restatement detection ─────────────────────────────────────────────

class TestPreflightRestatement:
    def test_restatement_detected(self) -> None:
        result = preflight(RESTATED_TEXT)
        assert result.restatement_detected is True

    def test_restatement_signals_count(self) -> None:
        result = preflight(RESTATED_TEXT)
        assert len(result.restatement_signals) >= 2

    def test_restatement_signal_fields(self) -> None:
        result = preflight(RESTATED_TEXT)
        sig = result.restatement_signals[0]
        assert "confidence" in sig
        assert "sample" in sig


# ── PreflightResult ───────────────────────────────────────────────────

class TestPreflightResult:
    def test_to_dict(self) -> None:
        result = preflight(US_GAAP_TEXT)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "language" in d
        assert "sections_detected" in d
        assert isinstance(d["sections_detected"], list)


# ── Section boundaries helper ─────────────────────────────────────────

class TestSectionBoundaries:
    def test_finds_sections(self) -> None:
        bounds = _find_section_boundaries(US_GAAP_TEXT)
        names = [b[0] for b in bounds]
        assert "income_statement" in names
        assert "balance_sheet" in names

    def test_empty_text(self) -> None:
        bounds = _find_section_boundaries("")
        assert bounds == []


# ── confidence_by_signal ──────────────────────────────────────────────

class TestConfidenceBySignal:
    def test_language_signal(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert "lang:en" in result.confidence_by_signal

    def test_standard_signal(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert "standard:US-GAAP" in result.confidence_by_signal

    def test_currency_signal(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert "currency:USD" in result.confidence_by_signal

    def test_fiscal_year_signal(self) -> None:
        result = preflight(US_GAAP_TEXT)
        assert "fiscal_year" in result.confidence_by_signal

    def test_restatement_signal(self) -> None:
        text = US_GAAP_TEXT + "\nThe figures have been restated for comparison."
        result = preflight(text)
        assert "restatement" in result.confidence_by_signal
        assert result.confidence_by_signal["restatement"] in ("high", "medium")

    def test_ifrs_signals(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        assert "lang:fr" in result.confidence_by_signal
        assert "standard:IFRS" in result.confidence_by_signal
        assert "currency:EUR" in result.confidence_by_signal

    def test_empty_text_no_signals(self) -> None:
        result = preflight("")
        assert result.confidence_by_signal == {}

    def test_confidence_in_to_dict(self) -> None:
        result = preflight(US_GAAP_TEXT)
        d = result.to_dict()
        assert "confidence_by_signal" in d
        assert isinstance(d["confidence_by_signal"], dict)


# ── to_prompt_block ───────────────────────────────────────────────────

class TestToPromptBlock:
    def test_us_gaap_block(self) -> None:
        result = preflight(US_GAAP_TEXT)
        block = result.to_prompt_block()
        assert block is not None
        assert "METADATA DEL DOCUMENTO" in block
        assert "en" in block.lower()

    def test_includes_currency(self) -> None:
        result = preflight(US_GAAP_TEXT)
        block = result.to_prompt_block()
        assert "USD" in block

    def test_includes_accounting_standard(self) -> None:
        result = preflight(US_GAAP_TEXT)
        block = result.to_prompt_block()
        assert "US-GAAP" in block

    def test_includes_units(self) -> None:
        result = preflight(US_GAAP_TEXT)
        block = result.to_prompt_block()
        assert block is not None
        # Should mention units (thousands or global)
        assert "unit" in block.lower() or "Units" in block

    def test_restatement_warning(self) -> None:
        text = US_GAAP_TEXT + "\nThe figures have been restated for comparison."
        result = preflight(text)
        block = result.to_prompt_block()
        assert "RESTATEMENT" in block

    def test_empty_returns_none(self) -> None:
        result = preflight("")
        block = result.to_prompt_block()
        assert block is None

    def test_no_confidence_returns_none(self) -> None:
        result = PreflightResult()
        block = result.to_prompt_block()
        assert block is None

    def test_ifrs_block(self) -> None:
        result = preflight(IFRS_EUR_TEXT)
        block = result.to_prompt_block()
        assert block is not None
        assert "EUR" in block or "IFRS" in block
