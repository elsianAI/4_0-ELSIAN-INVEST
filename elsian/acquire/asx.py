"""ASX (Australian Securities Exchange) filing fetcher.

Fetches announcements from the ASX public announcement list API,
filters for the target company's financial filings, and downloads PDFs.
Converts PDFs to text using pdfplumber.

API endpoint:
  https://www.asx.com.au/asx/1/announcement/list
  Parameters: page_size, end_date (unix ms), date_from (unix ms)
  Returns JSON with announcement_data[] containing all ASX announcements.

Announcement PDF URLs are direct links:
  https://announcements.asx.com.au/asxpdf/{date}/pdf/{id}.pdf
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from elsian.acquire.base import Fetcher
from elsian.acquire.dedup import content_hash
from elsian.convert.pdf_to_text import extract_pdf_text
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing
from elsian.models.result import AcquisitionResult

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

_BASE_URL = "https://www.asx.com.au/asx/1/announcement/list"
_USER_AGENT = "ELSIAN-INVEST-Bot/1.0 (research; bot@elsian-invest.local)"
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/json,*/*;q=0.8",
}
_TIMEOUT = 60
_RATE_LIMIT = 1.0  # ASX is a public website; be respectful
_PAGE_SIZE = 2000

# Financial filing types we want to download (ASX announcement headers)
_ANNUAL_PATTERNS = [
    re.compile(r"annual\s+report", re.IGNORECASE),
    re.compile(r"appendix\s+4e", re.IGNORECASE),
    re.compile(r"preliminary\s+final\s+report", re.IGNORECASE),
]

_HALFYEAR_PATTERNS = [
    re.compile(r"half[\s-]?year", re.IGNORECASE),
    re.compile(r"(?:^|\W)[12]H\s*\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\bHY\d{2,4}\b", re.IGNORECASE),
    re.compile(r"interim\s+(?:financial\s+)?report", re.IGNORECASE),
    re.compile(r"appendix\s+4d", re.IGNORECASE),
]

_RESULTS_PATTERNS = [
    re.compile(r"(?:asx|full\s+year|annual|fy\d{2})\s+(?:release|results)", re.IGNORECASE),
    re.compile(r"results?\s+(?:announcement|presentation)", re.IGNORECASE),
]

# Skip non-financial announcements even if they match partial keywords
_SKIP_PATTERNS = [
    re.compile(r"appendix\s+4g", re.IGNORECASE),
    re.compile(r"sustainability\s+report", re.IGNORECASE),
    re.compile(r"corporate\s+governance", re.IGNORECASE),
    re.compile(r"substantial\s+holder", re.IGNORECASE),
    re.compile(r"change\s+of\s+director", re.IGNORECASE),
    re.compile(r"buy[\s-]?back", re.IGNORECASE),
    re.compile(r"quotation\s+of\s+securities", re.IGNORECASE),
    re.compile(r"dividend/distribution", re.IGNORECASE),
]

ANNUAL_TARGET = 3
HALFYEAR_TARGET = 3


# ── Helpers ──────────────────────────────────────────────────────────

def _is_financial_filing(header: str) -> str | None:
    """Classify an announcement header. Returns filing_type or None."""
    for pat in _SKIP_PATTERNS:
        if pat.search(header):
            return None
    for pat in _ANNUAL_PATTERNS:
        if pat.search(header):
            return "annual"
    for pat in _HALFYEAR_PATTERNS:
        if pat.search(header):
            return "halfyear"
    for pat in _RESULTS_PATTERNS:
        if pat.search(header):
            return "results"
    return None


def _ms_timestamp(d: dt.date) -> int:
    """Convert date to Unix milliseconds."""
    return int(dt.datetime.combine(d, dt.time.max).timestamp() * 1000)


def _search_window(
    ticker: str,
    date_from: dt.date,
    date_to: dt.date,
) -> list[dict[str, Any]]:
    """Query ASX announcement list API for a date window, filtered by ticker."""
    params = {
        "page_size": _PAGE_SIZE,
        "end_date": _ms_timestamp(date_to),
        "date_from": _ms_timestamp(date_from),
    }

    try:
        resp = requests.get(
            _BASE_URL, headers=_HEADERS, params=params, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("ASX API request failed: %s", exc)
        return []

    items = data.get("announcement_data", [])
    ticker_upper = ticker.upper()
    return [
        item for item in items
        if item.get("issuer_code", "").upper() == ticker_upper
    ]


def _search_all_windows(
    ticker: str,
    years_back: int = 3,
    fy_end_month: int = 12,
) -> list[dict[str, Any]]:
    """Search targeted date windows to find financial filings for a ticker.

    Rather than scanning every 14-day window backwards, this targets the
    months when financial filings typically appear based on fiscal year end.
    For Dec FY: Feb-Mar (annual) and Aug-Sep (half-year).
    Falls back to a broader scan to catch any additional filings.
    """
    all_announcements: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    today = dt.date.today()

    # Determine reporting months: annual ~2-3 months after FY end,
    # half-year ~2-3 months after mid-year
    annual_months = [(fy_end_month % 12) + 1, (fy_end_month % 12) + 2, (fy_end_month % 12) + 3]
    halfyear_month = (fy_end_month + 6) % 12 or 12
    halfyear_months = [halfyear_month % 12 + 1, halfyear_month % 12 + 2, halfyear_month % 12 + 3]

    # Normalize months to 1-12
    annual_months = [((m - 1) % 12) + 1 for m in annual_months]
    halfyear_months = [((m - 1) % 12) + 1 for m in halfyear_months]

    target_months = set(annual_months + halfyear_months)

    annual_found = 0
    halfyear_found = 0
    results_found = 0

    # Generate targeted windows: scan reporting months for each year
    windows: list[tuple[dt.date, dt.date]] = []
    for year_offset in range(years_back + 1):
        year = today.year - year_offset
        for month in target_months:
            # Build a 30-day window around mid-month (split into 2x14-day)
            start1 = dt.date(year, month, 1)
            end1 = dt.date(year, month, 15)
            start2 = dt.date(year, month, 15)
            # Handle month end
            if month == 12:
                end2 = dt.date(year + 1, 1, 1)
            else:
                end2 = dt.date(year, month + 1, 1)

            # Only include windows that aren't in the future
            if start1 <= today:
                windows.append((start1, min(end1, today)))
            if start2 <= today:
                windows.append((start2, min(end2, today)))

    # Sort windows by date (most recent first)
    windows.sort(key=lambda x: x[1], reverse=True)

    for start, end in windows:
        if start >= end:
            continue

        items = _search_window(ticker, start, end)
        new_in_window = 0
        financial_in_window = 0
        for item in items:
            ann_id = item.get("id", "")
            if ann_id and ann_id not in seen_ids:
                seen_ids.add(ann_id)
                all_announcements.append(item)
                new_in_window += 1
                header = item.get("header", "")
                ftype = _is_financial_filing(header)
                if ftype:
                    financial_in_window += 1
                    logger.debug("  → %s: %s", ftype, header)
                if ftype == "annual":
                    annual_found += 1
                elif ftype == "halfyear":
                    halfyear_found += 1
                elif ftype == "results":
                    results_found += 1

        if new_in_window > 0:
            logger.info(
                "Window %s to %s: %d items (%d financial) [A:%d H:%d R:%d]",
                start.isoformat(), end.isoformat(), new_in_window,
                financial_in_window, annual_found, halfyear_found, results_found,
            )

        # Early stop: found enough of each type
        if annual_found >= ANNUAL_TARGET and halfyear_found >= HALFYEAR_TARGET:
            logger.info(
                "Early stop (target met): %d annual + %d halfyear + %d results",
                annual_found, halfyear_found, results_found,
            )
            break

        time.sleep(_RATE_LIMIT)

    all_announcements.sort(
        key=lambda x: x.get("document_release_date", ""),
        reverse=True,
    )
    return all_announcements


def _infer_period(header: str, filing_date: str, fy_end_month: int) -> str:
    """Infer period label from announcement header and date.

    Looks for year patterns (FY25, TY23, 2024, etc.) in the header.
    Falls back to filing date-based inference.
    """
    # Try "1H 2024", "H1 2024", "HY24", "Half Year 2024" patterns first
    half_match = re.search(
        r"(?:1H|H1|HY)\s*(\d{2,4})", header, re.IGNORECASE,
    )
    if half_match:
        year_str = half_match.group(1)
        year = int(year_str) if len(year_str) == 4 else int(f"20{year_str}")
        return f"H1-{year}"

    # Try "half year" with year nearby
    hy_match = re.search(r"half\s+year.*?(\d{4})", header, re.IGNORECASE)
    if hy_match:
        return f"H1-{hy_match.group(1)}"

    # Try FY/TY/CY year patterns
    fy_match = re.search(
        r"(?:FY|TY|CY)\s*(\d{2,4})", header, re.IGNORECASE,
    )
    if fy_match:
        year_str = fy_match.group(1)
        year = int(year_str) if len(year_str) == 4 else int(f"20{year_str}")
        return f"FY{year}"

    # Try standalone year (e.g., "Annual Report 2024")
    year_match = re.search(r"\b(20\d{2})\b", header)
    if year_match:
        year = int(year_match.group(1))
        filing_type = _is_financial_filing(header)
        if filing_type == "halfyear":
            return f"H1-{year}"
        return f"FY{year}"

    # Fall back to filing date
    try:
        d = dt.date.fromisoformat(filing_date[:10])
    except (ValueError, IndexError):
        return "unknown"

    if d.month <= fy_end_month + 4:
        return f"FY{d.year - 1}"
    return f"FY{d.year}"


def _download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF from ASX announcements CDN."""
    try:
        resp = requests.get(
            url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
        )
        resp.raise_for_status()
        if len(resp.content) < 100:
            logger.warning("PDF too small (%d bytes): %s", len(resp.content), url)
            return False
        dest.write_bytes(resp.content)
        return True
    except Exception as exc:
        logger.warning("PDF download failed: %s — %s", url, exc)
        return False


# ── AsxFetcher ───────────────────────────────────────────────────────

class AsxFetcher(Fetcher):
    """Fetches financial filings from ASX for Australian-listed companies."""

    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Download filings and return Filing objects."""
        self.acquire(case)
        filings_dir = Path(case.case_dir) / "filings"
        if not filings_dir.exists():
            return []

        filings: list[Filing] = []
        for f in sorted(filings_dir.iterdir()):
            if f.is_file() and f.suffix in (".txt", ".pdf"):
                filings.append(Filing(
                    source_id=f.stem,
                    local_path=str(f),
                    primary_doc=f.name,
                ))
        return filings

    def acquire(self, case: CaseConfig) -> AcquisitionResult:
        """Search ASX announcements, download financial filings as PDFs.

        If filings already exist in the case directory, skips download (cache).
        """
        ticker = case.ticker
        out_path = Path(case.case_dir) / "filings"
        out_path.mkdir(parents=True, exist_ok=True)

        # Cache: if filings already exist, skip
        existing = list(out_path.glob("SRC_*"))
        if existing:
            return AcquisitionResult(
                ticker=ticker,
                source="asx",
                filings_downloaded=len(existing),
                filings_coverage_pct=100.0,
                notes="Using cached filings (directory not empty).",
            )

        # Search ASX for all announcements
        all_announcements = _search_all_windows(
            ticker, years_back=3, fy_end_month=case.fiscal_year_end_month,
        )
        logger.info(
            "Found %d total ASX announcements for %s",
            len(all_announcements), ticker,
        )

        # Classify financial filings
        financial_filings: list[tuple[str, str, dict[str, Any]]] = []
        for ann in all_announcements:
            header = ann.get("header", "")
            filing_type = _is_financial_filing(header)
            if filing_type:
                financial_filings.append((filing_type, header, ann))

        logger.info(
            "Identified %d financial filings for %s",
            len(financial_filings), ticker,
        )

        # Select: prioritize annual reports, then half-year, then results
        annual = [
            (h, a) for ft, h, a in financial_filings if ft == "annual"
        ][:ANNUAL_TARGET]
        halfyear = [
            (h, a) for ft, h, a in financial_filings if ft == "halfyear"
        ][:HALFYEAR_TARGET]
        results_list = [
            (h, a) for ft, h, a in financial_filings if ft == "results"
        ]

        selected: list[tuple[str, dict[str, Any]]] = []
        selected.extend(annual)
        selected.extend(halfyear)

        # Add results releases (they often have summary tables)
        for h, a in results_list:
            if len(selected) < (ANNUAL_TARGET + HALFYEAR_TARGET + 3):
                selected.append((h, a))

        # Download
        source_counter = 1
        downloaded = 0
        failed = 0
        seen_hashes: set[str] = set()

        for header, ann in selected:
            url = ann.get("url", "")
            if not url:
                logger.warning("No PDF URL for announcement: %s", header)
                failed += 1
                continue

            filing_type = _is_financial_filing(header) or "other"
            release_date = ann.get("document_release_date", "")[:10]
            period = _infer_period(
                header, release_date, case.fiscal_year_end_month,
            )

            prefix = f"SRC_{source_counter:03d}"
            base_name = f"{prefix}_{filing_type}_{period}"

            pdf_path = out_path / f"{base_name}.pdf"
            logger.info("Downloading: %s -> %s", header, pdf_path.name)

            if _download_pdf(url, pdf_path):
                # Convert PDF to text
                txt_path = out_path / f"{base_name}.txt"
                text = extract_pdf_text(pdf_path.read_bytes())
                if text.strip():
                    # Content dedup: skip if we already have this text
                    h = content_hash(text)
                    if h and h in seen_hashes:
                        logger.info("Skipping duplicate content: %s", pdf_path.name)
                        pdf_path.unlink(missing_ok=True)
                        continue
                    if h:
                        seen_hashes.add(h)
                    txt_path.write_text(text, encoding="utf-8")
                downloaded += 1
                source_counter += 1
            else:
                failed += 1

            time.sleep(_RATE_LIMIT)

        # Coverage
        total_expected = min(
            ANNUAL_TARGET + HALFYEAR_TARGET,
            len(annual) + len(halfyear),
        )
        coverage_pct = (
            (downloaded / total_expected * 100.0)
            if total_expected > 0
            else 0.0
        )

        return AcquisitionResult(
            ticker=ticker,
            source="asx",
            filings_downloaded=downloaded,
            filings_failed=failed,
            filings_coverage_pct=round(min(coverage_pct, 100.0), 1),
            coverage={
                "annual": {
                    "found": len(
                        [ft for ft, _, _ in financial_filings if ft == "annual"]
                    ),
                    "target": ANNUAL_TARGET,
                    "downloaded": len(annual),
                },
                "halfyear": {
                    "found": len(
                        [ft for ft, _, _ in financial_filings if ft == "halfyear"]
                    ),
                    "target": HALFYEAR_TARGET,
                    "downloaded": len(halfyear),
                },
                "results": {
                    "found": len(results_list),
                    "downloaded": len(
                        [
                            h for h, _ in selected
                            if _is_financial_filing(h) == "results"
                        ]
                    ),
                },
                "total_announcements_scanned": len(all_announcements),
            },
            notes=f"ASX acquisition: {downloaded} financial filings downloaded.",
            download_date=dt.date.today().isoformat(),
        )
