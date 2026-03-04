"""Tests for elsian.acquire.market_data — market data snapshot fetcher.

All HTTP calls are mocked. No live API calls.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from elsian.acquire.market_data import (
    MarketData,
    MarketDataFetcher,
    _build_yahoo_candidates,
    _get_with_retry,
    max_min_52w,
    parse_finviz_table,
    rolling_avg_volume,
    to_float,
)


# ── to_float tests ───────────────────────────────────────────────────


class TestToFloat:
    """Test robust string-to-float conversion."""

    def test_none(self):
        assert to_float(None) is None

    def test_empty_string(self):
        assert to_float("") is None
        assert to_float("   ") is None

    def test_na_variants(self):
        assert to_float("N/A") is None
        assert to_float("n/a") is None
        assert to_float("-") is None
        assert to_float("—") is None

    def test_plain_integer(self):
        assert to_float("42") == 42.0

    def test_plain_float(self):
        assert to_float("3.14") == 3.14

    def test_negative(self):
        assert to_float("-12.5") == -12.5

    def test_commas(self):
        assert to_float("1,234.56") == 1234.56
        assert to_float("1,000,000") == 1_000_000.0

    def test_suffix_k(self):
        assert to_float("1.5K") == 1500.0
        assert to_float("1.5k") == 1500.0

    def test_suffix_m(self):
        assert to_float("42.3M") == 42_300_000.0
        assert to_float("42.3m") == 42_300_000.0

    def test_suffix_b(self):
        assert to_float("1.5B") == 1_500_000_000.0

    def test_suffix_t(self):
        assert to_float("2T") == 2_000_000_000_000.0

    def test_percentage(self):
        assert to_float("-12.5%") == -12.5
        assert to_float("0.5%") == 0.5

    def test_percentage_invalid(self):
        assert to_float("abc%") is None

    def test_invalid_string(self):
        assert to_float("not a number") is None

    def test_positive_sign(self):
        assert to_float("+3.5") == 3.5

    def test_whitespace(self):
        assert to_float("  42  ") == 42.0


# ── parse_finviz_table tests ─────────────────────────────────────────

FINVIZ_HTML = """
<html><body>
<table class="snapshot-table2">
  <tr>
    <td>Price</td><td>25.50</td>
    <td>Market Cap</td><td>1.5B</td>
  </tr>
  <tr>
    <td>P/E</td><td>12.3</td>
    <td>Volume</td><td>500000</td>
  </tr>
  <tr>
    <td>Beta</td><td>1.05</td>
    <td>Shs Outstand</td><td>58.82M</td>
  </tr>
  <tr>
    <td>Target Price</td><td>30.00</td>
    <td>Inst Own</td><td>65.30%</td>
  </tr>
  <tr>
    <td>Dividend %</td><td>1.20%</td>
    <td>Insider Own</td><td>10.50%</td>
  </tr>
  <tr>
    <td>P/B</td><td>2.50</td>
    <td>Prev Close</td><td>25.20</td>
  </tr>
</table>
</body></html>
"""


class TestParseFinvizTable:
    """Test Finviz HTML snapshot table parsing."""

    def test_parse_basic(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(FINVIZ_HTML, "html.parser")
        result = parse_finviz_table(soup)
        assert result["Price"] == "25.50"
        assert result["Market Cap"] == "1.5B"
        assert result["P/E"] == "12.3"
        assert result["Volume"] == "500000"
        assert result["Beta"] == "1.05"
        assert result["Shs Outstand"] == "58.82M"

    def test_parse_no_table(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        result = parse_finviz_table(soup)
        assert result == {}


# ── rolling_avg_volume tests ─────────────────────────────────────────


class TestRollingAvgVolume:
    """Test OHLCV volume averaging."""

    def test_empty(self):
        assert rolling_avg_volume([]) is None

    def test_single_row(self):
        rows = [{"Date": "2024-01-01", "Close": "10", "Volume": "1000"}]
        assert rolling_avg_volume(rows, 30) == 1000

    def test_exact_n(self):
        rows = [
            {"Date": f"2024-01-{i:02d}", "Close": "10", "Volume": str(i * 100)}
            for i in range(1, 4)
        ]
        # volumes: 100, 200, 300 → avg = 200
        assert rolling_avg_volume(rows, 3) == 200

    def test_more_than_n(self):
        rows = [
            {"Date": f"2024-01-{i:02d}", "Close": "10", "Volume": str(i * 100)}
            for i in range(1, 6)
        ]
        # last 3: 300, 400, 500 → avg = 400
        assert rolling_avg_volume(rows, 3) == 400

    def test_invalid_volume_skipped(self):
        rows = [
            {"Date": "2024-01-01", "Close": "10", "Volume": "abc"},
            {"Date": "2024-01-02", "Close": "10", "Volume": "200"},
        ]
        assert rolling_avg_volume(rows, 30) == 200

    def test_missing_volume_key(self):
        rows = [{"Date": "2024-01-01", "Close": "10"}]
        assert rolling_avg_volume(rows, 30) is None


# ── max_min_52w tests ────────────────────────────────────────────────


class TestMaxMin52w:
    """Test 52-week high/low extraction from OHLCV data."""

    def test_empty(self):
        h, l = max_min_52w([])
        assert h is None
        assert l is None

    def test_basic(self):
        rows = [
            {"Date": "2024-01-01", "Close": "10.5"},
            {"Date": "2024-01-02", "Close": "12.0"},
            {"Date": "2024-01-03", "Close": "9.0"},
        ]
        h, l = max_min_52w(rows)
        assert h == 12.0
        assert l == 9.0

    def test_truncates_to_252(self):
        rows = [
            {"Date": f"day-{i}", "Close": str(float(i))}
            for i in range(1, 300)
        ]
        h, l = max_min_52w(rows)
        # last 252 rows: 48..299
        assert h == 299.0
        assert l == 48.0

    def test_invalid_close_skipped(self):
        rows = [
            {"Date": "2024-01-01", "Close": "abc"},
            {"Date": "2024-01-02", "Close": "15.0"},
        ]
        h, l = max_min_52w(rows)
        assert h == 15.0
        assert l == 15.0


# ── _build_yahoo_candidates tests ────────────────────────────────────


class TestBuildYahooCandidates:
    """Test Yahoo symbol candidate generation."""

    def test_us_exchange(self):
        result = _build_yahoo_candidates("AAPL", "NASDAQ")
        assert result == ["AAPL"]  # No suffix for US

    def test_lse(self):
        result = _build_yahoo_candidates("VOD", "LSE")
        assert "VOD.L" in result
        assert "VOD" in result

    def test_euronext_fr(self):
        result = _build_yahoo_candidates("TEP", "EURONEXT", country="FR")
        assert result[0] == "TEP.PA"  # Country-preferred first
        assert "TEP.AS" in result
        assert "TEP.BR" in result
        assert "TEP.LS" in result
        assert "TEP" in result

    def test_euronext_nl(self):
        result = _build_yahoo_candidates("PHIA", "EURONEXT", country="NL")
        assert result[0] == "PHIA.AS"

    def test_euronext_be(self):
        result = _build_yahoo_candidates("UCB", "EURONEXT", country="BE")
        assert result[0] == "UCB.BR"

    def test_euronext_no_country(self):
        result = _build_yahoo_candidates("XYZ", "EURONEXT")
        assert result[0] == "XYZ.PA"  # Default order: PA, AS, BR, LS
        assert len(result) == 5  # 4 suffixed + bare

    def test_hkex(self):
        result = _build_yahoo_candidates("0700", "HKEX")
        assert "0700.HK" in result
        assert "0700" in result

    def test_deduplication(self):
        # NYSE has no suffix, so bare ticker is same as suffixed → deduplicated
        result = _build_yahoo_candidates("AAPL", "NYSE")
        assert len(result) == len(set(result))


# ── MarketData.to_dict tests ────────────────────────────────────────


class TestMarketDataToDict:
    """Test MarketData serialization."""

    def test_basic_serialization(self):
        md = MarketData(
            ticker="TZOO",
            price=25.5,
            market_cap=1500.0,
            currency="USD",
            sector="Technology",
        )
        d = md.to_dict()
        assert d["ticker"] == "TZOO"
        assert d["price"] == 25.5
        assert d["market_cap"] == 1500.0
        assert d["currency"] == "USD"
        assert d["sector"] == "Technology"

    def test_none_values_omitted(self):
        md = MarketData(ticker="TZOO", price=10.0)
        d = md.to_dict()
        assert "beta" not in d
        assert "sector" not in d
        assert "market_cap" not in d

    def test_empty_string_omitted(self):
        md = MarketData(ticker="TZOO", fetched_at="")
        d = md.to_dict()
        assert "fetched_at" not in d

    def test_ticker_always_present(self):
        md = MarketData(ticker="")
        d = md.to_dict()
        assert "ticker" in d

    def test_json_serializable(self):
        md = MarketData(
            ticker="TZOO",
            price=25.5,
            volume=100000,
            avg_volume_30d=90000,
        )
        # Should not raise
        s = json.dumps(md.to_dict())
        assert '"TZOO"' in s


# ── _get_with_retry tests ───────────────────────────────────────────


class TestGetWithRetry:
    """Test HTTP retry logic."""

    @patch("elsian.acquire.market_data.requests")
    def test_success_first_try(self, mock_requests):
        resp = MagicMock()
        resp.status_code = 200
        mock_requests.get.return_value = resp
        result = _get_with_retry("https://example.com")
        assert result == resp
        assert mock_requests.get.call_count == 1

    @patch("elsian.acquire.market_data.time.sleep")
    @patch("elsian.acquire.market_data.requests")
    def test_retry_on_429(self, mock_requests, mock_sleep):
        import requests as real_requests

        first_resp = MagicMock()
        first_resp.status_code = 429
        first_resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError(
            response=first_resp
        )

        second_resp = MagicMock()
        second_resp.status_code = 200
        second_resp.raise_for_status.return_value = None

        mock_requests.get.side_effect = [first_resp, second_resp]
        mock_requests.exceptions = real_requests.exceptions

        result = _get_with_retry("https://example.com")
        assert result == second_resp
        mock_sleep.assert_called_once_with(3)

    @patch("elsian.acquire.market_data.time.sleep")
    @patch("elsian.acquire.market_data.requests")
    def test_retry_on_503(self, mock_requests, mock_sleep):
        import requests as real_requests

        first_resp = MagicMock()
        first_resp.status_code = 503
        first_resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError(
            response=first_resp
        )

        second_resp = MagicMock()
        second_resp.status_code = 200
        second_resp.raise_for_status.return_value = None

        mock_requests.get.side_effect = [first_resp, second_resp]
        mock_requests.exceptions = real_requests.exceptions

        result = _get_with_retry("https://example.com")
        assert result == second_resp

    @patch("elsian.acquire.market_data.requests")
    def test_no_retry_on_404(self, mock_requests):
        import requests as real_requests

        resp = MagicMock()
        resp.status_code = 404
        resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError(
            response=resp
        )

        mock_requests.get.return_value = resp
        mock_requests.exceptions = real_requests.exceptions

        with pytest.raises(real_requests.exceptions.HTTPError):
            _get_with_retry("https://example.com")


# ── fetch() orchestration tests (mocked) ─────────────────────────────


class TestMarketDataFetcherUS:
    """Test fetch() for US tickers with mocked Finviz + Stooq."""

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_us_ticker_basic(self, mock_finviz, mock_stooq):
        mock_finviz.return_value = {
            "url": "https://finviz.com/quote.ashx?t=TZOO",
            "company_name": "Travelzoo",
            "sector": "Communication Services",
            "industry": "Internet Content & Information",
            "country": "USA",
            "exchange": "NASDAQ",
            "snapshot": {
                "Price": "25.50",
                "Market Cap": "1.5B",
                "P/E": "12.3",
                "Volume": "500000",
                "Beta": "1.05",
                "Shs Outstand": "58.82M",
                "Target Price": "30.00",
                "Inst Own": "65.30%",
                "Insider Own": "10.50%",
                "Dividend %": "1.20%",
                "P/B": "2.50",
                "Prev Close": "25.20",
            },
        }
        mock_stooq.return_value = [
            {"Date": f"2024-01-{i:02d}", "Close": str(24.0 + i * 0.1), "Volume": "400000"}
            for i in range(1, 31)
        ]

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TZOO", exchange="NASDAQ", country="US")

        assert md.ticker == "TZOO"
        assert md.price == 25.50
        assert md.company_name == "Travelzoo"
        assert md.sector == "Communication Services"
        assert md.pe_ratio == 12.3
        assert md.beta == 1.05
        assert md.volume == 500000
        assert md.currency == "USD"
        assert md.avg_volume_30d == 400000
        assert md.target_price == 30.0
        assert md.institutional_ownership == 65.3
        assert md.dividend_yield == 1.2

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_us_ticker_market_cap_in_millions(self, mock_finviz, mock_stooq):
        mock_finviz.return_value = {
            "url": "https://finviz.com/quote.ashx?t=TZOO",
            "company_name": "Travelzoo",
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": "NASDAQ",
            "snapshot": {
                "Price": "25.50",
                "Market Cap": "1.5B",
                "Shs Outstand": "58.82M",
            },
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TZOO", exchange="NASDAQ", country="US")

        # 1.5B = 1,500,000,000 → in millions = 1500.0
        assert md.market_cap == 1500.0
        # 58.82M = 58,820,000 → in millions = 58.82
        assert md.shares_outstanding == 58.82

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_yahoo_chart")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_us_ticker_finviz_fails_yahoo_fallback(self, mock_finviz, mock_yahoo, mock_stooq):
        mock_finviz.side_effect = Exception("Finviz down")
        mock_yahoo.return_value = {
            "url": "https://finance.yahoo.com/quote/TZOO",
            "symbol": "TZOO",
            "company_name": "Travelzoo",
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": "NASDAQ",
            "snapshot": {"Price": "25.50", "Volume": "300000"},
            "currency": "USD",
            "instrument_type": "EQUITY",
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TZOO", exchange="NASDAQ", country="US")

        assert md.ticker == "TZOO"
        assert md.price == 25.50
        assert md.source == "yahoo"


class TestMarketDataFetcherNonUS:
    """Test fetch() for non-US tickers with mocked Yahoo."""

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_yahoo_summary")
    @patch("elsian.acquire.market_data._select_yahoo_symbol")
    def test_non_us_ticker(self, mock_select, mock_summary, mock_stooq):
        mock_select.return_value = (
            {
                "url": "https://finance.yahoo.com/quote/TEP.PA",
                "symbol": "TEP.PA",
                "company_name": "Teleperformance SE",
                "sector": None,
                "industry": None,
                "country": None,
                "exchange": "PAR",
                "snapshot": {"Price": "85.20", "Volume": "200000"},
                "currency": "EUR",
                "instrument_type": "EQUITY",
            },
            "TEP.PA",
        )
        mock_summary.return_value = {
            "market_cap": 5_000_000_000,
            "shares_outstanding": 58_000_000,
            "sector": "Industrials",
            "industry": "Staffing & Employment Services",
            "country": "France",
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TEP", exchange="EPA", country="FR")

        assert md.ticker == "TEP"
        assert md.price == 85.20
        assert md.currency == "EUR"
        assert md.sector == "Industrials"
        assert md.industry == "Staffing & Employment Services"

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_yahoo_summary")
    @patch("elsian.acquire.market_data._select_yahoo_symbol")
    def test_gbp_pence_conversion(self, mock_select, mock_summary, mock_stooq):
        """LSE stocks quoted in pence (GBp) should be converted to GBP."""
        mock_select.return_value = (
            {
                "url": "https://finance.yahoo.com/quote/VOD.L",
                "symbol": "VOD.L",
                "company_name": "Vodafone Group Plc",
                "sector": None,
                "industry": None,
                "country": None,
                "exchange": "LSE",
                "snapshot": {"Price": "7520", "Prev Close": "7500", "Volume": "1000000"},
                "currency": "GBp",
                "instrument_type": "EQUITY",
            },
            "VOD.L",
        )
        mock_summary.return_value = {}
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("VOD", exchange="LSE", country="GB")

        assert md.currency == "GBP"
        assert md.price == 75.20  # 7520 / 100
        assert md.prev_close == 75.0  # 7500 / 100


class TestMarketDataFetchAndSave:
    """Test fetch_and_save writes JSON to disk."""

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_writes_json(self, mock_finviz, mock_stooq, tmp_path):
        mock_finviz.return_value = {
            "url": "https://finviz.com/quote.ashx?t=TZOO",
            "company_name": "Travelzoo",
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": "NASDAQ",
            "snapshot": {"Price": "25.50"},
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch_and_save("TZOO", tmp_path, exchange="NASDAQ", country="US")

        out_file = tmp_path / "_market_data.json"
        assert out_file.exists()

        data = json.loads(out_file.read_text())
        assert data["ticker"] == "TZOO"
        assert data["price"] == 25.50


class TestMarketCapSharesFallback:
    """Test derived market_cap / shares_outstanding computation."""

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_compute_market_cap_from_price_and_shares(self, mock_finviz, mock_stooq):
        """If market_cap is missing, compute from price * shares."""
        mock_finviz.return_value = {
            "url": "https://finviz.com/quote.ashx?t=TEST",
            "company_name": "Test Co",
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": "NASDAQ",
            "snapshot": {
                "Price": "10.00",
                "Shs Outstand": "100M",
                # No Market Cap
            },
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TEST", exchange="NASDAQ", country="US")

        # shares = 100M = 100,000,000; price = 10 → market_cap_raw = 1B
        # market_cap in millions = 1000.0
        assert md.market_cap == 1000.0

    @patch("elsian.acquire.market_data._fetch_stooq_ohlcv")
    @patch("elsian.acquire.market_data._fetch_finviz")
    def test_compute_shares_from_price_and_market_cap(self, mock_finviz, mock_stooq):
        """If shares is missing, compute from market_cap / price."""
        mock_finviz.return_value = {
            "url": "https://finviz.com/quote.ashx?t=TEST",
            "company_name": "Test Co",
            "sector": None,
            "industry": None,
            "country": None,
            "exchange": "NASDAQ",
            "snapshot": {
                "Price": "10.00",
                "Market Cap": "1B",
                # No Shs Outstand
            },
        }
        mock_stooq.return_value = []

        fetcher = MarketDataFetcher()
        md = fetcher.fetch("TEST", exchange="NASDAQ", country="US")

        # market_cap_raw = 1B; price = 10 → shares_raw = 100M
        # shares in millions = 100.0
        assert md.shares_outstanding == 100.0
