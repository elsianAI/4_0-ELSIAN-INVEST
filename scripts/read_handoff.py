#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

check_governance = importlib.import_module("check_governance")
write_handoff = importlib.import_module("write_handoff")


REQUIRED_FIELDS = {
    "schema_version",
    "generated_at",
    "generated_by",
    "repo_root",
    "worktree_path",
    "head",
    "branch",
    "next_resolution_mode",
    "current_focus",
    "status",
    "last_completed_step",
    "recommended_next_route",
    "recommended_next_action",
    "blocking_questions",
    "stale_if",
    "scope",
}
REQUIRED_STALE_IF_FIELDS = {
    "head_must_match",
    "branch_must_match",
    "live_state_fingerprint_must_match",
    "live_state_snapshot",
}


def load_handoff(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def missing_required_fields(payload: dict[str, Any]) -> list[str]:
    missing = sorted(REQUIRED_FIELDS - payload.keys())
    stale_if = payload.get("stale_if")
    if not isinstance(stale_if, dict):
        missing.append("stale_if")
        return missing
    missing.extend(sorted(f"stale_if.{key}" for key in REQUIRED_STALE_IF_FIELDS - stale_if.keys()))
    return missing


def diff_live_state(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(previous) | set(current)):
        previous_value = previous.get(key)
        current_value = current.get(key)
        if previous_value != current_value:
            diff[key] = {"stored": previous_value, "current": current_value}
    return diff


def validate_handoff(
    payload: dict[str, Any],
    *,
    report: dict[str, Any],
    current_head: str,
) -> dict[str, Any]:
    current_snapshot = write_handoff.build_live_state_snapshot(report)
    current_fingerprint = write_handoff.compute_live_state_fingerprint(current_snapshot)
    stale_if = payload["stale_if"]
    reasons: list[str] = []

    if current_head != stale_if["head_must_match"]:
        reasons.append("head_changed")
    if report["branch"] != stale_if["branch_must_match"]:
        reasons.append("branch_changed")
    if current_fingerprint != stale_if["live_state_fingerprint_must_match"]:
        reasons.append("live_state_changed")

    return {
        "valid": not reasons,
        "effective_status": payload["status"] if not reasons else "stale",
        "reasons": reasons,
        "current_head": current_head,
        "stored_head": stale_if["head_must_match"],
        "current_branch": report["branch"],
        "stored_branch": stale_if["branch_must_match"],
        "current_live_state_fingerprint": current_fingerprint,
        "stored_live_state_fingerprint": stale_if["live_state_fingerprint_must_match"],
        "live_state_diff": diff_live_state(stale_if["live_state_snapshot"], current_snapshot),
    }


def build_json_output(
    *,
    exists: bool,
    payload: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    return {
        "exists": exists,
        "error": error,
        "handoff": payload,
        "validation": validation,
    }


def print_text(payload: dict[str, Any], validation: dict[str, Any]) -> None:
    header = "HANDOFF VALID" if validation["valid"] else "HANDOFF STALE"
    lines = [
        header,
        f"status: {validation['effective_status']}",
        f"generated_at: {payload['generated_at']}",
        f"generated_by: {payload['generated_by']}",
        f"branch: {payload['branch']}",
        f"head: {payload['head']}",
        f"next_resolution_mode: {payload['next_resolution_mode']}",
        f"current_focus: {payload['current_focus']}",
        f"last_completed_step: {payload['last_completed_step'] or '-'}",
        f"recommended_next_route: {payload['recommended_next_route'] or '-'}",
        f"recommended_next_action: {payload['recommended_next_action'] or '-'}",
        f"scope: {payload['scope']}",
        "blocking_questions:",
    ]
    if payload["blocking_questions"]:
        lines.extend(f"- {question}" for question in payload["blocking_questions"])
    else:
        lines.append("- none")

    if validation["reasons"]:
        lines.append("stale_reasons:")
        lines.extend(f"- {reason}" for reason in validation["reasons"])
    if validation["live_state_diff"]:
        lines.append("live_state_diff:")
        for key, change in validation["live_state_diff"].items():
            lines.append(f"- {key}: stored={change['stored']!r} current={change['current']!r}")
    sys.stdout.write("\n".join(lines) + "\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read and validate local runtime handoff.")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = check_governance.resolve_repo_root()
    path = write_handoff.handoff_path(repo_root)
    if not path.exists():
        error = f"handoff file not found: {path}"
        if args.format == "json":
            json.dump(build_json_output(exists=False, payload=None, validation=None, error=error), sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(error + "\n")
        return 2

    try:
        payload = load_handoff(path)
    except json.JSONDecodeError as exc:
        error = f"invalid handoff JSON: {exc}"
        if args.format == "json":
            json.dump(build_json_output(exists=True, payload=None, validation=None, error=error), sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(error + "\n")
        return 1

    missing = missing_required_fields(payload)
    if missing:
        error = f"invalid handoff schema: missing {', '.join(missing)}"
        if args.format == "json":
            json.dump(build_json_output(exists=True, payload=payload, validation=None, error=error), sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(error + "\n")
        return 1

    report = check_governance.build_report(repo_root)
    current_head = check_governance.run_git(repo_root, "rev-parse", "HEAD").strip()
    validation = validate_handoff(payload, report=report, current_head=current_head)

    if args.format == "json":
        json.dump(
            build_json_output(exists=True, payload=payload, validation=validation, error=None),
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    else:
        print_text(payload, validation)
    return 0 if validation["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
