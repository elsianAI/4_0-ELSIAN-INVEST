"""Tests for CLI fetcher routing — post BL-062 via registry.

After BL-062 both ``elsian.cli`` and ``elsian.acquire.phase`` delegate to
``elsian.acquire.registry.get_fetcher``.  These tests verify that the CLI
adapter path still resolves the correct fetcher type for every known hint.
"""

from __future__ import annotations

import pytest

from elsian.acquire.registry import get_fetcher
from elsian.models.case import CaseConfig


def _case(hint: str) -> CaseConfig:
    return CaseConfig(ticker="TEST", source_hint=hint, case_dir="/tmp/test")


def test_hkex_hint_returns_hkex_fetcher():
    """hkex / hkex_manual must route to HkexFetcher, not ManualFetcher."""
    from elsian.acquire.hkex import HkexFetcher

    for hint in ("hkex", "hkex_manual"):
        fetcher = get_fetcher(_case(hint))
        assert isinstance(fetcher, HkexFetcher), (
            f"source_hint={hint!r}: expected HkexFetcher, got {type(fetcher).__name__}"
        )


def test_unknown_hint_falls_back_to_manual_fetcher():
    from elsian.acquire.manual import ManualFetcher

    assert isinstance(get_fetcher(_case("bogus_source")), ManualFetcher)


@pytest.mark.parametrize("hint,expected_cls_name", [
    ("sec", "SecEdgarFetcher"),
    ("sec_edgar", "SecEdgarFetcher"),
    ("asx", "AsxFetcher"),
    ("eu", "EuRegulatorsFetcher"),
    ("eu_manual", "EuRegulatorsFetcher"),
    ("manual_http", "EuRegulatorsFetcher"),
    ("hkex", "HkexFetcher"),
    ("hkex_manual", "HkexFetcher"),
    ("unknown_source", "ManualFetcher"),
])
def test_registry_routing(hint: str, expected_cls_name: str):
    """Registry must resolve every canonical hint to the expected fetcher class."""
    fetcher = get_fetcher(_case(hint))
    assert type(fetcher).__name__ == expected_cls_name, (
        f"source_hint={hint!r}: expected {expected_cls_name}, "
        f"got {type(fetcher).__name__}"
    )
