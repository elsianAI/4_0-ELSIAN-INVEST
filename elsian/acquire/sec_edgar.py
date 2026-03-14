"""SEC EDGAR filing fetcher.

Ported from 3_0-ELSIAN-INVEST/deterministic/src/acquire/sec_edgar.py.
Downloads annual (10-K/20-F/40-F), quarterly (10-Q/6-K), and earnings
(8-K with Exhibit 99) filings from SEC EDGAR.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from elsian.acquire._http import get_user_agent, load_json_ttl
from elsian.acquire.base import Fetcher
from elsian.convert.html_to_markdown import convert as html_to_markdown
from elsian.convert.pdf_to_text import extract_pdf_text
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing
from elsian.models.result import AcquisitionResult

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Centralised UA: configurable via ELSIAN_USER_AGENT env var (see _http.py).
USER_AGENT = get_user_agent()
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
# TTL for the stable SEC company_tickers.json mapping (24 h by default).
_TICKERS_TTL_SECONDS = 86_400
TIMEOUT = 40
RATE_LIMIT_SECONDS = 0.12

ANNUAL_FORMS = {"10-K", "20-F", "40-F"}
PERIODIC_FORMS = {"10-Q", "6-K"}

ANNUAL_TARGET = 6
QUARTERLY_TARGET = 12
EARNINGS_TARGET = 10


# ── HTTP Client ──────────────────────────────────────────────────────

class SecClient:
    """Rate-limited HTTP client for SEC EDGAR."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._last_req = 0.0
        self._retries: int = 0  # cumulative retry counter (BL-066)

    @property
    def retries(self) -> int:
        """Total HTTP retries accumulated since this client was created."""
        return self._retries

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_req
        if elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
        self._last_req = time.time()

    def get(
        self,
        url: str,
        *,
        binary: bool = False,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        max_retries = 3
        eff_timeout = timeout or TIMEOUT
        for attempt in range(1, max_retries + 1):
            self._throttle()
            try:
                resp = self._session.get(
                    url,
                    headers=HEADERS,
                    params=params,
                    timeout=eff_timeout,
                    allow_redirects=True,
                )
                resp.raise_for_status()
                break  # success
            except (
                requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", 0)
                retryable = status in (429, 500, 502, 503, 504) or isinstance(
                    exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
                )
                if retryable and attempt < max_retries:
                    wait = 5 * attempt  # 5s, 10s
                    logger.debug("Retry %d/%d for %s (status=%s): waiting %ds",
                                 attempt, max_retries, url, status, wait)
                    time.sleep(wait)
                    eff_timeout = (timeout or TIMEOUT) + 20  # more generous on retry
                    self._retries += 1
                    continue
                raise
        if not binary:
            resp.encoding = resp.encoding or "utf-8"
        return resp

    def get_json(self, url: str) -> dict[str, Any]:
        return self.get(url).json()


# ── Helpers ──────────────────────────────────────────────────────────

def _quarter_for_month(month: int) -> str:
    if month <= 3:
        return "Q1"
    if month <= 6:
        return "Q2"
    if month <= 9:
        return "Q3"
    return "Q4"


def _period_from_doc_or_date(
    primary_doc: str, filing_date: str, form: str
) -> str:
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", primary_doc)
    if match:
        y = int(match.group(1))
        m = int(match.group(2))
    else:
        d = dt.date.fromisoformat(filing_date)
        y = d.year
        m = d.month
    if form in ANNUAL_FORMS:
        return f"FY{y}"
    if form in PERIODIC_FORMS:
        return f"{_quarter_for_month(m)}-{y}"
    return filing_date


def _build_doc_url(cik_int: int, accession_nodash: str, document: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"


def _build_index_json_url(cik_int: int, accession_nodash: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"


def _strip_html_to_text(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


# ── CIK Resolution ──────────────────────────────────────────────────

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def resolve_cik(
    client: SecClient, ticker: str
) -> tuple[Optional[tuple[int, str]], bool]:
    """Resolve ticker -> ((cik_int, cik10), cache_hit). Returns (None, <bool>) if not found.

    Uses a TTL file-cache (default 24 h) for the stable company_tickers.json
    mapping to avoid a network round-trip on every acquire run.
    """
    ticker_map, cache_hit = load_json_ttl(
        _TICKERS_URL,
        session=client._session,
        headers=HEADERS,
        ttl_seconds=_TICKERS_TTL_SECONDS,
    )
    for val in ticker_map.values():
        if str(val.get("ticker", "")).upper() == ticker.upper():
            cik_int = int(val["cik_str"])
            return (cik_int, str(cik_int).zfill(10)), cache_hit
    return None, cache_hit


# ── Filing record (internal exchange type) ───────────────────────────

class _FilingRecord:
    """Internal record for a filing from EDGAR submissions index."""

    __slots__ = ("form", "filing_date", "accession", "primary_doc")

    def __init__(self, form: str, filing_date: str, accession: str, primary_doc: str) -> None:
        self.form = form
        self.filing_date = filing_date
        self.accession = accession
        self.primary_doc = primary_doc

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")


# ── Filing Collection ────────────────────────────────────────────────

def _collect_all_filings(
    client: SecClient, cik10: str
) -> tuple[dict[str, Any], list[_FilingRecord]]:
    """Fetch all filings for a CIK from EDGAR submissions API."""
    sub = client.get_json(f"https://data.sec.gov/submissions/CIK{cik10}.json")
    recent = sub.get("filings", {}).get("recent", {})
    all_forms: list[str] = list(recent.get("form", []))
    all_dates: list[str] = list(recent.get("filingDate", []))
    all_acc: list[str] = list(recent.get("accessionNumber", []))
    all_docs: list[str] = list(recent.get("primaryDocument", []))

    for extra in sub.get("filings", {}).get("files", []):
        name = extra.get("name")
        if not name:
            continue
        payload = client.get_json(f"https://data.sec.gov/submissions/{name}")
        all_forms.extend(payload.get("form", []))
        all_dates.extend(payload.get("filingDate", []))
        all_acc.extend(payload.get("accessionNumber", []))
        all_docs.extend(payload.get("primaryDocument", []))

    records: list[_FilingRecord] = []
    for form, date_s, acc, pdoc in zip(
        all_forms, all_dates, all_acc, all_docs
    ):
        if not (form and date_s and acc and pdoc):
            continue
        records.append(_FilingRecord(
            form=form.strip(),
            filing_date=date_s,
            accession=acc,
            primary_doc=pdoc,
        ))

    seen: set[tuple[str, str]] = set()
    deduped: list[_FilingRecord] = []
    for r in records:
        k = (r.form, r.accession)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    return sub, deduped


def _find_exhibit_99(
    client: SecClient, cik_int: int, rec: _FilingRecord
) -> Optional[str]:
    """Find Exhibit 99.1 (or variant) in a filing's index.

    Works for both 8-K earnings releases and 6-K interim reports from
    foreign private issuers, who attach financial statements as Exhibit 99.1.
    Returns the exhibit filename, or None if no matching exhibit is found.
    """
    try:
        idx = client.get_json(_build_index_json_url(cik_int, rec.accession_nodash))
    except Exception:
        return None
    items = idx.get("directory", {}).get("item", [])
    for entry in items:
        name = str(entry.get("name", ""))
        doc_type = str(entry.get("type", ""))
        low = name.lower()
        if "index" in low or "header" in low:
            continue
        if not low.endswith((".htm", ".html", ".txt", ".xml", ".pdf")):
            continue
        # Match by EDGAR document type tag OR by filename pattern
        if doc_type in ("EX-99.1", "EX-99.2", "EX-99") or re.search(
            r"(exhibit[-_ ]?99|ex[-_ ]?99|99[-_ ]?1)", low
        ):
            return name
    return None


# ── Download Logic ───────────────────────────────────────────────────

def _download_and_save(
    client: SecClient,
    url: str,
    output_dir: Path,
    prefix: str,
    form_label: str,
    period: str,
) -> tuple[bool, str]:
    """Download a filing, save as .htm + .txt (+ .clean.md if HTML).

    Returns (success, error_message).
    """
    try:
        resp = client.get(url, binary=True)
    except Exception as exc:
        return False, str(exc)

    content = resp.content
    ctype = resp.headers.get("Content-Type", "").lower()
    is_pdf = "application/pdf" in ctype or url.lower().endswith(".pdf")

    base_name = f"{prefix}_{form_label}_{period}"

    if is_pdf:
        pdf_path = output_dir / f"{base_name}.pdf"
        pdf_path.write_bytes(content)
        text = extract_pdf_text(content)
        txt_path = output_dir / f"{base_name}.txt"
        txt_path.write_text(text, encoding="utf-8")
    else:
        try:
            decoded = content.decode(
                resp.encoding or "utf-8", errors="replace"
            )
        except Exception:
            decoded = content.decode("utf-8", errors="replace")

        htm_path = output_dir / f"{base_name}.htm"
        htm_path.write_text(decoded, encoding="utf-8")

        text = _strip_html_to_text(decoded)
        txt_path = output_dir / f"{base_name}.txt"
        txt_path.write_text(text, encoding="utf-8")

        clean_md = html_to_markdown(htm_path)
        if clean_md:
            md_path = output_dir / f"{base_name}.clean.md"
            md_path.write_text(clean_md, encoding="utf-8")

    return True, ""


# ── SecEdgarFetcher ──────────────────────────────────────────────────

class SecEdgarFetcher(Fetcher):
    """Fetches filings from SEC EDGAR for US-listed companies."""

    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Download filings and return Filing objects."""
        result = self.acquire(case)
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
        """Download SEC EDGAR filings for a case.

        If filings already exist in the case directory, skips download (cache).
        Returns AcquisitionResult with manifest data.
        """
        ticker = case.ticker
        out_path = Path(case.case_dir) / "filings"
        out_path.mkdir(parents=True, exist_ok=True)

        # Cache: if filings already exist, skip
        existing = [f for f in out_path.glob("SRC_*") if f.is_file()]
        if existing:
            stems = {f.stem for f in existing if f.suffix in (".htm", ".txt")}
            logical_filing_count = len(stems)
            if logical_filing_count == 0:
                stems = {f.stem for f in existing}
                logical_filing_count = len(stems)
            # BL-089: preserve cik from case config; if null, recover from existing manifest
            cached_cik: str | None = case.cik
            if cached_cik is None:
                _manifest_path = Path(case.case_dir) / "filings_manifest.json"
                if _manifest_path.exists():
                    try:
                        _prev = json.loads(_manifest_path.read_text(encoding="utf-8"))
                        cached_cik = _prev.get("cik") or None
                    except Exception:
                        pass
            _annual_labels = {frm.replace("/", "-") for frm in ANNUAL_FORMS}
            _quarterly_labels = {frm.replace("/", "-") for frm in PERIODIC_FORMS}
            cached_coverage = {
                "annual": {
                    "downloaded": len({s for s in stems if any(f"_{lbl}_" in s for lbl in _annual_labels)}),
                    "from_cache": True,
                },
                "quarterly": {
                    "downloaded": len({s for s in stems if any(f"_{lbl}_" in s for lbl in _quarterly_labels)}),
                    "from_cache": True,
                },
                "earnings": {
                    # Count both plain 8-K and 8-K/A (saved as 8-K-A) for coherence
                    # with the normal path, which selects both form variants.
                    "downloaded": len({s for s in stems if "_8-K_" in s or "_8-K-A_" in s}),
                    "from_cache": True,
                },
            }
            return AcquisitionResult(
                ticker=ticker,
                source="sec_edgar",
                cik=cached_cik,
                filings_downloaded=logical_filing_count,
                filings_coverage_pct=100.0,
                coverage=cached_coverage,
                notes="Using cached filings (directory not empty).",
                source_kind="filing",
                cache_hit=True,
            )

        client = SecClient()
        cik_cache_hit = False

        # Resolve CIK — use pre-configured cik from case.json if available
        if case.cik:
            cik_int = int(case.cik)
            cik10 = str(cik_int).zfill(10)
            logger.info("Using pre-configured CIK %s for %s", cik10, ticker)
            cik_result: Optional[tuple[int, str]] = (cik_int, cik10)
        else:
            cik_result, cik_cache_hit = resolve_cik(client, ticker)
        if cik_result is None:
            return AcquisitionResult(
                ticker=ticker,
                source="sec_edgar",
                notes=f"Ticker {ticker} not found in SEC EDGAR.",
                gaps=[f"CIK not found for {ticker}"],
                source_kind="filing",
            )

        cik_int, cik10 = cik_result

        # Collect all filings
        _sub, records = _collect_all_filings(client, cik10)

        # Select filings by type
        annual = [r for r in records if r.form in ANNUAL_FORMS][:ANNUAL_TARGET]
        quarterly = [r for r in records if r.form in PERIODIC_FORMS][:QUARTERLY_TARGET]

        # Earnings 8-K: look for Exhibit 99
        earnings_8k: list[tuple[_FilingRecord, Optional[str]]] = []
        for rec in [r for r in records if r.form in {"8-K", "8-K/A"}][:160]:
            exhibit = _find_exhibit_99(client, cik_int, rec)
            if exhibit:
                earnings_8k.append((rec, exhibit))
                if len(earnings_8k) >= EARNINGS_TARGET:
                    break
            else:
                try:
                    doc_url = _build_doc_url(cik_int, rec.accession_nodash, rec.primary_doc)
                    resp = client.get(doc_url)
                    low = resp.text.lower()
                    if (
                        "item 2.02" in low
                        or "results of operations and financial condition" in low
                    ):
                        earnings_8k.append((rec, None))
                        if len(earnings_8k) >= EARNINGS_TARGET:
                            break
                except Exception:
                    pass

        avail_annual = min(
            len([r for r in records if r.form in ANNUAL_FORMS]), ANNUAL_TARGET
        )
        avail_quarterly = min(
            len([r for r in records if r.form in PERIODIC_FORMS]), QUARTERLY_TARGET
        )
        avail_earnings = min(len(earnings_8k), EARNINGS_TARGET)

        # Download
        source_counter = 1
        downloaded = 0
        failed = 0

        def _download_record(
            rec: _FilingRecord,
            form_label: str,
            period: str,
            doc_override: Optional[str] = None,
        ) -> None:
            nonlocal source_counter, downloaded, failed
            prefix = f"SRC_{source_counter:03d}"
            source_counter += 1
            doc = doc_override or rec.primary_doc
            doc_url = _build_doc_url(cik_int, rec.accession_nodash, doc)
            ok, err = _download_and_save(
                client, doc_url, out_path, prefix, form_label, period
            )
            if ok:
                downloaded += 1
            else:
                failed += 1
                logger.warning("Download failed: %s — %s", doc_url, err)

        for rec in annual:
            period = _period_from_doc_or_date(rec.primary_doc, rec.filing_date, rec.form)
            _download_record(rec, rec.form.replace("/", "-"), period)

        for rec in quarterly:
            period = _period_from_doc_or_date(rec.primary_doc, rec.filing_date, rec.form)
            exhibit: Optional[str] = None
            if rec.form == "6-K":
                # Foreign private issuers attach financial statements as Exhibit 99.1
                exhibit = _find_exhibit_99(client, cik_int, rec)
            _download_record(rec, rec.form.replace("/", "-"), period, exhibit)

        for rec, exhibit in earnings_8k:
            period = rec.filing_date
            _download_record(rec, "8-K", period, exhibit)

        # Coverage
        total_expected = avail_annual + avail_quarterly + avail_earnings
        coverage_pct = (
            (downloaded / total_expected * 100.0) if total_expected > 0 else 0.0
        )

        annual_years: list[int] = []
        for r in annual:
            m = re.search(r"20\d{2}", r.filing_date)
            if m:
                annual_years.append(int(m.group(0)))

        return AcquisitionResult(
            ticker=ticker,
            source="sec_edgar",
            cik=cik10,
            filings_downloaded=downloaded,
            filings_failed=failed,
            filings_coverage_pct=round(coverage_pct, 1),
            coverage={
                "annual": {
                    "available_in_index": len([r for r in records if r.form in ANNUAL_FORMS]),
                    "target": ANNUAL_TARGET,
                    "expected": avail_annual,
                    "downloaded": len(annual),
                    "years": sorted(set(annual_years)),
                },
                "quarterly": {
                    "available_in_index": len([r for r in records if r.form in PERIODIC_FORMS]),
                    "target": QUARTERLY_TARGET,
                    "expected": avail_quarterly,
                    "downloaded": len(quarterly),
                },
                "earnings": {
                    "available_in_index": avail_earnings,
                    "target": EARNINGS_TARGET,
                    "expected": avail_earnings,
                    "downloaded": len(earnings_8k),
                },
            },
            notes="All available filings processed.",
            download_date=dt.date.today().isoformat(),
            source_kind="filing",
            cache_hit=cik_cache_hit,
            retries_total=client.retries,
        )
