"""HkexFetcher -- reads pre-downloaded HKEX filings from disk.

Operates in hkex_manual mode: returns all pre-placed filings found in
cases/{TICKER}/filings/. No network calls are made. For live HKEX
acquisition, subclass or extend this fetcher and override fetch().
"""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.acquire.base import Fetcher
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".htm", ".html", ".txt", ".pdf", ".md"}


class HkexFetcher(Fetcher):
    """Reads HKEX filings already present in cases/{TICKER}/filings/.

    Designed for HKEX-listed companies (source_hint: 'hkex_manual').
    Filings must be manually placed following the SRC_NNN naming convention.
    """

    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Return Filing objects for all pre-placed files in the filings dir.

        Args:
            case: CaseConfig for the HKEX-listed company.

        Returns:
            Sorted list of Filing objects found on disk.
        """
        filings_dir = Path(case.case_dir) / "filings"
        if not filings_dir.exists():
            logger.warning("HkexFetcher: no filings directory at %s", filings_dir)
            return []

        filings: list[Filing] = []
        for f in sorted(filings_dir.iterdir()):
            if f.is_file() and f.suffix in _SUPPORTED_EXTENSIONS:
                filings.append(Filing(
                    source_id=f.stem,
                    local_path=str(f),
                    primary_doc=f.name,
                ))

        logger.info(
            "HkexFetcher: found %d filings in %s for %s",
            len(filings),
            filings_dir,
            case.ticker,
        )
        return filings
