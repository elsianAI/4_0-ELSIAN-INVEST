"""Filing classification and quality assessment.

Ported from 3_0-ELSIAN-INVEST sec_fetcher_v2_runner.py:
  - `_classify_local_filing_type`
  - `_classify_local_annual_extractability`
  - `_financial_signal_hits`
"""

from __future__ import annotations

import re
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────

LOCAL_ANNUAL_MIN_TEXT_CHARS = 1_500
LOCAL_ANNUAL_MIN_SIGNAL_HITS = 2
LOCAL_ANNUAL_LONG_SAMPLE_CHARS = 8_000

_FIN_HINTS: tuple[str, ...] = (
    "revenue",
    "profit",
    "income",
    "cash flow",
    "assets",
    "liabilities",
    "equity",
    "ebit",
    "ebitda",
    "dividend",
    "capex",
    "hk$",
    "usd",
    "rmb",
    "cny",
    "%",
)

_MEDIA_EXTENSIONS = (".mp4", ".mov", ".avi", ".m3u8")
_MEDIA_DOMAINS = ("youtube.com", "youtu.be", "vimeo.com")


# ── Public API ────────────────────────────────────────────────────────

def classify_filing_type(title: str, doc_url: str, snippet: str) -> str:
    """Classify a filing candidate into a type category.

    Returns one of: ANNUAL_REPORT, INTERIM_REPORT, REGULATORY_FILING,
    IR_NEWS, OTHER.
    """
    ctx = f"{title.lower()} {doc_url.lower()} {snippet.lower()}"
    ctx_norm = re.sub(r"[-_/]+", " ", ctx)
    url_low = doc_url.lower()

    # Skip media URLs
    if any(d in url_low for d in _MEDIA_DOMAINS) or "watch?v=" in url_low:
        return "OTHER"
    if url_low.endswith(_MEDIA_EXTENSIONS):
        return "OTHER"

    has_press_release = any(
        w in ctx_norm
        for w in (
            "press release",
            "press-release",
            "news release",
            "earnings release",
            "communique",
            "communiqué",
        )
    )
    has_urd_strong = bool(
        re.search(r"\burd\b", ctx_norm)
        or "universal registration document" in ctx_norm
        or "document d'enregistrement universel" in ctx_norm
    )
    has_annual_doc_signal = any(
        w in ctx_norm
        for w in (
            "annual report",
            "registration document",
            "integrated report",
            "integrated annual report",
            "rapport annuel",
        )
    ) or has_urd_strong

    if has_press_release:
        if (
            "results" in ctx_norm
            or "financial" in ctx_norm
            or "earnings" in ctx_norm
        ):
            return "REGULATORY_FILING"
        return "IR_NEWS"

    if has_annual_doc_signal:
        return "ANNUAL_REPORT"
    if any(w in ctx_norm for w in ("interim", "half year", "h1 ", "h2 ")):
        return "INTERIM_REPORT"
    if "rns" in ctx_norm or "regulatory news" in ctx_norm or "announcement" in ctx_norm:
        return "IR_NEWS"
    if any(w in ctx_norm for w in ("results", "financial")):
        return "REGULATORY_FILING"
    return "OTHER"


def financial_signal_hits(text: str) -> tuple[int, list[str]]:
    """Count how many financial keyword signals are present in *text*.

    Returns (count, sorted list of matched hints).
    """
    if not text:
        return 0, []
    normalized = re.sub(r"\s+", " ", text.lower())
    hits = sorted({hint for hint in _FIN_HINTS if hint in normalized})
    return len(hits), hits


def classify_annual_extractability(
    *,
    tipo: str,
    extraction_status: str,
    extraction_reason: str,
    text_chars: int,
    text_sample: str,
) -> tuple[str, str, dict[str, Any]]:
    """Downgrade low-quality local annual filings to non-extractable.

    Returns (new_status, new_reason, quality_meta).
    """
    tipo_up = str(tipo or "").upper().replace(" ", "")
    is_local_annual = tipo_up in {
        "ANNUAL_REPORT", "10-K", "10K", "20-F", "20F", "40-F", "40F",
    }
    if not is_local_annual or extraction_status != "OK":
        return extraction_status, extraction_reason, {}

    signal_hits_count, signal_hits = financial_signal_hits(text_sample)
    sample_len = len(text_sample or "")
    sample_long_enough = sample_len >= LOCAL_ANNUAL_LONG_SAMPLE_CHARS

    if text_chars < LOCAL_ANNUAL_MIN_TEXT_CHARS:
        reason = (
            "Local annual fallback downgraded: extracted text too short "
            f"({text_chars} < {LOCAL_ANNUAL_MIN_TEXT_CHARS})."
        )
        merged_reason = f"{extraction_reason} {reason}".strip()
        return "NON_EXTRACTABLE_LOW_TEXT_ANNUAL", merged_reason, {
            "rejected_low_quality": True,
            "reject_reason": "LOW_TEXT_ANNUAL",
            "signal_hits": signal_hits,
            "signal_hits_count": signal_hits_count,
            "sample_len": sample_len,
            "sample_long_enough": sample_long_enough,
        }

    if signal_hits_count < LOCAL_ANNUAL_MIN_SIGNAL_HITS and not sample_long_enough:
        reason = (
            "Local annual fallback downgraded: insufficient financial signal "
            f"(hits={signal_hits_count} < {LOCAL_ANNUAL_MIN_SIGNAL_HITS}; "
            f"sample_len={sample_len})."
        )
        if signal_hits:
            reason = f"{reason} matched={','.join(signal_hits[:8])}."
        merged_reason = f"{extraction_reason} {reason}".strip()
        return "NON_EXTRACTABLE_LOW_SIGNAL_ANNUAL", merged_reason, {
            "rejected_low_quality": True,
            "reject_reason": "LOW_SIGNAL_ANNUAL",
            "signal_hits": signal_hits,
            "signal_hits_count": signal_hits_count,
            "sample_len": sample_len,
            "sample_long_enough": sample_long_enough,
        }

    return extraction_status, extraction_reason, {
        "rejected_low_quality": False,
        "signal_hits": signal_hits,
        "signal_hits_count": signal_hits_count,
        "sample_len": sample_len,
        "sample_long_enough": sample_long_enough,
    }
