"""Integration tests for elsian/discover — requires network access.

These tests hit real APIs (SEC EDGAR, Yahoo Finance) so they are skipped
by default unless ELSIAN_NET_TESTS=1 is set.
"""

from __future__ import annotations

import os
import unittest

SKIP_NET = os.environ.get("ELSIAN_NET_TESTS", "0") != "1"
SKIP_REASON = "Set ELSIAN_NET_TESTS=1 to run network tests"


@unittest.skipIf(SKIP_NET, SKIP_REASON)
class TestDiscoverIntegration(unittest.TestCase):
    """Integration tests with real HTTP calls."""

    def test_discover_aapl_sec(self):
        from elsian.discover.discover import TickerDiscoverer

        discoverer = TickerDiscoverer()
        result = discoverer.discover("AAPL")

        self.assertEqual(result.ticker, "AAPL")
        self.assertEqual(result.source_hint, "sec")
        self.assertIsNotNone(result.cik)
        self.assertEqual(result.currency, "USD")
        self.assertIsNotNone(result.company_name)
        self.assertIn("Apple", result.company_name)
        self.assertEqual(result.accounting_standard, "US-GAAP")
        # Apple FY ends in September (month 9) — but mapped as "0930"
        self.assertIn(result.fiscal_year_end_month, (9, 10))

    def test_discover_tep_pa_euronext(self):
        from elsian.discover.discover import TickerDiscoverer

        discoverer = TickerDiscoverer()
        result = discoverer.discover("TEP.PA")

        self.assertEqual(result.ticker, "TEP")
        self.assertEqual(result.source_hint, "eu_manual")
        self.assertEqual(result.accounting_standard, "IFRS")
        self.assertIn(result.country, ("FR",))
        # Currency should be EUR
        self.assertEqual(result.currency, "EUR")
        self.assertIsNotNone(result.company_name)

    def test_discover_kar_ax_asx(self):
        from elsian.discover.discover import TickerDiscoverer

        discoverer = TickerDiscoverer()
        result = discoverer.discover("KAR.AX")

        self.assertEqual(result.ticker, "KAR")
        self.assertEqual(result.source_hint, "asx")
        self.assertIn(result.country, ("AU",))


if __name__ == "__main__":
    unittest.main()
