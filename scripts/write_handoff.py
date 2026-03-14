#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_governance


HANDOFF_DIRNAME = ".runtime"
HANDOFF_FILENAME = "handoff.json"
SCHEMA_VERSION = "1.0"
DEFAULT_GENERATED_BY = "scripts/write_handoff.py"
STATUS_CHOICES = ("active", "completed", "blocked", "stale")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def handoff_path(repo_root: Path) -> Path:
    return repo_root / HANDOFF_DIRNAME / HANDOFF_FILENAME


def build_live_state_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "next_resolution_mode": report["summary"]["next_resolution_mode"],
        "technical_dirty": report["worktree"]["technical_dirty"],
        "governance_dirty": report["worktree"]["governance_dirty"],
        "other_dirty": report["worktree"]["other_dirty"],
        "untracked_technical_files": report["worktree"]["untracked_technical_files"],
        "untracked_test_files": report["worktree"]["untracked_test_files"],
        "backlog_active_ids": report["backlog"]["active_ids"],
        "backlog_active_count": report["backlog"]["active_count"],
        "module1_status": report["project_state"]["module1_status"],
        "project_state_lags_changelog": report["document_sync"]["project_state_lags_changelog"],
        "governance_contract_violations": report["summary"]["governance_contract_violations"],
    }


def compute_live_state_fingerprint(snapshot: dict[str, Any]) -> str:
    normalized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_stale_if(head: str, branch: str, live_state_snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "head_must_match": head,
        "branch_must_match": branch,
        "live_state_fingerprint_must_match": compute_live_state_fingerprint(live_state_snapshot),
        "live_state_snapshot": live_state_snapshot,
        "note": (
            "Stale if HEAD changes or if the material live-state snapshot changes. "
            "workspace_only_dirty is ignored by design."
        ),
    }


def build_handoff(
    repo_root: Path,
    *,
    generated_by: str,
    current_focus: str,
    status: str,
    last_completed_step: str,
    recommended_next_route: str,
    recommended_next_action: str,
    blocking_questions: list[str],
    scope: str,
    report: dict[str, Any],
    head: str,
) -> dict[str, Any]:
    repo_root_resolved = repo_root.resolve()
    live_state_snapshot = build_live_state_snapshot(report)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "generated_by": generated_by,
        "repo_root": str(repo_root_resolved),
        "worktree_path": str(repo_root_resolved),
        "head": head,
        "branch": report["branch"],
        "next_resolution_mode": report["summary"]["next_resolution_mode"],
        "current_focus": current_focus,
        "status": status,
        "last_completed_step": last_completed_step,
        "recommended_next_route": recommended_next_route,
        "recommended_next_action": recommended_next_action,
        "blocking_questions": blocking_questions,
        "stale_if": build_stale_if(head, report["branch"], live_state_snapshot),
        "scope": scope,
    }


def write_handoff_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write local runtime handoff for the current worktree.")
    parser.add_argument("--generated-by", default=DEFAULT_GENERATED_BY, help="Agent/tool identifier.")
    parser.add_argument("--current-focus", required=True, help="Brief description of current focus.")
    parser.add_argument(
        "--status",
        choices=STATUS_CHOICES,
        default="active",
        help="Session status stored in the handoff.",
    )
    parser.add_argument("--last-completed-step", default="", help="Last completed step.")
    parser.add_argument("--recommended-next-route", default="", help="Recommended route from ROLES.")
    parser.add_argument("--recommended-next-action", default="", help="Concrete next action.")
    parser.add_argument(
        "--blocking-question",
        action="append",
        default=[],
        help="Question that still requires Elsian intervention. Repeatable.",
    )
    parser.add_argument("--scope", required=True, help="Brief scope summary for this session.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = check_governance.resolve_repo_root()
    report = check_governance.build_report(repo_root)
    head = check_governance.run_git(repo_root, "rev-parse", "HEAD").strip()
    payload = build_handoff(
        repo_root,
        generated_by=args.generated_by,
        current_focus=args.current_focus,
        status=args.status,
        last_completed_step=args.last_completed_step,
        recommended_next_route=args.recommended_next_route,
        recommended_next_action=args.recommended_next_action,
        blocking_questions=args.blocking_question,
        scope=args.scope,
        report=report,
        head=head,
    )
    output_path = handoff_path(repo_root)
    write_handoff_file(output_path, payload)

    summary_lines = [
        f"Wrote handoff: {output_path}",
        f"status: {payload['status']}",
        f"head: {payload['head']}",
        f"next_resolution_mode: {payload['next_resolution_mode']}",
        f"current_focus: {payload['current_focus']}",
    ]
    if payload["recommended_next_action"]:
        summary_lines.append(f"recommended_next_action: {payload['recommended_next_action']}")
    if payload["blocking_questions"]:
        summary_lines.append(f"blocking_questions: {len(payload['blocking_questions'])}")
    sys.stdout.write("\n".join(summary_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
