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

import datetime as dt
import html as html_lib
import logging
import re
from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import unquote, urljoin, urlparse

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

LOCAL_EVENT_REGISTRATION_HINTS_STRONG: tuple[str, ...] = (
    "engagestream",
    "register",
    "registration",
    "signup",
    "webcast",
)


# ── Date parsing helpers (ported from sec_fetcher_v2_runner.py) ───────

def parse_date_loose(text: str) -> Optional[str]:
    """Parse a date from free text.  Returns ISO date string or None.

    Handles: YYYY-MM-DD, YYYYMMDD, "March 15, 2024", "15 March 2024".
    """
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return None

    # ISO-like: 2024-03-15, 2024/03/15
    for m in re.finditer(r"\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", value):
        try:
            y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return dt.date(y, mo, day).isoformat()
        except ValueError:
            continue

    # Compact: 20240315
    for m in re.finditer(r"(?<!\d)((?:19|20)\d{2})(\d{2})(\d{2})(?!\d)", value):
        try:
            y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return dt.date(y, mo, day).isoformat()
        except ValueError:
            continue

    # Text dates: "March 15, 2024" or "15 March 2024"
    for pattern in (
        r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
        r"(\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2})",
    ):
        m = re.search(pattern, value, flags=re.IGNORECASE)
        if not m:
            continue
        raw = m.group(1).strip()
        normalized = raw.title()
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
            try:
                return dt.datetime.strptime(normalized, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def parse_year_hint(text: str) -> Optional[int]:
    """Extract a fiscal year hint from text containing keywords like 'annual', 'year', etc."""
    low = re.sub(r"\s+", " ", str(text or "")).lower()
    if not low:
        return None
    if not any(k in low for k in ("annual", "interim", "year", "fy", "report", "results")):
        return None
    years = [int(m.group(0)) for m in re.finditer(r"(?<!\d)(?:19|20)\d{2}(?!\d)", low)]
    if not years:
        return None
    return max(years)


# ── Candidate date resolution (ported from sec_fetcher_v2_runner.py) ──

def _resolve_local_candidate_date(
    anchor_text: str,
    row_text: str,
    full_url: str,
) -> Tuple[Optional[str], str, bool]:
    """Resolve publication date from context around a filing link.

    Tries parse_date_loose on (anchor_text + row_text), then URL.
    Falls back to parse_year_hint → "{year}-12-31".

    Returns:
        (date_str | None, source_name, is_estimated)
    """
    for source_name, chunk in (
        ("context", f"{anchor_text} {row_text}"),
        ("url", full_url),
    ):
        date_guess = parse_date_loose(chunk)
        if date_guess:
            estimated = source_name != "context"
            return date_guess, source_name, estimated
    for source_name, chunk in (
        ("title_year", f"{anchor_text} {row_text}"),
        ("url_year", full_url),
    ):
        year_hint = parse_year_hint(chunk)
        if year_hint:
            inferred = f"{int(year_hint):04d}-12-31"
            return inferred, source_name, True
    return None, "unknown", True


def _extract_date_from_html_document(html: str, doc_url: str) -> Tuple[Optional[str], str]:
    """Extract publication date from an HTML document's metadata.

    Checks meta tags (article:published_time, date, publishdate,
    publication_date, dc.date), then <time> tags, title, and URL.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None, "unknown"

    soup = BeautifulSoup(html, "html.parser")
    meta_selectors = (
        ("html_meta", {"property": "article:published_time"}),
        ("html_meta", {"name": "date"}),
        ("html_meta", {"name": "publishdate"}),
        ("html_meta", {"name": "publication_date"}),
        ("html_meta", {"name": "dc.date"}),
    )
    for source_name, attrs in meta_selectors:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            parsed = parse_date_loose(str(tag.get("content")))
            if parsed:
                return parsed, source_name

    for t in soup.find_all("time"):
        text = str(t.get("datetime") or t.get_text(" ", strip=True) or "")
        parsed = parse_date_loose(text)
        if parsed:
            return parsed, "html_time_tag"

    if soup.title and soup.title.get_text():
        parsed = parse_date_loose(soup.title.get_text(" ", strip=True))
        if parsed:
            return parsed, "html_title"

    parsed = parse_date_loose(doc_url)
    if parsed:
        return parsed, "url"
    return None, "unknown"


# ── Event registration penalty (ported from sec_fetcher_v2_runner.py) ─

def _local_event_registration_penalty(context_norm: str, full_url: str) -> float:
    """Soft-penalize event/registration links so annual reports rank higher."""
    ctx = f"{context_norm} {full_url.lower()}"
    penalty = 0.0
    if any(hint in ctx for hint in LOCAL_EVENT_REGISTRATION_HINTS_STRONG):
        penalty -= 3.0
    if re.search(r"\bevents?\b", ctx):
        penalty -= 1.0
    return penalty


# ── Embedded PDF helpers (ported from sec_fetcher_v2_runner.py) ───────

def _clean_embedded_pdf_url(raw_url: str) -> str:
    """Clean raw PDF URL from embedded HTML/JSON contexts."""
    if not raw_url:
        return ""
    cleaned = str(raw_url).strip().strip("\"'`")
    cleaned = html_lib.unescape(cleaned)
    cleaned = cleaned.replace("\\/", "/")
    cleaned = re.sub(r"\\u0*2f", "/", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\\x2f", "/", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("\\\\", "\\")
    cleaned = cleaned.strip().strip("\"'`")
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    return cleaned


def _extract_embedded_title(context_window: str, full_url: str) -> str:
    """Extract title from context window around a PDF URL match."""
    patterns = (
        r'data-gtm-elem-text\\?"?\s*[:=]\s*["\']([^"\']{6,220})["\']',
        r'"name"\s*:\s*\{\s*"Value"\s*:\s*"([^"]{6,220})"',
        r'"name"\s*:\s*\{\s*"value"\s*:\s*"([^"]{6,220})"',
        r'"title"\s*:\s*"([^"]{6,220})"',
    )
    for pat in patterns:
        m = re.search(pat, context_window, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = re.sub(r"\s+", " ", html_lib.unescape(m.group(1))).strip()
        if candidate:
            return candidate[:240]
    basename = unquote(Path(urlparse(full_url).path).name).replace("+", " ").strip()
    return basename[:240] or "Local filing"


def _extract_embedded_pdf_candidates(
    html: str,
    base_url: str,
    exchange: Optional[str],
) -> list[dict[str, Any]]:
    """Extract PDF candidates from embedded/linked PDFs in HTML.

    Searches for absolute, relative, and slash-relative PDF URLs
    via regex, extracts context windows, scores by keyword hits,
    and deduplicates.
    """
    from elsian.acquire.classify import classify_filing_type

    ex = (exchange or "").upper()
    kws = set(LOCAL_FILING_KEYWORDS_COMMON)
    kws.update(LOCAL_FILING_KEYWORDS_BY_EXCHANGE.get(ex, ()))

    positive_plain_hints = (
        "annual",
        "results",
        "registration document",
        "universal registration document",
        "integrated report",
        "interim",
        "financial",
        "urd",
    )
    negative_plain_hints = ("privacy", "cookie", "terms", "policy")
    event_register_re = re.compile(
        r"(webcast|event)[\w\s:/-]{0,40}register|signup", re.IGNORECASE
    )
    period_hint_re = re.compile(r"\b(q[1-4]|h[12])\b", re.IGNORECASE)

    pattern = re.compile(
        r"""(?ix)
        (?:
            (?P<absolute>https?://[^\s"'<>\\]+?\.pdf(?:\?[^\s"'<>\\]*)?)
            |
            (?P<relative>(?:\\?/)?media/[^\s"'<>\\]+?\.pdf(?:\?[^\s"'<>\\]*)?)
            |
            (?P<slash_relative>\\?/media/[^\s"'<>\\]+?\.pdf(?:\?[^\s"'<>\\]*)?)
        )
        """
    )

    by_url: dict[str, dict[str, Any]] = {}
    for match in pattern.finditer(html):
        raw_url = (
            match.group("absolute")
            or match.group("relative")
            or match.group("slash_relative")
            or ""
        )
        cleaned_url = _clean_embedded_pdf_url(raw_url)
        if not cleaned_url:
            continue

        if not cleaned_url.startswith(("http://", "https://", "/")):
            continue
        if cleaned_url.startswith("media/"):
            cleaned_url = f"/{cleaned_url}"
        full_url = urljoin(base_url, cleaned_url)
        if not full_url.lower().startswith(("http://", "https://")):
            continue
        if not full_url.lower().endswith(".pdf") and ".pdf?" not in full_url.lower():
            continue

        start, end = match.span()
        left = max(0, start - 180)
        right = min(len(html), end + 180)
        context_window = html[left:right]
        context_window = html_lib.unescape(context_window.replace("\\/", "/"))
        context_window = re.sub(r"\s+", " ", context_window).strip()
        context_low = context_window.lower()
        context_norm = re.sub(r"[-_/]+", " ", context_low)
        merged_ctx = f"{full_url.lower()} {context_low}"

        if any(neg in merged_ctx for neg in negative_plain_hints):
            continue
        if event_register_re.search(merged_ctx):
            continue

        title = _extract_embedded_title(context_window, full_url)
        url_title_ctx = f"{full_url.lower()} {title.lower()}"
        has_positive = any(
            pos in url_title_ctx for pos in positive_plain_hints
        ) or bool(period_hint_re.search(url_title_ctx))
        if not has_positive:
            continue

        date_guess, date_source, date_estimated = _resolve_local_candidate_date(
            title,
            context_window,
            full_url,
        )
        basename_hint = unquote(
            Path(urlparse(full_url).path).name
        ).replace("+", " ")
        filing_type = classify_filing_type(title, full_url, basename_hint)

        score = 1  # Base score for embedded PDF match
        kw_hits = sum(
            1 for kw in kws if kw in context_norm or kw in url_title_ctx
        )
        score += min(3, kw_hits)
        if "annual" in url_title_ctx or "integrated report" in url_title_ctx or "urd" in url_title_ctx:
            score += 2
        if "interim" in url_title_ctx or re.search(r"\b(h1|h2|q[1-4])\b", url_title_ctx):
            score += 2

        selection_score = float(score)
        if filing_type == "ANNUAL_REPORT":
            selection_score += 4.0
        elif filing_type == "INTERIM_REPORT":
            selection_score += 3.0
        elif filing_type == "REGULATORY_FILING":
            selection_score += 2.0
        elif filing_type == "IR_NEWS":
            selection_score += 1.0
        if date_guess:
            selection_score += 0.5
        selection_score += _local_event_registration_penalty(context_norm, full_url)

        snippet = context_window[:280] if context_window else title[:280]
        candidate = {
            "url": full_url,
            "titulo": title[:240],
            "score": score,
            "fecha_publicacion": date_guess,
            "fecha_source": date_source,
            "fecha_publicacion_estimated": date_estimated,
            "snippet": snippet,
            "tipo_guess": filing_type,
            "selection_score": selection_score,
            "discovered_via": "embedded_pdf",
        }
        prev = by_url.get(full_url)
        if prev is None or _prefer_new_candidate(prev, candidate):
            by_url[full_url] = candidate

    return list(by_url.values())


# ── Candidate dedup helper (ported from sec_fetcher_v2_runner.py) ─────

def _prefer_new_candidate(
    prev: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    """Decide whether *candidate* should replace *prev* for the same URL.

    Score comparison with date-aware protection: protects date-carrying
    candidates from date-less overwrite unless the score delta is >= 2.
    """
    prev_score = int(prev.get("score", 0))
    new_score = int(candidate.get("score", 0))
    if new_score > prev_score:
        if prev.get("fecha_publicacion") and not candidate.get("fecha_publicacion"):
            return (new_score - prev_score) >= 2
        return True
    if new_score < prev_score:
        return False
    # Scores tied — prefer the one with a date
    prev_has_date = bool(prev.get("fecha_publicacion"))
    new_has_date = bool(candidate.get("fecha_publicacion"))
    if new_has_date and not prev_has_date:
        return True
    if prev_has_date and not new_has_date:
        return False
    return float(candidate.get("selection_score", 0.0)) > float(
        prev.get("selection_score", 0.0)
    )


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

    Returns a list of dicts with: url, titulo, score, tipo_guess, snippet,
    fecha_publicacion, fecha_source, fecha_publicacion_estimated, etc.
    Sorted by selection_score descending, capped at 20.

    Integrates:
    - Date resolution per candidate (anchor text, row text, URL)
    - Event registration penalty (soft-penalize webcasts/signups)
    - Embedded PDF extraction via regex (non-anchor PDFs)
    - Duplicate resolution via _prefer_new_candidate
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

        # Date resolution
        date_guess, date_source, date_estimated = _resolve_local_candidate_date(
            text, row_text, full_url,
        )

        selection_score = float(score)
        if filing_type == "ANNUAL_REPORT":
            selection_score += 4.0
        elif filing_type == "INTERIM_REPORT":
            selection_score += 3.0
        elif filing_type == "REGULATORY_FILING":
            selection_score += 2.0
        elif filing_type == "IR_NEWS":
            selection_score += 1.0
        if date_guess:
            selection_score += 0.5
        # Event registration penalty
        selection_score += _local_event_registration_penalty(context_norm, full_url)

        candidate = {
            "url": full_url,
            "titulo": title[:240],
            "score": score,
            "fecha_publicacion": date_guess,
            "fecha_source": date_source,
            "fecha_publicacion_estimated": date_estimated,
            "snippet": row_text[:280] if row_text else title[:280],
            "tipo_guess": filing_type,
            "selection_score": selection_score,
        }

        prev = by_url.get(full_url)
        if prev is None or _prefer_new_candidate(prev, candidate):
            by_url[full_url] = candidate

    # Merge embedded PDF candidates
    for emb_cand in _extract_embedded_pdf_candidates(html, base_url, exchange):
        emb_url = emb_cand["url"]
        prev = by_url.get(emb_url)
        if prev is None or _prefer_new_candidate(prev, emb_cand):
            by_url[emb_url] = emb_cand

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
