"""Fetcher registry."""

from __future__ import annotations

from elsian.models.case import CaseConfig

_HINT_TO_KEY: dict[str, str] = {
    "sec": "sec_edgar",
    "sec_edgar": "sec_edgar",
    "asx": "asx",
    "eu": "eu_regulators",
    "eu_manual": "eu_regulators",
    "manual_http": "eu_regulators",
    "hkex": "hkex",
    "hkex_manual": "hkex",
}


def get_fetcher(case: CaseConfig):
    """Return Fetcher for case.source_hint."""
    key = _HINT_TO_KEY.get(case.source_hint.lower())
    if key == "sec_edgar":
        from elsian.acquire.sec_edgar import SecEdgarFetcher
        return SecEdgarFetcher()
    if key == "asx":
        from elsian.acquire.asx import AsxFetcher
        return AsxFetcher()
    if key == "eu_regulators":
        from elsian.acquire.eu_regulators import EuRegulatorsFetcher
        return EuRegulatorsFetcher()
    if key == "hkex":
        from elsian.acquire.hkex import HkexFetcher
        return HkexFetcher()
    from elsian.acquire.manual import ManualFetcher
    return ManualFetcher()
