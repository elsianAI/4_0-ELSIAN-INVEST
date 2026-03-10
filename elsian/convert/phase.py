"""ConvertPhase -- pipeline phase for filing conversion (htm->md, pdf->txt)."""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.context import PipelineContext
from elsian.models.result import PhaseResult
from elsian.pipeline import PipelinePhase

logger = logging.getLogger(__name__)


class ConvertPhase(PipelinePhase):
    """Convert raw filings to clean parseable formats.

    htm → .clean.md  via html_to_markdown
    pdf → .txt       via pdf_to_text

    Never fatal: missing/empty filings dirs are a no-op; per-file errors are
    logged as warnings and counted in diagnostics.
    """

    def __init__(self, force: bool = False) -> None:
        self._force = force

    def run(self, context: PipelineContext) -> PhaseResult:
        from elsian.convert.html_to_markdown import convert as _html_to_md
        from elsian.convert.pdf_to_text import extract_pdf_text

        ticker = context.case.ticker
        filings_dir = Path(context.case.case_dir) / "filings"

        if not filings_dir.exists():
            return PhaseResult(
                phase_name="ConvertPhase",
                success=True,
                severity="ok",
                message=f"{ticker}: no filings dir -- skipping convert",
                diagnostics={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
            )

        converted = skipped = failed = total = 0

        for filing_path in sorted(filings_dir.iterdir()):
            if not filing_path.is_file():
                continue
            suffix = filing_path.suffix.lower()

            if suffix == ".htm":
                total += 1
                out_path = filings_dir / f"{filing_path.stem}.clean.md"
                if out_path.exists() and not self._force:
                    skipped += 1
                    continue
                try:
                    clean_md = _html_to_md(filing_path)
                    if clean_md:
                        out_path.write_text(clean_md, encoding="utf-8")
                        converted += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    logger.warning("Convert failed %s: %s", filing_path.name, exc)
                    failed += 1

            elif suffix == ".pdf":
                total += 1
                out_path = filings_dir / f"{filing_path.stem}.txt"
                if out_path.exists() and not self._force:
                    skipped += 1
                    continue
                try:
                    text = extract_pdf_text(filing_path.read_bytes())
                    out_path.write_text(text, encoding="utf-8")
                    converted += 1
                except Exception as exc:
                    logger.warning("Convert failed %s: %s", filing_path.name, exc)
                    failed += 1

        msg = (
            f"{ticker}: {total} filings -- "
            f"{converted} converted, {skipped} cached, {failed} failed"
        )
        severity = "warning" if failed > 0 else "ok"
        return PhaseResult(
            phase_name="ConvertPhase",
            success=True,
            severity=severity,
            message=msg,
            diagnostics={
                "total": total,
                "converted": converted,
                "skipped": skipped,
                "failed": failed,
            },
        )
