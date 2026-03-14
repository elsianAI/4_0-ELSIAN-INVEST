from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"


def _load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_handoff = _load_script_module("write_handoff", SCRIPTS_ROOT / "write_handoff.py")
read_handoff = _load_script_module("read_handoff", SCRIPTS_ROOT / "read_handoff.py")


def _fake_report(*, branch: str = "main", next_resolution_mode: str = "empty_backlog_discovery"):
    return {
        "branch": branch,
        "worktree": {
            "technical_dirty": [],
            "governance_dirty": [],
            "other_dirty": [],
            "untracked_technical_files": [],
            "untracked_test_files": [],
        },
        "backlog": {
            "active_ids": [],
            "active_count": 0,
        },
        "project_state": {
            "module1_status": "OPEN",
        },
        "document_sync": {
            "project_state_lags_changelog": False,
        },
        "summary": {
            "next_resolution_mode": next_resolution_mode,
            "governance_contract_violations": [],
        },
    }


def test_build_handoff_populates_stale_if_from_live_state(tmp_path: Path) -> None:
    handoff = write_handoff.build_handoff(
        tmp_path,
        generated_by="pytest",
        current_focus="test focus",
        status="active",
        last_completed_step="step 1",
        recommended_next_route="auditor",
        recommended_next_action="continue",
        blocking_questions=["Need review?"],
        scope="testing",
        report=_fake_report(),
        head="abc123",
    )

    assert handoff["schema_version"] == "1.0"
    assert handoff["head"] == "abc123"
    assert handoff["stale_if"]["head_must_match"] == "abc123"
    assert handoff["stale_if"]["branch_must_match"] == "main"
    assert handoff["stale_if"]["live_state_snapshot"]["next_resolution_mode"] == "empty_backlog_discovery"
    assert handoff["stale_if"]["live_state_fingerprint_must_match"]


def test_validate_handoff_marks_stale_when_head_changes(tmp_path: Path) -> None:
    handoff = write_handoff.build_handoff(
        tmp_path,
        generated_by="pytest",
        current_focus="test focus",
        status="active",
        last_completed_step="step 1",
        recommended_next_route="auditor",
        recommended_next_action="continue",
        blocking_questions=[],
        scope="testing",
        report=_fake_report(),
        head="abc123",
    )

    validation = read_handoff.validate_handoff(
        handoff,
        report=_fake_report(),
        current_head="def456",
    )

    assert validation["valid"] is False
    assert validation["effective_status"] == "stale"
    assert "head_changed" in validation["reasons"]


def test_validate_handoff_marks_stale_when_live_state_changes(tmp_path: Path) -> None:
    handoff = write_handoff.build_handoff(
        tmp_path,
        generated_by="pytest",
        current_focus="test focus",
        status="active",
        last_completed_step="step 1",
        recommended_next_route="auditor",
        recommended_next_action="continue",
        blocking_questions=[],
        scope="testing",
        report=_fake_report(next_resolution_mode="empty_backlog_discovery"),
        head="abc123",
    )

    validation = read_handoff.validate_handoff(
        handoff,
        report=_fake_report(next_resolution_mode="execute_backlog"),
        current_head="abc123",
    )

    assert validation["valid"] is False
    assert validation["effective_status"] == "stale"
    assert "live_state_changed" in validation["reasons"]
    assert validation["live_state_diff"]["next_resolution_mode"] == {
        "stored": "empty_backlog_discovery",
        "current": "execute_backlog",
    }
