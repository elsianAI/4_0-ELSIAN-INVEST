"""EvaluatePhase -- pipeline phase for evaluation against expected.json."""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.context import PipelineContext
from elsian.evaluate.evaluator import evaluate
from elsian.models.result import PhaseResult
from elsian.pipeline import PipelinePhase

logger = logging.getLogger(__name__)


class EvaluatePhase(PipelinePhase):
    """Evaluate extraction result against expected.json."""

    def run(self, context: PipelineContext) -> PhaseResult:
        case = context.case
        case_dir = Path(case.case_dir)
        expected_path = case_dir / "expected.json"

        if not expected_path.exists():
            return PhaseResult(
                phase_name="EvaluatePhase",
                success=True,
                severity="ok",
                message=f"{case.ticker}: no expected.json — skipping evaluation",
            )

        report = evaluate(context.result, str(expected_path))
        status = "PASS" if report.score == 100.0 else "FAIL"
        severity = "ok" if report.score == 100.0 else "warning"
        msg = (
            f"{case.ticker}: {status} -- {report.score}% "
            f"({report.matched}/{report.total_expected}) "
            f"wrong={report.wrong} missed={report.missed} extra={report.extra}"
        )

        return PhaseResult(
            phase_name="EvaluatePhase",
            # EvaluatePhase is never fatal — a score < 100% is a quality signal,
            # not a blocking error.  The pipeline (and Assemble) continue.
            success=True,
            severity=severity,
            message=msg,
            data=report,
            diagnostics={
                "score": report.score,
                "matched": report.matched,
                "total_expected": report.total_expected,
                "wrong": report.wrong,
                "missed": report.missed,
                "extra": report.extra,
            },
        )
