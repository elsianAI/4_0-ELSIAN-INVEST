#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
OVERRIDE_LEAF_KEYS = {"value", "note", "source_filing", "extraction_method", "confidence"}
WORKSPACE_ONLY_PREFIXES = (".vscode/", ".idea/")
WORKSPACE_ONLY_SUFFIXES = (".code-workspace",)
GOVERNANCE_FILES = {"CHANGELOG.md", "VISION.md", "ROADMAP.md", "README.md"}
GOVERNANCE_PREFIXES = ("docs/project/", ".github/agents/")
TECHNICAL_FILES = {"pyproject.toml"}
TECHNICAL_PREFIXES = ("cases/", "config/", "elsian/", "schemas/", "scripts/", "tasks/", "tests/")
BACKLOG_ID_RE = re.compile(r"^###\s+(BL-\d+)\b")
PROJECT_STATE_DATE_RE = re.compile(r"^>\s+Última actualización:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
CHANGELOG_DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\b", re.MULTILINE)


def run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout


def resolve_repo_root() -> Path:
    try:
        return Path(run_git(SCRIPT_ROOT, "rev-parse", "--show-toplevel").strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return SCRIPT_ROOT


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def classify_dirty_path(path: str) -> str:
    normalized = path.strip()
    if any(normalized.startswith(prefix) for prefix in WORKSPACE_ONLY_PREFIXES):
        return "workspace_only_dirty"
    if any(normalized.endswith(suffix) for suffix in WORKSPACE_ONLY_SUFFIXES):
        return "workspace_only_dirty"
    if normalized in GOVERNANCE_FILES or any(
        normalized.startswith(prefix) for prefix in GOVERNANCE_PREFIXES
    ):
        return "governance_dirty"
    if normalized in TECHNICAL_FILES or any(normalized.startswith(prefix) for prefix in TECHNICAL_PREFIXES):
        return "technical_dirty"
    return "other_dirty"


def parse_status_output(status_output: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for raw_line in status_output.splitlines():
        if not raw_line or raw_line.startswith("##"):
            continue
        code = raw_line[:2]
        path = raw_line[3:]
        if " -> " in path and ("R" in code or "C" in code):
            path = path.split(" -> ", 1)[1]
        entries.append(
            {
                "code": code,
                "path": path,
                "tracked": code != "??",
                "category": classify_dirty_path(path),
            }
        )
    return entries


def parse_duplicate_backlog_ids(backlog_path: Path) -> list[dict[str, Any]]:
    positions: dict[str, list[int]] = defaultdict(list)
    if not backlog_path.exists():
        return []
    for lineno, line in enumerate(backlog_path.read_text().splitlines(), start=1):
        match = BACKLOG_ID_RE.match(line)
        if match:
            positions[match.group(1)].append(lineno)
    return [
        {"id": backlog_id, "lines": lines, "count": len(lines)}
        for backlog_id, lines in sorted(positions.items())
        if len(lines) > 1
    ]


def parse_project_state_last_updated(project_state_path: Path) -> str | None:
    if not project_state_path.exists():
        return None
    match = PROJECT_STATE_DATE_RE.search(project_state_path.read_text())
    return match.group(1) if match else None


def parse_changelog_latest_date(changelog_path: Path) -> str | None:
    if not changelog_path.exists():
        return None
    dates = CHANGELOG_DATE_RE.findall(changelog_path.read_text())
    return max(dates) if dates else None


def count_manual_override_entries(node: Any) -> int:
    if node is None:
        return 0
    if isinstance(node, list):
        return sum(count_manual_override_entries(item) for item in node)
    if isinstance(node, dict):
        if OVERRIDE_LEAF_KEYS.intersection(node):
            return 1
        return sum(count_manual_override_entries(value) for value in node.values())
    return 0


def collect_manual_override_counts(cases_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not cases_root.exists():
        return counts
    for case_path in sorted(cases_root.glob("*/case.json")):
        ticker = case_path.parent.name
        try:
            payload = json.loads(case_path.read_text())
        except json.JSONDecodeError:
            counts[ticker] = -1
            continue
        counts[ticker] = count_manual_override_entries(payload.get("manual_overrides"))
    return counts


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def build_report(repo_root: Path, status_output: str | None = None) -> dict[str, Any]:
    branch = run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    head = run_git(repo_root, "rev-parse", "--short", "HEAD").strip()
    status_output = status_output or run_git(repo_root, "status", "--short", "--untracked-files=all")
    entries = parse_status_output(status_output)

    grouped: dict[str, list[str]] = {
        "technical_dirty": [],
        "governance_dirty": [],
        "workspace_only_dirty": [],
        "other_dirty": [],
    }
    untracked_technical_files: list[str] = []
    untracked_test_files: list[str] = []
    for entry in entries:
        grouped[entry["category"]].append(entry["path"])
        if not entry["tracked"] and entry["category"] == "technical_dirty":
            untracked_technical_files.append(entry["path"])
            if entry["path"].startswith("tests/"):
                untracked_test_files.append(entry["path"])

    project_state_path = repo_root / "docs/project/PROJECT_STATE.md"
    changelog_path = repo_root / "CHANGELOG.md"
    backlog_path = repo_root / "docs/project/BACKLOG.md"
    project_state_last_updated = parse_project_state_last_updated(project_state_path)
    changelog_latest_date = parse_changelog_latest_date(changelog_path)
    project_state_lags = False
    if project_state_last_updated and changelog_latest_date:
        project_state_lags = parse_iso_date(project_state_last_updated) < parse_iso_date(
            changelog_latest_date
        )

    manual_override_counts = collect_manual_override_counts(repo_root / "cases")

    return {
        "repo_root": str(repo_root),
        "branch": branch,
        "head": head,
        "worktree": {
            "is_clean": not entries,
            "repo_tracked_dirty": any(entry["tracked"] for entry in entries),
            "entries": entries,
            "technical_dirty": grouped["technical_dirty"],
            "governance_dirty": grouped["governance_dirty"],
            "workspace_only_dirty": grouped["workspace_only_dirty"],
            "other_dirty": grouped["other_dirty"],
            "untracked_technical_files": untracked_technical_files,
            "untracked_test_files": untracked_test_files,
        },
        "backlog": {
            "duplicate_ids": parse_duplicate_backlog_ids(backlog_path),
        },
        "project_state": {
            "path": str(project_state_path),
            "last_updated": project_state_last_updated,
            "content_sha256": file_hash(project_state_path),
        },
        "changelog": {
            "path": str(changelog_path),
            "latest_date": changelog_latest_date,
            "content_sha256": file_hash(changelog_path),
        },
        "document_sync": {
            "project_state_lags_changelog": project_state_lags,
        },
        "manual_overrides": {
            "by_ticker": manual_override_counts,
            "nonzero_by_ticker": {
                ticker: count
                for ticker, count in manual_override_counts.items()
                if count and count > 0
            },
        },
        "summary": {
            "technical_work_pending": bool(grouped["technical_dirty"]),
            "governance_work_pending": bool(grouped["governance_dirty"]),
            "workspace_noise_present": bool(grouped["workspace_only_dirty"]),
            "duplicate_backlog_ids_present": bool(parse_duplicate_backlog_ids(backlog_path)),
            "project_state_lags_changelog": project_state_lags,
            "untracked_technical_files_present": bool(untracked_technical_files),
            "untracked_test_files_present": bool(untracked_test_files),
        },
    }


def format_text(report: dict[str, Any]) -> str:
    lines = [
        f"repo_root: {report['repo_root']}",
        f"branch: {report['branch']}",
        f"head: {report['head']}",
        f"worktree.is_clean: {report['worktree']['is_clean']}",
        f"technical_dirty: {', '.join(report['worktree']['technical_dirty']) or '-'}",
        f"governance_dirty: {', '.join(report['worktree']['governance_dirty']) or '-'}",
        f"workspace_only_dirty: {', '.join(report['worktree']['workspace_only_dirty']) or '-'}",
        f"untracked_technical_files: {', '.join(report['worktree']['untracked_technical_files']) or '-'}",
        f"untracked_test_files: {', '.join(report['worktree']['untracked_test_files']) or '-'}",
        f"backlog.duplicate_ids: {report['backlog']['duplicate_ids'] or '-'}",
        f"project_state.last_updated: {report['project_state']['last_updated'] or '-'}",
        f"changelog.latest_date: {report['changelog']['latest_date'] or '-'}",
        f"project_state_lags_changelog: {report['document_sync']['project_state_lags_changelog']}",
        f"manual_overrides.nonzero_by_ticker: {report['manual_overrides']['nonzero_by_ticker'] or '-'}",
    ]
    return "\n".join(lines)


def _path_in_surface(path: str, surface: str) -> bool:
    """Return True if path equals or is nested under surface prefix."""
    if path == surface:
        return True
    prefix = surface if surface.endswith("/") else surface + "/"
    return path.startswith(prefix)


def check_manifest_scope(
    manifest: dict[str, Any],
    dirty_paths: list[str],
) -> list[str]:
    """Check that repo dirty paths respect a task manifest contract.

    Args:
        manifest: Loaded task manifest dict.
        dirty_paths: Repo-relative dirty paths (workspace noise already excluded).

    Returns:
        List of violation strings.  Empty list means the scope is clean.
    """
    violations: list[str] = []
    write_set: list[str] = manifest.get("write_set") or []
    blocked_surfaces: list[str] = manifest.get("blocked_surfaces") or []
    _egu_raw = manifest.get("expected_governance_updates")
    expected_governance_updates: list[str] = [] if _egu_raw == "none" else (_egu_raw or [])
    claimed_bl_status: str = manifest.get("claimed_bl_status", "")
    validation_tier: str = manifest.get("validation_tier", "")

    write_set_set: set[str] = set(write_set)
    dirty_set: set[str] = set(dirty_paths)
    governance_update_set: set[str] = set(expected_governance_updates)

    # 1. Dirty path outside write_set
    # Paths declared in expected_governance_updates are additional permitted surfaces
    # for reconciliation, but only when they classify as governance_dirty.  This
    # prevents misuse of the field to bypass write_set for technical files.
    for path in dirty_paths:
        in_write_set = path in write_set_set
        in_governance_updates = (
            path in governance_update_set
            and classify_dirty_path(path) == "governance_dirty"
        )
        if not in_write_set and not in_governance_updates:
            violations.append(
                f"write_set_violation: {path!r} is dirty but not declared in write_set"
            )

    # 2. Dirty path touches a blocked surface
    for path in dirty_paths:
        for blocked in blocked_surfaces:
            if _path_in_surface(path, blocked):
                violations.append(
                    f"blocked_surface_violation: {path!r} touches blocked surface {blocked!r}"
                )
                break

    # 3. Missing governance reconciliation (required when claimed_bl_status='done'
    #    AND there is an active diff; an empty diff means the manifest is a
    #    historical closed record — no reconciliation can be pending).
    if claimed_bl_status == "done" and dirty_paths:
        for doc in expected_governance_updates:
            if doc not in dirty_set:
                violations.append(
                    f"missing_reconciliation: {doc!r} is required by expected_governance_updates"
                    f" but is not in the diff (claimed_bl_status='done')"
                )

    # 4. Tier coherence: governance-only must not touch technical files
    if validation_tier == "governance-only":
        for path in dirty_paths:
            if classify_dirty_path(path) == "technical_dirty":
                violations.append(
                    f"tier_violation: {path!r} is a technical file"
                    f" but validation_tier='governance-only'"
                )

    return violations


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic governance/worktree checker for ELSIAN.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--task-manifest",
        metavar="PATH",
        help=(
            "Path to a task_manifest JSON. When provided, checks the current diff against "
            "the manifest's write_set, blocked_surfaces, expected_governance_updates, "
            "validation_tier, and claimed_bl_status."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = resolve_repo_root()
    report = build_report(repo_root)

    manifest_violations: list[str] = []
    if args.task_manifest:
        manifest_path = Path(args.task_manifest)
        if not manifest_path.is_absolute():
            manifest_path = repo_root / manifest_path
        try:
            manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"check_governance: cannot load task manifest {args.task_manifest!r}: {exc}\n")
            return 1
        # Fail-closed: validate manifest against task_manifest contract before enforcement (BL-061 audit fix)
        _vc_script = Path(__file__).parent / "validate_contracts.py"
        _vc_result = subprocess.run(
            [sys.executable, str(_vc_script), "--schema", "task_manifest", "--path", str(manifest_path)],
            capture_output=True,
            text=True,
        )
        if _vc_result.returncode != 0:
            sys.stderr.write(
                f"check_governance: manifest {manifest_path.name!r} failed contract validation:\n"
            )
            sys.stderr.write(_vc_result.stdout or "(no output)\n")
            return 1
        # Exclude workspace noise from the scope check
        dirty_paths = [
            entry["path"]
            for entry in report["worktree"]["entries"]
            if entry["category"] != "workspace_only_dirty"
        ]
        manifest_violations = check_manifest_scope(manifest, dirty_paths)
        report["task_manifest"] = {
            "task_id": manifest.get("task_id"),
            "manifest_path": str(manifest_path.relative_to(repo_root)),
            "write_set": manifest.get("write_set", []),
            "blocked_surfaces": manifest.get("blocked_surfaces", []),
            "expected_governance_updates": manifest.get("expected_governance_updates", []),
            "claimed_bl_status": manifest.get("claimed_bl_status"),
            "validation_tier": manifest.get("validation_tier"),
            "violations": manifest_violations,
            "scope_clean": not manifest_violations,
        }

    if args.format == "json":
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_text(report) + "\n")
        if args.task_manifest and manifest_violations:
            for v in manifest_violations:
                sys.stdout.write(f"manifest_violation: {v}\n")

    return 1 if manifest_violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
