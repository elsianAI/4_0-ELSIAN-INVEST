"""Unit tests for elsian/discover/discover.py.

All HTTP calls are mocked — no network access required.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from elsian.discover.discover import (
    DiscoveryResult,
    TickerDiscoverer,
    _HttpClient,
    _discover_non_us,
    _discover_sec,
    parse_ticker_suffix,
    suffix_to_exchange_info,
    SUFFIX_MAP,
)


# ── Suffix parsing tests ────────────────────────────────────────────

class TestParseTickerSuffix(unittest.TestCase):
    """Tests for parse_ticker_suffix()."""

    def test_us_ticker_no_suffix(self):
        base, suffix = parse_ticker_suffix("AAPL")
        self.assertEqual(base, "AAPL")
        self.assertIsNone(suffix)

    def test_euronext_paris(self):
        base, suffix = parse_ticker_suffix("TEP.PA")
        self.assertEqual(base, "TEP")
        self.assertEqual(suffix, ".PA")

    def test_asx(self):
        base, suffix = parse_ticker_suffix("KAR.AX")
        self.assertEqual(base, "KAR")
        self.assertEqual(suffix, ".AX")

    def test_lse(self):
        base, suffix = parse_ticker_suffix("SOM.L")
        self.assertEqual(base, "SOM")
        self.assertEqual(suffix, ".L")

    def test_hkex(self):
        base, suffix = parse_ticker_suffix("3988.HK")
        self.assertEqual(base, "3988")
        self.assertEqual(suffix, ".HK")

    def test_toronto(self):
        base, suffix = parse_ticker_suffix("RY.TO")
        self.assertEqual(base, "RY")
        self.assertEqual(suffix, ".TO")

    def test_tokyo(self):
        base, suffix = parse_ticker_suffix("7203.T")
        self.assertEqual(base, "7203")
        self.assertEqual(suffix, ".T")

    def test_case_insensitive(self):
        base, suffix = parse_ticker_suffix("tep.pa")
        self.assertEqual(base, "tep")
        self.assertEqual(suffix, ".PA")

    def test_suffix_four_chars_no_match(self):
        """Suffixes longer than 3 chars are not parsed."""
        base, suffix = parse_ticker_suffix("ABC.LONG")
        self.assertEqual(base, "ABC.LONG")
        self.assertIsNone(suffix)


class TestSuffixToExchangeInfo(unittest.TestCase):
    """Tests for suffix_to_exchange_info()."""

    def test_pa_euronext(self):
        info = suffix_to_exchange_info(".PA")
        self.assertIsNotNone(info)
        exchange, country, source, acct = info
        self.assertEqual(exchange, "EPA")
        self.assertEqual(country, "FR")
        self.assertEqual(source, "eu_manual")
        self.assertEqual(acct, "IFRS")

    def test_ax_asx(self):
        info = suffix_to_exchange_info(".AX")
        self.assertIsNotNone(info)
        exchange, country, source, acct = info
        self.assertEqual(exchange, "ASX")
        self.assertEqual(country, "AU")
        self.assertEqual(source, "asx")
        self.assertEqual(acct, "IFRS")

    def test_l_lse(self):
        info = suffix_to_exchange_info(".L")
        self.assertIsNotNone(info)
        exchange, country, source, acct = info
        self.assertEqual(exchange, "LSE")
        self.assertEqual(country, "GB")

    def test_hk_sehk(self):
        info = suffix_to_exchange_info(".HK")
        self.assertIsNotNone(info)
        exchange, country, source, acct = info
        self.assertEqual(exchange, "SEHK")
        self.assertEqual(country, "HK")

    def test_unknown_suffix(self):
        info = suffix_to_exchange_info(".ZZ")
        self.assertIsNone(info)

    def test_all_known_suffixes(self):
        """Every suffix in SUFFIX_MAP should return valid info."""
        for suffix, expected in SUFFIX_MAP.items():
            with self.subTest(suffix=suffix):
                info = suffix_to_exchange_info(suffix)
                self.assertIsNotNone(info)
                self.assertEqual(info, expected)


# ── Discovery result tests ───────────────────────────────────────────

class TestDiscoveryResult(unittest.TestCase):
    """Tests for DiscoveryResult.to_case_dict()."""

    def test_full_case_dict(self):
        r = DiscoveryResult(
            ticker="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            source_hint="sec",
            accounting_standard="US-GAAP",
            cik="320193",
            fiscal_year_end_month=9,
            sector="Electronic Equipment",
            period_scope="FULL",
        )
        d = r.to_case_dict()
        self.assertEqual(d["ticker"], "AAPL")
        self.assertEqual(d["company_name"], "Apple Inc.")
        self.assertEqual(d["exchange"], "NASDAQ")
        self.assertEqual(d["country"], "US")
        self.assertEqual(d["currency"], "USD")
        self.assertEqual(d["source_hint"], "sec")
        self.assertEqual(d["accounting_standard"], "US-GAAP")
        self.assertEqual(d["cik"], "320193")
        self.assertEqual(d["fiscal_year_end_month"], 9)
        self.assertEqual(d["sector"], "Electronic Equipment")
        self.assertNotIn("_discovery_warnings", d)

    def test_case_dict_omits_none(self):
        r = DiscoveryResult(ticker="TEST")
        d = r.to_case_dict()
        self.assertEqual(d["ticker"], "TEST")
        self.assertNotIn("company_name", d)
        self.assertNotIn("cik", d)

    def test_case_dict_with_warnings(self):
        r = DiscoveryResult(
            ticker="TEST",
            warnings=["Something failed"],
        )
        d = r.to_case_dict()
        self.assertIn("_discovery_warnings", d)
        self.assertEqual(len(d["_discovery_warnings"]), 1)

    def test_case_dict_json_serializable(self):
        r = DiscoveryResult(
            ticker="AAPL",
            company_name="Apple Inc.",
            exchange="NASDAQ",
            country="US",
            currency="USD",
            cik="320193",
            fiscal_year_end_month=9,
        )
        # Should not raise
        json_str = json.dumps(r.to_case_dict(), indent=2)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["ticker"], "AAPL")


# ── SEC discovery tests (mocked) ────────────────────────────────────

def _make_mock_sec_client(
    ticker_map: dict | None = None,
    submissions: dict | None = None,
) -> _HttpClient:
    """Create a mock _HttpClient that returns predefined SEC data."""
    client = _HttpClient.__new__(_HttpClient)

    default_ticker_map = {
        "0": {"ticker": "AAPL", "cik_str": 320193, "exchange": "NASDAQ"},
        "1": {"ticker": "MSFT", "cik_str": 789019, "exchange": "NASDAQ"},
        "2": {"ticker": "TZOO", "cik_str": 1091596, "exchange": "NASDAQ"},
    }

    default_submissions = {
        "name": "Apple Inc.",
        "sic": "3571",
        "fiscalYearEnd": "0930",
        "exchanges": ["NASDAQ"],
        "stateOfIncorporation": "CA",
        "addresses": {
            "mailing": {"stateOrCountry": "CA"},
        },
        "website": "https://www.apple.com",
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "10-Q", "10-Q", "10-K"],
                "filingDate": ["2025-10-30", "2025-07-30", "2025-04-30",
                               "2025-01-30", "2024-10-30"],
                "accessionNumber": ["0001-25-1", "0001-25-2", "0001-25-3",
                                    "0001-25-4", "0001-24-1"],
                "primaryDocument": ["aapl-20250930.htm", "aapl-20250630.htm",
                                    "aapl-20250331.htm", "aapl-20250103.htm",
                                    "aapl-20240930.htm"],
            },
            "files": [],
        },
    }

    calls: dict[str, Any] = {
        "https://www.sec.gov/files/company_tickers.json": ticker_map or default_ticker_map,
    }
    cik10 = str((ticker_map or default_ticker_map).get("0", {}).get("cik_str", 320193)).zfill(10)
    calls[f"https://data.sec.gov/submissions/CIK{cik10}.json"] = (
        submissions or default_submissions
    )

    def mock_sec_get_json(url):
        if url in calls:
            return calls[url]
        # For any CIK submission URL
        for key, val in calls.items():
            if "submissions/CIK" in key and "submissions/CIK" in url:
                return val
        raise Exception(f"Unmocked URL: {url}")

    client.sec_get_json = mock_sec_get_json
    client.yahoo_get_json = MagicMock(return_value={})
    return client


class TestDiscoverSec(unittest.TestCase):
    """Tests for SEC-based discovery."""

    def test_discover_aapl(self):
        client = _make_mock_sec_client()
        result = _discover_sec(client, "AAPL")
        self.assertEqual(result.ticker, "AAPL")
        self.assertEqual(result.company_name, "Apple Inc.")
        self.assertEqual(result.cik, "320193")
        self.assertEqual(result.exchange, "NASDAQ")
        self.assertEqual(result.country, "US")
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.accounting_standard, "US-GAAP")
        self.assertEqual(result.fiscal_year_end_month, 9)
        self.assertEqual(result.source_hint, "sec")
        self.assertEqual(len(result.warnings), 0)

    def test_discover_sec_not_found(self):
        client = _make_mock_sec_client()
        result = _discover_sec(client, "XYZNOTREAL")
        self.assertIsNone(result.cik)
        self.assertTrue(len(result.warnings) > 0)
        self.assertIn("not found", result.warnings[0])

    def test_discover_sec_20f_filer(self):
        """20-F filers should be detected as IFRS."""
        submissions = {
            "name": "InMode Ltd.",
            "sic": "3845",
            "fiscalYearEnd": "1231",
            "exchanges": ["NASDAQ"],
            "stateOfIncorporation": "L3",
            "addresses": {"mailing": {"stateOrCountry": "IL"}},
            "website": "https://www.inmodemd.com",
            "filings": {
                "recent": {
                    "form": ["20-F", "6-K", "6-K", "6-K", "20-F"],
                    "filingDate": ["2025-03-01"] * 5,
                    "accessionNumber": ["a"] * 5,
                    "primaryDocument": ["d"] * 5,
                },
                "files": [],
            },
        }
        ticker_map = {"0": {"ticker": "INMD", "cik_str": 1742692, "exchange": "NASDAQ"}}
        client = _make_mock_sec_client(ticker_map=ticker_map, submissions=submissions)
        result = _discover_sec(client, "INMD")
        self.assertEqual(result.accounting_standard, "IFRS")
        self.assertEqual(result.cik, "1742692")

    def test_discover_sec_fiscal_year_end(self):
        """Fiscal year end month parsed from submissions.fiscalYearEnd."""
        submissions = {
            "name": "NVIDIA Corporation",
            "sic": "3674",
            "fiscalYearEnd": "0131",
            "exchanges": ["NASDAQ"],
            "stateOfIncorporation": "DE",
            "addresses": {"mailing": {"stateOrCountry": "CA"}},
            "website": "https://www.nvidia.com",
            "filings": {
                "recent": {"form": ["10-K"], "filingDate": ["2025-03-01"],
                           "accessionNumber": ["a"], "primaryDocument": ["d"]},
                "files": [],
            },
        }
        ticker_map = {"0": {"ticker": "NVDA", "cik_str": 1045810, "exchange": "NASDAQ"}}
        client = _make_mock_sec_client(ticker_map=ticker_map, submissions=submissions)
        result = _discover_sec(client, "NVDA")
        self.assertEqual(result.fiscal_year_end_month, 1)

    def test_discover_sec_website_to_web_ir(self):
        client = _make_mock_sec_client()
        result = _discover_sec(client, "AAPL")
        self.assertEqual(result.web_ir, "https://www.apple.com")

    def test_discover_sec_sic_to_sector(self):
        client = _make_mock_sec_client()
        result = _discover_sec(client, "AAPL")
        # SIC 3571 → prefix "35" → Industrial Machinery
        self.assertEqual(result.sector, "Industrial Machinery")


# ── Non-US discovery tests (mocked) ─────────────────────────────────

class TestDiscoverNonUs(unittest.TestCase):
    """Tests for non-US ticker discovery."""

    def _make_yahoo_client(
        self,
        chart_meta: dict | None = None,
    ) -> _HttpClient:
        """Create mock client that returns Yahoo Finance chart data."""
        client = _HttpClient.__new__(_HttpClient)

        default_meta = {
            "shortName": "Teleperformance SE",
            "currency": "EUR",
            "exchangeName": "PAR",
            "instrumentType": "EQUITY",
            "regularMarketPrice": 85.0,
        }

        def mock_yahoo(url):
            return {
                "chart": {
                    "result": [
                        {"meta": chart_meta or default_meta}
                    ]
                }
            }

        client.yahoo_get_json = mock_yahoo
        client.sec_get_json = MagicMock(side_effect=Exception("Should not call SEC"))
        return client

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_euronext_paris(self, _mock_summary):
        client = self._make_yahoo_client()
        result = _discover_non_us(client, "TEP.PA", "TEP", ".PA")
        self.assertEqual(result.ticker, "TEP")
        self.assertEqual(result.company_name, "Teleperformance SE")
        self.assertEqual(result.currency, "EUR")
        self.assertEqual(result.source_hint, "eu_manual")
        self.assertEqual(result.accounting_standard, "IFRS")
        self.assertEqual(result.country, "FR")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_asx(self, _mock_summary):
        meta = {
            "shortName": "Karoon Energy Ltd",
            "currency": "AUD",
            "exchangeName": "ASX",
        }
        client = self._make_yahoo_client(chart_meta=meta)
        result = _discover_non_us(client, "KAR.AX", "KAR", ".AX")
        self.assertEqual(result.ticker, "KAR")
        self.assertEqual(result.currency, "AUD")
        self.assertEqual(result.source_hint, "asx")
        self.assertEqual(result.country, "AU")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_lse(self, _mock_summary):
        meta = {
            "shortName": "Somero Enterprises",
            "currency": "GBP",
            "exchangeName": "LSE",
        }
        client = self._make_yahoo_client(chart_meta=meta)
        result = _discover_non_us(client, "SOM.L", "SOM", ".L")
        self.assertEqual(result.ticker, "SOM")
        self.assertEqual(result.exchange, "LSE")
        self.assertEqual(result.country, "GB")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_hkex(self, _mock_summary):
        meta = {
            "shortName": "Bank of China Ltd",
            "currency": "HKD",
            "exchangeName": "HKG",
        }
        client = self._make_yahoo_client(chart_meta=meta)
        result = _discover_non_us(client, "3988.HK", "3988", ".HK")
        self.assertEqual(result.ticker, "3988")
        self.assertEqual(result.currency, "HKD")
        self.assertEqual(result.country, "HK")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_yahoo_failure_graceful(self, _mock_summary):
        """When Yahoo Finance fails, should return partial result with warnings."""
        client = _HttpClient.__new__(_HttpClient)
        client.yahoo_get_json = MagicMock(side_effect=Exception("Network error"))
        client.sec_get_json = MagicMock(side_effect=Exception("Should not call SEC"))

        result = _discover_non_us(client, "TEP.PA", "TEP", ".PA")
        # Should still have suffix-derived info
        self.assertEqual(result.ticker, "TEP")
        self.assertEqual(result.source_hint, "eu_manual")
        self.assertEqual(result.accounting_standard, "IFRS")
        self.assertEqual(result.country, "FR")
        # Should have a warning
        self.assertTrue(len(result.warnings) > 0)

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_discover_fallback_currency_from_country(self, _mock_summary):
        """When Yahoo Finance doesn't return currency, infer from country."""
        client = _HttpClient.__new__(_HttpClient)

        def mock_yahoo(url):
            return {"chart": {"result": [{"meta": {"shortName": "Test"}}]}}

        client.yahoo_get_json = mock_yahoo
        result = _discover_non_us(client, "TEST.PA", "TEST", ".PA")
        # Currency should be inferred from FR → EUR
        self.assertEqual(result.currency, "EUR")


# ── TickerDiscoverer orchestration tests ─────────────────────────────

class TestTickerDiscoverer(unittest.TestCase):
    """Tests for the TickerDiscoverer class."""

    def test_us_ticker_routes_to_sec(self):
        client = _make_mock_sec_client()
        discoverer = TickerDiscoverer(client=client)
        result = discoverer.discover("AAPL")
        self.assertEqual(result.source_hint, "sec")
        self.assertEqual(result.cik, "320193")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_pa_suffix_routes_to_non_us(self, _mock_summary):
        client = _HttpClient.__new__(_HttpClient)
        client.yahoo_get_json = MagicMock(return_value={
            "chart": {"result": [{"meta": {
                "shortName": "Teleperformance SE",
                "currency": "EUR",
                "exchangeName": "PAR",
            }}]}
        })
        discoverer = TickerDiscoverer(client=client)
        result = discoverer.discover("TEP.PA")
        self.assertEqual(result.source_hint, "eu_manual")
        self.assertEqual(result.ticker, "TEP")

    def test_unknown_suffix_tries_sec_first(self):
        """Unknown suffix should try SEC, then fall back to non-US."""
        client = _make_mock_sec_client()
        discoverer = TickerDiscoverer(client=client)
        # AAPL.ZZ has unknown suffix but SEC can find AAPL
        result = discoverer.discover("AAPL.ZZ")
        self.assertEqual(result.cik, "320193")

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_us_not_found_tries_yahoo_fallback(self, _mock_summary):
        """US ticker not in SEC should fallback to Yahoo Finance."""
        client = _HttpClient.__new__(_HttpClient)
        client.sec_get_json = MagicMock(return_value={
            "0": {"ticker": "MSFT", "cik_str": 789019},
        })
        client.yahoo_get_json = MagicMock(return_value={
            "chart": {"result": [{"meta": {
                "shortName": "Unknown Corp",
                "currency": "USD",
            }}]}
        })
        discoverer = TickerDiscoverer(client=client)
        result = discoverer.discover("NOTREAL")
        self.assertTrue(any("not found" in w.lower() for w in result.warnings))


# ── case.json output format tests ────────────────────────────────────

class TestCaseJsonFormat(unittest.TestCase):
    """Verify output format matches existing case.json schema."""

    REQUIRED_KEYS = {"ticker"}
    KNOWN_KEYS = {
        "ticker", "company_name", "exchange", "country", "currency",
        "source_hint", "accounting_standard", "cik", "web_ir",
        "fiscal_year_end_month", "sector", "period_scope",
        "_discovery_warnings",
    }

    def test_sec_case_has_expected_keys(self):
        client = _make_mock_sec_client()
        result = _discover_sec(client, "AAPL")
        d = result.to_case_dict()
        # Must have ticker
        self.assertIn("ticker", d)
        # All keys must be known
        for key in d:
            self.assertIn(key, self.KNOWN_KEYS, f"Unknown key: {key}")
        # SEC case should have these
        self.assertIn("cik", d)
        self.assertIn("source_hint", d)
        self.assertIn("accounting_standard", d)

    @patch("elsian.discover.discover._fetch_yahoo_summary_minimal", return_value={})
    def test_non_us_case_has_expected_keys(self, _mock_summary):
        client = _HttpClient.__new__(_HttpClient)
        client.yahoo_get_json = MagicMock(return_value={
            "chart": {"result": [{"meta": {
                "shortName": "Test Corp",
                "currency": "EUR",
                "exchangeName": "PAR",
            }}]}
        })
        result = _discover_non_us(client, "TEST.PA", "TEST", ".PA")
        d = result.to_case_dict()
        self.assertIn("ticker", d)
        for key in d:
            self.assertIn(key, self.KNOWN_KEYS, f"Unknown key: {key}")
        # non-US should have these
        self.assertIn("source_hint", d)
        self.assertIn("accounting_standard", d)
        self.assertIn("country", d)
        # non-US should NOT have CIK
        self.assertNotIn("cik", d)

    def test_period_scope_default(self):
        r = DiscoveryResult(ticker="TEST")
        d = r.to_case_dict()
        self.assertEqual(d.get("period_scope"), "FULL")


if __name__ == "__main__":
    unittest.main()
