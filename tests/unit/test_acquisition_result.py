"""Tests for AcquisitionResult model."""

from elsian.models.result import AcquisitionResult


class TestAcquisitionResult:
    def test_defaults(self):
        r = AcquisitionResult()
        assert r.ticker == ""
        assert r.filings_downloaded == 0
        assert r.filings_coverage_pct == 0.0

    def test_to_dict(self):
        r = AcquisitionResult(
            ticker="TZOO",
            source="sec_edgar",
            cik="0001375966",
            filings_downloaded=28,
            filings_coverage_pct=100.0,
        )
        d = r.to_dict()
        assert d["ticker"] == "TZOO"
        assert d["source"] == "sec_edgar"
        assert d["cik"] == "0001375966"
        assert d["filings_downloaded"] == 28
        assert d["filings_coverage_pct"] == 100.0

    def test_gaps_list(self):
        r = AcquisitionResult(
            ticker="TEST",
            gaps=["Missing annual filings"],
        )
        assert "Missing annual filings" in r.to_dict()["gaps"]