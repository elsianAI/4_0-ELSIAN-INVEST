"""EU regulators filing acquisition — HTTP download + raw filings import.

Ported from 3_0-ELSIAN-INVEST/deterministic/src/acquire/eu_regulators.py.
For EU cases, filings are acquired via two mechanisms:

1. HTTP download: case.json declares filings_sources with URLs.
2. Raw filings import: fallback from pre-existing raw filings directory.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any, Optional

import requests

from elsian.acquire.base import Fetcher
from elsian.convert.html_to_markdown import convert as html_to_markdown
from elsian.convert.pdf_to_text import extract_pdf_text_from_file
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing
from elsian.models.result import AcquisitionResult

logger = logging.getLogger(__name__)

_TEXT_SUFFIXES = {".md", ".txt", ".htm", ".html", ".pdf"}

# ── HTTP client ──────────────────────────────────────────────────────

USER_AGENT = "ELSIAN-INVEST-Bot/1.0 (research; bot@elsian-invest.local)"
_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT = 60
_RATE_LIMIT = 0.5


def _http_get(url: str, retries: int = 2) -> Optional[bytes]:
    """Download url and return raw bytes, or None on failure."""
    for attempt in range(retries + 1):
        try:
            resp = requests.get(
                url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            if attempt == retries:
                logger.warning("Download failed: %s — %s", url, exc)
                return None
            time.sleep(1.0)
    return None


# ── HTTP source download ─────────────────────────────────────────────

def _download_sources(sources: list[dict[str, Any]], filings_dir: Path) -> int:
    """Download each entry in sources into filings_dir if not already present."""
    filings_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0

    for src in sources:
        url: str = src.get("url", "").strip()
        filename: str = src.get("filename", "").strip()
        if not url or not filename:
            continue

        dst = filings_dir / filename
        if dst.exists():
            continue

        logger.info("Downloading %s …", filename)
        content = _http_get(url)
        if content is None:
            continue

        dst.write_bytes(content)
        downloaded += 1
        time.sleep(_RATE_LIMIT)

        suffix = dst.suffix.lower()

        if suffix == ".pdf":
            txt_path = filings_dir / (dst.stem + ".txt")
            if not txt_path.exists():
                text = extract_pdf_text_from_file(str(dst))
                if text.strip():
                    txt_path.write_text(text, encoding="utf-8")

        elif suffix in {".htm", ".html"}:
            md_path = filings_dir / (dst.stem + ".clean.md")
            if not md_path.exists():
                clean_md = html_to_markdown(dst)
                if clean_md and clean_md.strip():
                    md_path.write_text(clean_md, encoding="utf-8")

    return downloaded


def _import_raw_filings(raw_dir: Path, filings_dir: Path) -> int:
    """Copy raw filings into the filings/ directory."""
    if not raw_dir.exists():
        return 0

    filings_dir.mkdir(parents=True, exist_ok=True)

    groups: dict[str, list[Path]] = {}
    for f in sorted(raw_dir.iterdir()):
        if not f.is_file():
            continue
        name = f.name
        if name.startswith("SRC_SEC_") or name.startswith("SRC_PR_"):
            continue
        m = re.match(r"(SRC_\d+)", name)
        if not m:
            groups.setdefault(name.split(".")[0], []).append(f)
            continue
        groups.setdefault(m.group(1), []).append(f)

    imported = 0
    for _prefix, files in sorted(groups.items()):
        txt_files = [f for f in files if f.suffix == ".txt"]
        pdf_files = [f for f in files if f.suffix == ".pdf"]
        htm_files = [f for f in files if f.suffix in {".htm", ".html"}]
        md_files = [f for f in files if f.name.endswith(".clean.md")]

        if not txt_files and not pdf_files and not htm_files:
            continue

        for src in txt_files:
            dst = filings_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)

        for src in pdf_files:
            dst = filings_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)

        if not txt_files and pdf_files:
            for pdf in pdf_files:
                txt_dst = filings_dir / (pdf.stem + ".txt")
                if not txt_dst.exists():
                    text = extract_pdf_text_from_file(str(pdf))
                    if text.strip():
                        txt_dst.write_text(text, encoding="utf-8")

        for src in md_files:
            dst = filings_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)

        if not md_files and htm_files:
            for htm in htm_files:
                if htm.name.endswith(".clean.md"):
                    continue
                md_dst = filings_dir / (htm.stem + ".clean.md")
                if not md_dst.exists():
                    clean_md = html_to_markdown(htm)
                    if clean_md and clean_md.strip():
                        md_dst.write_text(clean_md, encoding="utf-8")

        imported += 1

    return imported


# ── EuRegulatorsFetcher ──────────────────────────────────────────────

class EuRegulatorsFetcher(Fetcher):
    """Fetches filings for EU/non-SEC companies via HTTP download or raw import."""

    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Download/import filings and return Filing objects."""
        self.acquire(case)
        filings_dir = Path(case.case_dir) / "filings"
        if not filings_dir.exists():
            return []

        filings: list[Filing] = []
        for f in sorted(filings_dir.iterdir()):
            if f.is_file() and f.suffix in (".htm", ".html", ".txt", ".pdf", ".md"):
                filings.append(Filing(
                    source_id=f.stem,
                    local_path=str(f),
                    primary_doc=f.name,
                ))
        return filings

    def acquire(self, case: CaseConfig) -> AcquisitionResult:
        """Acquire filings for an EU case."""
        case_path = Path(case.case_dir)
        filings_dir = case_path / "filings"

        case_json_path = case_path / "case.json"
        case_config: dict[str, Any] = {}
        if case_json_path.exists():
            case_config = json.loads(case_json_path.read_text(encoding="utf-8"))

        ticker = case_config.get("ticker", case_path.name)
        expected_count = case_config.get("filings_expected_count", 0)

        filings_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: HTTP download from filings_sources
        http_downloaded = 0
        sources: list[dict[str, Any]] = case_config.get("filings_sources", [])
        if sources:
            http_downloaded = _download_sources(sources, filings_dir)

        # Step 2: raw_filings_dir import (fallback)
        imported_count = 0
        has_existing = any(
            f.is_file() and f.suffix in _TEXT_SUFFIXES
            for f in filings_dir.iterdir()
        )
        if not has_existing:
            raw_dir_rel = case_config.get("raw_filings_dir", "")
            if raw_dir_rel:
                raw_dir = (case_path / raw_dir_rel).resolve()
                imported_count = _import_raw_filings(raw_dir, filings_dir)

        # Inventory
        existing_files = sorted(
            f.name
            for f in filings_dir.iterdir()
            if f.is_file() and f.suffix in _TEXT_SUFFIXES
        )

        found = len(existing_files)
        coverage_pct = (found / expected_count * 100.0) if expected_count > 0 else 0.0

        gaps: list[str] = []
        if found == 0:
            gaps.append(
                f"No filings found. Add filings_sources URLs to case.json or "
                f"place files in {filings_dir}/."
            )
        elif found < expected_count:
            gaps.append(f"Expected {expected_count} filings, found {found}.")

        notes_parts = [f"EU acquisition. {found} filings in filings/."]
        if http_downloaded:
            notes_parts.append(f"HTTP-downloaded: {http_downloaded} new file(s).")
        if imported_count:
            notes_parts.append(f"Imported {imported_count} group(s) from raw_filings_dir.")

        return AcquisitionResult(
            ticker=ticker,
            source="eu_manual",
            filings_downloaded=found,
            filings_failed=0,
            filings_coverage_pct=round(min(coverage_pct, 100.0), 1),
            coverage={
                "http": {
                    "sources_declared": len(sources),
                    "downloaded_new": http_downloaded,
                },
                "raw_import": {
                    "groups_imported": imported_count,
                },
                "total": {
                    "expected": expected_count,
                    "found": found,
                    "files": existing_files,
                },
            },
            gaps=gaps,
            notes=" ".join(notes_parts),
            download_date=dt.date.today().isoformat(),
        )