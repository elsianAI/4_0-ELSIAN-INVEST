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

    # ── BL-066 observability fields ───────────────────────────────────

    def test_bl066_default_observability_fields(self):
        r = AcquisitionResult()
        assert r.source_kind == ""
        assert r.cache_hit is False
        assert r.retries_total == 0
        assert r.throttle_ms == 0.0

    def test_bl066_observability_fields_round_trip(self):
        r = AcquisitionResult(
            ticker="KAR",
            source="asx",
            source_kind="filing",
            cache_hit=True,
            retries_total=3,
            throttle_ms=450.0,
        )
        d = r.to_dict()
        assert d["source_kind"] == "filing"
        assert d["cache_hit"] is True
        assert d["retries_total"] == 3
        assert d["throttle_ms"] == 450.0

    def test_bl066_to_dict_backward_compatible(self):
        """Existing consumers keying on known fields are unaffected."""
        r = AcquisitionResult(
            ticker="TZOO",
            source="sec_edgar",
            filings_downloaded=10,
            filings_failed=0,
            filings_coverage_pct=83.3,
        )
        d = r.to_dict()
        # All original keys still present
        for key in (
            "ticker", "source", "cik", "filings_downloaded",
            "filings_failed", "filings_coverage_pct",
            "coverage", "gaps", "notes", "download_date",
        ):
            assert key in d, f"Missing key: {key}"
        # New keys also present
        for key in ("source_kind", "cache_hit", "retries_total", "throttle_ms"):
            assert key in d, f"Missing BL-066 key: {key}"
