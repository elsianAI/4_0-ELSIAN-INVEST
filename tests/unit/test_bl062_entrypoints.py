"""tests/unit/test_bl062_entrypoints.py — BL-062 audit remediation.

Verifies that the refactored entrypoints ``cmd_acquire`` (elsian/cli.py)
and ``AcquirePhase.run`` (elsian/acquire/phase.py) both delegate fetcher
routing exclusively to ``elsian.acquire.registry.get_fetcher``, without
reimplementing any local selection logic.

These tests complement ``test_acquire_registry.py`` (registry contract) and
``test_cli_fetcher_routing.py`` (hint->class mapping) by exercising the *call
path* of the two entrypoints themselves.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from elsian.models.case import CaseConfig
from elsian.models.result import AcquisitionResult


# ── helpers ───────────────────────────────────────────────────────────


def _fake_acq(ticker: str = "TST") -> AcquisitionResult:
    return AcquisitionResult(
        ticker=ticker,
        source="sec",
        filings_downloaded=3,
        filings_coverage_pct=75.0,
    )


def _fetcher_with_acquire(acq: AcquisitionResult) -> MagicMock:
    """Mock fetcher that exposes acquire(); hasattr check returns True."""
    f = MagicMock()
    f.acquire.return_value = acq
    return f


def _fetcher_fetch_only() -> MagicMock:
    """Mock spec'd to fetch() only; hasattr(f, 'acquire') → False."""
    f = MagicMock(spec=["fetch"])
    f.fetch.return_value = []
    return f


def _write_case(path: Path, ticker: str, source_hint: str = "sec") -> None:
    (path / "case.json").write_text(
        json.dumps({"ticker": ticker, "source_hint": source_hint}),
        encoding="utf-8",
    )


# ── cmd_acquire delegation ────────────────────────────────────────────


class TestCmdAcquireDelegatesToRegistry:
    """cmd_acquire must resolve the fetcher via get_fetcher only."""

    def test_get_fetcher_called_once_with_correct_case(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """get_fetcher receives the CaseConfig built from case.json."""
        _write_case(tmp_path, ticker="FAKE", source_hint="sec")
        mock_fetcher = _fetcher_with_acquire(_fake_acq("FAKE"))

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.cli.get_fetcher", return_value=mock_fetcher) as mock_gf,
        ):
            from elsian.cli import cmd_acquire

            cmd_acquire(argparse.Namespace(ticker="FAKE"))

        mock_gf.assert_called_once()
        resolved: CaseConfig = mock_gf.call_args[0][0]
        assert resolved.ticker == "FAKE"
        assert resolved.source_hint == "sec"

    def test_acquire_path_writes_manifest(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """When fetcher has acquire(), cmd_acquire writes filings_manifest.json."""
        _write_case(tmp_path, ticker="FAKEACQ")
        acq = _fake_acq("FAKEACQ")
        mock_fetcher = _fetcher_with_acquire(acq)

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.cli.get_fetcher", return_value=mock_fetcher),
        ):
            from elsian.cli import cmd_acquire

            cmd_acquire(argparse.Namespace(ticker="FAKEACQ"))

        mock_fetcher.acquire.assert_called_once()
        manifest = tmp_path / "filings_manifest.json"
        assert manifest.exists(), "manifest not written"
        data = json.loads(manifest.read_text())
        assert data["filings_downloaded"] == 3

    def test_fetch_fallback_when_no_acquire_method(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """When fetcher lacks acquire(), cmd_acquire calls fetch() instead."""
        _write_case(tmp_path, ticker="FAKEFETCH", source_hint="manual")
        mock_fetcher = _fetcher_fetch_only()

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.cli.get_fetcher", return_value=mock_fetcher),
        ):
            from elsian.cli import cmd_acquire

            cmd_acquire(argparse.Namespace(ticker="FAKEFETCH"))

        mock_fetcher.fetch.assert_called_once()

    def test_no_local_routing_logic_in_cmd_acquire(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """get_fetcher is the sole routing decision — called exactly once."""
        _write_case(tmp_path, ticker="BYPASS", source_hint="asx")
        call_count: list[int] = []

        def tracking(case: CaseConfig) -> MagicMock:
            call_count.append(1)
            return _fetcher_with_acquire(_fake_acq("BYPASS"))

        with (
            patch("elsian.cli._find_case_dir", return_value=tmp_path),
            patch("elsian.cli.get_fetcher", side_effect=tracking),
        ):
            from elsian.cli import cmd_acquire

            cmd_acquire(argparse.Namespace(ticker="BYPASS"))

        assert call_count == [1], (
            f"get_fetcher must be called exactly once; got {len(call_count)}"
        )


# ── AcquirePhase.run delegation ───────────────────────────────────────


class TestAcquirePhaseRunDelegatesToRegistry:
    """AcquirePhase.run must route solely via registry.get_fetcher."""

    def test_get_fetcher_called_with_context_case(self, tmp_path: Path) -> None:
        """get_fetcher receives context.case as its sole argument."""
        from elsian.acquire.phase import AcquirePhase
        from elsian.context import PipelineContext

        case = CaseConfig(ticker="PHA", source_hint="sec", case_dir=str(tmp_path))
        ctx = PipelineContext(case=case)
        mock_fetcher = _fetcher_with_acquire(_fake_acq("PHA"))

        with patch("elsian.acquire.phase.get_fetcher", return_value=mock_fetcher) as mock_gf:
            AcquirePhase().run(ctx)

        mock_gf.assert_called_once_with(case)

    def test_run_returns_success_and_data_from_fetcher(self, tmp_path: Path) -> None:
        """PhaseResult.data is the AcquisitionResult produced by the fetcher."""
        from elsian.acquire.phase import AcquirePhase
        from elsian.context import PipelineContext

        case = CaseConfig(ticker="PHAB", source_hint="sec", case_dir=str(tmp_path))
        ctx = PipelineContext(case=case)
        acq = _fake_acq("PHAB")
        mock_fetcher = _fetcher_with_acquire(acq)

        with patch("elsian.acquire.phase.get_fetcher", return_value=mock_fetcher):
            result = AcquirePhase().run(ctx)

        assert result.success
        assert result.phase_name == "AcquirePhase"
        mock_fetcher.acquire.assert_called_once_with(case)
        assert result.data is acq

    def test_fetch_fallback_sets_context_filings(self, tmp_path: Path) -> None:
        """When fetcher lacks acquire(), run falls back to fetch() and sets ctx.filings."""
        from elsian.acquire.phase import AcquirePhase
        from elsian.context import PipelineContext

        case = CaseConfig(ticker="PHAC", source_hint="manual", case_dir=str(tmp_path))
        ctx = PipelineContext(case=case)
        sentinels = [object(), object()]
        mock_fetcher = MagicMock(spec=["fetch"])
        mock_fetcher.fetch.return_value = sentinels

        with patch("elsian.acquire.phase.get_fetcher", return_value=mock_fetcher):
            result = AcquirePhase().run(ctx)

        mock_fetcher.fetch.assert_called_once_with(case)
        assert result.success
        assert ctx.filings is sentinels

    def test_fetcher_type_consistent_with_direct_registry_call(
        self, tmp_path: Path
    ) -> None:
        """The fetcher type resolved by AcquirePhase equals get_fetcher(case) directly."""
        from elsian.acquire.phase import AcquirePhase
        from elsian.acquire.registry import get_fetcher
        from elsian.context import PipelineContext

        case = CaseConfig(ticker="PHAD", source_hint="sec", case_dir=str(tmp_path))
        ctx = PipelineContext(case=case)
        resolved: list[type] = []
        original = get_fetcher

        def spy(c: CaseConfig):  # noqa: ANN001
            f = original(c)
            resolved.append(type(f))
            stub = MagicMock()
            stub.acquire.return_value = _fake_acq("PHAD")
            return stub

        with patch("elsian.acquire.phase.get_fetcher", side_effect=spy):
            AcquirePhase().run(ctx)

        direct_type = type(original(case))
        assert resolved == [direct_type], (
            f"AcquirePhase resolved {resolved[0].__name__}, "
            f"registry directly resolves {direct_type.__name__}"
        )
