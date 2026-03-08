from __future__ import annotations

import pytest

from elsian.cli import _get_fetcher as cli_fetcher
from elsian.acquire.phase import _get_fetcher as phase_fetcher
from elsian.models.case import CaseConfig


def _case(hint: str) -> CaseConfig:
    return CaseConfig(ticker="TEST", source_hint=hint, case_dir="/tmp/test")


def test_cli_hkex_hint_returns_hkex_fetcher():
    """CLI must route hkex/hkex_manual to HkexFetcher, not ManualFetcher."""
    from elsian.acquire.hkex import HkexFetcher

    for hint in ("hkex", "hkex_manual"):
        fetcher = cli_fetcher(_case(hint))
        assert isinstance(fetcher, HkexFetcher), (
            f"source_hint={hint!r}: expected HkexFetcher, got {type(fetcher).__name__}"
        )


def test_cli_unknown_hint_falls_back_to_manual_fetcher():
    from elsian.acquire.manual import ManualFetcher

    assert isinstance(cli_fetcher(_case("bogus_source")), ManualFetcher)


@pytest.mark.parametrize("hint", [
    "sec", "sec_edgar", "asx", "eu", "eu_manual", "manual_http",
    "hkex", "hkex_manual", "unknown_source",
])
def test_cli_and_phase_fetcher_are_same_type(hint: str):
    """CLI _get_fetcher and AcquirePhase _get_fetcher must agree on every hint."""
    case = _case(hint)
    cli_type = type(cli_fetcher(case))
    phase_type = type(phase_fetcher(case))
    assert cli_type is phase_type, (
        f"source_hint={hint!r}: CLI returns {cli_type.__name__}, "
        f"AcquirePhase returns {phase_type.__name__}"
    )
