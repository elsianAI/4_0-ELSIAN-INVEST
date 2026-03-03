"""Integration tests for _find_exhibit_99 — BL-030.

Uses a realistic EDGAR index.json fixture based on TZOO 8-K filings
(accession 0001133311-26-000007, filed 2026-02-19, earnings release).
No network calls — the SEC API response is mocked with a real structure.

## Pass 2 Analysis (HTML fallback)
──────────────────────────────────
Examined all downloaded 8-K/6-K filings for TZOO, NEXN, and INMD:

- **TZOO**: 9 8-K earnings releases (SRC_019 – SRC_027) were successfully
  acquired, meaning `_find_exhibit_99` found the Exhibit 99 via Pass 1
  (index.json type/filename matching) for all of them.

- **NEXN**: 0 earnings filings found. All 6-K filings classified as
  periodic (quarterly). NEXN uses 6-K for regular financial reports,
  not as exhibit-bearing earnings releases. The 6-K form is in
  PERIODIC_FORMS so `_find_exhibit_99` is never called for them.

- **INMD**: Same as NEXN — 0 earnings. The 52 6-K filings were classified
  as periodic, not earnings. `_find_exhibit_99` never invoked.

**Conclusion**: Pass 2 (HTML fallback — scanning primary doc for links to
exhibit files) is NOT needed for any current case. All 8-K earnings
filings in the existing corpus resolve via Pass 1. The fallback path in
`acquire()` (checking for "item 2.02" in the primary doc) covers edge
cases where a filing is an earnings 8-K but has no Exhibit 99 at all.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from elsian.acquire.sec_edgar import (
    _find_exhibit_99,
    _FilingRecord,
    SecClient,
)


# ── Realistic fixture: TZOO 8-K 2026-02-19 ──────────────────────────
# Structure mirrors https://www.sec.gov/Archives/edgar/data/1133311/
# 000113331126000007/index.json  (simplified to key fields)

TZOO_8K_INDEX = {
    "directory": {
        "name": "000113331126000007",
        "item": [
            {
                "name": "0001133311-26-000007-index.htm",
                "type": "",
                "last-modified": "2026-02-19 16:05:33",
                "size": "",
            },
            {
                "name": "tzoo-20260219.htm",
                "type": "8-K",
                "last-modified": "2026-02-19 16:05:33",
                "size": "23456",
            },
            {
                "name": "tzoo-20260219ex991.htm",
                "type": "EX-99.1",
                "last-modified": "2026-02-19 16:05:33",
                "size": "98765",
            },
            {
                "name": "R1.htm",
                "type": "GRAPHIC",
                "last-modified": "2026-02-19 16:05:33",
                "size": "1234",
            },
        ],
    }
}


@pytest.fixture
def tzoo_8k_rec() -> _FilingRecord:
    return _FilingRecord(
        form="8-K",
        filing_date="2026-02-19",
        accession="0001133311-26-000007",
        primary_doc="tzoo-20260219.htm",
    )


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=SecClient)
    client.get_json.return_value = TZOO_8K_INDEX
    return client


class TestExhibit99IntegrationTZOO:
    """Integration test with realistic TZOO 8-K index.json fixture."""

    def test_finds_exhibit_in_real_8k_structure(self, mock_client, tzoo_8k_rec):
        """Pass 1 finds the EX-99.1 exhibit by document type in a
        realistic EDGAR index.json structure."""
        result = _find_exhibit_99(mock_client, 1133311, tzoo_8k_rec)
        assert result == "tzoo-20260219ex991.htm"

    def test_skips_index_and_graphic_files(self, mock_client, tzoo_8k_rec):
        """Should not return the index.htm or GRAPHIC entries."""
        result = _find_exhibit_99(mock_client, 1133311, tzoo_8k_rec)
        assert result != "0001133311-26-000007-index.htm"
        assert result != "R1.htm"

    def test_correct_url_called(self, mock_client, tzoo_8k_rec):
        """Verify the function builds the correct index.json URL."""
        _find_exhibit_99(mock_client, 1133311, tzoo_8k_rec)
        expected_url = (
            "https://www.sec.gov/Archives/edgar/data/1133311/"
            "000113331126000007/index.json"
        )
        mock_client.get_json.assert_called_once_with(expected_url)


class TestExhibit99IntegrationGCT6K:
    """Integration test simulating a 6-K with Exhibit 99.1.

    GCT (Gigacloud Technology) is a foreign private issuer that files 6-K
    reports. Some 6-K filings carry Exhibit 99.1 with earnings data.
    This test verifies _find_exhibit_99 also works for 6-K filings when
    the index includes an EX-99.1 typed document.
    """

    GCT_6K_INDEX = {
        "directory": {
            "name": "000121390025000123",
            "item": [
                {
                    "name": "gct-6k_index.htm",
                    "type": "",
                    "size": "",
                },
                {
                    "name": "gct-6k20250315.htm",
                    "type": "6-K",
                    "size": "45000",
                },
                {
                    "name": "gct-ex991_20250315.htm",
                    "type": "EX-99.1",
                    "size": "120000",
                },
            ],
        }
    }

    def test_finds_exhibit_99_in_6k(self):
        client = MagicMock(spec=SecClient)
        client.get_json.return_value = self.GCT_6K_INDEX
        rec = _FilingRecord(
            form="6-K",
            filing_date="2025-03-15",
            accession="0001213900-25-000123",
            primary_doc="gct-6k20250315.htm",
        )
        result = _find_exhibit_99(client, 1819574, rec)
        assert result == "gct-ex991_20250315.htm"
