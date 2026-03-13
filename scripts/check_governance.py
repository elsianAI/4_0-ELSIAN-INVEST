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
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from elsian.analyze.discovery_baseline import parse_discovery_baseline_block

OVERRIDE_LEAF_KEYS = {"value", "note", "source_filing", "extraction_method", "confidence"}
WORKSPACE_ONLY_PREFIXES = (".vscode/", ".idea/")
WORKSPACE_ONLY_SUFFIXES = (".code-workspace",)
GOVERNANCE_FILES = {"CHANGELOG.md", "VISION.md", "ROADMAP.md", "README.md"}
GOVERNANCE_PREFIXES = ("docs/project/", ".github/agents/")
TECHNICAL_FILES = {"pyproject.toml"}
TECHNICAL_PREFIXES = ("cases/", "config/", "elsian/", "schemas/", "scripts/", "tasks/", "tests/")
BACKLOG_ID_RE = re.compile(r"^###\s+(BL-\d+)\b")
PROJECT_STATE_DATE_RE = re.compile(r"^>\s+Última actualización:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
PROJECT_STATE_MODULE_STATUS_RE = re.compile(
    r"^>\s+Module 1 status:\s*(OPEN|CLOSEOUT_CANDIDATE|CLOSED)\s*$", re.MULTILINE
)
CHANGELOG_DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
OPPORTUNITIES_OPERATIONAL_HEADING = "## Module 1 operational opportunities"
OPPORTUNITIES_NON_OPERATIONAL_HEADING = "## Non-operational / future opportunities"
OPPORTUNITIES_LANES = (
    "### Near BL-ready",
    "### Exception watchlist",
    "### Extractor / format frontiers",
    "### Expansion candidates",
    "### Retired / absorbed",
)
OPPORTUNITY_ITEM_RE = re.compile(r"^####\s+(OP-\d+)\s+—\s+(.+)$")
OPPORTUNITY_FIELD_RE = re.compile(r"^- \*\*(.+?):\*\*\s*(.+)$")
VALID_OPPORTUNITY_SUBJECT_TYPES = {"ticker", "market", "extractor", "acquire", "governance"}
VALID_BLAST_RADIUS = {"targeted", "shared-core", "governance-only"}
VALID_EFFORT = {"minimal", "bounded", "broad"}
VALID_DISPOSITION = {"keep", "promote_to_backlog", "reaffirm_exception", "retire"}
REQUIRED_OPPORTUNITY_FIELDS = {
    "Subject type": "subject_type",
    "Subject id": "subject_id",
    "Canonical state": "canonical_state",
    "Why it matters": "why_it_matters",
    "Live evidence": "live_evidence",
    "Unknowns remaining": "unknowns_remaining",
    "Promotion trigger": "promotion_trigger",
    "Blast radius if promoted": "blast_radius_if_promoted",
    "Expected effort": "expected_effort",
    "Last reviewed": "last_reviewed",
    "Disposition": "disposition",
}
MODULE1_STATUS_OPEN = "OPEN"
MODULE1_STATUS_CLOSEOUT_CANDIDATE = "CLOSEOUT_CANDIDATE"
MODULE1_STATUS_CLOSED = "CLOSED"
NEXT_RESOLUTION_RECONCILE = "reconcile_pending_work"
NEXT_RESOLUTION_EXECUTE = "execute_backlog"
NEXT_RESOLUTION_EMPTY_BACKLOG = "empty_backlog_discovery"
NEXT_RESOLUTION_CLOSEOUT = "module_closeout_review"
NEXT_RESOLUTION_IDLE = "idle_clean"
LAST_REVIEWED_STALENESS_DAYS = 30


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


def parse_active_backlog_ids(backlog_path: Path) -> list[str]:
    if not backlog_path.exists():
        return []
    active_ids: list[str] = []
    for line in backlog_path.read_text(encoding="utf-8").splitlines():
        match = BACKLOG_ID_RE.match(line)
        if match:
            active_ids.append(match.group(1))
    return active_ids


def parse_project_state_last_updated(project_state_path: Path) -> str | None:
    if not project_state_path.exists():
        return None
    match = PROJECT_STATE_DATE_RE.search(project_state_path.read_text())
    return match.group(1) if match else None


def parse_project_state_module1_status(project_state_path: Path) -> tuple[str | None, list[str]]:
    if not project_state_path.exists():
        return None, ["project_state_module_status_missing_file"]
    matches = PROJECT_STATE_MODULE_STATUS_RE.findall(project_state_path.read_text(encoding="utf-8"))
    if not matches:
        return None, ["project_state_module_status_missing"]
    if len(matches) > 1:
        return None, ["project_state_module_status_duplicated"]
    return matches[0], []


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
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _find_heading_indices(lines: list[str], heading: str) -> list[int]:
    return [idx for idx, line in enumerate(lines) if line.strip() == heading]


def _normalize_opportunity_item(
    item_id: str,
    title: str,
    lane: str,
    field_map: dict[str, str],
    violations: list[str],
) -> dict[str, Any]:
    missing = [field for field in REQUIRED_OPPORTUNITY_FIELDS if field not in field_map]
    if missing:
        violations.append(f"opportunity_missing_fields:{item_id}:{','.join(sorted(missing))}")
    subject_type = field_map.get("Subject type")
    blast_radius = field_map.get("Blast radius if promoted")
    effort = field_map.get("Expected effort")
    disposition = field_map.get("Disposition")
    last_reviewed_raw = field_map.get("Last reviewed")

    if subject_type and subject_type not in VALID_OPPORTUNITY_SUBJECT_TYPES:
        violations.append(f"opportunity_invalid_subject_type:{item_id}:{subject_type}")
    if blast_radius and blast_radius not in VALID_BLAST_RADIUS:
        violations.append(f"opportunity_invalid_blast_radius:{item_id}:{blast_radius}")
    if effort and effort not in VALID_EFFORT:
        violations.append(f"opportunity_invalid_effort:{item_id}:{effort}")
    if disposition and disposition not in VALID_DISPOSITION:
        violations.append(f"opportunity_invalid_disposition:{item_id}:{disposition}")

    last_reviewed: str | None = None
    stale = False
    if last_reviewed_raw:
        parsed = parse_iso_date(last_reviewed_raw)
        if parsed is None:
            violations.append(f"opportunity_invalid_last_reviewed:{item_id}:{last_reviewed_raw}")
        else:
            last_reviewed = last_reviewed_raw
            stale = (date.today() - parsed).days > LAST_REVIEWED_STALENESS_DAYS

    blocks_closed = False
    if lane in {"Near BL-ready", "Extractor / format frontiers", "Expansion candidates"}:
        blocks_closed = True
    elif lane == "Exception watchlist" and disposition != "reaffirm_exception":
        blocks_closed = True
    elif lane == "Retired / absorbed" and disposition != "retire":
        violations.append(
            f"opportunity_invalid_retired_disposition:{item_id}:{disposition or '-'}"
        )
        blocks_closed = True

    return {
        "id": item_id,
        "title": title,
        "lane": lane,
        "subject_type": subject_type,
        "subject_id": field_map.get("Subject id"),
        "canonical_state": field_map.get("Canonical state"),
        "why_it_matters": field_map.get("Why it matters"),
        "live_evidence": field_map.get("Live evidence"),
        "unknowns_remaining": field_map.get("Unknowns remaining"),
        "promotion_trigger": field_map.get("Promotion trigger"),
        "blast_radius_if_promoted": blast_radius,
        "expected_effort": effort,
        "last_reviewed": last_reviewed,
        "stale": stale,
        "disposition": disposition,
        "blocks_module_closeout": blocks_closed,
    }


def parse_operational_opportunities(opportunities_path: Path) -> dict[str, Any]:
    if not opportunities_path.exists():
        return {
            "path": str(opportunities_path),
            "shape_valid": False,
            "violations": ["opportunities_missing_file"],
            "lanes": {},
            "all_items": [],
            "blocking_for_closed": [],
            "stale_items": [],
        }

    lines = opportunities_path.read_text(encoding="utf-8").splitlines()
    violations: list[str] = []
    op_heading_idx = _find_heading_indices(lines, OPPORTUNITIES_OPERATIONAL_HEADING)
    non_op_heading_idx = _find_heading_indices(lines, OPPORTUNITIES_NON_OPERATIONAL_HEADING)
    if len(op_heading_idx) != 1:
        violations.append(
            "opportunities_operational_heading_missing"
            if not op_heading_idx
            else "opportunities_operational_heading_duplicated"
        )
    if len(non_op_heading_idx) != 1:
        violations.append(
            "opportunities_non_operational_heading_missing"
            if not non_op_heading_idx
            else "opportunities_non_operational_heading_duplicated"
        )
    if violations:
        return {
            "path": str(opportunities_path),
            "shape_valid": False,
            "violations": violations,
            "lanes": {},
            "all_items": [],
            "blocking_for_closed": [],
            "stale_items": [],
        }

    op_start = op_heading_idx[0] + 1
    op_end = non_op_heading_idx[0]
    if op_end <= op_start:
        return {
            "path": str(opportunities_path),
            "shape_valid": False,
            "violations": ["opportunities_operational_section_empty"],
            "lanes": {},
            "all_items": [],
            "blocking_for_closed": [],
            "stale_items": [],
        }

    lane_positions: dict[str, int] = {}
    for lane_heading in OPPORTUNITIES_LANES:
        matches = [
            idx
            for idx in range(op_start, op_end)
            if lines[idx].strip() == lane_heading
        ]
        if not matches:
            violations.append(f"opportunities_lane_missing:{lane_heading[4:]}")
        elif len(matches) > 1:
            violations.append(f"opportunities_lane_duplicated:{lane_heading[4:]}")
        else:
            lane_positions[lane_heading] = matches[0]

    if violations:
        return {
            "path": str(opportunities_path),
            "shape_valid": False,
            "violations": violations,
            "lanes": {},
            "all_items": [],
            "blocking_for_closed": [],
            "stale_items": [],
        }

    ordered_lanes = list(OPPORTUNITIES_LANES)
    lane_names = [lane[4:] for lane in ordered_lanes]
    lane_ranges: list[tuple[str, int, int]] = []
    for idx, lane_heading in enumerate(ordered_lanes):
        start = lane_positions[lane_heading] + 1
        end = lane_positions[ordered_lanes[idx + 1]] if idx + 1 < len(ordered_lanes) else op_end
        lane_ranges.append((lane_heading[4:], start, end))

    lanes: dict[str, list[dict[str, Any]]] = {name: [] for name in lane_names}
    all_items: list[dict[str, Any]] = []
    seen_item_ids: dict[str, str] = {}

    for lane_name, start, end in lane_ranges:
        current_id: str | None = None
        current_title: str | None = None
        current_fields: dict[str, str] = {}

        def flush_current() -> None:
            nonlocal current_id, current_title, current_fields
            if current_id and current_title:
                if current_id in seen_item_ids:
                    violations.append(
                        f"opportunity_duplicate_id:{current_id}:{seen_item_ids[current_id]}:{lane_name}"
                    )
                else:
                    seen_item_ids[current_id] = lane_name
                item = _normalize_opportunity_item(
                    current_id,
                    current_title,
                    lane_name,
                    current_fields,
                    violations,
                )
                lanes[lane_name].append(item)
                all_items.append(item)
            current_id = None
            current_title = None
            current_fields = {}

        for idx in range(start, end):
            line = lines[idx].rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            item_match = OPPORTUNITY_ITEM_RE.match(stripped)
            if item_match:
                flush_current()
                current_id = item_match.group(1)
                current_title = item_match.group(2)
                continue
            field_match = OPPORTUNITY_FIELD_RE.match(stripped)
            if field_match and current_id:
                field_name = field_match.group(1)
                field_value = field_match.group(2)
                if field_name in current_fields:
                    violations.append(
                        f"opportunity_duplicate_field:{current_id}:{field_name}"
                    )
                    continue
                current_fields[field_name] = field_value
                continue
            violations.append(f"opportunities_unparseable_line:{lane_name}:{idx + 1}:{stripped}")
        flush_current()

    blocking_for_closed = [
        item["id"]
        for item in all_items
        if item["blocks_module_closeout"]
    ]
    stale_items = [item["id"] for item in all_items if item["stale"]]

    return {
        "path": str(opportunities_path),
        "shape_valid": not violations,
        "violations": violations,
        "lanes": lanes,
        "all_items": all_items,
        "blocking_for_closed": blocking_for_closed,
        "stale_items": stale_items,
    }


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
    opportunities_path = repo_root / "docs/project/OPPORTUNITIES.md"
    project_state_last_updated = parse_project_state_last_updated(project_state_path)
    module1_status, module1_status_violations = parse_project_state_module1_status(project_state_path)
    discovery_baseline = (
        parse_discovery_baseline_block(project_state_path.read_text(encoding="utf-8"))
        if project_state_path.exists()
        else {
            "present": False,
            "valid": True,
            "values": None,
            "violations": [],
        }
    )
    changelog_latest_date = parse_changelog_latest_date(changelog_path)
    project_state_lags = False
    if project_state_last_updated and changelog_latest_date:
        project_state_date = parse_iso_date(project_state_last_updated)
        changelog_date = parse_iso_date(changelog_latest_date)
        if project_state_date and changelog_date:
            project_state_lags = project_state_date < changelog_date

    manual_override_counts = collect_manual_override_counts(repo_root / "cases")
    active_backlog_ids = parse_active_backlog_ids(backlog_path)
    opportunities_report = parse_operational_opportunities(opportunities_path)

    governance_contract_violations = list(module1_status_violations)
    governance_contract_violations.extend(discovery_baseline["violations"])
    governance_contract_violations.extend(opportunities_report["violations"])
    duplicate_backlog_ids = parse_duplicate_backlog_ids(backlog_path)
    if duplicate_backlog_ids:
        governance_contract_violations.append("backlog_duplicate_active_ids")

    if (
        module1_status == MODULE1_STATUS_CLOSED
        and active_backlog_ids
    ):
        governance_contract_violations.append("module1_closed_with_active_backlog")
    if (
        module1_status == MODULE1_STATUS_CLOSED
        and opportunities_report["blocking_for_closed"]
    ):
        governance_contract_violations.append("module1_closed_with_open_operational_opportunities")
    if (
        module1_status == MODULE1_STATUS_CLOSEOUT_CANDIDATE
        and active_backlog_ids
    ):
        governance_contract_violations.append("module1_closeout_candidate_with_active_backlog")

    technical_work_pending = bool(grouped["technical_dirty"])
    governance_work_pending = bool(grouped["governance_dirty"] or governance_contract_violations)
    workspace_noise_present = bool(grouped["workspace_only_dirty"])
    duplicate_backlog_ids_present = bool(duplicate_backlog_ids)
    untracked_technical_files_present = bool(untracked_technical_files)
    untracked_test_files_present = bool(untracked_test_files)
    repo_requires_reconcile = technical_work_pending or governance_work_pending or bool(grouped["other_dirty"])
    backlog_is_empty = not active_backlog_ids

    if repo_requires_reconcile:
        next_resolution_mode = NEXT_RESOLUTION_RECONCILE
    elif active_backlog_ids:
        next_resolution_mode = NEXT_RESOLUTION_EXECUTE
    elif backlog_is_empty and module1_status == MODULE1_STATUS_OPEN:
        next_resolution_mode = NEXT_RESOLUTION_EMPTY_BACKLOG
    elif backlog_is_empty and module1_status == MODULE1_STATUS_CLOSEOUT_CANDIDATE:
        next_resolution_mode = NEXT_RESOLUTION_CLOSEOUT
    else:
        next_resolution_mode = NEXT_RESOLUTION_IDLE

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
            "active_ids": active_backlog_ids,
            "active_count": len(active_backlog_ids),
            "is_empty": backlog_is_empty,
            "duplicate_ids": duplicate_backlog_ids,
        },
        "project_state": {
            "path": str(project_state_path),
            "last_updated": project_state_last_updated,
            "module1_status": module1_status,
            "content_sha256": file_hash(project_state_path),
            "discovery_baseline": discovery_baseline,
        },
        "opportunities": {
            "path": str(opportunities_path),
            "operational_shape_valid": opportunities_report["shape_valid"],
            "operational_violations": opportunities_report["violations"],
            "operational_blocking_for_closed": opportunities_report["blocking_for_closed"],
            "operational_stale_items": opportunities_report["stale_items"],
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
            "technical_work_pending": technical_work_pending,
            "governance_work_pending": governance_work_pending,
            "workspace_noise_present": workspace_noise_present,
            "duplicate_backlog_ids_present": duplicate_backlog_ids_present,
            "project_state_lags_changelog": project_state_lags,
            "untracked_technical_files_present": untracked_technical_files_present,
            "untracked_test_files_present": untracked_test_files_present,
            "governance_contract_violations": governance_contract_violations,
            "next_resolution_mode": next_resolution_mode,
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
        f"backlog.active_ids: {', '.join(report['backlog']['active_ids']) or '-'}",
        f"backlog.active_count: {report['backlog']['active_count']}",
        f"backlog.is_empty: {report['backlog']['is_empty']}",
        f"backlog.duplicate_ids: {report['backlog']['duplicate_ids'] or '-'}",
        f"project_state.last_updated: {report['project_state']['last_updated'] or '-'}",
        f"project_state.module1_status: {report['project_state']['module1_status'] or '-'}",
        (
            "project_state.discovery_baseline: "
            f"present={report['project_state']['discovery_baseline']['present']} "
            f"valid={report['project_state']['discovery_baseline']['valid']} "
            f"violations={report['project_state']['discovery_baseline']['violations'] or '-'}"
        ),
        f"changelog.latest_date: {report['changelog']['latest_date'] or '-'}",
        f"project_state_lags_changelog: {report['document_sync']['project_state_lags_changelog']}",
        f"opportunities.operational_shape_valid: {report['opportunities']['operational_shape_valid']}",
        f"opportunities.operational_violations: {report['opportunities']['operational_violations'] or '-'}",
        f"opportunities.operational_blocking_for_closed: {report['opportunities']['operational_blocking_for_closed'] or '-'}",
        f"opportunities.operational_stale_items: {report['opportunities']['operational_stale_items'] or '-'}",
        f"manual_overrides.nonzero_by_ticker: {report['manual_overrides']['nonzero_by_ticker'] or '-'}",
        f"next_resolution_mode: {report['summary']['next_resolution_mode']}",
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

    contract_violations_present = bool(report["summary"]["governance_contract_violations"])
    return 1 if (manifest_violations or contract_violations_present) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
