"""tests/integration/test_scaffold_command.py — integration tests for scaffold CLI.

Exercises ``elsian scaffold-task`` and ``elsian scaffold-case`` end-to-end
through the CLI's command functions, using tmp_path to isolate all file I/O.
No network calls.  No mutation of real tasks/ or cases/ directories.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scaffold_task_args(**overrides: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "task_id": "BL-TEST",
        "title": "Test scaffold task",
        "kind": "technical",
        "validation_tier": "targeted",
        "write_set": ["elsian/scaffold.py", "elsian/cli.py"],
        "risks": ["Scope creep", "Test coverage gap"],
        "validation_plan": "Run pytest -q on targeted tests.",
        "acceptance_criteria": "All targeted tests pass, check_governance clean.",
        "references": None,
        "blocked_surfaces": None,
        "notes": "",
        "force": False,
        "output": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_scaffold_case_args(**overrides: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "ticker": "NEWCO",
        "source_hint": "sec",
        "currency": "USD",
        "period_scope": "ANNUAL_ONLY",
        "exchange": "NASDAQ",
        "country": "US",
        "cik": None,
        "fiscal_year_end_month": None,
        "notes": "",
        "force": False,
        "output": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# cmd_scaffold_task
# ---------------------------------------------------------------------------


class TestCmdScaffoldTask:
    def test_generates_manifest_and_notes(self, tmp_path: Path, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)

        manifest_path = tmp_path / "BL-TEST.task_manifest.json"
        notes_path = tmp_path / "BL-TEST.task_notes.md"
        assert manifest_path.exists()
        assert notes_path.exists()

    def test_manifest_passes_contract_validation(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vc", REPO_ROOT / "scripts" / "validate_contracts.py"
        )
        assert spec and spec.loader
        vc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vc)  # type: ignore[union-attr]

        manifest_path = tmp_path / "BL-TEST.task_manifest.json"
        issues = vc.validate_single_contract("task_manifest", manifest_path)
        assert issues == [], f"Contract violations: {issues}"

    def test_manifest_has_risks_in_notes(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path), risks=["Critical risk A"])
        cmd_scaffold_task(args)

        data = json.loads((tmp_path / "BL-TEST.task_manifest.json").read_text("utf-8"))
        assert "Critical risk A" in data["notes"]

    def test_manifest_has_validation_plan_in_notes(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)

        data = json.loads((tmp_path / "BL-TEST.task_manifest.json").read_text("utf-8"))
        assert "Run pytest -q on targeted tests." in data["notes"]

    def test_manifest_has_acceptance_criteria_in_notes(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)

        data = json.loads((tmp_path / "BL-TEST.task_manifest.json").read_text("utf-8"))
        assert "All targeted tests pass" in data["notes"]

    def test_notes_md_has_structured_sections(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)

        notes_content = (tmp_path / "BL-TEST.task_notes.md").read_text("utf-8")
        for section in ("## Risks", "## Validation Plan", "## Acceptance Criteria", "## Write Set"):
            assert section in notes_content, f"Missing section: {section}"

    def test_exits_1_when_risks_empty(self, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(risks=[])
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_exits_1_when_risks_not_provided(self, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(risks=None)
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_exits_1_when_validation_plan_missing(self, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(validation_plan="")
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_exits_1_when_acceptance_criteria_missing(self, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(acceptance_criteria="")
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_exits_1_when_write_set_empty(self, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(write_set=[])
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_exits_1_on_duplicate_without_force(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_task

        args = _make_scaffold_task_args(output=str(tmp_path))
        cmd_scaffold_task(args)
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_task(args)
        assert exc_info.value.code == 1

    def test_force_flag_overwrites(self, tmp_path: Path, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        cmd_scaffold_task(_make_scaffold_task_args(output=str(tmp_path)))
        # Second call with force should succeed
        cmd_scaffold_task(_make_scaffold_task_args(output=str(tmp_path), force=True, title="Updated"))
        data = json.loads((tmp_path / "BL-TEST.task_manifest.json").read_text("utf-8"))
        assert data["title"] == "Updated"

    def test_stdout_summary_printed(self, tmp_path: Path, capsys) -> None:
        from elsian.cli import cmd_scaffold_task

        cmd_scaffold_task(_make_scaffold_task_args(output=str(tmp_path)))
        out = capsys.readouterr().out
        assert "BL-TEST" in out
        assert "Manifest" in out or "manifest" in out

    def test_writes_to_tasks_dir_by_default(self, monkeypatch) -> None:
        """Smoke test that default output_dir is tasks/ if no --output given."""
        import elsian.scaffold as sc

        written: list[Path] = []
        original = sc.write_task_seed

        def _fake(*args, **kwargs):
            written.append(kwargs.get("output_dir"))
            return (Path("/tmp/BL-TEST.task_manifest.json"), Path("/tmp/BL-TEST.task_notes.md"))

        monkeypatch.setattr(sc, "write_task_seed", _fake)

        from elsian.cli import cmd_scaffold_task
        args = _make_scaffold_task_args(output=None)
        cmd_scaffold_task(args)
        assert written[0] is None  # output_dir=None → helper uses TASKS_DIR


# ---------------------------------------------------------------------------
# cmd_scaffold_case
# ---------------------------------------------------------------------------


class TestCmdScaffoldCase:
    def test_generates_case_json_and_notes(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(output=str(tmp_path))
        cmd_scaffold_case(args)

        assert (tmp_path / "NEWCO" / "case.json").exists()
        assert (tmp_path / "NEWCO" / "CASE_NOTES.md").exists()

    def test_case_json_passes_contract_validation(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(output=str(tmp_path))
        cmd_scaffold_case(args)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "vc", REPO_ROOT / "scripts" / "validate_contracts.py"
        )
        assert spec and spec.loader
        vc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vc)  # type: ignore[union-attr]

        case_path = tmp_path / "NEWCO" / "case.json"
        data = json.loads(case_path.read_text("utf-8"))
        issues = vc.validate_case_data(data, case_path)
        assert issues == [], f"Contract violations: {issues}"

    def test_ticker_uppercased_in_dir_and_json(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(ticker="newco", output=str(tmp_path))
        cmd_scaffold_case(args)

        data = json.loads((tmp_path / "NEWCO" / "case.json").read_text("utf-8"))
        assert data["ticker"] == "NEWCO"

    def test_currency_uppercased(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(currency="aud", output=str(tmp_path))
        cmd_scaffold_case(args)

        data = json.loads((tmp_path / "NEWCO" / "case.json").read_text("utf-8"))
        assert data["currency"] == "AUD"

    def test_case_notes_has_structured_sections(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(output=str(tmp_path))
        cmd_scaffold_case(args)

        notes = (tmp_path / "NEWCO" / "CASE_NOTES.md").read_text("utf-8")
        for section in ("## TODO before acquire", "## Risks", "## Acceptance Criteria", "## Source Notes"):
            assert section in notes, f"Missing section: {section}"

    def test_exits_1_on_duplicate_without_force(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(output=str(tmp_path))
        cmd_scaffold_case(args)
        with pytest.raises(SystemExit) as exc_info:
            cmd_scaffold_case(args)
        assert exc_info.value.code == 1

    def test_force_flag_overwrites(self, tmp_path: Path, capsys) -> None:
        from elsian.cli import cmd_scaffold_case

        cmd_scaffold_case(_make_scaffold_case_args(output=str(tmp_path)))
        cmd_scaffold_case(_make_scaffold_case_args(output=str(tmp_path), force=True, currency="EUR"))
        data = json.loads((tmp_path / "NEWCO" / "case.json").read_text("utf-8"))
        assert data["currency"] == "EUR"

    def test_stdout_summary_printed(self, tmp_path: Path, capsys) -> None:
        from elsian.cli import cmd_scaffold_case

        cmd_scaffold_case(_make_scaffold_case_args(output=str(tmp_path)))
        out = capsys.readouterr().out
        assert "NEWCO" in out

    def test_full_period_scope(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(period_scope="FULL", output=str(tmp_path))
        cmd_scaffold_case(args)

        data = json.loads((tmp_path / "NEWCO" / "case.json").read_text("utf-8"))
        assert data["period_scope"] == "FULL"

    def test_optional_fields_propagated(self, tmp_path: Path) -> None:
        from elsian.cli import cmd_scaffold_case

        args = _make_scaffold_case_args(
            cik="0001234567",
            fiscal_year_end_month=6,
            output=str(tmp_path),
        )
        cmd_scaffold_case(args)

        data = json.loads((tmp_path / "NEWCO" / "case.json").read_text("utf-8"))
        assert data["cik"] == "0001234567"
        assert data["fiscal_year_end_month"] == 6


# ---------------------------------------------------------------------------
# Contract: BL-071 task manifest itself passes contract validation
# ---------------------------------------------------------------------------


def test_bl071_task_manifest_passes_contract() -> None:
    """BL-071.task_manifest.json must pass validate_task_manifest_data."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "vc", REPO_ROOT / "scripts" / "validate_contracts.py"
    )
    assert spec and spec.loader
    vc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vc)  # type: ignore[union-attr]

    manifest_path = REPO_ROOT / "tasks" / "BL-071.task_manifest.json"
    assert manifest_path.exists(), "tasks/BL-071.task_manifest.json not found"
    issues = vc.validate_single_contract("task_manifest", manifest_path)
    assert issues == [], f"BL-071 manifest contract violations: {issues}"
