"""Exchange/country awareness — market classification utilities.

Ported from 3_0-ELSIAN-INVEST/scripts/runners/sec_fetcher_v2_runner.py (lines ~50-170, ~297-358).
Provides normalisation and classification functions for exchanges and countries,
used by fetchers to decide acquisition strategy (SEC vs local IR crawling).
"""

from __future__ import annotations

from typing import Optional

# ── Exchange / Country sets ──────────────────────────────────────────

NON_US_EXCHANGES: frozenset[str] = frozenset({
    "LSE", "AIM", "SEHK", "HKEX", "ASX", "EPA", "TSX", "OTRA",
})

NON_US_COUNTRIES: frozenset[str] = frozenset({
    "HK", "GB", "UK", "AU", "FR", "CA", "IL", "ISRAEL", "CN", "JP", "SG", "EU",
})

# ── Filing keyword hints by exchange ─────────────────────────────────

LOCAL_FILING_KEYWORDS_COMMON: tuple[str, ...] = (
    "announcement",
    "results",
    "financial report",
    "interim report",
    "annual report",
    "regulatory",
    "filing",
    "press release",
    "news release",
    "trading update",
    "statement",
)

LOCAL_FILING_KEYWORDS_BY_EXCHANGE: dict[str, tuple[str, ...]] = {
    "SEHK": ("hkex", "announcement", "interim report", "annual report"),
    "HKEX": ("hkex", "announcement", "interim report", "annual report"),
    "LSE": ("rns", "regulatory news service", "annual report", "half year"),
    "AIM": ("rns", "regulatory news service", "annual report", "half year"),
    "ASX": ("asx", "appendix 4e", "appendix 4d", "quarterly activities report"),
    "EPA": ("document d'enregistrement universel", "communiqué", "résultats"),
}

# ── Negative keywords (navigation / non-filing pages) ────────────────

LOCAL_FILING_NEGATIVE: tuple[str, ...] = (
    "privacy",
    "cookie",
    "terms",
    "policy",
    "careers",
    "job",
    "linkedin",
    "twitter.com",
    "facebook.com",
)


# ── Normalisation ────────────────────────────────────────────────────

_COUNTRY_ALIASES: dict[str, str] = {
    "USA": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "AUSTRALIA": "AU",
    "ISRAEL": "IL",
    "FRANCE": "FR",
    "CANADA": "CA",
    "UNITED KINGDOM": "GB",
    "HONG KONG": "HK",
    "CHINA": "CN",
    "JAPAN": "JP",
    "SINGAPORE": "SG",
    "GERMANY": "DE",
    "SWITZERLAND": "CH",
}


def normalize_country(value: Optional[str]) -> Optional[str]:
    """Normalise a country string to a 2-letter ISO code or upper-case form.

    Handles common aliases: USA, UNITED STATES -> US, AUSTRALIA -> AU, etc.
    Returns None for empty/None input.
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    upper = raw.upper()
    return _COUNTRY_ALIASES.get(upper, upper)


def normalize_exchange(value: Optional[str]) -> Optional[str]:
    """Normalise an exchange string to upper-case canonical form.

    E.g. "nyse" -> "NYSE", "otc markets" -> "OTC".
    Returns None for empty/None input.
    """
    if not value:
        return None
    raw = value.strip().upper()
    if not raw:
        return None
    if "OTC" in raw:
        return "OTC"
    return raw


def is_non_us(
    exchange: Optional[str] = None,
    country: Optional[str] = None,
    cik: Optional[str] = None,
) -> bool:
    """Determine whether a company is non-US based on exchange/country/cik.

    Returns True if the company appears to be non-US (i.e. needs local
    IR crawling or non-SEC fetcher).
    """
    if country and country not in {"US", "USA"}:
        return True
    if exchange and exchange in NON_US_EXCHANGES:
        return True
    if cik is None and country not in {"US", "USA"}:
        return True
    return False


def infer_regulator_code(
    exchange: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Infer the regulator code from exchange and country.

    Returns a string like 'HKEX', 'RNS', 'ASX', 'EURONEXT', 'SEDAR+', or
    'LOCAL_IR' as fallback.
    """
    ex = (exchange or "").upper()
    c = (country or "").upper()
    if ex in {"SEHK", "HKEX"} or c == "HK":
        return "HKEX"
    if ex in {"LSE", "AIM"} or c in {"GB", "UK"}:
        return "RNS"
    if ex == "ASX" or c == "AU":
        return "ASX"
    if ex == "EPA" or c == "FR":
        return "EURONEXT"
    if ex == "TSX" or c == "CA":
        return "SEDAR+"
    return "LOCAL_IR"
