"""tests/integration/test_assemble.py — Integration test for TruthPackAssembler.

E2E test: assemble TZOO (requires extraction_result.json in cases/TZOO/).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elsian.assemble.truth_pack import TruthPackAssembler

CASES_DIR = Path(__file__).resolve().parent.parent.parent / "cases"


def _has_extraction_result(ticker: str) -> bool:
    """Check if extraction_result.json exists for a ticker."""
    return (CASES_DIR / ticker / "extraction_result.json").exists()


@pytest.mark.skipif(
    not _has_extraction_result("TZOO"),
    reason="TZOO extraction_result.json not found",
)
class TestAssembleTZOO:
    """E2E integration test: assemble TruthPack for TZOO."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path) -> None:
        """Copy TZOO case files to tmp_path to avoid polluting real case dir."""
        src = CASES_DIR / "TZOO"
        self.case_dir = tmp_path / "TZOO"
        self.case_dir.mkdir()

        # Copy essential files
        for name in ("extraction_result.json", "case.json"):
            src_file = src / name
            if src_file.exists():
                (self.case_dir / name).write_text(
                    src_file.read_text(encoding="utf-8"), encoding="utf-8"
                )

        # Copy _market_data.json if exists
        md_file = src / "_market_data.json"
        if md_file.exists():
            (self.case_dir / "_market_data.json").write_text(
                md_file.read_text(encoding="utf-8"), encoding="utf-8"
            )

    def test_assemble_produces_truth_pack(self) -> None:
        """TruthPack assembler must produce truth_pack.json for TZOO."""
        assembler = TruthPackAssembler()
        tp = assembler.assemble(self.case_dir)

        assert tp["schema_version"] == "TruthPack_v1"
        assert tp["ticker"] == "TZOO"
        assert tp["currency"] == "USD"
        assert (self.case_dir / "truth_pack.json").exists()

    def test_financial_data_matches_extraction_result(self) -> None:
        """financial_data in TruthPack must match extraction_result.json periods."""
        er = json.loads(
            (self.case_dir / "extraction_result.json").read_text(encoding="utf-8")
        )
        assembler = TruthPackAssembler()
        tp = assembler.assemble(self.case_dir)

        er_periods = set(er.get("periods", {}).keys())
        tp_periods = set(tp.get("financial_data", {}).keys())
        assert er_periods == tp_periods

        # Spot-check: field values should match
        for pk in list(er_periods)[:3]:
            er_fields = er["periods"][pk].get("fields", {})
            tp_fields = tp["financial_data"][pk].get("fields", {})
            for fname in er_fields:
                assert fname in tp_fields
                assert tp_fields[fname]["value"] == er_fields[fname]["value"]

    def test_derived_metrics_populated(self) -> None:
        """derived_metrics must be populated with calculations."""
        assembler = TruthPackAssembler()
        tp = assembler.assemble(self.case_dir)
        dm = tp["derived_metrics"]

        assert "ttm" in dm
        assert "margins" in dm
        assert "returns" in dm
        assert "multiples" in dm
        assert "per_share" in dm
        assert "periodo_base" in dm

    def test_quality_section_populated(self) -> None:
        """quality section must be populated with validation gates."""
        assembler = TruthPackAssembler()
        tp = assembler.assemble(self.case_dir)
        q = tp["quality"]

        assert q["validation_status"] in {"PASS", "PARTIAL", "FAIL"}
        assert isinstance(q["confidence_score"], (int, float))
        assert len(q["gates_summary"]) == 9

    def test_metadata_correct(self) -> None:
        """metadata must reflect TZOO case configuration."""
        assembler = TruthPackAssembler()
        tp = assembler.assemble(self.case_dir)
        meta = tp["metadata"]

        assert meta["total_periods"] > 0
        assert meta["total_fields"] > 0
        assert meta["source_hint"] == "sec"
        assert meta["period_scope"] == "FULL"
