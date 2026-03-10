"""AssemblePhase -- pipeline phase for truth_pack.json assembly."""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.context import PipelineContext
from elsian.models.result import PhaseResult
from elsian.pipeline import PipelinePhase

logger = logging.getLogger(__name__)


class AssemblePhase(PipelinePhase):
    """Assemble truth_pack.json from extraction result.

    Non-fatal by design: an assemble failure degrades output quality but
    does not invalidate the extraction or evaluation results that precede it.
    Exceptions are captured as severity='warning'.
    """

    def run(self, context: PipelineContext) -> PhaseResult:
        ticker = context.case.ticker
        case_dir = Path(context.case.case_dir)

        try:
            from elsian.assemble.truth_pack import TruthPackAssembler

            assembler = TruthPackAssembler()
            tp = assembler.assemble(case_dir)
            truth_pack_path = case_dir / "truth_pack.json"
            meta = tp.get("metadata", {})
            dm = tp.get("derived_metrics", {})
            derived_count = sum(
                len(v) if isinstance(v, dict) else 1
                for v in dm.values()
                if v is not None and v != {}
            )
            msg = (
                f"{ticker}: truth_pack.json "
                f"({meta.get('total_periods', 0)} periods, "
                f"{meta.get('total_fields', 0)} fields, "
                f"{derived_count} derived)"
            )
            return PhaseResult(
                phase_name="AssemblePhase",
                success=True,
                severity="ok",
                message=msg,
                diagnostics={"truth_pack_path": str(truth_pack_path)},
            )
        except Exception as exc:
            logger.warning("AssemblePhase failed for %s: %s", ticker, exc)
            return PhaseResult(
                phase_name="AssemblePhase",
                success=True,  # non-fatal by design
                severity="warning",
                message=f"{ticker}: assemble warning -- {exc}",
                diagnostics={"exception": str(exc)},
            )
