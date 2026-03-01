"""ManualFetcher -- reads pre-downloaded filings from disk."""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.acquire.base import Fetcher
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing

logger = logging.getLogger(__name__)


class ManualFetcher(Fetcher):
    """Reads filings already present in cases/{TICKER}/filings/."""

    def fetch(self, case: CaseConfig) -> list[Filing]:
        filings_dir = Path(case.case_dir) / "filings"
        if not filings_dir.exists():
            logger.warning("No filings directory: %s", filings_dir)
            return []

        filings: list[Filing] = []
        for f in sorted(filings_dir.iterdir()):
            if f.is_file() and f.suffix in (".htm", ".html", ".txt", ".pdf", ".md"):
                filings.append(Filing(
                    source_id=f.stem,
                    local_path=str(f),
                    primary_doc=f.name,
                ))

        logger.info("ManualFetcher: found %d filings in %s", len(filings), filings_dir)
        return filings
