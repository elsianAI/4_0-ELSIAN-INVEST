from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_governance.py"
SPEC = importlib.util.spec_from_file_location("check_governance", MODULE_PATH)
assert SPEC and SPEC.loader
check_governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_governance)


def _opportunity_item(
    op_id: str,
    title: str,
    *,
    subject_type: str = "ticker",
    subject_id: str = "SOM",
    canonical_state: str = "frontera abierta",
    why_it_matters: str = "Importa para capacidad Module 1.",
    live_evidence: str = "PROJECT_STATE y OPPORTUNITIES.",
    unknowns_remaining: str = "Existe filing H1 pero falta confirmación.",
    promotion_trigger: str = "Evidencia nueva suficiente para BL.",
    blast_radius: str = "targeted",
    effort: str = "bounded",
    last_reviewed: str | None = None,
    disposition: str = "keep",
) -> str:
    if last_reviewed is None:
        last_reviewed = date.today().isoformat()
    return (
        f"#### {op_id} — {title}\n"
        f"- **Subject type:** {subject_type}\n"
        f"- **Subject id:** {subject_id}\n"
        f"- **Canonical state:** {canonical_state}\n"
        f"- **Why it matters:** {why_it_matters}\n"
        f"- **Live evidence:** {live_evidence}\n"
        f"- **Unknowns remaining:** {unknowns_remaining}\n"
        f"- **Promotion trigger:** {promotion_trigger}\n"
        f"- **Blast radius if promoted:** {blast_radius}\n"
        f"- **Expected effort:** {effort}\n"
        f"- **Last reviewed:** {last_reviewed}\n"
        f"- **Disposition:** {disposition}\n"
    )


def _valid_opportunities_md(*, op1_last_reviewed: str | None = None) -> str:
    return (
        "# Opportunities\n\n"
        "## Module 1 operational opportunities\n\n"
        "### Near BL-ready\n\n"
        f"{_opportunity_item('OP-001', 'SOM frontier', subject_id='SOM', disposition='keep', last_reviewed=op1_last_reviewed)}\n"
        "### Exception watchlist\n\n"
        f"{_opportunity_item('OP-002', 'JBH exception', subject_id='JBH', canonical_state='ANNUAL_ONLY justificado', disposition='reaffirm_exception')}\n"
        f"{_opportunity_item('OP-003', 'TEP autonomy', subject_id='TEP', subject_type='acquire', canonical_state='documented exception', disposition='reaffirm_exception')}\n"
        "### Extractor / format frontiers\n\n"
        f"{_opportunity_item('OP-004', 'TALO manifest gap', subject_id='TALO', subject_type='acquire', canonical_state='gradual', blast_radius='shared-core', disposition='keep')}\n"
        "### Expansion candidates\n\n"
        f"{_opportunity_item('OP-005', 'HKEX beyond 0327', subject_id='HKEX', subject_type='market', canonical_state='documented exception', blast_radius='shared-core', effort='broad', disposition='keep')}\n"
        "### Retired / absorbed\n\n"
        f"{_opportunity_item('OP-006', 'Legacy absorbed item', subject_id='LEGACY', subject_type='governance', canonical_state='absorbed', disposition='retire')}\n"
        "## Non-operational / future opportunities\n\n"
        "- Future module note.\n"
    )


def _closed_compatible_opportunities_md() -> str:
    return (
        "# Opportunities\n\n"
        "## Module 1 operational opportunities\n\n"
        "### Near BL-ready\n\n"
        "### Exception watchlist\n\n"
        f"{_opportunity_item('OP-002', 'JBH exception', subject_id='JBH', canonical_state='ANNUAL_ONLY justificado', disposition='reaffirm_exception')}\n"
        f"{_opportunity_item('OP-003', 'TEP autonomy', subject_id='TEP', subject_type='acquire', canonical_state='documented exception', disposition='reaffirm_exception')}\n"
        "### Extractor / format frontiers\n\n"
        "### Expansion candidates\n\n"
        "### Retired / absorbed\n\n"
        f"{_opportunity_item('OP-006', 'Legacy absorbed item', subject_id='LEGACY', subject_type='governance', canonical_state='absorbed', disposition='retire')}\n"
        "## Non-operational / future opportunities\n\n"
        "- Future module note.\n"
    )


def _baseline_block(
    *,
    last_scout_pass_at: str = "2026-03-13T10:20:30Z",
    last_scout_head: str = "a" * 40,
    last_eval_signature: str = "b" * 64,
    last_diagnose_signature: str = "c" * 64,
    last_cases_signature: str = "d" * 64,
    last_operational_opportunities_signature: str = "e" * 64,
) -> str:
    return (
        "## Discovery Baseline\n"
        f"- last_scout_pass_at: {last_scout_pass_at}\n"
        f"- last_scout_head: {last_scout_head}\n"
        f"- last_eval_signature: {last_eval_signature}\n"
        f"- last_diagnose_signature: {last_diagnose_signature}\n"
        f"- last_cases_signature: {last_cases_signature}\n"
        "- last_operational_opportunities_signature: "
        f"{last_operational_opportunities_signature}\n"
    )


def test_classify_dirty_path_buckets_workspace_governance_and_technical():
    assert (
        check_governance.classify_dirty_path("4_0-ELSIAN-INVEST.code-workspace")
        == "workspace_only_dirty"
    )
    assert check_governance.classify_dirty_path(".runtime/handoff.json") == "workspace_only_dirty"
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
        "# Estado\n\n> Última actualización: 2026-03-05\n> Module 1 status: OPEN\n"
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "### BL-054 — Uno\n### BL-054 — Dos\n"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(_valid_opportunities_md())
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
    assert report["backlog"]["active_ids"] == ["BL-054", "BL-054"]
    assert report["backlog"]["active_count"] == 2
    assert report["backlog"]["is_empty"] is False
    assert report["project_state"]["module1_status"] == "OPEN"
    assert report["opportunities"]["operational_shape_valid"] is True
    assert report["document_sync"]["project_state_lags_changelog"] is True
    assert report["backlog"]["duplicate_ids"] == [{"id": "BL-054", "lines": [1, 2], "count": 2}]
    assert report["manual_overrides"]["nonzero_by_ticker"] == {"AAA": 1}
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"


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


def test_parse_project_state_module1_status_detects_missing_and_duplicated(tmp_path: Path):
    project_state = tmp_path / "PROJECT_STATE.md"
    project_state.write_text("> Última actualización: 2026-03-12\n")
    status, violations = check_governance.parse_project_state_module1_status(project_state)
    assert status is None
    assert violations == ["project_state_module_status_missing"]

    project_state.write_text(
        "> Module 1 status: OPEN\n> Module 1 status: CLOSED\n", encoding="utf-8"
    )
    status, violations = check_governance.parse_project_state_module1_status(project_state)
    assert status is None
    assert violations == ["project_state_module_status_duplicated"]


def test_parse_discovery_baseline_block_absent_is_valid(tmp_path: Path):
    project_state = tmp_path / "PROJECT_STATE.md"
    project_state.write_text("> Module 1 status: OPEN\n", encoding="utf-8")

    parsed = check_governance.parse_discovery_baseline_block(project_state.read_text(encoding="utf-8"))

    assert parsed == {
        "present": False,
        "valid": True,
        "values": None,
        "violations": [],
    }


def test_parse_discovery_baseline_block_valid_shape(tmp_path: Path):
    project_state = tmp_path / "PROJECT_STATE.md"
    project_state.write_text(
        "# Estado\n\n"
        "> Última actualización: 2026-03-13\n"
        "> Module 1 status: OPEN\n\n"
        f"{_baseline_block()}\n"
        "## Otro bloque\n",
        encoding="utf-8",
    )

    parsed = check_governance.parse_discovery_baseline_block(project_state.read_text(encoding="utf-8"))

    assert parsed["present"] is True
    assert parsed["valid"] is True
    assert parsed["values"]["last_scout_head"] == "a" * 40
    assert parsed["violations"] == []


def test_build_report_corrupt_baseline_marks_governance_dirty(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "cases").mkdir()

    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n"
        "> Última actualización: 2026-03-13\n"
        "> Module 1 status: OPEN\n\n"
        "## Discovery Baseline\n"
        "- last_scout_head: invalid\n"
        "- last_scout_pass_at: 2026-03-13T10:20:30Z\n"
        "## Otro bloque\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _valid_opportunities_md(),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-13\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)

    report = check_governance.build_report(tmp_path)

    assert report["project_state"]["discovery_baseline"]["present"] is True
    assert report["project_state"]["discovery_baseline"]["valid"] is False
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"
    assert any(
        violation.startswith("project_state_discovery_baseline")
        for violation in report["summary"]["governance_contract_violations"]
    )


def test_build_report_valid_baseline_is_clean_when_repo_is_clean(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "cases").mkdir()

    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n"
        "> Última actualización: 2026-03-13\n"
        "> Module 1 status: OPEN\n\n"
        f"{_baseline_block()}\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _valid_opportunities_md(),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-13\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)

    report = check_governance.build_report(tmp_path)

    assert report["project_state"]["discovery_baseline"]["valid"] is True
    assert report["summary"]["governance_contract_violations"] == []
    assert report["summary"]["next_resolution_mode"] == "empty_backlog_discovery"


def test_parse_active_backlog_ids_returns_only_live_ids(tmp_path: Path):
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(
        "### BL-085 — Uno\n"
        "Texto\n"
        "### BL-086 — Dos\n",
        encoding="utf-8",
    )
    assert check_governance.parse_active_backlog_ids(backlog) == ["BL-085", "BL-086"]


def test_parse_operational_opportunities_requires_structured_operational_subtree(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(
        "# Opportunities\n\n## Module 1 operational opportunities\n\n### Near BL-ready\n",
        encoding="utf-8",
    )
    report = check_governance.parse_operational_opportunities(opportunities)
    assert report["shape_valid"] is False
    assert any("opportunities_non_operational_heading_missing" in v for v in report["violations"])


def test_parse_operational_opportunities_tracks_blockers_and_stale_items(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(_valid_opportunities_md(), encoding="utf-8")
    report = check_governance.parse_operational_opportunities(opportunities)

    assert report["shape_valid"] is True
    assert report["blocking_for_closed"] == ["OP-001", "OP-004", "OP-005"]
    assert report["stale_items"] == []


def test_parse_operational_opportunities_allows_empty_operational_lane(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(
        (
            "# Opportunities\n\n"
            "## Module 1 operational opportunities\n\n"
            "### Near BL-ready\n\n"
            "### Exception watchlist\n\n"
            f"{_opportunity_item('OP-002', 'JBH exception', subject_id='JBH', canonical_state='ANNUAL_ONLY justificado', disposition='reaffirm_exception')}\n"
            "### Extractor / format frontiers\n\n"
            f"{_opportunity_item('OP-004', 'TALO manifest gap', subject_id='TALO', subject_type='acquire', canonical_state='gradual', blast_radius='shared-core', disposition='keep')}\n"
            "### Expansion candidates\n\n"
            f"{_opportunity_item('OP-005', 'HKEX beyond 0327', subject_id='HKEX', subject_type='market', canonical_state='documented exception', blast_radius='shared-core', effort='broad', disposition='keep')}\n"
            "### Retired / absorbed\n\n"
            f"{_opportunity_item('OP-006', 'Legacy absorbed item', subject_id='LEGACY', subject_type='governance', canonical_state='absorbed', disposition='retire')}\n"
            "## Non-operational / future opportunities\n\n"
            "- Future module note.\n"
        ),
        encoding="utf-8",
    )
    report = check_governance.parse_operational_opportunities(opportunities)

    assert report["shape_valid"] is True
    assert not any("opportunities_lane_empty" in v for v in report["violations"])


def test_parse_operational_opportunities_invalid_last_reviewed_is_structural_violation(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(
        _valid_opportunities_md(op1_last_reviewed="2026-02-30"),
        encoding="utf-8",
    )
    report = check_governance.parse_operational_opportunities(opportunities)

    assert report["shape_valid"] is False
    assert "opportunity_invalid_last_reviewed:OP-001:2026-02-30" in report["violations"]


def test_parse_operational_opportunities_duplicate_field_fails_closed(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(
        _valid_opportunities_md().replace(
            "- **Disposition:** keep\n",
            "- **Disposition:** keep\n- **Disposition:** retire\n",
            1,
        ),
        encoding="utf-8",
    )
    report = check_governance.parse_operational_opportunities(opportunities)

    assert report["shape_valid"] is False
    assert "opportunity_duplicate_field:OP-001:Disposition" in report["violations"]


def test_parse_operational_opportunities_duplicate_id_fails_closed(tmp_path: Path):
    opportunities = tmp_path / "OPPORTUNITIES.md"
    opportunities.write_text(
        _valid_opportunities_md().replace(
            "#### OP-003 — TEP autonomy\n",
            "#### OP-001 — Duplicate SOM reference\n",
            1,
        ),
        encoding="utf-8",
    )
    report = check_governance.parse_operational_opportunities(opportunities)

    assert report["shape_valid"] is False
    assert any(v.startswith("opportunity_duplicate_id:OP-001:") for v in report["violations"])


def test_build_report_uses_empty_backlog_discovery_when_repo_clean_and_module_open(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(_valid_opportunities_md(), encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is False
    assert report["summary"]["technical_work_pending"] is False
    assert report["summary"]["next_resolution_mode"] == "empty_backlog_discovery"


def test_build_report_uses_execute_backlog_when_repo_clean_and_backlog_live(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "### BL-085 — Uno\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(_valid_opportunities_md(), encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)
    assert report["summary"]["next_resolution_mode"] == "execute_backlog"


def test_build_report_uses_module_closeout_review_when_repo_clean_and_candidate(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: CLOSEOUT_CANDIDATE\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _closed_compatible_opportunities_md(), encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is False
    assert report["summary"]["next_resolution_mode"] == "module_closeout_review"


def test_build_report_uses_idle_clean_when_repo_clean_and_module_closed(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: CLOSED\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _closed_compatible_opportunities_md(), encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is False
    assert report["summary"]["next_resolution_mode"] == "idle_clean"


def test_build_report_invalid_last_reviewed_fails_closed_to_reconcile(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _valid_opportunities_md(op1_last_reviewed="2026-02-30"),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is True
    assert "opportunity_invalid_last_reviewed:OP-001:2026-02-30" in report["summary"]["governance_contract_violations"]
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"


def test_main_returns_zero_for_valid_operational_state(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _valid_opportunities_md(),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(check_governance, "run_git", fake_run_git)

    assert check_governance.main(["--format", "json"]) == 0


def test_main_returns_one_for_governance_contract_violations(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "# Backlog\n\nNo hay tareas activas.\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        _valid_opportunities_md(),
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(check_governance, "run_git", fake_run_git)

    assert check_governance.main(["--format", "json"]) == 1


def test_build_report_duplicate_active_backlog_ids_fail_closed_to_reconcile(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text(
        "### BL-085 — Uno\n### BL-085 — Duplicada\n", encoding="utf-8"
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(_valid_opportunities_md(), encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is True
    assert report["summary"]["duplicate_backlog_ids_present"] is True
    assert "backlog_duplicate_active_ids" in report["summary"]["governance_contract_violations"]
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"


def test_build_report_fails_closed_when_operational_opportunities_is_malformed(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: OPEN\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        "# Opportunities\n\n## Module 1 operational opportunities\n\n### Near BL-ready\n\nbad line\n\n## Non-operational / future opportunities\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is True
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"


def test_build_report_closed_module_rejects_open_operational_items(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: CLOSED\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(_valid_opportunities_md(), encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"
    assert "module1_closed_with_open_operational_opportunities" in report["summary"]["governance_contract_violations"]


def test_build_report_closed_module_rejects_open_item_hidden_in_retired_lane(tmp_path: Path, monkeypatch):
    (tmp_path / "docs/project").mkdir(parents=True)
    (tmp_path / "docs/project/PROJECT_STATE.md").write_text(
        "# Estado\n\n> Última actualización: 2026-03-12\n> Module 1 status: CLOSED\n",
        encoding="utf-8",
    )
    (tmp_path / "docs/project/BACKLOG.md").write_text("", encoding="utf-8")
    opportunities_text = _closed_compatible_opportunities_md().replace(
        "#### OP-006 — Legacy absorbed item\n",
        "#### OP-006 — Hidden open frontier\n",
    ).replace(
        "- **Canonical state:** absorbed\n",
        "- **Canonical state:** frontera abierta\n",
        1,
    ).replace(
        "- **Disposition:** retire\n",
        "- **Disposition:** keep\n",
        1,
    )
    (tmp_path / "docs/project/OPPORTUNITIES.md").write_text(
        opportunities_text,
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 2026-03-12\n", encoding="utf-8")

    def fake_run_git(_repo_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--abbrev-ref", "HEAD"):
            return "main"
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        if args == ("status", "--short", "--untracked-files=all"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(check_governance, "run_git", fake_run_git)
    report = check_governance.build_report(tmp_path)

    assert report["summary"]["governance_work_pending"] is True
    assert "opportunity_invalid_retired_disposition:OP-006:keep" in report["summary"]["governance_contract_violations"]
    assert "module1_closed_with_open_operational_opportunities" in report["summary"]["governance_contract_violations"]
    assert report["summary"]["next_resolution_mode"] == "reconcile_pending_work"


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
