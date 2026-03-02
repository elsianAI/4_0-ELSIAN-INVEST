"""ASX (Australian Securities Exchange) filing fetcher.

Fetches announcements from the ASX public announcement list API,
filters for the target company's financial filings, and downloads PDFs.
Converts PDFs to text using pdfplumber.

API endpoint:
  https://www.asx.com.au/asx/1/announcement/list
  Parameters: page_size, end_date (unix ms), date_from (unix ms)
  Returns JSON with announcement_data[] containing all ASX announcements.

API limitations (verified empirically):
  - No company-level filtering: all params (issuer_code, ticker, etc.) ignored.
  - No pagination: page, page_no, offset, start all ignored.
  - Hard cap: always returns the 2000 most recent items in the date window.
  - No company-specific endpoint: asx.api.markitdigital.com endpoint is
    limited to 5 items with no pagination.

Strategy: use narrow 1-day windows and scan backward from expected reporting
months to find the target company's financial filings within the 2000-item cap.

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
_RATE_LIMIT = 0.15  # Minimal delay between requests (API ignores page_size)
_PAGE_SIZE = 2000
_MAX_SCAN_DAYS = 15  # Max days to scan backward per target month

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


def _scan_day(ticker: str, d: dt.date) -> list[dict[str, Any]]:
    """Query the ASX announcement list for a single day, filter by ticker.

    Returns all announcements for *ticker* released on *d*.
    The API returns up to 2000 items from ALL companies; we filter locally.
    """
    params = {
        "page_size": _PAGE_SIZE,
        "date_from": int(dt.datetime.combine(d, dt.time.min).timestamp() * 1000),
        "end_date": int(dt.datetime.combine(d, dt.time.max).timestamp() * 1000),
    }
    try:
        resp = requests.get(
            _BASE_URL, headers=_HEADERS, params=params, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("announcement_data", [])
    except Exception as exc:
        logger.warning("ASX API request failed for %s: %s", d, exc)
        return []

    ticker_upper = ticker.upper()
    return [i for i in items if i.get("issuer_code", "").upper() == ticker_upper]


def _find_filings_in_month(
    ticker: str,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    """Scan backward from month end until financial filings are found.

    Returns all ticker announcements from the first day that contains at
    least one financial filing.  Gives up after ``_MAX_SCAN_DAYS`` days.
    """
    today = dt.date.today()

    for day in range(28, max(28 - _MAX_SCAN_DAYS, 0), -1):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d > today:
            continue

        items = _scan_day(ticker, d)
        financial = [i for i in items if _is_financial_filing(i.get("header", ""))]

        if financial:
            logger.info(
                "Found %d financial filings on %s (%d total ticker items)",
                len(financial), d, len(items),
            )
            return items  # Return ALL ticker items from that day (includes results)

        time.sleep(_RATE_LIMIT)

    return []


def _reporting_months(fy_end_month: int) -> tuple[list[int], list[int]]:
    """Calculate the expected reporting months for annual and half-year.

    Annual reports are typically published 2-3 months after fiscal year end.
    Half-year reports are 2-3 months after mid-year.
    Returns: (annual_months, halfyear_months) as lists of calendar months.
    """
    ann = [(fy_end_month + offset) % 12 + 1 for offset in [1, 2]]
    hy = [(fy_end_month + offset) % 12 + 1 for offset in [7, 8]]
    return ann, hy


def _search_all_windows(
    ticker: str,
    years_back: int = 3,
    fy_end_month: int = 12,
    halfyear_target: int = HALFYEAR_TARGET,
) -> list[dict[str, Any]]:
    """Search targeted 1-day windows around expected reporting dates.

    For each year going back, scans the months where annual and half-year
    reports are expected.  For each target month, scans backward from the
    28th until financial filings are found (max ``_MAX_SCAN_DAYS`` days).

    Early stops once enough annual + half-year filings are collected.
    Set *halfyear_target* to 0 to skip half-year scans entirely.
    """
    all_announcements: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    today = dt.date.today()

    ann_months, hy_months = _reporting_months(fy_end_month)

    annual_years_found = 0
    halfyear_years_found = 0

    for year_offset in range(years_back + 1):
        # ── Annual reporting season ────────────────────────────────
        if annual_years_found < ANNUAL_TARGET:
            for m in ann_months:
                scan_year = today.year - year_offset
                try:
                    if dt.date(scan_year, m, 1) > today:
                        continue
                except ValueError:
                    continue

                items = _find_filings_in_month(ticker, scan_year, m)
                if items:
                    new = 0
                    for item in items:
                        ann_id = item.get("id", "")
                        if ann_id and ann_id not in seen_ids:
                            seen_ids.add(ann_id)
                            all_announcements.append(item)
                            new += 1
                    if new:
                        annual_years_found += 1
                        logger.info(
                            "Annual batch %d: %d new items from %d/%d",
                            annual_years_found, new, scan_year, m,
                        )
                    break  # Found annual filings for this year; skip next month

        # ── Half-year reporting season ─────────────────────────────
        if halfyear_target > 0 and halfyear_years_found < halfyear_target:
            for m in hy_months:
                scan_year = today.year - year_offset
                try:
                    if dt.date(scan_year, m, 1) > today:
                        continue
                except ValueError:
                    continue

                items = _find_filings_in_month(ticker, scan_year, m)
                if items:
                    new = 0
                    for item in items:
                        ann_id = item.get("id", "")
                        if ann_id and ann_id not in seen_ids:
                            seen_ids.add(ann_id)
                            all_announcements.append(item)
                            new += 1
                    if new:
                        halfyear_years_found += 1
                        logger.info(
                            "Half-year batch %d: %d new items from %d/%d",
                            halfyear_years_found, new, scan_year, m,
                        )
                    break

        # Early stop: all targets met
        if (annual_years_found >= ANNUAL_TARGET
                and halfyear_years_found >= halfyear_target):
            logger.info(
                "Early stop: %d annual + %d half-year batches collected",
                annual_years_found, halfyear_years_found,
            )
            break

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
        hy_target = HALFYEAR_TARGET if case.period_scope == "FULL" else 0
        all_announcements = _search_all_windows(
            ticker,
            years_back=3,
            fy_end_month=case.fiscal_year_end_month,
            halfyear_target=hy_target,
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
        ][:hy_target]
        results_list = [
            (h, a) for ft, h, a in financial_filings if ft == "results"
        ]

        selected: list[tuple[str, dict[str, Any]]] = []
        selected.extend(annual)
        selected.extend(halfyear)

        # Add results releases (they often have summary tables)
        for h, a in results_list:
            if len(selected) < (ANNUAL_TARGET + hy_target + 3):
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
