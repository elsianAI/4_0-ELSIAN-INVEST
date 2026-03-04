"""Market data snapshot fetcher for ELSIAN 4.0.

Retrieves price, market cap, volume, 52-week range and key ratios from
Finviz (US equities), Stooq (OHLCV history), and Yahoo Finance (non-US fallback).

Ported from 3_0-ELSIAN-INVEST/scripts/runners/market_data_v1_runner.py per DEC-009.

Usage via CLI:
    python3 -m elsian.cli market TZOO
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from elsian.markets import normalize_exchange, is_non_us

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

HEADERS: dict[str, str] = {
    "User-Agent": "ELSIAN-INVEST-Bot/4.0 (research; bot@elsian-invest.local)",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
TIMEOUT: int = 45

# Stooq exchange suffixes (lower-case)
STOOQ_SUFFIX: dict[str, str] = {
    "NYSE": ".us", "NASDAQ": ".us", "AMEX": ".us", "US": ".us",
    "SEHK": ".hk", "HKEX": ".hk",
    "LSE": ".uk", "AIM": ".uk",
    "EPA": ".fr",
    "XETRA": ".de", "FRA": ".de",
    "TSE": ".jp",
    "ASX": ".au",
    "TSX": ".ca",
}

# Yahoo Finance ticker suffixes
YAHOO_SUFFIX: dict[str, str] = {
    "NYSE": "", "NASDAQ": "", "AMEX": "", "US": "",
    "SEHK": ".HK", "HKEX": ".HK",
    "LSE": ".L", "AIM": ".L",
    "EPA": ".PA",
    "XETRA": ".DE", "FRA": ".DE",
    "TSE": ".T",
    "ASX": ".AX",
    "TSX": ".TO",
}

US_EXCHANGES: frozenset[str] = frozenset({"NYSE", "NASDAQ", "AMEX", "US", ""})

EURONEXT_SUFFIX_BY_COUNTRY: dict[str, str] = {
    "FR": ".PA",
    "NL": ".AS",
    "BE": ".BR",
    "PT": ".LS",
}


# ── Data model ───────────────────────────────────────────────────────

@dataclass
class MarketData:
    """Market data snapshot for a single ticker.

    Monetary values that represent large numbers (market_cap, shares_outstanding)
    are stored in millions.
    """

    ticker: str = ""
    price: float | None = None
    prev_close: float | None = None
    market_cap: float | None = None  # in millions
    shares_outstanding: float | None = None  # in millions
    volume: int | None = None
    avg_volume_30d: int | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    beta: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    dividend_yield: float | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"
    exchange: str | None = None
    country: str | None = None
    target_price: float | None = None
    institutional_ownership: float | None = None
    insider_ownership: float | None = None
    company_name: str | None = None
    fetched_at: str = ""  # ISO timestamp
    source: str = ""  # e.g. "finviz+stooq", "yahoo+stooq"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict, omitting None values."""
        d: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "" and v != 0:
                d[k] = v
            elif k in ("ticker", "currency"):
                d[k] = v
        return d


# ── Helper functions ─────────────────────────────────────────────────

def to_float(value: str | None) -> float | None:
    """Convert a string to float, handling K/M/B/T suffixes, %, commas, N/A.

    Args:
        value: Raw string value like "1.5B", "42.3M", "1,234.56", "N/A",
               "-12.5%", None.

    Returns:
        Parsed float or None if unparseable.
    """
    if value is None:
        return None
    s = value.strip()
    if not s or s.upper() in {"N/A", "-", "—", "N/A\nN/A"}:
        return None
    s = s.replace(",", "")
    if s.endswith("%"):
        try:
            return float(s[:-1])
        except ValueError:
            return None
    m = re.match(r"^([-+]?[0-9]*\.?[0-9]+)\s*([KMBT])$", s, re.IGNORECASE)
    if m:
        num = float(m.group(1))
        unit = m.group(2).upper()
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[unit]
        return num * mult
    try:
        return float(s)
    except ValueError:
        return None


def parse_finviz_table(soup: BeautifulSoup) -> dict[str, str]:
    """Parse Finviz snapshot-table2 into a key→value dict.

    Args:
        soup: BeautifulSoup of the Finviz quote page.

    Returns:
        Dict of label→value pairs from the snapshot table.
    """
    table = soup.find("table", class_="snapshot-table2")
    if not table:
        return {}
    cells = [td.get_text(" ", strip=True) for td in table.find_all("td")]
    values: dict[str, str] = {}
    for i in range(0, len(cells) - 1, 2):
        key = cells[i]
        val = cells[i + 1]
        if key:
            values[key] = val
    return values


def rolling_avg_volume(rows: list[dict[str, str]], n: int = 30) -> int | None:
    """Compute rolling average volume over last *n* trading days.

    Args:
        rows: OHLCV rows (dicts with "Volume" key).
        n: Number of trailing days.

    Returns:
        Average volume as int, or None.
    """
    if not rows:
        return None
    tail = rows[-n:] if len(rows) >= n else rows
    vols: list[float] = []
    for r in tail:
        try:
            vols.append(float(r["Volume"]))
        except (ValueError, KeyError, TypeError):
            continue
    if not vols:
        return None
    return round(sum(vols) / len(vols))


def max_min_52w(rows: list[dict[str, str]]) -> tuple[float | None, float | None]:
    """Compute 52-week high and low from OHLCV rows.

    Args:
        rows: OHLCV rows (dicts with "Close" key).

    Returns:
        (high, low) tuple, or (None, None) if no data.
    """
    if not rows:
        return None, None
    tail = rows[-252:] if len(rows) >= 252 else rows
    closes: list[float] = []
    for r in tail:
        try:
            closes.append(float(r["Close"]))
        except (ValueError, KeyError, TypeError):
            continue
    if not closes:
        return None, None
    return max(closes), min(closes)


def _get_with_retry(
    url: str,
    session: requests.Session | None = None,
    timeout: int = TIMEOUT,
) -> requests.Response:
    """GET with 1 retry on 429/5xx or connection errors (3s backoff).

    Args:
        url: Target URL.
        session: Optional requests.Session (uses default if None).
        timeout: Request timeout in seconds.

    Returns:
        requests.Response on success.

    Raises:
        requests.exceptions.HTTPError: On non-retryable HTTP errors.
        requests.exceptions.ConnectionError: On persistent connection failure.
    """
    requester = session or requests
    try:
        resp = requester.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        if status in (429, 500, 502, 503, 504) or isinstance(
            exc, requests.exceptions.ConnectionError
        ):
            time.sleep(3)
            resp = requester.get(
                url, headers=HEADERS, timeout=timeout, allow_redirects=True
            )
            resp.raise_for_status()
            return resp
        raise


# ── Data source fetchers ─────────────────────────────────────────────

def _fetch_finviz(ticker: str) -> dict[str, Any]:
    """Fetch snapshot data from Finviz (US equities only).

    Args:
        ticker: US stock ticker (e.g. "TZOO").

    Returns:
        Dict with keys: url, company_name, sector, industry, country,
        exchange, snapshot (dict of label→value).
    """
    url = f"https://finviz.com/quote.ashx?t={quote_plus(ticker)}&p=d"
    resp = _get_with_retry(url)
    resp.encoding = resp.encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    company_node = soup.select_one(".quote-header_left h2")
    company_name = company_node.get_text(" ", strip=True) if company_node else ticker

    # Parse quote-links for sector, industry, country, exchange
    box = soup.select_one(".quote-links")
    sector = industry = country = exchange_val = None
    if box:
        text = box.get_text(" ", strip=True)
        parts = [p.strip() for p in text.split("•")]
        clean = [p for p in parts if p and p.lower() not in {"chart", "stock detail"}]
        if len(clean) >= 4:
            sector, industry, country, exchange_val = clean[0], clean[1], clean[2], clean[3]

    snap = parse_finviz_table(soup)

    return {
        "url": url,
        "company_name": company_name,
        "sector": sector,
        "industry": industry,
        "country": country,
        "exchange": exchange_val,
        "snapshot": snap,
    }


def _fetch_stooq_ohlcv(ticker: str, exchange: str = "US") -> list[dict[str, str]]:
    """Fetch daily OHLCV from Stooq.

    Args:
        ticker: Stock ticker.
        exchange: Exchange code for suffix mapping (e.g. "NASDAQ", "LSE").

    Returns:
        List of dicts with Date, Close, Volume (+ other OHLCV keys).
    """
    suffix = STOOQ_SUFFIX.get(exchange.upper(), ".us")
    sym = f"{ticker.lower()}{suffix}"
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    try:
        resp = _get_with_retry(url)
    except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
        return []
    text = resp.text.strip()
    if not text or "No data" in text:
        return []
    rows = list(csv.DictReader(io.StringIO(text)))
    return [r for r in rows if r.get("Date") and r.get("Close")]


def _fetch_yahoo_chart(
    ticker: str,
    exchange: str,
    symbol_override: str | None = None,
) -> dict[str, Any]:
    """Fetch basic quote data from Yahoo Finance v8 chart API.

    Args:
        ticker: Stock ticker.
        exchange: Exchange code for suffix mapping.
        symbol_override: Explicit Yahoo symbol (skips suffix resolution).

    Returns:
        Dict with url, symbol, company_name, snapshot, currency, exchange, etc.
    """
    suffix = YAHOO_SUFFIX.get(exchange.upper(), "")
    sym = symbol_override or f"{ticker}{suffix}"
    chart_url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote_plus(sym)}?range=5d&interval=1d"
    )
    empty: dict[str, Any] = {
        "url": f"https://finance.yahoo.com/quote/{quote_plus(sym)}",
        "symbol": sym,
        "company_name": ticker,
        "sector": None,
        "industry": None,
        "country": None,
        "exchange": exchange,
        "snapshot": {},
        "currency": "USD",
        "instrument_type": None,
    }
    try:
        resp = _get_with_retry(chart_url)
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return empty
        meta = result[0].get("meta", {})
        snap: dict[str, str] = {}
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        volume = meta.get("regularMarketVolume")
        if price is not None:
            snap["Price"] = str(price)
        if prev is not None:
            snap["Prev Close"] = str(prev)
        if volume is not None:
            snap["Volume"] = str(int(volume))
        return {
            "url": f"https://finance.yahoo.com/quote/{quote_plus(sym)}",
            "symbol": sym,
            "company_name": meta.get("shortName") or meta.get("longName") or ticker,
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": meta.get("exchangeName") or exchange,
            "snapshot": snap,
            "currency": meta.get("currency", "USD"),
            "instrument_type": meta.get("instrumentType"),
        }
    except Exception:
        return empty


def _get_yahoo_crumb_session() -> tuple[str | None, requests.Session]:
    """Obtain a Yahoo Finance crumb + authenticated session.

    Yahoo's quoteSummary endpoint requires a crumb token obtained via cookie.
    Steps: 1) hit fc.yahoo.com to get cookies, 2) fetch crumb from /v1/test/getcrumb.

    Returns:
        (crumb_string_or_None, session).
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    try:
        session.get("https://fc.yahoo.com", timeout=15, allow_redirects=True)
    except Exception:
        pass  # Expected — sets cookies even on error
    try:
        crumb_resp = session.get(
            "https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=15
        )
        crumb = crumb_resp.text.strip()
        if crumb and len(crumb) < 50:
            return crumb, session
    except Exception:
        pass
    return None, session


def _fetch_yahoo_summary(
    ticker: str,
    exchange: str,
    symbol_override: str | None = None,
) -> dict[str, Any]:
    """Fetch market cap, shares, sector/industry from Yahoo quoteSummary.

    The v8/chart endpoint only returns price/volume. This endpoint provides
    richer fundamental data (market cap, shares outstanding, sector).
    Requires crumb authentication (cookie + crumb token).

    Args:
        ticker: Stock ticker.
        exchange: Exchange code.
        symbol_override: Explicit Yahoo symbol.

    Returns:
        Dict with market_cap, shares_outstanding, sector, industry, country
        (only populated keys).
    """
    suffix = YAHOO_SUFFIX.get(exchange.upper(), "")
    sym = symbol_override or f"{ticker}{suffix}"

    crumb, session = _get_yahoo_crumb_session()
    if not crumb:
        return {}

    url = (
        f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{quote_plus(sym)}?modules=price,summaryProfile&crumb={quote_plus(crumb)}"
    )
    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        result_data = data.get("quoteSummary", {}).get("result", [])
        if not result_data:
            return {}
        modules = result_data[0]

        price_mod = modules.get("price", {})
        profile_mod = modules.get("summaryProfile", {})

        out: dict[str, Any] = {}

        mcap_raw = price_mod.get("marketCap", {})
        mcap = mcap_raw.get("raw") if isinstance(mcap_raw, dict) else None
        if mcap is not None:
            out["market_cap"] = mcap

        shares_raw = price_mod.get("sharesOutstanding", {})
        shares = shares_raw.get("raw") if isinstance(shares_raw, dict) else None
        if shares is not None:
            out["shares_outstanding"] = shares

        if profile_mod.get("sector"):
            out["sector"] = profile_mod["sector"]
        if profile_mod.get("industry"):
            out["industry"] = profile_mod["industry"]
        if profile_mod.get("country"):
            out["country"] = profile_mod["country"]

        return out
    except Exception:
        return {}


def _build_yahoo_candidates(
    ticker: str,
    exchange: str,
    country: str = "",
) -> list[str]:
    """Build ordered list of Yahoo symbol candidates for non-US equities.

    For Euronext, tries country-preferred suffix first, then other Euronext
    suffixes, then bare ticker.

    Args:
        ticker: Stock ticker.
        exchange: Exchange code (e.g. "EURONEXT", "LSE").
        country: Country hint (e.g. "FR", "NL").

    Returns:
        Deduplicated list of Yahoo symbol candidates.
    """
    candidates: list[str] = []
    ex = (exchange or "").upper()
    c = (country or "").upper()

    if ex == "EURONEXT":
        # Country-preferred suffix first
        if c in EURONEXT_SUFFIX_BY_COUNTRY:
            preferred = EURONEXT_SUFFIX_BY_COUNTRY[c]
            others = [s for cc, s in EURONEXT_SUFFIX_BY_COUNTRY.items() if cc != c]
            suffixes = [preferred] + others
        else:
            suffixes = [".PA", ".AS", ".BR", ".LS"]
        for suffix in suffixes:
            candidates.append(f"{ticker}{suffix}")
    else:
        suffix = YAHOO_SUFFIX.get(ex, "")
        if suffix:
            candidates.append(f"{ticker}{suffix}")

    candidates.append(ticker)

    # Deduplicate preserving order
    seen: set[str] = set()
    out: list[str] = []
    for sym in candidates:
        if sym and sym not in seen:
            out.append(sym)
            seen.add(sym)
    return out


def _select_yahoo_symbol(
    ticker: str,
    exchange: str,
    country: str = "",
) -> tuple[dict[str, Any], str | None]:
    """Resolve best Yahoo symbol for non-US equities.

    Tries each candidate from _build_yahoo_candidates() via _fetch_yahoo_chart(),
    preferring EQUITY instrument types with a price.

    Args:
        ticker: Stock ticker.
        exchange: Exchange code.
        country: Country hint.

    Returns:
        (yahoo_context_dict, selected_symbol_or_None).
    """
    candidates = _build_yahoo_candidates(ticker, exchange, country=country)
    fallback_ctx: dict[str, Any] | None = None
    fallback_sym: str | None = None

    for sym in candidates:
        ctx = _fetch_yahoo_chart(ticker, exchange, symbol_override=sym)
        inst = str(ctx.get("instrument_type") or "").upper()
        has_price = bool((ctx.get("snapshot") or {}).get("Price"))

        if inst == "EQUITY" and has_price:
            return ctx, sym

        if inst == "EQUITY" and fallback_ctx is None:
            fallback_ctx = ctx
            fallback_sym = sym

    if fallback_ctx is not None:
        return fallback_ctx, fallback_sym

    return {
        "url": "",
        "symbol": None,
        "company_name": ticker,
        "sector": None,
        "industry": None,
        "country": country or None,
        "exchange": exchange or "UNKNOWN",
        "snapshot": {},
        "currency": "USD",
        "instrument_type": None,
    }, None


# ── Orchestrator class ───────────────────────────────────────────────

class MarketDataFetcher:
    """Fetches market data from Finviz, Yahoo, and Stooq.

    Not a Fetcher(ABC) — market data is not a Filing. This is a standalone
    class with a single ``fetch()`` method.

    Example::

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TZOO", exchange="NASDAQ")
        print(md.to_dict())
    """

    def fetch(
        self,
        ticker: str,
        exchange: str | None = None,
        country: str | None = None,
    ) -> MarketData:
        """Fetch market data for a ticker.

        Orchestration:
          - US (exchange in NYSE/NASDAQ/AMEX/US/""): Finviz primary, Yahoo fallback.
          - Non-US: Yahoo primary with symbol resolution.
          - Always tries Stooq for OHLCV analytics.

        Args:
            ticker: Stock ticker (e.g. "TZOO", "TEP").
            exchange: Exchange code (e.g. "NASDAQ", "EPA"). Auto-detects US if None.
            country: Country hint (e.g. "US", "FR").

        Returns:
            MarketData instance populated with available data.
        """
        ticker = ticker.upper().strip()
        ex = normalize_exchange(exchange) or ""
        c = (country or "").upper().strip()

        now_iso = (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        use_us = ex in US_EXCHANGES and not is_non_us(exchange=ex, country=c)

        # ── Snapshot data ────────────────────────────────────────
        ctx: dict[str, Any]
        currency = "USD"
        source_label = ""
        selected_symbol: str | None = ticker

        if use_us:
            try:
                ctx = _fetch_finviz(ticker)
                source_label = "finviz"
            except Exception as exc:
                logger.warning("Finviz failed for %s: %s — falling back to Yahoo", ticker, exc)
                ctx = _fetch_yahoo_chart(ticker, ex)
                source_label = "yahoo"
            currency = "USD"
        else:
            ctx, selected_symbol = _select_yahoo_symbol(ticker, ex, country=c)
            currency = ctx.get("currency", "USD")
            source_label = "yahoo"

            # Enrich with quoteSummary for market_cap, shares, sector/industry
            if selected_symbol:
                summary = _fetch_yahoo_summary(ticker, ex, symbol_override=selected_symbol)
                snap = ctx.get("snapshot", {})
                if summary.get("market_cap") and "Market Cap" not in snap:
                    snap["Market Cap"] = str(summary["market_cap"])
                if summary.get("shares_outstanding") and "Shs Outstand" not in snap:
                    snap["Shs Outstand"] = str(summary["shares_outstanding"])
                if summary.get("sector") and ctx.get("sector") is None:
                    ctx["sector"] = summary["sector"]
                if summary.get("industry") and ctx.get("industry") is None:
                    ctx["industry"] = summary["industry"]
                if summary.get("country") and ctx.get("country") is None:
                    ctx["country"] = summary["country"]
                ctx["snapshot"] = snap

            # Handle GBp (pence sterling) → GBP conversion for LSE stocks
            if currency == "GBp":
                snap = ctx.get("snapshot", {})
                for key in ("Price", "Prev Close"):
                    if key in snap:
                        try:
                            snap[key] = str(float(snap[key]) / 100)
                        except (ValueError, TypeError):
                            pass
                currency = "GBP"

        snapshot = ctx.get("snapshot", {})

        # ── OHLCV history ────────────────────────────────────────
        stooq_exchange = ex if ex else "US"
        stooq_rows = _fetch_stooq_ohlcv(ticker, stooq_exchange)

        if not stooq_rows and not use_us:
            # Fallback: try Yahoo chart for OHLCV (1y range)
            stooq_rows = self._yahoo_ohlcv_fallback(ticker, ex)

        source_label += "+stooq" if stooq_rows else ""

        # ── Extract values ───────────────────────────────────────
        price = to_float(snapshot.get("Price"))
        prev_close = to_float(snapshot.get("Prev Close"))
        market_cap_raw = to_float(snapshot.get("Market Cap"))
        shares_raw = to_float(snapshot.get("Shs Outstand"))

        # Fallback: compute missing market_cap or shares from the other + price
        if market_cap_raw is None and price is not None and shares_raw is not None:
            market_cap_raw = price * shares_raw
        elif shares_raw is None and price is not None and price > 0 and market_cap_raw is not None:
            shares_raw = market_cap_raw / price

        market_cap_m = round(market_cap_raw / 1_000_000, 2) if market_cap_raw is not None else None
        shares_m = round(shares_raw / 1_000_000, 4) if shares_raw is not None else None

        vol_last_raw = to_float(snapshot.get("Volume"))
        vol_last = int(vol_last_raw) if vol_last_raw is not None else None
        vol_avg30 = rolling_avg_volume(stooq_rows, 30)

        high_52w, low_52w = max_min_52w(stooq_rows)
        if high_52w is not None:
            high_52w = round(high_52w, 4)
        if low_52w is not None:
            low_52w = round(low_52w, 4)

        beta = to_float(snapshot.get("Beta"))
        pe = to_float(snapshot.get("P/E"))
        pb = to_float(snapshot.get("P/B"))
        target = to_float(snapshot.get("Target Price"))
        inst_own = to_float(snapshot.get("Inst Own"))
        insider_own = to_float(snapshot.get("Insider Own"))
        div_yield = to_float(snapshot.get("Dividend %"))

        return MarketData(
            ticker=ticker,
            price=price,
            prev_close=prev_close,
            market_cap=market_cap_m,
            shares_outstanding=shares_m,
            volume=vol_last,
            avg_volume_30d=vol_avg30,
            high_52w=high_52w,
            low_52w=low_52w,
            beta=beta,
            pe_ratio=pe,
            pb_ratio=pb,
            dividend_yield=div_yield,
            sector=ctx.get("sector"),
            industry=ctx.get("industry"),
            currency=currency,
            exchange=ctx.get("exchange") or ex or None,
            country=ctx.get("country") or c or None,
            target_price=target,
            institutional_ownership=inst_own,
            insider_ownership=insider_own,
            company_name=ctx.get("company_name", ticker),
            fetched_at=now_iso,
            source=source_label,
        )

    @staticmethod
    def _yahoo_ohlcv_fallback(ticker: str, exchange: str) -> list[dict[str, str]]:
        """Try Yahoo Finance chart API for 1-year OHLCV as Stooq fallback.

        Args:
            ticker: Stock ticker.
            exchange: Exchange code.

        Returns:
            List of OHLCV row dicts compatible with rolling_avg_volume/max_min_52w.
        """
        suffix = YAHOO_SUFFIX.get(exchange.upper(), "") if exchange else ""
        sym = f"{ticker}{suffix}"
        rows: list[dict[str, str]] = []
        try:
            chart_url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/"
                f"{quote_plus(sym)}?range=1y&interval=1d"
            )
            resp = _get_with_retry(chart_url)
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                ts_list = result[0].get("timestamp", [])
                indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
                closes = indicators.get("close", [])
                volumes = indicators.get("volume", [])
                for i, ts in enumerate(ts_list):
                    if i < len(closes) and closes[i] is not None:
                        d = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime(
                            "%Y-%m-%d"
                        )
                        vol = (
                            str(volumes[i])
                            if i < len(volumes) and volumes[i] is not None
                            else "0"
                        )
                        rows.append({"Date": d, "Close": str(closes[i]), "Volume": vol})
        except Exception:
            pass
        return rows

    def fetch_and_save(
        self,
        ticker: str,
        case_dir: str | Path,
        exchange: str | None = None,
        country: str | None = None,
    ) -> MarketData:
        """Fetch market data and write to ``{case_dir}/_market_data.json``.

        Args:
            ticker: Stock ticker.
            case_dir: Path to the case directory.
            exchange: Exchange code.
            country: Country hint.

        Returns:
            The MarketData instance.
        """
        md = self.fetch(ticker, exchange=exchange, country=country)
        out_path = Path(case_dir) / "_market_data.json"
        out_path.write_text(
            json.dumps(md.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info("Market data saved to %s", out_path)
        return md
