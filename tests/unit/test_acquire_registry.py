"""Unit tests for elsian.acquire.registry (BL-062)."""

from __future__ import annotations

import pytest

from elsian.acquire.registry import get_fetcher, _HINT_TO_KEY
from elsian.models.case import CaseConfig


def _case(hint: str) -> CaseConfig:
    return CaseConfig(ticker="TEST", source_hint=hint, case_dir="/tmp/test")


def test_hint_to_key_has_expected_entries():
    for hint in ("sec", "sec_edgar", "asx", "eu", "eu_manual", "manual_http", "hkex", "hkex_manual"):
        assert hint in _HINT_TO_KEY, f"{hint!r} missing from _HINT_TO_KEY"


def test_unknown_hint_not_in_map():
    assert "bogus" not in _HINT_TO_KEY


@pytest.mark.parametrize("hint,expected_cls", [
    ("sec", "SecEdgarFetcher"),
    ("sec_edgar", "SecEdgarFetcher"),
    ("asx", "AsxFetcher"),
    ("eu", "EuRegulatorsFetcher"),
    ("eu_manual", "EuRegulatorsFetcher"),
    ("manual_http", "EuRegulatorsFetcher"),
    ("hkex", "HkexFetcher"),
    ("hkex_manual", "HkexFetcher"),
    ("manual", "ManualFetcher"),
    ("unknown_xyz", "ManualFetcher"),
])
def test_get_fetcher_returns_correct_type(hint: str, expected_cls: str):
    fetcher = get_fetcher(_case(hint))
    assert type(fetcher).__name__ == expected_cls, (
        f"hint={hint!r}: expected {expected_cls}, got {type(fetcher).__name__}"
    )


def test_get_fetcher_case_insensitive():
    from elsian.acquire.sec_edgar import SecEdgarFetcher
    for hint in ("SEC", "Sec", "SEC_EDGAR", "Sec_Edgar"):
        fetcher = get_fetcher(_case(hint))
        assert isinstance(fetcher, SecEdgarFetcher), f"hint={hint!r} should resolve to SecEdgarFetcher"
