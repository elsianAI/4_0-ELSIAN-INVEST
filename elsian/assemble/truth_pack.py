"""truth_pack.py — TruthPack assembler for ELSIAN 4.0.

Combines extraction_result.json + _market_data.json + derived metrics
into a single TruthPack_v1 dict, the consumable output of Module 1.

Schema: TruthPack_v1
    {
        "schema_version": "TruthPack_v1",
        "ticker": str,
        "currency": str,
        "assembly_date": "YYYY-MM-DD",
        "sources": {
            "extraction_result": "extraction_result.json",
            "market_data": "_market_data.json" | null,
            "case_config": "case.json"
        },
        "financial_data": {
            "<period_key>": {
                "fecha_fin": str,
                "tipo_periodo": str,
                "fields": {
                    "<field_name>": {
                        "value": float,
                        "source_filing": str,
                        "extraction_method": str,
                        ...provenance fields
                    }
                }
            }
        },
        "derived_metrics": {
            "ttm": { ... },
            "fcf": float | null,
            "ev": float | null,
            "margins": { "gross_margin_pct": ..., "operating_margin_pct": ..., ... },
            "returns": { "roic_pct": ..., "roe_pct": ..., "roa_pct": ... },
            "multiples": { "ev_ebit": ..., "ev_fcf": ..., "p_fcf": ..., "fcf_yield_pct": ... },
            "per_share": { "eps": ..., "fcf_per_share": ..., "bv_per_share": ... },
            "net_debt": float | null,
            "periodo_base": str
        },
        "market_data": { ... } | null,
        "quality": {
            "validation_status": str,
            "confidence_score": float,
            "gates_summary": { "<gate_name>": "<status>" },
            "warnings": [...],
            "campos_faltantes_criticos": [...]
        },
        "metadata": {
            "total_periods": int,
            "total_fields": int,
            "period_scope": str,
            "source_hint": str,
            "fiscal_year_end_month": int
        }
    }
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TruthPackAssembler:
    """Assembles extraction_result + market_data + derived metrics into TruthPack_v1."""

    SCHEMA_VERSION = "TruthPack_v1"

    def assemble(self, case_dir: Path) -> dict[str, Any]:
        """Main entry point. Returns TruthPack_v1 dict and saves to case_dir.

        Args:
            case_dir: Path to a case directory containing extraction_result.json
                      and optionally _market_data.json.

        Returns:
            TruthPack_v1 dict.

        Raises:
            FileNotFoundError: If extraction_result.json or case.json is missing.
        """
        case_dir = Path(case_dir)

        # a) Load extraction_result.json
        extraction_result = self._load_extraction_result(case_dir)

        # b) Load _market_data.json (optional)
        market_data = self._load_market_data(case_dir)

        # c) Load case.json
        case_config = self._load_case_config(case_dir)

        # d) Calculate derived metrics
        derived = self._calculate_derived(extraction_result, market_data)

        # e) Run autonomous validator
        quality = self._run_validation(
            extraction_result, derived, case_config.get("sector")
        )

        # f) Assemble TruthPack_v1
        truth_pack = self._build_truth_pack(
            extraction_result=extraction_result,
            market_data=market_data,
            case_config=case_config,
            derived=derived,
            quality=quality,
        )

        # g) Save as truth_pack.json
        out_path = case_dir / "truth_pack.json"
        out_path.write_text(
            json.dumps(truth_pack, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Saved truth_pack.json to %s", out_path)

        # h) Return the dict
        return truth_pack

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _load_extraction_result(case_dir: Path) -> dict[str, Any]:
        """Load extraction_result.json from case directory."""
        path = case_dir / "extraction_result.json"
        if not path.exists():
            raise FileNotFoundError(
                f"extraction_result.json not found in {case_dir}"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_market_data(case_dir: Path) -> dict[str, Any] | None:
        """Load _market_data.json if it exists, else return None."""
        path = case_dir / "_market_data.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_case_config(case_dir: Path) -> dict[str, Any]:
        """Load case.json from case directory."""
        path = case_dir / "case.json"
        if not path.exists():
            raise FileNotFoundError(f"case.json not found in {case_dir}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _calculate_derived(
        extraction_result: dict[str, Any],
        market_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Calculate derived metrics using elsian.calculate.derived."""
        from elsian.calculate.derived import calculate

        return calculate(extraction_result, market_data)

    @staticmethod
    def _run_validation(
        extraction_result: dict[str, Any],
        derived: dict[str, Any],
        sector: str | None,
    ) -> dict[str, Any]:
        """Run autonomous validator using elsian.evaluate.validation."""
        from elsian.evaluate.validation import validate

        return validate(extraction_result, derived, sector)

    def _build_truth_pack(
        self,
        *,
        extraction_result: dict[str, Any],
        market_data: dict[str, Any] | None,
        case_config: dict[str, Any],
        derived: dict[str, Any],
        quality: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble all components into TruthPack_v1 dict."""
        periods = extraction_result.get("periods", {})
        ticker = extraction_result.get("ticker", case_config.get("ticker", ""))
        currency = extraction_result.get("currency", case_config.get("currency", "USD"))

        # Build financial_data section (pass through periods as-is)
        financial_data: dict[str, Any] = {}
        total_fields = 0
        for pk, pv in periods.items():
            financial_data[pk] = {
                "fecha_fin": pv.get("fecha_fin", ""),
                "tipo_periodo": pv.get("tipo_periodo", ""),
                "fields": pv.get("fields", {}),
            }
            total_fields += len(pv.get("fields", {}))

        # Build derived_metrics section
        derived_metrics = self._format_derived(derived)

        # Build market_data section
        market_section = self._format_market_data(market_data)

        # Build quality section
        quality_section = self._format_quality(quality)

        # Build metadata section
        metadata = {
            "total_periods": len(periods),
            "total_fields": total_fields,
            "period_scope": case_config.get("period_scope", "ANNUAL_ONLY"),
            "source_hint": case_config.get("source_hint", "sec"),
            "fiscal_year_end_month": case_config.get("fiscal_year_end_month", 12),
        }

        return {
            "schema_version": self.SCHEMA_VERSION,
            "ticker": ticker,
            "currency": currency,
            "assembly_date": dt.date.today().isoformat(),
            "sources": {
                "extraction_result": "extraction_result.json",
                "market_data": "_market_data.json" if market_data else None,
                "case_config": "case.json",
            },
            "financial_data": financial_data,
            "derived_metrics": derived_metrics,
            "market_data": market_section,
            "quality": quality_section,
            "metadata": metadata,
        }

    @staticmethod
    def _format_derived(derived: dict[str, Any]) -> dict[str, Any]:
        """Format derived metrics into TruthPack structure."""
        ttm = derived.get("ttm", {})
        dm = derived.get("derived_metrics", {})

        return {
            "ttm": ttm,
            "fcf": dm.get("fcf"),
            "ev": dm.get("ev"),
            "margins": {
                "gross_margin_pct": dm.get("gross_margin_pct"),
                "operating_margin_pct": dm.get("operating_margin_pct"),
                "net_margin_pct": dm.get("net_margin_pct"),
                "fcf_margin_pct": dm.get("fcf_margin_pct"),
            },
            "returns": {
                "roic_pct": dm.get("roic_pct"),
                "roe_pct": dm.get("roe_pct"),
                "roa_pct": dm.get("roa_pct"),
            },
            "multiples": {
                "ev_ebit": dm.get("ev_ebit"),
                "ev_fcf": dm.get("ev_fcf"),
                "p_fcf": dm.get("p_fcf"),
                "fcf_yield_pct": dm.get("fcf_yield_pct"),
            },
            "per_share": {
                "eps": dm.get("eps"),
                "fcf_per_share": dm.get("fcf_per_share"),
                "bv_per_share": dm.get("bv_per_share"),
            },
            "net_debt": dm.get("net_debt"),
            "periodo_base": dm.get("periodo_base", "no_disponible"),
        }

    @staticmethod
    def _format_market_data(market_data: dict[str, Any] | None) -> dict[str, Any] | None:
        """Format market data for TruthPack, or return None if unavailable."""
        if market_data is None:
            return None
        # Pass through the market data dict as-is (already flat from MarketDataFetcher)
        return dict(market_data)

    @staticmethod
    def _format_quality(quality: dict[str, Any]) -> dict[str, Any]:
        """Format validation results into TruthPack quality section."""
        gates = quality.get("gates", [])
        gates_summary: dict[str, str] = {}
        for gate in gates:
            gates_summary[gate.get("name", "UNKNOWN")] = gate.get("status", "SKIP")

        return {
            "validation_status": quality.get("status", "UNKNOWN"),
            "confidence_score": quality.get("confidence_score", 0),
            "gates_summary": gates_summary,
            "warnings": quality.get("warnings", []),
            "campos_faltantes_criticos": quality.get("faltantes_criticos", []),
        }
