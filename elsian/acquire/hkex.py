"""HKEX filing acquisition with live official lookup and manual fallback."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from elsian.acquire._http import bounded_get, get_eu_user_agent
from elsian.acquire.base import Fetcher
from elsian.convert.pdf_to_text import extract_pdf_text_from_file
from elsian.models.case import CaseConfig
from elsian.models.filing import Filing
from elsian.models.result import AcquisitionResult

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".htm", ".html", ".txt", ".pdf", ".md"}
_BASE_URL = "https://www1.hkexnews.hk"
_TITLE_SEARCH_URL = f"{_BASE_URL}/search/titlesearch.xhtml?lang=en"
_LOOKUP_ENDPOINTS = (
    f"{_BASE_URL}/search/prefix.do",
    f"{_BASE_URL}/search/partial.do",
)
_HEADERS = {
    "User-Agent": get_eu_user_agent(),
    "Accept": "application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": _TITLE_SEARCH_URL,
}
_TIMEOUT = 60
_RATE_LIMIT = 0.5
_LOOKBACK_YEARS = 8
_ANNUAL_TARGET = 3
_INTERIM_TARGET_FULL = 3
_CURRENT_SECURITIES = "0"
_MARKET = "SEHK"
_START_DATE = "19990401"
_CALLBACK = "callback"
_ANNUAL_TITLE_RE = re.compile(r"^ANNUAL REPORT (20\d{2})$", re.IGNORECASE)
_INTERIM_TITLE_RE = re.compile(r"^INTERIM REPORT (20\d{2})$", re.IGNORECASE)

_HKEX_SESSION: requests.Session | None = None


def _hkex_session() -> requests.Session:
    """Return the module-level HKEX session."""
    global _HKEX_SESSION
    if _HKEX_SESSION is None:
        _HKEX_SESSION = requests.Session()
    return _HKEX_SESSION


def _scan_filings_dir(filings_dir: Path) -> list[Filing]:
    """Return Filing objects for all supported files in *filings_dir*."""
    if not filings_dir.exists():
        return []

    filings: list[Filing] = []
    for f in sorted(filings_dir.iterdir()):
        if f.is_file() and f.suffix in _SUPPORTED_EXTENSIONS:
            filings.append(Filing(
                source_id=f.stem,
                local_path=str(f),
                primary_doc=f.name,
            ))
    return filings


def _logical_source_ids(filings_dir: Path) -> list[str]:
    """Return deduplicated logical source IDs from a filings directory."""
    logical_ids: set[str] = set()
    for f in sorted(filings_dir.iterdir()):
        if not f.is_file() or not f.name.startswith("SRC_"):
            continue
        if f.name.endswith(".clean.md"):
            logical_ids.add(f.name[:-9])
        else:
            logical_ids.add(f.stem)
    return sorted(logical_ids)


def _normalize_lookup_name(raw: str) -> str:
    """Normalize a stock code / company name candidate for HKEX lookup."""
    text = (raw or "").strip()
    digits = re.sub(r"\D", "", text)
    if digits:
        return digits.lstrip("0") or "0"
    return re.sub(r"\s+", " ", text).upper()


def _ticker_code(ticker: str) -> str:
    """Return the ticker zero-padded to HKEX's five-digit stock code."""
    digits = re.sub(r"\D", "", ticker or "")
    if not digits:
        return (ticker or "").strip().upper()
    return digits.zfill(5)


def _extract_jsonp_payload(text: str) -> dict[str, Any]:
    """Parse a JSONP payload of the form ``callback({...});``."""
    body = (text or "").strip()
    if not body:
        return {}
    start = body.find("(")
    end = body.rfind(")")
    if start == -1 or end == -1 or end <= start + 1:
        return {}
    try:
        payload = json.loads(body[start + 1:end])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class HkexIssuer:
    """Resolved HKEX issuer identity."""

    stock_id: int
    code: str
    name: str


@dataclass(frozen=True)
class HkexDocument:
    """Single HKEX document candidate returned by title search."""

    title: str
    href: str
    headline: str
    release_time: str
    year: int
    kind: str  # "AR" or "IR"

    @property
    def url(self) -> str:
        return urljoin(f"{_BASE_URL}/", self.href.lstrip("/"))


def _classify_document_title(title: str) -> tuple[str, int] | None:
    """Return ``(kind, year)`` for supported financial-document titles."""
    clean_title = " ".join((title or "").split())
    annual_match = _ANNUAL_TITLE_RE.match(clean_title)
    if annual_match:
        return "AR", int(annual_match.group(1))
    interim_match = _INTERIM_TITLE_RE.match(clean_title)
    if interim_match:
        return "IR", int(interim_match.group(1))
    return None


def _parse_search_documents(html: str) -> tuple[int, list[HkexDocument]]:
    """Extract total record count and supported document rows from HKEX HTML."""
    soup = BeautifulSoup(html, "lxml")

    total_records = 0
    total_node = soup.select_one("div.total-records")
    if total_node:
        match = re.search(r"Total records found:\s*(\d+)", total_node.get_text(" ", strip=True))
        if match:
            total_records = int(match.group(1))

    documents: list[HkexDocument] = []
    for row in soup.select("div.title-search-result tbody tr"):
        link = row.select_one("div.doc-link a[href]")
        if link is None:
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        classification = _classify_document_title(title)
        if classification is None:
            continue
        kind, year = classification
        headline_node = row.select_one("div.headline")
        release_node = row.select_one("td.release-time")
        documents.append(HkexDocument(
            title=title,
            href=(link.get("href") or "").strip(),
            headline=" ".join(headline_node.get_text(" ", strip=True).split()) if headline_node else "",
            release_time=" ".join(release_node.get_text(" ", strip=True).split()) if release_node else "",
            year=year,
            kind=kind,
        ))
    return total_records, documents


def _lookup_stock(case: CaseConfig) -> tuple[HkexIssuer | None, int]:
    """Resolve an HKEX issuer through the official lookup endpoints."""
    retries_total = 0
    candidates = [_normalize_lookup_name(case.ticker)]
    if case.company_name:
        candidates.append(_normalize_lookup_name(case.company_name))
    seen_queries: set[str] = set()
    target_code = _ticker_code(case.ticker)

    for endpoint in _LOOKUP_ENDPOINTS:
        for query in candidates:
            if not query or query in seen_queries:
                continue
            seen_queries.add(query)
            resp, retries_used = bounded_get(
                endpoint,
                session=_hkex_session(),
                headers=_HEADERS,
                params={
                    "callback": _CALLBACK,
                    "lang": "EN",
                    "type": "A",
                    "name": query,
                    "market": _MARKET,
                },
                timeout=_TIMEOUT,
                max_retries=3,
                base_backoff=2.0,
            )
            retries_total += retries_used
            payload = _extract_jsonp_payload(resp.text)
            stock_info = payload.get("stockInfo") or []
            if not isinstance(stock_info, list):
                continue

            exact = next((
                item for item in stock_info
                if _ticker_code(str(item.get("code", ""))) == target_code
            ), None)
            if exact is None and stock_info:
                exact = stock_info[0]
            if exact is None:
                continue

            try:
                return HkexIssuer(
                    stock_id=int(exact["stockId"]),
                    code=str(exact.get("code", "")).zfill(5),
                    name=str(exact.get("name", "")).strip(),
                ), retries_total
            except (KeyError, TypeError, ValueError):
                continue

    return None, retries_total


def _post_title_search(stock_id: int, title: str, date_to: str) -> str:
    """Run one HKEX Title Search POST and return the HTML response."""
    resp = _hkex_session().post(
        _TITLE_SEARCH_URL,
        headers=_HEADERS,
        data={
            "lang": "EN",
            "category": _CURRENT_SECURITIES,
            "market": _MARKET,
            "searchType": _CURRENT_SECURITIES,
            "documentType": "",
            "t1code": "",
            "t2Gcode": "",
            "t2code": "",
            "stockId": str(stock_id),
            "from": _START_DATE,
            "to": date_to,
            "MB-Daterange": _CURRENT_SECURITIES,
            "title": title,
        },
        timeout=_TIMEOUT,
        allow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def _discover_documents(case: CaseConfig, issuer: HkexIssuer) -> tuple[list[HkexDocument], dict[str, Any]]:
    """Discover annual/interim HKEX reports via exact-title searches."""
    today = dt.date.today()
    date_to = today.strftime("%Y%m%d")
    total_records_html = _post_title_search(issuer.stock_id, "", date_to)
    total_records, _ = _parse_search_documents(total_records_html)

    targets: list[tuple[str, int]] = [("AR", _ANNUAL_TARGET)]
    if (case.period_scope or "").upper() == "FULL":
        targets.append(("IR", _INTERIM_TARGET_FULL))

    selected: list[HkexDocument] = []
    gaps: list[str] = []

    for kind, needed in targets:
        found = 0
        title_prefix = "ANNUAL REPORT" if kind == "AR" else "INTERIM REPORT"
        for year in range(today.year, today.year - _LOOKBACK_YEARS, -1):
            title = f"{title_prefix} {year}"
            html = _post_title_search(issuer.stock_id, title, date_to)
            _, documents = _parse_search_documents(html)
            exact = next((doc for doc in documents if doc.title.upper() == title.upper()), None)
            if exact is None:
                continue
            selected.append(exact)
            found += 1
            time.sleep(_RATE_LIMIT)
            if found >= needed:
                break
        if found < needed:
            gaps.append(f"Missing {kind} target: found {found}/{needed}")

    annual_docs = sorted((doc for doc in selected if doc.kind == "AR"), key=lambda doc: doc.year, reverse=True)
    interim_docs = sorted((doc for doc in selected if doc.kind == "IR"), key=lambda doc: doc.year, reverse=True)
    ordered = [*annual_docs, *interim_docs]

    coverage = {
        "lookup": {
            "stock_id": issuer.stock_id,
            "code": issuer.code,
            "name": issuer.name,
        },
        "search": {
            "total_records_found": total_records,
            "annual_candidates": len(annual_docs),
            "interim_candidates": len(interim_docs),
        },
        "annual": {
            "downloaded": len(annual_docs),
            "titles": [doc.title for doc in annual_docs],
        },
        "interim": {
            "downloaded": len(interim_docs),
            "titles": [doc.title for doc in interim_docs],
        },
    }
    return ordered, {"coverage": coverage, "gaps": gaps}


def _source_id_for(index: int, document: HkexDocument) -> str:
    """Return the stable ``SRC_*`` identifier for one financial document."""
    if document.kind == "AR":
        return f"SRC_{index:03d}_AR_FY{document.year}"
    return f"SRC_{index:03d}_IR_H1{document.year}"


def _download_document(document: HkexDocument, pdf_path: Path) -> int:
    """Download one HKEX PDF and materialize its ``.txt`` companion."""
    resp, retries_used = bounded_get(
        document.url,
        session=_hkex_session(),
        headers=_HEADERS,
        timeout=_TIMEOUT,
        max_retries=3,
        base_backoff=2.0,
    )
    content = resp.content
    if len(content) < 100 or b"%PDF" not in content[:32]:
        raise ValueError(f"HKEX document is not a valid PDF: {document.url}")

    pdf_path.write_bytes(content)
    txt_path = pdf_path.with_suffix(".txt")
    if not txt_path.exists():
        text = extract_pdf_text_from_file(str(pdf_path))
        if text.strip():
            txt_path.write_text(text, encoding="utf-8")
    time.sleep(_RATE_LIMIT)
    return retries_used


def _cached_result(case: CaseConfig, filings_dir: Path) -> AcquisitionResult | None:
    """Build an AcquisitionResult for a non-empty local HKEX filings dir."""
    if not filings_dir.exists():
        return None
    source_ids = _logical_source_ids(filings_dir)
    if not source_ids:
        return None

    annual_ids = [sid for sid in source_ids if "_AR_" in sid]
    interim_ids = [sid for sid in source_ids if "_IR_" in sid]
    return AcquisitionResult(
        ticker=case.ticker,
        source="hkex_manual" if case.source_hint.lower() == "hkex_manual" else "hkex",
        filings_downloaded=len(source_ids),
        filings_coverage_pct=100.0,
        coverage={
            "annual": {"downloaded": len(annual_ids), "from_cache": True, "source_ids": annual_ids},
            "interim": {"downloaded": len(interim_ids), "from_cache": True, "source_ids": interim_ids},
            "total": {"found": len(source_ids), "files": sorted(p.name for p in filings_dir.iterdir() if p.is_file())},
        },
        notes="Using cached filings (directory not empty).",
        source_kind="filing",
        cache_hit=True,
    )


class HkexFetcher(Fetcher):
    """Acquire HKEX annual/interim reports via official title search."""

    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Acquire when needed, then return all supported files on disk."""
        self.acquire(case)
        filings_dir = Path(case.case_dir) / "filings"
        filings = _scan_filings_dir(filings_dir)
        if filings:
            logger.info(
                "HkexFetcher: found %d filings in %s for %s",
                len(filings),
                filings_dir,
                case.ticker,
            )
        return filings

    def acquire(self, case: CaseConfig) -> AcquisitionResult:
        """Acquire HKEX reports or fall back to the cached/manual corpus."""
        filings_dir = Path(case.case_dir) / "filings"
        filings_dir.mkdir(parents=True, exist_ok=True)

        cached = _cached_result(case, filings_dir)
        if cached is not None:
            return cached

        issuer, lookup_retries = _lookup_stock(case)
        if issuer is None:
            return AcquisitionResult(
                ticker=case.ticker,
                source="hkex",
                gaps=[f"HKEX stock lookup failed for {case.ticker}"],
                notes="Official HKEX lookup did not resolve the issuer.",
                source_kind="filing",
                retries_total=lookup_retries,
            )

        try:
            documents, discovery_meta = _discover_documents(case, issuer)
        except Exception as exc:
            logger.warning("HKEX title search failed for %s: %s", case.ticker, exc)
            return AcquisitionResult(
                ticker=case.ticker,
                source="hkex",
                gaps=[f"HKEX title search failed for {case.ticker}"],
                notes=f"Title search failed: {exc}",
                source_kind="filing",
                retries_total=lookup_retries,
            )

        retries_total = lookup_retries
        downloaded = 0
        failed = 0
        gaps = list(discovery_meta["gaps"])
        selected_titles: list[str] = []

        for index, document in enumerate(documents, start=1):
            source_id = _source_id_for(index, document)
            pdf_path = filings_dir / f"{source_id}.pdf"
            try:
                retries_total += _download_document(document, pdf_path)
                downloaded += 1
                selected_titles.append(document.title)
            except Exception as exc:
                failed += 1
                gaps.append(f"Download failed for {document.title}: {exc}")

        expected = _ANNUAL_TARGET
        if (case.period_scope or "").upper() == "FULL":
            expected += _INTERIM_TARGET_FULL
        coverage_pct = round((downloaded / expected) * 100.0, 1) if expected else 100.0

        coverage = dict(discovery_meta["coverage"])
        coverage["selected_source_ids"] = [_source_id_for(i, doc) for i, doc in enumerate(documents, start=1)]
        coverage["selected_titles"] = selected_titles

        return AcquisitionResult(
            ticker=case.ticker,
            source="hkex",
            filings_downloaded=downloaded,
            filings_failed=failed,
            filings_coverage_pct=coverage_pct,
            coverage=coverage,
            gaps=gaps,
            notes=f"HKEX live acquire. {downloaded} financial filings downloaded for {issuer.code} {issuer.name}.",
            source_kind="filing",
            retries_total=retries_total,
            cache_hit=False,
        )
