from __future__ import annotations

import importlib.util
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
