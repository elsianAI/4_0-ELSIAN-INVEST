"""AcquirePhase -- pipeline phase for filing acquisition."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from elsian.context import PipelineContext
from elsian.models.case import CaseConfig
from elsian.models.result import PhaseResult
from elsian.pipeline import PipelinePhase

logger = logging.getLogger(__name__)


def _get_fetcher(case: CaseConfig):
    """Return the appropriate fetcher for a case."""
    hint = case.source_hint.lower()
    if hint in ("sec", "sec_edgar"):
        from elsian.acquire.sec_edgar import SecEdgarFetcher
        return SecEdgarFetcher()
    elif hint in ("eu", "eu_manual", "manual_http"):
        from elsian.acquire.eu_regulators import EuRegulatorsFetcher
        return EuRegulatorsFetcher()
    else:
        from elsian.acquire.manual import ManualFetcher
        return ManualFetcher()


class AcquirePhase(PipelinePhase):
    """Acquire filings for a case. Wraps fetcher routing + download logic."""

    def run(self, context: PipelineContext) -> PhaseResult:
        case = context.case
        case_dir = Path(case.case_dir)
        fetcher = _get_fetcher(case)

        try:
            if hasattr(fetcher, "acquire"):
                result = fetcher.acquire(case)
                manifest_path = case_dir / "filings_manifest.json"
                manifest_path.write_text(
                    json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                msg = (
                    f"{case.ticker}: {result.filings_downloaded} filings "
                    f"downloaded ({result.source})"
                )
                return PhaseResult(
                    phase_name="AcquirePhase", success=True, message=msg, data=result,
                )
            else:
                filings = fetcher.fetch(case)
                context.filings = filings
                msg = f"{case.ticker}: {len(filings)} filings found"
                return PhaseResult(
                    phase_name="AcquirePhase", success=True, message=msg,
                )
        except Exception as exc:
            logger.exception("AcquirePhase failed for %s", case.ticker)
            return PhaseResult(
                phase_name="AcquirePhase",
                success=False,
                message=f"Acquisition failed: {exc}",
            )
