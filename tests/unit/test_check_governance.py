from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_governance.py"
SPEC = importlib.util.spec_from_file_location("check_governance", MODULE_PATH)
assert SPEC and SPEC.loader
check_governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_governance)


def test_classify_dirty_path_buckets_workspace_governance_and_technical():
    assert (
        check_governance.classify_dirty_path("4_0-ELSIAN-INVEST.code-workspace")
        == "workspace_only_dirty"
    )
    assert check_governance.classify_dirty_path("CHANGELOG.md") == "governance_dirty"
    assert check_governance.classify_dirty_path("docs/project/ROLES.md") == "governance_dirty"
    assert check_governance.classify_dirty_path("cases/TEP/case.json") == "technical_dirty"
    assert check_governance.classify_dirty_path("elsian/extract/narrative.py") == "technical_dirty"


def test_count_manual_override_entries_handles_nested_period_map():
    payload = {
        "FY2024": {
            "dividends_per_share": {"value": 1.23, "note": "foo"},
            "fcf": {"value": 4.56, "note": "bar"},
        },
        "FY2023": {
            "dividends_per_share": {
                "value": 0.99,
                "note": "baz",
                "source_filing": "report.txt",
                "extraction_method": "manual",
            }
        },
    }
    assert check_governance.count_manual_override_entries(payload) == 3


def test_parse_duplicate_backlog_ids_returns_line_numbers(tmp_path: Path):
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "# Backlog\n\n"
        "### BL-001 — One\n"
        "### BL-002 — Two\n"
        "### BL-001 — Duplicate\n"
    )
    assert check_governance.parse_duplicate_backlog_ids(backlog) == [
        {"id": "BL-001", "lines": [3, 5], "count": 2}
    ]


def test_build_report_detects_dirty_buckets_and_state_lag(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "cases/AAA").mkdir(parents=True)

    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-05\n"
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "### BL-054 — Uno\n### BL-054 — Dos\n"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-06\n")
    (tmp_path / "cases/AAA/case.json").write_text(
        '{"manual_overrides":{"FY2024":{"fcf":{"value":1,"note":"x"}}}}'
    )

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return "\n".join(
                [
                    " M CHANGELOG.md",
                    " M cases/AAA/case.json",
                    "?? tests/unit/test_new.py",
                    " M 4_0-ELSIAN-INVEST.code-workspace",
                ]
            )
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)

    report = check_governance.build_report(tmp_path)

    assert report["branch"] == "main"
    assert report["head"] == "abc1234"
    assert report["worktree"]["technical_dirty"] == [
        "cases/AAA/case.json",
        "tests/unit/test_new.py",
    ]
    assert report["worktree"]["governance_dirty"] == ["CHANGELOG.md"]
    assert report["worktree"]["workspace_only_dirty"] == ["4_0-ELSIAN-INVEST.code-workspace"]
    assert report["worktree"]["untracked_technical_files"] == ["tests/unit/test_new.py"]
    assert report["worktree"]["untracked_test_files"] == ["tests/unit/test_new.py"]
    assert report["document_sync"]["project_state_lags_changelog"] is True
    assert report["backlog"]["duplicate_ids"] == [{"id": "BL-054", "lines": [1, 2], "count": 2}]
    assert report["manual_overrides"]["nonzero_by_ticker"] == {"AAA": 1}


# ---------------------------------------------------------------------------
# BL-061: check_manifest_scope enforcement
# ---------------------------------------------------------------------------


_BASE_MANIFEST = {
    "task_id": "BL-061",
    "title": "Test",
    "kind": "technical",
    "validation_tier": "targeted",
    "claimed_bl_status": "in_progress",
    "write_set": ["CHANGELOG.md", "scripts/check_governance.py"],
    "blocked_surfaces": ["elsian/", "config/"],
    "expected_governance_updates": ["CHANGELOG.md"],
}


def test_check_manifest_scope_passes_when_all_dirty_in_write_set():
    """No violations when every dirty path is declared in write_set."""
    violations = check_governance.check_manifest_scope(
        _BASE_MANIFEST,
        ["CHANGELOG.md", "scripts/check_governance.py"],
    )
    assert violations == []


def test_check_manifest_scope_fails_when_dirty_path_outside_write_set():
    """write_set_violation reported when a dirty path is not in write_set."""
    violations = check_governance.check_manifest_scope(
        _BASE_MANIFEST,
        ["CHANGELOG.md", "docs/project/PROJECT_STATE.md"],
    )
    assert any("write_set_violation" in v and "PROJECT_STATE.md" in v for v in violations)


def test_check_manifest_scope_fails_when_blocked_surface_file_touched():
    """blocked_surface_violation reported when a dirty path touches a blocked surface."""
    violations = check_governance.check_manifest_scope(
        _BASE_MANIFEST,
        ["elsian/pipeline.py"],
    )
    assert any("blocked_surface_violation" in v and "elsian/pipeline.py" in v for v in violations)


def test_check_manifest_scope_fails_when_blocked_surface_nested_file_touched():
    """blocked_surface_violation reported for deeply nested file under blocked surface."""
    violations = check_governance.check_manifest_scope(
        _BASE_MANIFEST,
        ["config/field_aliases.json"],
    )
    assert any("blocked_surface_violation" in v and "config/field_aliases.json" in v for v in violations)


def test_check_manifest_scope_fails_when_governance_reconciliation_missing():
    """missing_reconciliation reported when expected doc absent from diff and status=done."""
    manifest = {**_BASE_MANIFEST, "claimed_bl_status": "done"}
    violations = check_governance.check_manifest_scope(
        manifest,
        ["scripts/check_governance.py"],  # CHANGELOG.md not dirty
    )
    assert any("missing_reconciliation" in v and "CHANGELOG.md" in v for v in violations)


def test_check_manifest_scope_passes_when_all_reconciled_and_done():
    """No missing_reconciliation when all expected docs are dirty and status=done."""
    manifest = {**_BASE_MANIFEST, "claimed_bl_status": "done"}
    violations = check_governance.check_manifest_scope(
        manifest,
        ["CHANGELOG.md", "scripts/check_governance.py"],
    )
    assert not any("missing_reconciliation" in v for v in violations)


def test_check_manifest_scope_reconciliation_not_enforced_when_in_progress():
    """missing_reconciliation is NOT raised when claimed_bl_status is in_progress."""
    violations = check_governance.check_manifest_scope(
        _BASE_MANIFEST,  # claimed_bl_status=in_progress
        ["scripts/check_governance.py"],  # CHANGELOG.md not dirty
    )
    assert not any("missing_reconciliation" in v for v in violations)


def test_check_manifest_scope_fails_on_governance_only_tier_with_technical_file():
    """tier_violation reported when governance-only manifest has technical dirty path."""
    manifest = {**_BASE_MANIFEST, "validation_tier": "governance-only", "write_set": ["CHANGELOG.md", "scripts/check_governance.py"]}
    violations = check_governance.check_manifest_scope(
        manifest,
        ["scripts/check_governance.py"],
    )
    assert any("tier_violation" in v and "governance-only" in v for v in violations)


def test_check_manifest_scope_governance_update_exempt_from_write_set_violation():
    """Governance path in expected_governance_updates is a permitted surface even if not in write_set."""
    manifest = {
        **_BASE_MANIFEST,
        "write_set": ["CHANGELOG.md", "scripts/check_governance.py"],
        "expected_governance_updates": ["CHANGELOG.md", "docs/project/BACKLOG.md"],
        "claimed_bl_status": "done",
    }
    violations = check_governance.check_manifest_scope(
        manifest,
        ["CHANGELOG.md", "scripts/check_governance.py", "docs/project/BACKLOG.md"],
    )
    assert not any("write_set_violation" in v and "BACKLOG.md" in v for v in violations)


def test_check_manifest_scope_technical_path_in_governance_updates_still_flagged():
    """Technical path in expected_governance_updates does NOT exempt it from write_set_violation."""
    manifest = {
        **_BASE_MANIFEST,
        "write_set": ["CHANGELOG.md"],
        "expected_governance_updates": ["CHANGELOG.md", "tests/unit/test_new.py"],
    }
    violations = check_governance.check_manifest_scope(
        manifest,
        ["CHANGELOG.md", "tests/unit/test_new.py"],
    )
    assert any("write_set_violation" in v and "tests/unit/test_new.py" in v for v in violations)


# ---------------------------------------------------------------------------
# BL-061 audit fix: --task-manifest fail-closed on contract-invalid manifests
# ---------------------------------------------------------------------------


def test_check_governance_fails_closed_on_contract_invalid_manifest(tmp_path: Path):
    """--task-manifest exits 1 without running scope enforcement when manifest fails contract.

    Closes the gap identified in the BL-061 audit: a malformed or incoherent
    manifest must never reach check_manifest_scope.
    """
    bad_manifest = tmp_path / "bad.task_manifest.json"
    bad_manifest.write_text(
        json.dumps(
            {
                "task_id": "BL-bad",
                "title": "Bad",
                "kind": "INVALID_KIND",
                "validation_tier": "targeted",
                "claimed_bl_status": "none",
                "write_set": ["CHANGELOG.md"],
            }
        ),
        encoding="utf-8",
    )

    result = check_governance.main(["--task-manifest", str(bad_manifest)])

    assert result == 1


# ---------------------------------------------------------------------------
# BL-061 closeout-prep: expected_governance_updates="none" in check_manifest_scope
# ---------------------------------------------------------------------------


def test_check_manifest_scope_none_string_governance_updates_skips_reconciliation():
    """expected_governance_updates='none' disables reconciliation check even when status=done."""
    manifest = {
        **_BASE_MANIFEST,
        "claimed_bl_status": "done",
        "expected_governance_updates": "none",
    }
    violations = check_governance.check_manifest_scope(
        manifest,
        ["CHANGELOG.md", "scripts/check_governance.py"],
    )
    assert not any("missing_reconciliation" in v for v in violations)


# ---------------------------------------------------------------------------
# BL-061 final finding: schemas/ and tasks/ classify as technical_dirty
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Reproducibility fix: missing_reconciliation must NOT fire on clean worktree
# ---------------------------------------------------------------------------


def test_check_manifest_scope_done_clean_worktree_no_missing_reconciliation():
    """manifest done + dirty_paths=[] (clean repo) must NOT raise missing_reconciliation.

    A historical manifest already committed produces no diff; enforcing
    reconciliation here would break reproducibility for every closed packet.
    """
    manifest = {
        **_BASE_MANIFEST,
        "claimed_bl_status": "done",
        "expected_governance_updates": [
            "CHANGELOG.md",
            "docs/project/BACKLOG.md",
            "docs/project/BACKLOG_DONE.md",
            "docs/project/PROJECT_STATE.md",
        ],
    }
    violations = check_governance.check_manifest_scope(manifest, [])
    assert not any("missing_reconciliation" in v for v in violations)


def test_check_manifest_scope_done_partial_diff_still_enforces_reconciliation():
    """manifest done + some dirty paths present but governance doc absent → missing_reconciliation.

    Only the no-diff (clean worktree) case is exempt; an active packet being
    closed must still reconcile all expected governance documents.
    """
    manifest = {
        **_BASE_MANIFEST,
        "claimed_bl_status": "done",
        "write_set": ["CHANGELOG.md", "scripts/check_governance.py"],
        "expected_governance_updates": ["CHANGELOG.md", "docs/project/BACKLOG.md"],
    }
    # scripts/check_governance.py is dirty but docs/project/BACKLOG.md is not
    violations = check_governance.check_manifest_scope(
        manifest,
        ["scripts/check_governance.py"],
    )
    assert any("missing_reconciliation" in v and "BACKLOG.md" in v for v in violations)


def test_classify_dirty_path_schemas_and_tasks_are_technical():
    """schemas/ and tasks/ paths must be technical_dirty, not other_dirty."""
    assert check_governance.classify_dirty_path("schemas/v1/task_manifest.schema.json") == "technical_dirty"
    assert check_governance.classify_dirty_path("tasks/BL-061.task_manifest.json") == "technical_dirty"


def test_check_manifest_scope_governance_only_tier_with_schemas_path_triggers_violation():
    """governance-only manifest touching schemas/ must trigger tier_violation."""
    manifest = {
        **_BASE_MANIFEST,
        "validation_tier": "governance-only",
        "write_set": ["CHANGELOG.md", "schemas/v1/task_manifest.schema.json"],
    }
    violations = check_governance.check_manifest_scope(
        manifest,
        ["schemas/v1/task_manifest.schema.json"],
    )
    assert any("tier_violation" in v and "governance-only" in v for v in violations)


def test_check_manifest_scope_governance_only_tier_with_tasks_path_triggers_violation():
    """governance-only manifest touching tasks/ must trigger tier_violation."""
    manifest = {
        **_BASE_MANIFEST,
        "validation_tier": "governance-only",
        "write_set": ["CHANGELOG.md", "tasks/BL-061.task_manifest.json"],
    }
    violations = check_governance.check_manifest_scope(
        manifest,
        ["tasks/BL-061.task_manifest.json"],
    )
    assert any("tier_violation" in v and "governance-only" in v for v in violations)
