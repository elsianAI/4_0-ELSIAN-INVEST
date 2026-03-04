"""Transcript & Presentation finder — earnings call transcripts and IR presentations.

Ported from 3_0-ELSIAN-INVEST/scripts/runners/transcript_finder_v2_runner.py (1435 lines).
Adapted to 4.0 architecture:
  - Reuses ir_crawler.py: build_ir_pages, extract_filing_candidates, resolve_ir_base_url
  - Reuses dedup.py: content_hash
  - Reuses markets.py: is_non_us, NON_US_EXCHANGES

Provides:
  - TranscriptFinder.find() — orchestrator for Fintool transcripts + IR presentations
  - TranscriptSource / TranscriptResult — data model
  - Issuer verification with Jaccard + SequenceMatcher scoring
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from elsian.acquire.dedup import content_hash
from elsian.acquire.ir_crawler import (
    build_ir_pages,
    extract_filing_candidates,
    normalize_web_ir,
    resolve_ir_base_url,
)
from elsian.markets import NON_US_EXCHANGES, is_non_us
from elsian.models.case import CaseConfig

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

USER_AGENT = "ELSIAN-INVEST-Bot/1.0 (research; bot@elsian-invest.local)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
ALT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": HEADERS["Accept"],
}
TIMEOUT = 45

LEGAL_ENTITY_SUFFIXES: frozenset[str] = frozenset({
    "inc", "incorporated", "corp", "corporation", "co", "company",
    "companies", "limited", "ltd", "plc", "llc", "sa", "spa", "ag",
    "nv", "fpo", "holdings", "holding", "group",
})

TITLE_ISSUER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(.+?)\s*-\s*Earnings Call", re.IGNORECASE),
    re.compile(r"^(.+?)\s*\(([A-Z]{1,6})\)\s+Q[1-4]", re.IGNORECASE),
    re.compile(r"^(.+?)\s+Q[1-4]\s+\d{4}\s+Earnings", re.IGNORECASE),
)

FIN_HINTS: tuple[str, ...] = (
    "revenue", "income", "profit", "eps", "ebit", "ebitda",
    "cash flow", "balance sheet", "assets", "liabilities",
    "equity", "dividend", "capex",
)

ANNUAL_DOC_HINTS: tuple[str, ...] = (
    "urd", "universal registration document",
    "document d'enregistrement universel",
    "annual report", "integrated report",
)

NAV_HINTS: tuple[str, ...] = (
    "home", "search", "menu", "investor relations",
    "corporate governance", "cookie", "privacy",
    "latest news", "announcements", "publications", "financials",
)

IR_DOC_KEYWORDS: tuple[str, ...] = (
    "presentation", "investor", "earnings", "results", "deck",
    "slides", "annual report", "interim report", "financial report",
    "report and accounts", "registration document", "trading update",
    "full year results", "half year results",
)

IR_HTML_HINTS: tuple[str, ...] = (
    "results", "report", "announcement", "rns", "earnings",
    "financial", "trading update", "press release", "regulatory story",
)

IR_HTML_STRONG_DOC_HINTS: tuple[str, ...] = (
    "annual results", "full year", "full-year",
    "registration document", "universal registration document",
    "integrated report", "interim results", "financial results",
)


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class TranscriptSource:
    """A single found transcript or IR presentation."""

    source_id: str
    tipo: str  # EARNINGS_TRANSCRIPT | INVESTOR_PRESENTATION | ANNUAL_REPORT
    period: str | None
    url: str
    local_path: str | None = None
    issuer_match: bool = False
    issuer_match_score: float = 0.0
    content_hash: str | None = None
    title: str = ""
    date: str | None = None
    text_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "source_id": self.source_id,
            "tipo": self.tipo,
            "period": self.period,
            "url": self.url,
            "local_path": self.local_path,
            "issuer_match": self.issuer_match,
            "issuer_match_score": round(self.issuer_match_score, 3),
            "content_hash": self.content_hash,
            "title": self.title,
            "date": self.date,
            "text_chars": self.text_chars,
        }


@dataclass
class TranscriptResult:
    """Result of a transcript / presentation discovery run."""

    ticker: str
    sources: list[TranscriptSource] = field(default_factory=list)
    discarded: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "ticker": self.ticker,
            "sources": [s.to_dict() for s in self.sources],
            "discarded": self.discarded,
            "missing": self.missing,
        }


# ── Helpers: text / entity normalization ──────────────────────────────

def _clean_ws(text: str) -> str:
    """Collapse whitespace to single spaces and strip."""
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_entity_name(value: str | None) -> str:
    """Normalize a company name for fuzzy matching.

    Strips legal suffixes (Inc., Corp., Ltd., etc.), brackets, parens,
    and non-alphanumeric characters.

    Args:
        value: Raw entity name string.

    Returns:
        Lowercased, cleaned string with legal suffixes removed.
    """
    text = _clean_ws(str(value or "")).lower()
    if not text:
        return ""
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^\)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t not in LEGAL_ENTITY_SUFFIXES]
    return " ".join(tokens).strip()


def _extract_company_from_title(title: str | None) -> list[str]:
    """Extract potential company names from a transcript title.

    Uses regex patterns to extract issuer names from common title formats
    like "Company Inc. - Earnings Call Transcript" or "Company (TICK) Q4 2024".

    Args:
        title: Raw title string.

    Returns:
        List of deduplicated candidate company names.
    """
    t = _clean_ws(str(title or ""))
    if not t:
        return []
    out: list[str] = []
    for pattern in TITLE_ISSUER_PATTERNS:
        m = pattern.search(t)
        if m:
            cand = _clean_ws(m.group(1))
            if cand:
                out.append(cand)
    if " - " in t:
        first = _clean_ws(t.split(" - ", 1)[0])
        if first:
            out.append(first)
    deduped: list[str] = []
    seen: set[str] = set()
    for cand in out:
        norm = _normalize_entity_name(cand)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        deduped.append(cand)
    return deduped


# ── Issuer verification (Jaccard + SequenceMatcher) ──────────────────

def _is_weak_target_alias(alias_norm: str, ticker_norm: str) -> bool:
    """Check if a normalized alias is too weak for reliable matching."""
    if not alias_norm:
        return True
    if alias_norm == ticker_norm:
        return True
    if len(alias_norm) < 5:
        return True
    tokens = alias_norm.split()
    if len(tokens) == 1 and len(tokens[0]) <= 4:
        return True
    return False


def _build_target_aliases(
    ticker: str,
    empresa: str = "",
) -> tuple[list[str], str]:
    """Build list of strong target aliases for issuer matching.

    Args:
        ticker: Company ticker symbol.
        empresa: Optional company name hint.

    Returns:
        Tuple of (strong_aliases, quality) where quality is "STRONG" or "WEAK".
    """
    ticker_norm = _normalize_entity_name(ticker)
    strong_aliases: list[str] = []
    seen: set[str] = set()
    for raw in [empresa]:
        norm = _normalize_entity_name(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        if _is_weak_target_alias(norm, ticker_norm):
            continue
        strong_aliases.append(norm)
    quality = "STRONG" if strong_aliases else "WEAK"
    return strong_aliases, quality


def _score_issuer_pair(target_norm: str, candidate_norm: str) -> float:
    """Score match between a target alias and an issuer candidate.

    Uses max(Jaccard, SequenceMatcher) with substring bonus.

    Args:
        target_norm: Normalized target alias.
        candidate_norm: Normalized candidate name.

    Returns:
        Score in [0.0, 1.0].
    """
    target_tokens = set(target_norm.split())
    candidate_tokens = set(candidate_norm.split())
    union = target_tokens | candidate_tokens
    jaccard = (len(target_tokens & candidate_tokens) / len(union)) if union else 0.0
    seq_ratio = difflib.SequenceMatcher(None, target_norm, candidate_norm).ratio()
    score = max(jaccard, seq_ratio)

    if (
        len(target_tokens) >= 2
        and len(candidate_tokens) >= 2
        and min(len(target_norm), len(candidate_norm)) >= 6
        and (target_norm in candidate_norm or candidate_norm in target_norm)
    ):
        score = max(score, 0.90)
    return score


def _issuer_match_decision(
    target_aliases: list[str],
    issuer_candidates: list[str],
    ticker: str,
) -> tuple[bool, float]:
    """Decide whether transcript issuer matches the target company.

    Args:
        target_aliases: Normalized alias strings for the target company.
        issuer_candidates: Raw issuer names extracted from transcript metadata.
        ticker: Company ticker symbol.

    Returns:
        Tuple of (is_match, best_score).
    """
    if not target_aliases:
        return False, 0.0
    if not issuer_candidates:
        return False, 0.0

    best_score = -1.0
    best_target = ""
    for target_norm in target_aliases:
        for candidate in issuer_candidates:
            candidate_norm = _normalize_entity_name(candidate)
            if not candidate_norm:
                continue
            score = _score_issuer_pair(target_norm, candidate_norm)
            if score > best_score:
                best_score = score
                best_target = target_norm

    if best_score < 0:
        return False, 0.0

    target_token_count = len(best_target.split())
    threshold = 0.45 if (target_token_count >= 2 or len(best_target) >= 6) else 0.75
    is_match = best_score >= threshold
    return is_match, best_score


# ── Period normalization ──────────────────────────────────────────────

def normalize_period(period_raw: str | None) -> str:
    """Canonicalize a period slug to Q{n}-{YYYY} or FY{YYYY} format.

    Handles formats: Q42024, Q4-2024, 4Q2024, FY2024, Q4-FY2024, Q1-24, etc.

    Args:
        period_raw: Raw period string.

    Returns:
        Normalized period slug, or "UNKNOWN" if not parseable.
    """
    value = _clean_ws((period_raw or "").replace("_", "-")).upper().replace(" ", "-")
    m_q = re.match(r"Q([1-4])[-]?((?:19|20)\d{2})$", value)
    if m_q:
        return f"Q{m_q.group(1)}-{m_q.group(2)}"
    m_q_short = re.match(r"Q([1-4])[-]?(\d{2})$", value)
    if m_q_short:
        return f"Q{m_q_short.group(1)}-20{m_q_short.group(2)}"
    m_q2 = re.match(r"Q([1-4])[-]?FY[-]?((?:19|20)\d{2})$", value)
    if m_q2:
        return f"Q{m_q2.group(1)}-{m_q2.group(2)}"
    m_fy = re.match(r"FY[-]?((?:19|20)\d{2})$", value)
    if m_fy:
        return f"FY{m_fy.group(1)}"
    m_q3 = re.match(r"([1-4])Q[-]?((?:19|20)\d{2})$", value)
    if m_q3:
        return f"Q{m_q3.group(1)}-{m_q3.group(2)}"
    m_q3_short = re.match(r"([1-4])Q[-]?(\d{2})$", value)
    if m_q3_short:
        return f"Q{m_q3_short.group(1)}-20{m_q3_short.group(2)}"
    m_slug = re.match(r"Q([1-4])-((?:19|20)\d{2})", value)
    if m_slug:
        return f"Q{m_slug.group(1)}-{m_slug.group(2)}"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "UNKNOWN"


# ── Fintool transcript parsing ────────────────────────────────────────

def _parse_next_data(html: str) -> dict[str, Any] | None:
    """Extract __NEXT_DATA__ JSON from a Next.js page.

    Args:
        html: Full HTML page source.

    Returns:
        Parsed JSON dict, or None if not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("script", id="__NEXT_DATA__")
    if not node or not node.text:
        return None
    try:
        return json.loads(node.text)
    except (json.JSONDecodeError, TypeError):
        return None


def _build_transcript_text(page_props: dict[str, Any]) -> str:
    """Build structured plain text from Fintool transcript page_props.

    Assembles: title header, executive summary, and full transcript
    with speaker attribution.

    Args:
        page_props: The pageProps dict from __NEXT_DATA__.

    Returns:
        Formatted transcript text.
    """
    company = page_props.get("companyName") or page_props.get("ticker") or "UNKNOWN"
    display_period = page_props.get("displayPeriod") or page_props.get("period") or "UNKNOWN"
    title = page_props.get("title") or f"{company} Earnings Call Transcript"
    published_at = page_props.get("publishedAt") or "UNKNOWN"

    lines: list[str] = [
        f"{title}",
        f"Company: {company}",
        f"Period: {display_period}",
        f"Published: {published_at}",
        "",
    ]

    executive_summary = page_props.get("executiveSummary") or []
    if isinstance(executive_summary, list) and executive_summary:
        lines.append("EXECUTIVE SUMMARY")
        for item in executive_summary:
            item_text = _clean_ws(str(item))
            if item_text:
                lines.append(f"- {item_text}")
        lines.append("")

    transcript_obj = page_props.get("transcript") or {}
    sections = transcript_obj.get("transcript") if isinstance(transcript_obj, dict) else []
    lines.append("FULL TRANSCRIPT")
    if isinstance(sections, list):
        for block in sections:
            if not isinstance(block, dict):
                continue
            speaker = _clean_ws(str(block.get("name") or "UNKNOWN"))
            session = _clean_ws(str(block.get("session") or "session"))
            lines.append("")
            lines.append(f"[{speaker}] ({session})")
            speech = block.get("speech") or []
            if isinstance(speech, list):
                for chunk in speech:
                    chunk_text = _clean_ws(str(chunk))
                    if chunk_text:
                        lines.append(chunk_text)
            elif speech:
                lines.append(_clean_ws(str(speech)))
    return "\n".join(lines).strip() + "\n"


def _extract_transcript_periods(index_html: str, ticker: str) -> list[str]:
    """Extract available transcript period slugs from Fintool index page.

    Args:
        index_html: HTML of fintool.com transcript index page.
        ticker: Company ticker.

    Returns:
        List of period slugs sorted by recency (newest first).
    """
    pattern = re.compile(
        rf"/app/research/companies/{re.escape(ticker.upper())}/documents/transcripts/([a-z0-9-]+)",
        re.IGNORECASE,
    )
    periods = sorted(set(pattern.findall(index_html)), key=_period_sort_key, reverse=True)
    return periods


def _period_sort_key(slug: str) -> tuple[int, int]:
    """Sort key for period slugs — (year, quarter)."""
    low = slug.lower().strip()
    m = re.match(r"q([1-4])-(\d{4})", low)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m_fy = re.match(r"fy[-]?(\d{4})", low)
    if m_fy:
        return (int(m_fy.group(1)), 4)
    return (0, 0)


# ── Presentation classification ──────────────────────────────────────

def _classify_presentation_source_type(title: str, url: str, row_text: str = "") -> str:
    """Classify a presentation URL as ANNUAL_REPORT or INVESTOR_PRESENTATION.

    Args:
        title: Link/row title text.
        url: Full URL of the resource.
        row_text: Surrounding row text context.

    Returns:
        "ANNUAL_REPORT" or "INVESTOR_PRESENTATION".
    """
    combined = _clean_ws(f"{title} {row_text} {url}".lower())
    normalized = re.sub(r"[-_/]+", " ", combined)
    if any(h in normalized for h in ANNUAL_DOC_HINTS):
        return "ANNUAL_REPORT"
    return "INVESTOR_PRESENTATION"


def _is_navigation_like_source(title: str, text: str, url: str) -> bool:
    """Detect if a URL leads to an index/navigation page rather than a document.

    Args:
        title: Link title.
        text: Surrounding text / page text.
        url: Full URL.

    Returns:
        True if the URL appears to be a navigation/index page.
    """
    low_url = (url or "").lower()
    if low_url.endswith(".pdf"):
        return False
    sample = re.sub(r"\s+", " ", str(text or "")).strip().lower()[:2500]
    title_low = re.sub(r"\s+", " ", str(title or "")).strip().lower()
    nav_hits = sum(1 for k in NAV_HINTS if k in sample or k in title_low or k in low_url)
    index_like_url = any(
        p in low_url
        for p in (
            "/investor-relations", "/announcements", "/news",
            "/publications", "/finance-kit",
        )
    )
    if index_like_url and _is_low_financial_density(sample):
        return True
    return nav_hits >= 4 and _is_low_financial_density(sample)


def _is_low_financial_density(text: str, window: int = 2000) -> bool:
    """Detect text with little financial content.

    Args:
        text: Text sample to analyze.
        window: Number of characters to sample.

    Returns:
        True if text has fewer than 2 financial keyword hits AND
        fewer than 2 number-pattern hits in the sample window.
    """
    sample = re.sub(r"\s+", " ", str(text or "")).strip().lower()[:window]
    if not sample:
        return True
    fin_hits = sum(1 for k in FIN_HINTS if k in sample)
    num_hits = len(re.findall(
        r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?%\b", sample
    ))
    return fin_hits < 2 and num_hits < 2


# ── HTTP helpers ──────────────────────────────────────────────────────

def _request_text(session: requests.Session, url: str) -> str:
    """GET a URL and return text response with retry on 429/5xx.

    Args:
        session: requests.Session to use.
        url: URL to fetch.

    Returns:
        Response text content.

    Raises:
        requests.HTTPError: If request fails after retry.
    """
    import time as _time

    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.encoding or "utf-8"
        return resp.text
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        host = urlparse(url).netloc.lower()
        if status in (429, 500, 502, 503, 504) or isinstance(exc, requests.exceptions.ConnectionError):
            _time.sleep(3)
            resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        if status == 403 and "fintool.com" not in host:
            _time.sleep(1)
            resp = session.get(url, headers=ALT_HEADERS, timeout=TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        raise


def _request_bytes(session: requests.Session, url: str) -> bytes:
    """GET a URL and return raw bytes with retry on 429/5xx.

    Args:
        session: requests.Session to use.
        url: URL to fetch.

    Returns:
        Response bytes content.

    Raises:
        requests.HTTPError: If request fails after retry.
    """
    import time as _time

    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        if status in (429, 500, 502, 503, 504) or isinstance(exc, requests.exceptions.ConnectionError):
            _time.sleep(3)
            resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            resp.raise_for_status()
            return resp.content
        raise


def _strip_html_to_text(raw: str) -> str:
    """Convert HTML to plain text by removing tags."""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)


def _parse_human_date(value: str | None) -> str | None:
    """Parse a human-readable date to ISO format.

    Args:
        value: Date string like "March 15, 2024" or "2024-03-15".

    Returns:
        ISO date string (YYYY-MM-DD) or None.
    """
    import datetime as dt

    if not value:
        return None
    value = _clean_ws(value)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _safe_slug(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")


# ── Presentation extraction from IR pages ─────────────────────────────

def _extract_presentation_rows(
    ir_html: str,
    base_url: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract presentation/report rows from an IR page's HTML.

    Filters for presentation and document keywords, deduplicates by URL
    and filename.

    Args:
        ir_html: HTML content of the IR page.
        base_url: Base URL for resolving relative links.

    Returns:
        Tuple of (accepted_rows, rejected_rows).
        Each accepted_row is a dict with: url, period, date, title, doc_kind.
    """
    soup = BeautifulSoup(ir_html, "html.parser")
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        low_url = full_url.lower()
        if low_url.startswith(("mailto:", "javascript:")):
            continue
        if "sec-filings" in low_url:
            continue
        if "/news/" in low_url and "presentation" not in low_url:
            continue

        parent = a.find_parent(["li", "tr", "div", "section", "article"])
        text = _clean_ws(a.get_text(" ", strip=True))
        row_text = _clean_ws(parent.get_text(" ", strip=True) if parent else text)
        context = _clean_ws(f"{row_text} {full_url}".lower())
        context_norm = re.sub(r"[-_/]+", " ", context)
        if not any(k in context_norm for k in IR_DOC_KEYWORDS):
            continue
        is_pdf = ".pdf" in low_url
        if not is_pdf and not any(h in context_norm for h in IR_HTML_HINTS):
            continue

        period_match = re.search(
            r"(Q[1-4][\s_-]*(?:20)?\d{2}|[1-4]Q[\s_-]*(?:20)?\d{2}|FY[\s_-]*(?:20)?\d{2}|20\d{2})",
            f"{row_text} {full_url}",
            re.IGNORECASE,
        )
        period = normalize_period(period_match.group(1) if period_match else None)

        # Date extraction
        import datetime as _dt

        fecha_evento: str | None = None
        for chunk in (row_text, full_url):
            for match in re.findall(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", chunk):
                parsed = _parse_human_date(match)
                if parsed:
                    fecha_evento = parsed
                    break
            if fecha_evento:
                break
            for match in re.findall(r"(20\d{2}-\d{2}-\d{2})", chunk):
                parsed = _parse_human_date(match)
                if parsed:
                    fecha_evento = parsed
                    break
            if fecha_evento:
                break

        if not is_pdf:
            # Filter navigation pages
            if _is_navigation_like_source(text or row_text[:120], f"{row_text} {full_url}", full_url):
                rejected.append({
                    "url": full_url,
                    "title": text or row_text[:180],
                    "reason": "navigation_like_pattern",
                })
                continue

        rows.append({
            "url": full_url,
            "period": period,
            "date": fecha_evento,
            "title": row_text or text,
            "doc_kind": "pdf" if is_pdf else "html",
        })

    # Dedup by URL
    seen_url: set[str] = set()
    seen_name: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda x: _period_sort_key((x.get("period") or "").lower()), reverse=True):
        url = row["url"]
        basename = Path(urlparse(url).path).name.lower()
        if url in seen_url:
            continue
        if basename and basename in seen_name:
            continue
        seen_url.add(url)
        if basename:
            seen_name.add(basename)
        deduped.append(row)
    return deduped, rejected


# ── TranscriptFinder ──────────────────────────────────────────────────

class TranscriptFinder:
    """Discovers and downloads earnings transcripts and IR presentations.

    Searches Fintool.com for earnings call transcripts (US tickers)
    and company IR websites for investor presentations and reports.
    Reuses ir_crawler.py functions for IR website crawling.
    """

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def find(
        self,
        case: CaseConfig,
        empresa: str = "",
        max_transcripts: int = 8,
        max_presentations: int = 8,
    ) -> TranscriptResult:
        """Find earnings transcripts and IR presentations for a ticker.

        Args:
            case: Case configuration with ticker, source_hint, etc.
            empresa: Optional company name for issuer verification.
            max_transcripts: Maximum Fintool transcripts to fetch.
            max_presentations: Maximum IR presentations to fetch.

        Returns:
            TranscriptResult with found sources and discarded items.
        """
        ticker = case.ticker.upper()
        result = TranscriptResult(ticker=ticker)

        # Load case.json for web_ir and other metadata
        case_config = self._load_case_config(case)
        web_ir = case_config.get("web_ir", "")
        exchange = case_config.get("exchange", case_config.get("market", ""))
        country = case_config.get("country", "")
        if not empresa:
            empresa = case_config.get("company_name", "")

        # Build issuer aliases
        target_aliases, target_quality = _build_target_aliases(ticker, empresa)

        # Step 1: Fintool transcripts (US tickers only)
        non_us = is_non_us(
            exchange=exchange if exchange else None,
            country=country if country else None,
            cik=case.cik,
        )
        if not non_us:
            sources, discarded = self._fetch_fintool_transcripts(
                ticker, max_transcripts, target_aliases, target_quality,
            )
            result.sources.extend(sources)
            result.discarded.extend(discarded)

        # Step 2: IR presentations
        if web_ir:
            pres_sources, pres_discarded = self._fetch_ir_presentations(
                ticker, web_ir, exchange, max_presentations,
            )
            result.sources.extend(pres_sources)
            result.discarded.extend(pres_discarded)

        # Step 3: Identify gaps
        transcript_count = sum(1 for s in result.sources if s.tipo == "EARNINGS_TRANSCRIPT")
        presentation_count = sum(
            1 for s in result.sources
            if s.tipo in ("INVESTOR_PRESENTATION", "ANNUAL_REPORT")
        )
        if transcript_count == 0 and not non_us:
            result.missing.append(
                "No earnings transcripts found. Check Fintool/IR page or use manual sources."
            )
        if presentation_count == 0 and web_ir:
            result.missing.append(
                "No investor presentations found from IR website."
            )

        return result

    def _load_case_config(self, case: CaseConfig) -> dict[str, Any]:
        """Load raw case.json data."""
        case_path = Path(case.case_dir) / "case.json"
        if case_path.exists():
            try:
                return json.loads(case_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _fetch_fintool_transcripts(
        self,
        ticker: str,
        max_transcripts: int,
        target_aliases: list[str],
        target_quality: str,
    ) -> tuple[list[TranscriptSource], list[dict[str, Any]]]:
        """Fetch earnings call transcripts from Fintool.com.

        Args:
            ticker: Company ticker symbol.
            max_transcripts: Maximum number of transcripts to fetch.
            target_aliases: Normalized company name aliases for issuer matching.
            target_quality: "STRONG" or "WEAK" alias quality.

        Returns:
            Tuple of (accepted_sources, discarded_items).
        """
        sources: list[TranscriptSource] = []
        discarded: list[dict[str, Any]] = []
        source_idx = 1

        try:
            index_url = f"https://fintool.com/app/research/companies/{ticker}/documents/transcripts"
            index_html = _request_text(self._session, index_url)
            periods = _extract_transcript_periods(index_html, ticker)[:max_transcripts]
        except Exception as exc:
            logger.warning("Failed to load Fintool transcript index for %s: %s", ticker, exc)
            return sources, discarded

        for period_slug in periods:
            source_id = f"SRC_TRS_{source_idx:03d}"
            source_idx += 1
            period_norm = normalize_period(period_slug)
            transcript_url = (
                f"https://fintool.com/app/research/companies/{ticker}"
                f"/documents/transcripts/{period_slug}"
            )

            try:
                html = _request_text(self._session, transcript_url)
                next_data = _parse_next_data(html)
                if not next_data:
                    logger.warning("%s: no __NEXT_DATA__ found", source_id)
                    continue

                page_props = next_data.get("props", {}).get("pageProps", {})
                display_period = normalize_period(
                    page_props.get("displayPeriod") or period_slug
                )
                title = _clean_ws(
                    str(page_props.get("title") or f"{ticker} Earnings Call Transcript - {display_period}")
                )
                published = _parse_human_date(page_props.get("publishedAt"))
                transcript_text = _build_transcript_text(page_props)

                # Issuer verification
                issuer_candidates: list[str] = []
                company_name = _clean_ws(str(page_props.get("companyName") or ""))
                if company_name:
                    issuer_candidates.append(company_name)
                issuer_candidates.extend(_extract_company_from_title(title))
                first_line = _clean_ws(transcript_text.splitlines()[0]) if transcript_text else ""
                issuer_candidates.extend(_extract_company_from_title(first_line))
                # Deduplicate candidates
                deduped_candidates: list[str] = []
                seen_norm: set[str] = set()
                for cand in issuer_candidates:
                    norm = _normalize_entity_name(cand)
                    if not norm or norm in seen_norm:
                        continue
                    seen_norm.add(norm)
                    deduped_candidates.append(cand)
                issuer_candidates = deduped_candidates

                # Fail-closed if target identity is weak
                if target_quality == "WEAK":
                    discarded.append({
                        "source_id": source_id,
                        "url": transcript_url,
                        "title": title,
                        "reason": "target_identity_weak",
                    })
                    continue

                is_match, match_score = _issuer_match_decision(
                    target_aliases, issuer_candidates, ticker,
                )
                if not is_match:
                    discarded.append({
                        "source_id": source_id,
                        "url": transcript_url,
                        "title": title,
                        "issuer_candidates": issuer_candidates[:3],
                        "score": round(match_score, 3),
                        "reason": "issuer_mismatch",
                    })
                    continue

                text_hash = content_hash(transcript_text)
                sources.append(TranscriptSource(
                    source_id=source_id,
                    tipo="EARNINGS_TRANSCRIPT",
                    period=display_period,
                    url=transcript_url,
                    issuer_match=True,
                    issuer_match_score=match_score,
                    content_hash=text_hash,
                    title=title,
                    date=published,
                    text_chars=len(transcript_text),
                ))
            except Exception as exc:
                logger.warning("%s (%s) fetch error: %s", source_id, transcript_url, exc)

        return sources, discarded

    def _fetch_ir_presentations(
        self,
        ticker: str,
        web_ir: str,
        exchange: str,
        max_presentations: int,
    ) -> tuple[list[TranscriptSource], list[dict[str, Any]]]:
        """Fetch investor presentations from company IR website.

        Reuses ir_crawler.py build_ir_pages for URL generation.

        Args:
            ticker: Company ticker symbol.
            web_ir: Investor Relations base URL.
            exchange: Exchange identifier (for keyword hints).
            max_presentations: Maximum presentations to return.

        Returns:
            Tuple of (accepted_sources, discarded_items).
        """
        sources: list[TranscriptSource] = []
        discarded: list[dict[str, Any]] = []

        # Resolve IR URL
        normalized_ir = normalize_web_ir(web_ir)
        if not normalized_ir:
            return sources, discarded

        try:
            resolved = resolve_ir_base_url(normalized_ir, self._session, timeout=10)
            if resolved:
                normalized_ir = resolved
        except Exception as exc:
            logger.warning("IR URL resolution failed for %s: %s", web_ir, exc)

        # Build IR pages using ir_crawler.py
        ir_pages = build_ir_pages(normalized_ir)
        if not ir_pages:
            return sources, discarded

        all_rows: list[dict[str, Any]] = []
        all_rejected: list[dict[str, Any]] = []
        for ir_page in ir_pages:
            try:
                ir_html = _request_text(self._session, ir_page)
                rows, rejected_rows = _extract_presentation_rows(ir_html, ir_page)
                all_rows.extend(rows)
                for rej in rejected_rows:
                    rej["discovered_from"] = ir_page
                all_rejected.extend(rejected_rows)
            except Exception as exc:
                logger.debug("Failed to crawl IR page %s: %s", ir_page, exc)

        # Add rejected rows to discarded
        for rej in all_rejected:
            discarded.append({
                "url": rej.get("url", ""),
                "title": rej.get("title", ""),
                "reason": rej.get("reason", "navigation_like"),
            })

        # Dedup and limit presentations
        dedup_by_url: dict[str, dict[str, Any]] = {}
        for row in all_rows:
            url = row["url"]
            if url not in dedup_by_url:
                dedup_by_url[url] = row
        dedup_by_name: dict[str, dict[str, Any]] = {}
        for row in dedup_by_url.values():
            basename = Path(urlparse(row["url"]).path).name.lower()
            key = basename or row["url"]
            if key not in dedup_by_name:
                dedup_by_name[key] = row
        limited = sorted(
            dedup_by_name.values(),
            key=lambda x: (
                x.get("date") or "0000-00-00",
                _period_sort_key((x.get("period") or "").lower()),
            ),
            reverse=True,
        )[:max_presentations]

        # Build TranscriptSource for each presentation
        source_idx = 1
        for row in limited:
            source_id = f"SRC_PRS_{source_idx:03d}"
            source_idx += 1
            tipo = _classify_presentation_source_type(
                row.get("title", ""), row["url"], row.get("title", ""),
            )
            sources.append(TranscriptSource(
                source_id=source_id,
                tipo=tipo,
                period=row.get("period"),
                url=row["url"],
                title=row.get("title", "")[:240],
                date=row.get("date"),
                issuer_match=False,  # Not evaluated for presentations
                issuer_match_score=0.0,
            ))

        return sources, discarded
