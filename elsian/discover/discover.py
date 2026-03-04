"""Auto-discovery of ticker metadata.

Given a ticker symbol (e.g. "AAPL", "TEP.PA", "KAR.AX"), detects exchange,
country, currency, regulator, accounting standard, CIK (SEC), company name,
fiscal year end month, and (optionally) sector.

Usage:
    discoverer = TickerDiscoverer()
    result = discoverer.discover("AAPL")
    case_dict = result.to_case_dict()
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from elsian.markets import (
    normalize_country,
    normalize_exchange,
    infer_regulator_code,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

USER_AGENT = "ELSIAN-INVEST-Bot/4.0 (research; bot@elsian-invest.local)"
SEC_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
YAHOO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}
TIMEOUT = 30
SEC_RATE_LIMIT = 0.12

# Ticker suffix → (exchange, country, source_hint, accounting_standard)
SUFFIX_MAP: dict[str, tuple[str, str, str, str]] = {
    ".PA": ("EPA", "FR", "eu_manual", "IFRS"),
    ".AX": ("ASX", "AU", "asx", "IFRS"),
    ".L":  ("LSE", "GB", "eu_manual", "IFRS"),
    ".HK": ("SEHK", "HK", "eu_manual", "IFRS"),
    ".TO": ("TSX", "CA", "eu_manual", "IFRS"),
    ".T":  ("TSE", "JP", "eu_manual", "IFRS"),
    ".DE": ("XETRA", "DE", "eu_manual", "IFRS"),
    ".AS": ("EPA", "NL", "eu_manual", "IFRS"),
    ".BR": ("EPA", "BE", "eu_manual", "IFRS"),
    ".LS": ("EPA", "PT", "eu_manual", "IFRS"),
    ".SI": ("SGX", "SG", "eu_manual", "IFRS"),
}

# Yahoo Finance suffix for each exchange (for building Yahoo symbol)
YAHOO_SUFFIX: dict[str, str] = {
    "NYSE": "", "NASDAQ": "", "AMEX": "", "US": "",
    "SEHK": ".HK", "HKEX": ".HK",
    "LSE": ".L", "AIM": ".L",
    "EPA": ".PA",
    "XETRA": ".DE", "FRA": ".DE",
    "TSE": ".T",
    "ASX": ".AX",
    "TSX": ".TO",
    "SGX": ".SI",
}

# SIC code → broad sector mapping (top-level divisions)
SIC_SECTOR: dict[str, str] = {
    "01": "Agriculture", "02": "Agriculture", "07": "Agriculture", "09": "Agriculture",
    "10": "Mining", "12": "Mining", "13": "Oil & Gas", "14": "Mining",
    "15": "Construction", "16": "Construction", "17": "Construction",
    "20": "Food & Beverage", "21": "Tobacco", "22": "Textiles", "23": "Apparel",
    "24": "Lumber & Wood", "25": "Furniture", "26": "Paper",
    "27": "Publishing & Printing", "28": "Chemicals & Pharma",
    "29": "Petroleum Refining", "30": "Rubber & Plastics", "31": "Leather",
    "32": "Stone, Clay & Glass", "33": "Primary Metals", "34": "Fabricated Metals",
    "35": "Industrial Machinery", "36": "Electronic Equipment",
    "37": "Transportation Equipment", "38": "Instruments & Measurement",
    "39": "Miscellaneous Manufacturing",
    "40": "Rail Transportation", "41": "Transit", "42": "Trucking & Warehousing",
    "43": "Postal Service", "44": "Water Transportation",
    "45": "Air Transportation", "46": "Pipelines",
    "47": "Transportation Services", "48": "Communications",
    "49": "Utilities",
    "50": "Wholesale - Durables", "51": "Wholesale - Non-durables",
    "52": "Retail - Building Materials", "53": "Retail - General Merchandise",
    "54": "Retail - Food Stores", "55": "Retail - Auto Dealers",
    "56": "Retail - Apparel", "57": "Retail - Furniture",
    "58": "Retail - Eating & Drinking", "59": "Retail - Miscellaneous",
    "60": "Banking", "61": "Credit Institutions", "62": "Securities & Commodities",
    "63": "Insurance", "64": "Insurance Agents", "65": "Real Estate",
    "67": "Holding & Investment",
    "70": "Hotels & Lodging", "72": "Personal Services",
    "73": "Business Services & Technology", "75": "Auto Repair & Services",
    "76": "Miscellaneous Repair", "78": "Motion Pictures",
    "79": "Recreation", "80": "Health Services", "81": "Legal Services",
    "82": "Educational Services", "83": "Social Services",
    "84": "Museums & Gardens", "86": "Membership Organizations",
    "87": "Engineering & Accounting", "89": "Services NEC",
    "91": "Government - Executive", "92": "Government - Legislative",
    "93": "Government - Finance", "94": "Government - Human Resources",
    "95": "Government - Environmental", "96": "Government - Economic",
    "97": "Government - National Security", "99": "Non-classifiable",
}


# ── Data model ───────────────────────────────────────────────────────

@dataclass
class DiscoveryResult:
    """Result of ticker auto-discovery."""

    ticker: str = ""
    company_name: str | None = None
    exchange: str | None = None
    country: str | None = None
    currency: str | None = None
    source_hint: str | None = None
    accounting_standard: str | None = None
    cik: str | None = None
    web_ir: str | None = None
    fiscal_year_end_month: int | None = None
    sector: str | None = None
    period_scope: str = "ANNUAL_ONLY"
    warnings: list[str] = field(default_factory=list)

    def to_case_dict(self) -> dict[str, Any]:
        """Serialize to a case.json-compatible dict.

        Omits None values. Includes _discovery_warnings if any.
        """
        d: dict[str, Any] = {"ticker": self.ticker}
        optional_keys = [
            "company_name", "exchange", "country", "currency", "source_hint",
            "accounting_standard", "cik", "web_ir", "fiscal_year_end_month",
            "sector", "period_scope",
        ]
        for key in optional_keys:
            val = getattr(self, key)
            if val is not None:
                d[key] = val
        if self.warnings:
            d["_discovery_warnings"] = self.warnings
        return d


# ── HTTP helpers ─────────────────────────────────────────────────────

class _HttpClient:
    """Minimal rate-limited HTTP client for discovery requests."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._last_sec_req = 0.0

    def sec_get(self, url: str, **kwargs: Any) -> requests.Response:
        """GET with SEC rate limiting and headers."""
        elapsed = time.time() - self._last_sec_req
        if elapsed < SEC_RATE_LIMIT:
            time.sleep(SEC_RATE_LIMIT - elapsed)
        self._last_sec_req = time.time()
        resp = self._session.get(
            url, headers=SEC_HEADERS, timeout=TIMEOUT, **kwargs,
        )
        resp.raise_for_status()
        return resp

    def sec_get_json(self, url: str) -> dict[str, Any]:
        """GET JSON from SEC EDGAR."""
        return self.sec_get(url).json()

    def yahoo_get_json(self, url: str) -> dict[str, Any]:
        """GET JSON from Yahoo Finance (no rate limiting needed)."""
        resp = self._session.get(
            url, headers=YAHOO_HEADERS, timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


# ── Ticker suffix parsing ────────────────────────────────────────────

def parse_ticker_suffix(ticker: str) -> tuple[str, str | None]:
    """Split a ticker into (base_ticker, suffix_or_None).

    Examples:
        "AAPL"    → ("AAPL", None)
        "TEP.PA"  → ("TEP", ".PA")
        "KAR.AX"  → ("KAR", ".AX")
        "3988.HK" → ("3988", ".HK")
    """
    m = re.match(r"^(.+?)(\.[A-Z]{1,3})$", ticker, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2).upper()
    return ticker, None


def suffix_to_exchange_info(suffix: str) -> tuple[str, str, str, str] | None:
    """Map a ticker suffix to (exchange, country, source_hint, accounting_standard).

    Returns None if the suffix is not recognized.
    """
    return SUFFIX_MAP.get(suffix.upper())


# ── SEC Discovery ────────────────────────────────────────────────────

def _discover_sec(client: _HttpClient, ticker: str) -> DiscoveryResult:
    """Discover metadata for a US-listed ticker via SEC EDGAR.

    Steps:
    1. Resolve CIK from company_tickers.json
    2. Fetch submissions for the CIK → company_name, SIC, fiscal year end,
       exchange, form type (10-K vs 20-F).
    """
    result = DiscoveryResult(ticker=ticker, source_hint="sec")

    # Step 1: Resolve CIK
    try:
        ticker_map = client.sec_get_json(
            "https://www.sec.gov/files/company_tickers.json"
        )
    except Exception as exc:
        result.warnings.append(f"Failed to fetch SEC company_tickers.json: {exc}")
        return result

    cik_int: int | None = None
    sec_exchange: str | None = None
    for val in ticker_map.values():
        if str(val.get("ticker", "")).upper() == ticker.upper():
            cik_int = int(val["cik_str"])
            sec_exchange = val.get("exchange")
            break

    if cik_int is None:
        result.warnings.append(f"Ticker {ticker} not found in SEC company_tickers.json")
        return result

    cik10 = str(cik_int).zfill(10)
    result.cik = str(cik_int)

    # Step 2: Fetch submissions
    try:
        sub = client.sec_get_json(
            f"https://data.sec.gov/submissions/CIK{cik10}.json"
        )
    except Exception as exc:
        result.warnings.append(f"Failed to fetch SEC submissions: {exc}")
        return result

    # Company name
    result.company_name = sub.get("name")

    # Exchange
    exchanges_raw = sub.get("exchanges", [])
    exchange_val = sec_exchange or (exchanges_raw[0] if exchanges_raw else None)
    if exchange_val:
        result.exchange = normalize_exchange(exchange_val)

    # Country / state
    state_country = sub.get("stateOfIncorporation", "")
    addresses = sub.get("addresses", {})
    mailing = addresses.get("mailing", {}) or addresses.get("business", {})
    country_raw = mailing.get("stateOrCountry", "")

    if country_raw and len(country_raw) > 2:
        result.country = normalize_country(country_raw)
    elif country_raw and len(country_raw) == 2:
        # SEC uses 2-letter state codes for US companies, country codes for foreign
        if country_raw.upper() in (
            "CA", "NY", "TX", "FL", "IL", "WA", "MA", "PA", "NJ", "GA",
            "OH", "VA", "NC", "MI", "CO", "AZ", "MN", "CT", "MD", "OR",
            "WI", "IN", "MO", "TN", "SC", "AL", "KY", "LA", "UT", "OK",
            "NE", "NM", "KS", "NV", "AR", "MS", "IA", "HI", "ID", "ME",
            "NH", "RI", "MT", "DE", "SD", "ND", "AK", "VT", "WV", "WY",
            "DC", "PR", "VI", "GU",
        ):
            result.country = "US"
        else:
            result.country = normalize_country(country_raw)
    else:
        result.country = "US"

    # SIC code → sector
    sic = sub.get("sic", "")
    if sic and len(sic) >= 2:
        sic_prefix = sic[:2]
        result.sector = SIC_SECTOR.get(sic_prefix)

    # Fiscal year end month
    fy_end = sub.get("fiscalYearEnd", "")
    if fy_end and len(fy_end) == 4:
        # Format is "MMDD"
        try:
            result.fiscal_year_end_month = int(fy_end[:2])
        except ValueError:
            result.fiscal_year_end_month = 12
    else:
        result.fiscal_year_end_month = 12

    # Currency: USD for US companies
    result.currency = "USD"

    # Accounting standard: detect from form types
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    has_20f = any(f.strip() in ("20-F", "20-F/A") for f in forms[:20])
    has_10k = any(f.strip() in ("10-K", "10-K/A") for f in forms[:20])
    has_40f = any(f.strip() in ("40-F", "40-F/A") for f in forms[:20])

    if has_20f:
        # 20-F filers are typically foreign private issuers using IFRS
        # (but some use US-GAAP — we default to IFRS as more common)
        result.accounting_standard = "IFRS"
    elif has_40f:
        # 40-F is Canadian companies, typically IFRS
        result.accounting_standard = "IFRS"
    elif has_10k:
        result.accounting_standard = "US-GAAP"
    else:
        result.accounting_standard = "US-GAAP"  # default for SEC filers

    # Web IR: try common patterns
    website = sub.get("website", "")
    if website:
        # Normalize: strip trailing slash
        website = website.rstrip("/")
        if not website.startswith("http"):
            website = f"https://{website}"
        result.web_ir = website

    return result


# ── Non-US Discovery ─────────────────────────────────────────────────

def _discover_non_us(
    client: _HttpClient,
    ticker: str,
    base_ticker: str,
    suffix: str,
) -> DiscoveryResult:
    """Discover metadata for a non-US ticker via suffix parsing + Yahoo Finance.

    Steps:
    1. Parse suffix → exchange, country, source_hint, accounting_standard
    2. Use Yahoo Finance chart API for company_name, currency, exchange
    3. Use Yahoo Finance quoteSummary for sector, industry, country if available
    """
    info = suffix_to_exchange_info(suffix)
    if info:
        exchange, country, source_hint, acct_std = info
    else:
        exchange, country, source_hint, acct_std = "UNKNOWN", "UNKNOWN", "eu_manual", "IFRS"

    result = DiscoveryResult(
        ticker=base_ticker,
        exchange=exchange,
        country=country,
        source_hint=source_hint,
        accounting_standard=acct_std,
        period_scope="ANNUAL_ONLY",
    )

    # Yahoo Finance chart API for basic metadata
    yahoo_symbol = f"{base_ticker}{suffix}"
    chart_url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{yahoo_symbol}?range=5d&interval=1d"
    )
    try:
        data = client.yahoo_get_json(chart_url)
        chart_result = data.get("chart", {}).get("result", [])
        if chart_result:
            meta = chart_result[0].get("meta", {})
            result.company_name = (
                meta.get("shortName") or meta.get("longName") or base_ticker
            )
            result.currency = meta.get("currency", result.currency)
            yahoo_exchange = meta.get("exchangeName")
            if yahoo_exchange:
                result.exchange = normalize_exchange(yahoo_exchange) or result.exchange
        else:
            result.warnings.append(
                f"Yahoo Finance chart returned no results for {yahoo_symbol}"
            )
    except Exception as exc:
        result.warnings.append(f"Yahoo Finance chart API failed: {exc}")

    # Yahoo Finance quoteSummary for sector/industry/fiscal year (best-effort)
    try:
        summary = _fetch_yahoo_summary_minimal(client, yahoo_symbol)
        if summary.get("sector"):
            result.sector = summary["sector"]
        # Only use Yahoo's country if suffix didn't already provide one
        if summary.get("country") and not info:
            result.country = normalize_country(summary["country"]) or result.country
        fiscal_month = summary.get("fiscal_year_end_month")
        if fiscal_month:
            result.fiscal_year_end_month = fiscal_month
        else:
            result.fiscal_year_end_month = result.fiscal_year_end_month or 12
    except Exception as exc:
        result.warnings.append(f"Yahoo Finance summary API failed: {exc}")
        if result.fiscal_year_end_month is None:
            result.fiscal_year_end_month = 12

    # If currency still not set
    if not result.currency:
        # Infer from country
        currency_by_country: dict[str, str] = {
            "US": "USD", "GB": "GBP", "FR": "EUR", "DE": "EUR",
            "NL": "EUR", "BE": "EUR", "PT": "EUR", "AU": "AUD",
            "HK": "HKD", "JP": "JPY", "CA": "CAD", "SG": "SGD",
        }
        result.currency = currency_by_country.get(result.country or "", "USD")

    return result


def _fetch_yahoo_summary_minimal(
    client: _HttpClient,
    yahoo_symbol: str,
) -> dict[str, Any]:
    """Fetch sector, country, fiscal year end from Yahoo quoteSummary.

    Uses crumb authentication. Returns partial dict — caller should
    handle missing keys gracefully.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    try:
        session.get("https://fc.yahoo.com", timeout=10, allow_redirects=True)
    except Exception:
        pass  # Expected — sets cookies even on error

    crumb: str | None = None
    try:
        crumb_resp = session.get(
            "https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=10,
        )
        crumb_text = crumb_resp.text.strip()
        if crumb_text and len(crumb_text) < 50:
            crumb = crumb_text
    except Exception:
        pass

    if not crumb:
        return {}

    from urllib.parse import quote_plus

    url = (
        f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{quote_plus(yahoo_symbol)}"
        f"?modules=summaryProfile,assetProfile&crumb={quote_plus(crumb)}"
    )
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("quoteSummary", {}).get("result", [])
        if not results:
            return {}

        modules = results[0]
        profile = modules.get("assetProfile", {}) or modules.get("summaryProfile", {})
        out: dict[str, Any] = {}
        if profile.get("sector"):
            out["sector"] = profile["sector"]
        if profile.get("country"):
            out["country"] = profile["country"]
        # Fiscal year end: assetProfile.fiscalYearEnd field
        # It comes as a month name or we can parse from other fields
        fy_end = profile.get("fiscalYearEnd")
        if fy_end:
            month_map = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            m = month_map.get(str(fy_end).lower())
            if m:
                out["fiscal_year_end_month"] = m
        return out
    except Exception:
        return {}


# ── Main class ───────────────────────────────────────────────────────

class TickerDiscoverer:
    """Auto-discovers ticker metadata for case.json generation.

    Detects exchange, country, currency, regulator, accounting standard,
    CIK (SEC), company name, fiscal year end month, and sector.

    Usage:
        discoverer = TickerDiscoverer()
        result = discoverer.discover("AAPL")
        case_dict = result.to_case_dict()

        result = discoverer.discover("TEP.PA")
        case_dict = result.to_case_dict()
    """

    def __init__(self, client: _HttpClient | None = None) -> None:
        self._client = client or _HttpClient()

    def discover(self, ticker: str) -> DiscoveryResult:
        """Discover metadata for a ticker symbol.

        Args:
            ticker: Ticker symbol, optionally with exchange suffix
                    (e.g. "AAPL", "TEP.PA", "KAR.AX", "3988.HK").

        Returns:
            DiscoveryResult with all discovered metadata and any warnings.
        """
        base_ticker, suffix = parse_ticker_suffix(ticker)

        if suffix and suffix.upper() in SUFFIX_MAP:
            # Non-US ticker with known suffix
            return _discover_non_us(self._client, ticker, base_ticker, suffix)
        elif suffix:
            # Unknown suffix — try SEC first, fallback to non-US
            result = _discover_sec(self._client, base_ticker)
            if result.cik:
                return result
            # SEC didn't find it — treat as non-US with unknown suffix
            result = _discover_non_us(self._client, ticker, base_ticker, suffix)
            result.warnings.append(
                f"Suffix {suffix} not in known exchange map; metadata may be incomplete"
            )
            return result
        else:
            # No suffix — assume US, try SEC
            result = _discover_sec(self._client, base_ticker)
            if result.cik:
                return result
            # SEC didn't find it — try Yahoo Finance as fallback
            result.warnings.append(
                f"Ticker {base_ticker} not found in SEC EDGAR; trying Yahoo Finance"
            )
            yahoo_result = _discover_non_us(
                self._client, ticker, base_ticker, "",
            )
            # Merge: keep SEC warnings
            yahoo_result.warnings = result.warnings + yahoo_result.warnings
            return yahoo_result
