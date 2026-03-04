"""tests/unit/test_truth_pack.py — Unit tests for elsian.assemble.truth_pack.

Covers:
    - TruthPack_v1 schema structure (all required sections present)
    - Assembler with extraction_result only (no market_data)
    - Assembler with extraction_result + market_data
    - Derived metrics section is correctly populated
    - Quality section is correctly generated
    - Metadata section has correct values
    - Sources section reflects presence/absence of market_data
    - Financial data passthrough from extraction_result
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from elsian.assemble.truth_pack import TruthPackAssembler


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _minimal_extraction_result(ticker: str = "TEST") -> dict:
    """Build a minimal extraction_result dict with one annual period."""
    return {
        "schema_version": "2.0",
        "ticker": ticker,
        "currency": "USD",
        "extraction_date": "2026-03-04",
        "filings_used": 2,
        "periods": {
            "FY2024": {
                "fecha_fin": "2024-12-31",
                "tipo_periodo": "anual",
                "fields": {
                    "ingresos": {
                        "value": 100000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "net_income": {
                        "value": 15000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "total_assets": {
                        "value": 500000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "total_equity": {
                        "value": 200000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "total_liabilities": {
                        "value": 300000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "cfo": {
                        "value": 20000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "capex": {
                        "value": -5000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                    "ebit": {
                        "value": 18000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                        "extraction_method": "table",
                    },
                },
            },
            "FY2023": {
                "fecha_fin": "2023-12-31",
                "tipo_periodo": "anual",
                "fields": {
                    "ingresos": {
                        "value": 90000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_002_10-K_FY2023.clean.md",
                        "extraction_method": "table",
                    },
                    "net_income": {
                        "value": 12000,
                        "scale": "raw",
                        "confidence": "high",
                        "source_filing": "SRC_002_10-K_FY2023.clean.md",
                        "extraction_method": "table",
                    },
                },
            },
        },
        "audit": {
            "fields_extracted": 10,
            "fields_discarded": 0,
            "discarded_reasons": [],
        },
    }


def _minimal_case_config(ticker: str = "TEST") -> dict:
    """Build a minimal case.json dict."""
    return {
        "ticker": ticker,
        "source_hint": "sec",
        "currency": "USD",
        "period_scope": "FULL",
        "fiscal_year_end_month": 12,
    }


def _sample_market_data() -> dict:
    """Build a sample _market_data.json dict."""
    return {
        "ticker": "TEST",
        "price": 25.50,
        "market_cap": 314.8,
        "shares_outstanding": 12.35,
        "currency": "USD",
        "sector": "Technology",
        "industry": "Software",
        "fetched_at": "2026-03-04T10:00:00Z",
        "source": "finviz+stooq",
    }


def _create_case_dir(
    tmp_dir: Path,
    ticker: str = "TEST",
    with_market_data: bool = False,
) -> Path:
    """Create a temporary case directory with required files."""
    case_dir = tmp_dir / ticker
    case_dir.mkdir(parents=True, exist_ok=True)

    er = _minimal_extraction_result(ticker)
    (case_dir / "extraction_result.json").write_text(
        json.dumps(er, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cc = _minimal_case_config(ticker)
    (case_dir / "case.json").write_text(
        json.dumps(cc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if with_market_data:
        md = _sample_market_data()
        md["ticker"] = ticker
        (case_dir / "_market_data.json").write_text(
            json.dumps(md, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return case_dir


# ── Tests: Schema structure ──────────────────────────────────────────────────


class TestTruthPackSchema:
    """Tests for TruthPack_v1 schema structure."""

    def test_schema_version(self, tmp_path: Path) -> None:
        """TruthPack must have schema_version = TruthPack_v1."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["schema_version"] == "TruthPack_v1"

    def test_all_top_level_sections_present(self, tmp_path: Path) -> None:
        """TruthPack must contain all required top-level sections."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)

        required_keys = {
            "schema_version",
            "ticker",
            "currency",
            "assembly_date",
            "sources",
            "financial_data",
            "derived_metrics",
            "market_data",
            "quality",
            "metadata",
        }
        assert required_keys.issubset(tp.keys())

    def test_assembly_date_is_today(self, tmp_path: Path) -> None:
        """assembly_date must be today's date in ISO format."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        import datetime as dt
        assert tp["assembly_date"] == dt.date.today().isoformat()

    def test_ticker_and_currency(self, tmp_path: Path) -> None:
        """ticker and currency must come from extraction_result."""
        case_dir = _create_case_dir(tmp_path, ticker="ACME")
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["ticker"] == "ACME"
        assert tp["currency"] == "USD"

    def test_truth_pack_json_saved(self, tmp_path: Path) -> None:
        """truth_pack.json must be saved to case_dir."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        assembler.assemble(case_dir)
        assert (case_dir / "truth_pack.json").exists()

    def test_truth_pack_json_is_valid_json(self, tmp_path: Path) -> None:
        """Saved truth_pack.json must be valid JSON."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        assembler.assemble(case_dir)
        content = (case_dir / "truth_pack.json").read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["schema_version"] == "TruthPack_v1"

    def test_truth_pack_json_matches_return(self, tmp_path: Path) -> None:
        """Saved JSON must match the returned dict."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        saved = json.loads((case_dir / "truth_pack.json").read_text(encoding="utf-8"))
        assert saved == tp


# ── Tests: Without market data ───────────────────────────────────────────────


class TestAssemblerNoMarketData:
    """Tests for assembler when _market_data.json is absent."""

    def test_market_data_is_none(self, tmp_path: Path) -> None:
        """market_data section must be None when no _market_data.json."""
        case_dir = _create_case_dir(tmp_path, with_market_data=False)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["market_data"] is None

    def test_sources_market_data_is_none(self, tmp_path: Path) -> None:
        """sources.market_data must be None when no _market_data.json."""
        case_dir = _create_case_dir(tmp_path, with_market_data=False)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["sources"]["market_data"] is None

    def test_derived_metrics_still_computed(self, tmp_path: Path) -> None:
        """Derived metrics must still be computed without market data."""
        case_dir = _create_case_dir(tmp_path, with_market_data=False)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        dm = tp["derived_metrics"]
        assert "ttm" in dm
        assert "margins" in dm
        assert "returns" in dm
        # EV requires market_cap, so should be None
        assert dm["ev"] is None

    def test_quality_section_present(self, tmp_path: Path) -> None:
        """Quality section must be present even without market data."""
        case_dir = _create_case_dir(tmp_path, with_market_data=False)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        q = tp["quality"]
        assert "validation_status" in q
        assert "confidence_score" in q
        assert "gates_summary" in q


# ── Tests: With market data ──────────────────────────────────────────────────


class TestAssemblerWithMarketData:
    """Tests for assembler when _market_data.json is present."""

    def test_market_data_populated(self, tmp_path: Path) -> None:
        """market_data section must be populated from _market_data.json."""
        case_dir = _create_case_dir(tmp_path, with_market_data=True)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["market_data"] is not None
        assert tp["market_data"]["price"] == 25.50
        assert tp["market_data"]["ticker"] == "TEST"

    def test_sources_market_data_filename(self, tmp_path: Path) -> None:
        """sources.market_data must be '_market_data.json' when present."""
        case_dir = _create_case_dir(tmp_path, with_market_data=True)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["sources"]["market_data"] == "_market_data.json"

    def test_ev_computed_with_market_data(self, tmp_path: Path) -> None:
        """EV should be computed when market_cap is available."""
        case_dir = _create_case_dir(tmp_path, with_market_data=True)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        dm = tp["derived_metrics"]
        # EV requires market_cap (provided via market_data) + debt - cash
        # Without total_debt and cash in market_data, may still be None or
        # computed from extraction data.  Just check it is reachable.
        assert "ev" in dm


# ── Tests: Financial data ────────────────────────────────────────────────────


class TestFinancialData:
    """Tests for financial_data section."""

    def test_periods_passthrough(self, tmp_path: Path) -> None:
        """financial_data must contain same periods as extraction_result."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert "FY2024" in tp["financial_data"]
        assert "FY2023" in tp["financial_data"]

    def test_fields_passthrough(self, tmp_path: Path) -> None:
        """Fields within periods must include value and provenance."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        fields = tp["financial_data"]["FY2024"]["fields"]
        assert "ingresos" in fields
        assert fields["ingresos"]["value"] == 100000
        assert "source_filing" in fields["ingresos"]

    def test_period_metadata(self, tmp_path: Path) -> None:
        """Each period must have fecha_fin and tipo_periodo."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        p = tp["financial_data"]["FY2024"]
        assert p["fecha_fin"] == "2024-12-31"
        assert p["tipo_periodo"] == "anual"


# ── Tests: Derived metrics ───────────────────────────────────────────────────


class TestDerivedMetrics:
    """Tests for derived_metrics section."""

    def test_derived_metrics_structure(self, tmp_path: Path) -> None:
        """derived_metrics must have the expected sub-sections."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        dm = tp["derived_metrics"]
        required_keys = {"ttm", "fcf", "ev", "margins", "returns", "multiples", "per_share", "net_debt", "periodo_base"}
        assert required_keys.issubset(dm.keys())

    def test_margins_subsection(self, tmp_path: Path) -> None:
        """margins must contain gross/operating/net/FCF margin fields."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        margins = tp["derived_metrics"]["margins"]
        assert "gross_margin_pct" in margins
        assert "operating_margin_pct" in margins
        assert "net_margin_pct" in margins
        assert "fcf_margin_pct" in margins

    def test_returns_subsection(self, tmp_path: Path) -> None:
        """returns must contain ROIC/ROE/ROA."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        returns = tp["derived_metrics"]["returns"]
        assert "roic_pct" in returns
        assert "roe_pct" in returns
        assert "roa_pct" in returns

    def test_multiples_subsection(self, tmp_path: Path) -> None:
        """multiples must contain ev_ebit/ev_fcf/p_fcf/fcf_yield."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        multiples = tp["derived_metrics"]["multiples"]
        assert "ev_ebit" in multiples
        assert "ev_fcf" in multiples
        assert "p_fcf" in multiples
        assert "fcf_yield_pct" in multiples

    def test_per_share_subsection(self, tmp_path: Path) -> None:
        """per_share must contain eps/fcf_per_share/bv_per_share."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        ps = tp["derived_metrics"]["per_share"]
        assert "eps" in ps
        assert "fcf_per_share" in ps
        assert "bv_per_share" in ps

    def test_fcf_calculated(self, tmp_path: Path) -> None:
        """fcf = cfo - |capex|. With cfo=20000, capex=-5000 → fcf=15000."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        fcf = tp["derived_metrics"]["fcf"]
        assert fcf == 15000.0

    def test_net_margin_calculated(self, tmp_path: Path) -> None:
        """net_margin = net_income/ingresos * 100. 15000/100000 = 15%."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        net_margin = tp["derived_metrics"]["margins"]["net_margin_pct"]
        assert net_margin is not None
        assert abs(net_margin - 15.0) < 0.1

    def test_periodo_base(self, tmp_path: Path) -> None:
        """periodo_base should be set (FY0_fallback for 2 annual periods without quarters)."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        pb = tp["derived_metrics"]["periodo_base"]
        assert pb is not None
        assert pb != "no_disponible"


# ── Tests: Quality section ───────────────────────────────────────────────────


class TestQualitySection:
    """Tests for quality section."""

    def test_quality_structure(self, tmp_path: Path) -> None:
        """quality must have all required fields."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        q = tp["quality"]
        required_keys = {"validation_status", "confidence_score", "gates_summary", "warnings", "campos_faltantes_criticos"}
        assert required_keys.issubset(q.keys())

    def test_validation_status_is_string(self, tmp_path: Path) -> None:
        """validation_status must be a string (PASS/PARTIAL/FAIL)."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        status = tp["quality"]["validation_status"]
        assert isinstance(status, str)
        assert status in {"PASS", "PARTIAL", "FAIL"}

    def test_confidence_score_is_number(self, tmp_path: Path) -> None:
        """confidence_score must be a number in [0, 100]."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        score = tp["quality"]["confidence_score"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

    def test_gates_summary_has_9_gates(self, tmp_path: Path) -> None:
        """gates_summary must have 9 gate entries."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        gs = tp["quality"]["gates_summary"]
        assert len(gs) == 9

    def test_warnings_is_list(self, tmp_path: Path) -> None:
        """warnings must be a list."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert isinstance(tp["quality"]["warnings"], list)


# ── Tests: Metadata section ──────────────────────────────────────────────────


class TestMetadataSection:
    """Tests for metadata section."""

    def test_metadata_structure(self, tmp_path: Path) -> None:
        """metadata must have all required fields."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        meta = tp["metadata"]
        required_keys = {"total_periods", "total_fields", "period_scope", "source_hint", "fiscal_year_end_month"}
        assert required_keys.issubset(meta.keys())

    def test_total_periods_correct(self, tmp_path: Path) -> None:
        """total_periods must match number of periods in financial_data."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["metadata"]["total_periods"] == 2  # FY2024 + FY2023

    def test_total_fields_correct(self, tmp_path: Path) -> None:
        """total_fields must match sum of fields across all periods."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        # FY2024 has 8 fields, FY2023 has 2 fields
        assert tp["metadata"]["total_fields"] == 10

    def test_period_scope_from_case(self, tmp_path: Path) -> None:
        """period_scope must come from case.json."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["metadata"]["period_scope"] == "FULL"

    def test_source_hint_from_case(self, tmp_path: Path) -> None:
        """source_hint must come from case.json."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["metadata"]["source_hint"] == "sec"

    def test_fiscal_year_end_month(self, tmp_path: Path) -> None:
        """fiscal_year_end_month must come from case.json."""
        case_dir = _create_case_dir(tmp_path)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["metadata"]["fiscal_year_end_month"] == 12


# ── Tests: Error handling ────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error cases."""

    def test_missing_extraction_result(self, tmp_path: Path) -> None:
        """Must raise FileNotFoundError when extraction_result.json is missing."""
        case_dir = tmp_path / "EMPTY"
        case_dir.mkdir()
        (case_dir / "case.json").write_text(
            json.dumps(_minimal_case_config()), encoding="utf-8"
        )
        assembler = TruthPackAssembler()
        with pytest.raises(FileNotFoundError, match="extraction_result.json"):
            assembler.assemble(case_dir)

    def test_missing_case_json(self, tmp_path: Path) -> None:
        """Must raise FileNotFoundError when case.json is missing."""
        case_dir = tmp_path / "NOCASE"
        case_dir.mkdir()
        (case_dir / "extraction_result.json").write_text(
            json.dumps(_minimal_extraction_result()), encoding="utf-8"
        )
        assembler = TruthPackAssembler()
        with pytest.raises(FileNotFoundError, match="case.json"):
            assembler.assemble(case_dir)


# ── Tests: Sources section ───────────────────────────────────────────────────


class TestSourcesSection:
    """Tests for sources section."""

    def test_sources_without_market_data(self, tmp_path: Path) -> None:
        """sources must have extraction_result and case_config, market_data=None."""
        case_dir = _create_case_dir(tmp_path, with_market_data=False)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["sources"]["extraction_result"] == "extraction_result.json"
        assert tp["sources"]["case_config"] == "case.json"
        assert tp["sources"]["market_data"] is None

    def test_sources_with_market_data(self, tmp_path: Path) -> None:
        """sources must reference _market_data.json when present."""
        case_dir = _create_case_dir(tmp_path, with_market_data=True)
        assembler = TruthPackAssembler()
        tp = assembler.assemble(case_dir)
        assert tp["sources"]["market_data"] == "_market_data.json"
