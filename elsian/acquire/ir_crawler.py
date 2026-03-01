"""IR Website Crawler — fetcher for non-SEC companies.

Ported from 3_0-ELSIAN-INVEST:
  - sec_fetcher_v2_runner.py: `_derive_local_ir_roots`, `build_local_ir_pages`,
    `discover_ir_subpages`, `extract_local_filing_candidates`,
    `_select_local_fallback_candidates`
  - ir_url_resolver.py: `build_ir_url_candidates`, `resolve_ir_base_url`

This module does NOT implement the Fetcher ABC directly — it provides the
building blocks that EuRegulatorsFetcher, AsxFetcher, or a future
IrCrawlerFetcher can compose.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from elsian.markets import (
    LOCAL_FILING_KEYWORDS_BY_EXCHANGE,
    LOCAL_FILING_KEYWORDS_COMMON,
    LOCAL_FILING_NEGATIVE,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

_IR_DISCOVERY_HINTS: tuple[str, ...] = (
    "investor",
    "financial",
    "results",
    "reports",
    "report",
    "announcement",
    "news",
    "regulatory",
    "finance kit",
    "financials",
)

_IR_SUFFIXES: tuple[str, ...] = (
    "/publications-and-events/financial-publications",
    "/publications-and-events/regulated-information",
    "/publications-and-events/press-releases",
    "/reports-results-and-presentations",
    "/financial-results",
    "/results",
    "/finance-kit",
    "/financial-reports",
    "/annual-reports",
    "/investor-relations",
    "/investors",
    "/company-announcements",
    "/announcements",
    "/news-events",
    "/news",
    "/publications",
)

_HOMEPAGE_TAILS = {
    "investors-homepage",
    "investor-homepage",
    "homepage",
    "home",
}

FALLBACK_MAX_TOTAL = 12
FALLBACK_PER_TYPE: dict[str, int] = {
    "ANNUAL_REPORT": 4,
    "INTERIM_REPORT": 4,
    "REGULATORY_FILING": 4,
    "IR_NEWS": 3,
    "_default": 2,
}

HEADERS = {
    "User-Agent": "ELSIAN-INVEST-Bot/1.0 (research; bot@elsian-invest.local)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}

_WEAK_STATUS = {403, 429}
_VALID_STATUS = {200, 403, 429}


# ── URL normalisation helpers ─────────────────────────────────────────

def normalize_web_ir(url: Optional[str]) -> Optional[str]:
    """Normalize an IR URL for consistent comparison."""
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"
    return candidate.rstrip("/")


# ── IR URL resolver (ported from ir_url_resolver.py) ──────────────────

def build_ir_url_candidates(base_url: str) -> list[str]:
    """Generate URL variants to try when the original IR URL fails.

    For ``https://www.somero.com/investors`` generates:
      1. original URL
      2. investors.{bare_domain}           (subdomain, no path)
      3. investors.{bare_domain}/investors (subdomain + path)
      4. {domain}/investor-relations       (alt path)
      5. {domain}/investors                (alt path)
      6. {bare_domain}{path}               (without www)
    """
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or ""
    path = parsed.path.rstrip("/")

    candidates: list[str] = [base_url]

    # Determine bare domain (strip www.)
    parts = netloc.split(".")
    if parts[0].lower() == "www":
        bare_domain = ".".join(parts[1:])
    else:
        bare_domain = netloc

    # investors.{bare_domain}
    inv_sub = f"investors.{bare_domain}"
    if inv_sub != netloc:
        candidates.append(f"{scheme}://{inv_sub}")
        candidates.append(f"{scheme}://{inv_sub}{path}")

    if "/investor-relations" not in path:
        candidates.append(f"{scheme}://{netloc}/investor-relations")

    if "/investors" not in path:
        candidates.append(f"{scheme}://{netloc}/investors")

    if bare_domain != netloc:
        candidates.append(f"{scheme}://{bare_domain}{path}")

    return list(dict.fromkeys(candidates))


def resolve_ir_base_url(
    web_ir: str,
    session: Any,
    timeout: int = 10,
) -> Optional[str]:
    """Resolve an IR base URL, trying variants if the original fails.

    Args:
        web_ir: Original IR URL from case.json.
        session: requests.Session (or compatible).
        timeout: Request timeout in seconds.

    Returns:
        First URL that responds with 200/403/429, or None.
    """
    if not web_ir or not web_ir.strip():
        return None

    base = web_ir.strip()
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    base = base.rstrip("/")

    candidates = build_ir_url_candidates(base)
    weak_match = None

    for url in candidates:
        status = _probe_url(session, url, timeout=timeout)
        if status is None:
            continue
        if status == 200:
            if url != base:
                logger.info("IR URL resolved: %s -> %s", web_ir, url)
            return url
        if status in _WEAK_STATUS and weak_match is None:
            weak_match = url

    if weak_match:
        if weak_match != base:
            logger.info("IR URL resolved (weak): %s -> %s", web_ir, weak_match)
        return weak_match

    logger.warning(
        "All %d IR URL candidates failed for %s", len(candidates), web_ir
    )
    return None


def _probe_url(session: Any, url: str, timeout: int = 10) -> Optional[int]:
    """Probe URL with HEAD then GET. Return status or None."""
    for method in (session.head, session.get):
        try:
            resp = method(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code in _VALID_STATUS:
                return int(resp.status_code)
            if method == session.head and resp.status_code == 405:
                continue
            return None
        except Exception:
            if method == session.head:
                continue
            return None
    return None


# ── IR root derivation ────────────────────────────────────────────────

def derive_ir_roots(base_url: str) -> list[str]:
    """Derive potential IR root URLs from a base IR URL.

    Handles locale prefixes (e.g. /en-us/investors) and homepage tails.
    """
    parsed = urlparse(base_url)
    host_root = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    path = parsed.path.strip("/")
    segments = [seg for seg in path.split("/") if seg]
    original_segments = list(segments)

    # Trim homepage tails
    while segments and segments[-1].lower() in _HOMEPAGE_TAILS:
        segments.pop()

    locale = (
        segments[0].lower()
        if segments and re.fullmatch(r"[a-z]{2}-[a-z]{2}", segments[0].lower())
        else None
    )
    investor_idx = next(
        (
            idx
            for idx, seg in enumerate(segments)
            if seg.lower() in {"investors", "investor-relations"}
        ),
        None,
    )
    has_homepage_tail = (
        bool(original_segments)
        and original_segments[-1].lower() in _HOMEPAGE_TAILS
    )

    roots: list[str] = []
    if locale and investor_idx is not None:
        roots.append(f"{host_root}/{locale}/{segments[investor_idx]}")
    elif investor_idx is not None:
        roots.append(f"{host_root}/{segments[investor_idx]}")
    if segments:
        roots.append(f"{host_root}/{'/'.join(segments)}")
    if locale:
        roots.append(f"{host_root}/{locale}")
        roots.append(f"{host_root}/{locale}/investors")
    if not has_homepage_tail:
        roots.append(base_url.rstrip("/"))
    roots.append(host_root)

    # Deduplicate preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for root in roots:
        cleaned = normalize_web_ir(root)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def build_ir_pages(web_ir: Optional[str]) -> list[str]:
    """Build list of IR pages to crawl (root + suffixes).

    Returns up to ~200 candidate page URLs.
    """
    base = normalize_web_ir(web_ir)
    if not base:
        return []

    homepage_tail_re = re.compile(
        r"/(?:investors-homepage|investor-homepage|homepage|home)$"
    )
    pages: list[str] = [base]
    for ir_root in derive_ir_roots(base):
        pages.append(ir_root)
        low_path = (urlparse(ir_root).path or "").rstrip("/").lower()
        if homepage_tail_re.search(low_path):
            continue
        for suffix in _IR_SUFFIXES:
            pages.append(urljoin(ir_root + "/", suffix.lstrip("/")))

    return list(dict.fromkeys(pages))


# ── Subpage discovery ─────────────────────────────────────────────────

def _is_same_domain(base_url: str, candidate_url: str) -> bool:
    base_host = urlparse(base_url).netloc.lower()
    cand_host = urlparse(candidate_url).netloc.lower()
    return bool(base_host and cand_host and base_host == cand_host)


def discover_ir_subpages(
    html: str,
    base_url: str,
    exchange: Optional[str] = None,
    max_links: int = 80,
) -> list[str]:
    """Scan *html* for links to IR subpages worth crawling.

    Filters by domain match, keyword hints, and negative list.
    Returns up to *max_links* unique URLs.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed — cannot discover subpages")
        return []

    soup = BeautifulSoup(html, "html.parser")
    ex = (exchange or "").upper()
    hints = set(_IR_DISCOVERY_HINTS)
    hints.update(LOCAL_FILING_KEYWORDS_BY_EXCHANGE.get(ex, ()))

    out: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if not full_url.startswith(("http://", "https://")):
            continue
        if not _is_same_domain(base_url, full_url):
            continue

        low_url = full_url.lower()
        if any(neg in low_url for neg in LOCAL_FILING_NEGATIVE):
            continue
        if low_url.endswith(
            (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".ppt", ".pptx")
        ):
            continue

        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        context_norm = re.sub(r"[-_/]+", " ", f"{text} {low_url}".lower())
        if not any(h in context_norm for h in hints):
            continue

        if full_url in seen:
            continue
        seen.add(full_url)
        out.append(full_url)
        if len(out) >= max_links:
            break
    return out


# ── Filing candidate extraction from HTML ─────────────────────────────

def extract_filing_candidates(
    html: str,
    base_url: str,
    exchange: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Extract filing candidates from an IR page's HTML.

    Returns a list of dicts with: url, titulo, score, tipo_guess, snippet, etc.
    Sorted by selection_score descending, capped at 20.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed — cannot extract candidates")
        return []

    from elsian.acquire.classify import classify_filing_type

    soup = BeautifulSoup(html, "html.parser")
    ex = (exchange or "").upper()
    kws = set(LOCAL_FILING_KEYWORDS_COMMON)
    kws.update(LOCAL_FILING_KEYWORDS_BY_EXCHANGE.get(ex, ()))

    event_register_re = re.compile(
        r"(webcast|event)[\w\s:/-]{0,40}register|engagestream|signup|/register(?:$|[/?#])",
        re.IGNORECASE,
    )

    by_url: dict[str, dict[str, Any]] = {}
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full_url = urljoin(base_url, href)
        if not full_url.startswith(("http://", "https://")):
            continue

        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        parent = a.find_parent(["li", "tr", "div", "section", "article"])
        row_text = (
            re.sub(r"\s+", " ", parent.get_text(" ", strip=True)).strip()
            if parent
            else text
        )

        context_raw = f"{text} {row_text} {full_url}"
        context = context_raw.lower()
        context_norm = re.sub(r"[-_/]+", " ", context)

        # Negative filters
        if any(neg in context for neg in LOCAL_FILING_NEGATIVE):
            continue
        if event_register_re.search(f"{context} {full_url.lower()}"):
            continue
        if "presentation" in context_norm or "deck" in context_norm or "slides" in context_norm:
            continue
        if not any(kw in context_norm for kw in kws):
            continue

        # Score
        score = sum(1 for kw in kws if kw in context_norm)
        if full_url.lower().endswith(".pdf"):
            score += 1
        if "annual" in context or "interim" in context:
            score += 2
        if "rns" in context or "hkex" in context or "asx" in context:
            score += 2

        title = text or urlparse(full_url).path.rsplit("/", 1)[-1] or "Local filing"
        filing_type = classify_filing_type(title, full_url, row_text)

        selection_score = float(score)
        if filing_type == "ANNUAL_REPORT":
            selection_score += 4.0
        elif filing_type == "INTERIM_REPORT":
            selection_score += 3.0
        elif filing_type == "REGULATORY_FILING":
            selection_score += 2.0
        elif filing_type == "IR_NEWS":
            selection_score += 1.0

        candidate = {
            "url": full_url,
            "titulo": title[:240],
            "score": score,
            "snippet": row_text[:280] if row_text else title[:280],
            "tipo_guess": filing_type,
            "selection_score": selection_score,
        }

        prev = by_url.get(full_url)
        if prev is None or candidate["selection_score"] > prev.get("selection_score", 0):
            by_url[full_url] = candidate

    candidates = sorted(
        by_url.values(),
        key=lambda x: float(x.get("selection_score", 0.0)),
        reverse=True,
    )
    return candidates[:20]


# ── Candidate selection with per-type limits ──────────────────────────

def select_fallback_candidates(
    candidates: list[dict[str, Any]],
    max_total: int = FALLBACK_MAX_TOTAL,
    per_type: Optional[dict[str, int]] = None,
) -> list[dict[str, Any]]:
    """Select best candidates respecting per-type limits.

    Args:
        candidates: List of candidate dicts from extract_filing_candidates.
        max_total: Maximum total candidates to return.
        per_type: Override per-type limits (defaults to FALLBACK_PER_TYPE).

    Returns:
        Filtered, ordered list of best candidates.
    """
    limits = per_type or FALLBACK_PER_TYPE

    ordered = sorted(
        candidates,
        key=lambda x: float(x.get("selection_score", 0.0)),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for cand in ordered:
        ctype = str(cand.get("tipo_guess") or "OTHER").upper()
        limit = int(limits.get(ctype, limits.get("_default", 2)))
        if counts.get(ctype, 0) >= limit:
            continue
        selected.append(cand)
        counts[ctype] = counts.get(ctype, 0) + 1
        if len(selected) >= max_total:
            break
    return selected
