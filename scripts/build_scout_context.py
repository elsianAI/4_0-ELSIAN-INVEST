#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from elsian.analyze.discovery_baseline import (
    compute_cases_signature,
    compute_diagnose_signature,
    compute_eval_signature,
    compute_operational_opportunities_signature,
    validate_eval_output_payload,
)


DIAGNOSE_REQUIRED_KEYS = {
    "summary",
    "root_cause_summary",
    "by_period_type",
    "by_field_category",
    "hotspots",
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ok_run(path: Path, signature: str, notes: str = "") -> dict[str, Any]:
    return {
        "status": "ok",
        "artifact_path": str(path.resolve()),
        "signature": signature,
        "notes": notes,
    }


def _bad_run(status: str, notes: str) -> dict[str, Any]:
    return {
        "status": status,
        "artifact_path": None,
        "signature": None,
        "notes": notes,
    }


def summarize_eval_run(eval_json_path: Path) -> dict[str, Any]:
    if not eval_json_path.exists():
        return _bad_run("unusable_artifact", f"Missing eval artifact: {eval_json_path}")

    try:
        payload = _load_json(eval_json_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _bad_run("unusable_artifact", f"Unreadable eval artifact: {exc}")

    if not isinstance(payload, Mapping):
        return _bad_run("unusable_artifact", "Eval artifact must be a JSON object")

    issues = validate_eval_output_payload(payload)
    if issues:
        return _bad_run("unusable_artifact", f"Invalid eval artifact shape: {', '.join(issues)}")

    return _ok_run(eval_json_path, compute_eval_signature(payload))


def summarize_diagnose_run(diagnose_json_path: Path) -> dict[str, Any]:
    if not diagnose_json_path.exists():
        return _bad_run("unusable_artifact", f"Missing diagnose artifact: {diagnose_json_path}")

    try:
        payload = _load_json(diagnose_json_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _bad_run("unusable_artifact", f"Unreadable diagnose artifact: {exc}")

    if not isinstance(payload, Mapping):
        return _bad_run("unusable_artifact", "Diagnose artifact must be a JSON object")

    missing_keys = sorted(DIAGNOSE_REQUIRED_KEYS.difference(payload.keys()))
    if missing_keys:
        return _bad_run(
            "unusable_artifact",
            f"Diagnose artifact missing required keys: {', '.join(missing_keys)}",
        )

    try:
        signature = compute_diagnose_signature(payload)
    except (AttributeError, TypeError, ValueError) as exc:
        return _bad_run("unusable_artifact", f"Diagnose artifact is not signable: {exc}")

    return _ok_run(diagnose_json_path, signature)


def build_case_review(cases_root: Path) -> tuple[dict[str, Any], list[str]]:
    if not cases_root.exists():
        return {
            "all_cases_reviewed": False,
            "all_manifests_reviewed": False,
            "manifest_missing_tickers": [],
        }, [f"Cases root does not exist: {cases_root}"]

    if not cases_root.is_dir():
        return {
            "all_cases_reviewed": False,
            "all_manifests_reviewed": False,
            "manifest_missing_tickers": [],
        }, [f"Cases root is not a directory: {cases_root}"]

    case_tickers = sorted(path.parent.name for path in cases_root.glob("*/case.json"))
    if not case_tickers:
        return {
            "all_cases_reviewed": False,
            "all_manifests_reviewed": False,
            "manifest_missing_tickers": [],
        }, [f"No case.json files found under: {cases_root}"]

    manifest_tickers = sorted(
        {
            path.parent.name
            for path in cases_root.glob("*/filings_manifest.json")
            if (path.parent / "case.json").exists()
        }
    )
    missing_tickers = [ticker for ticker in case_tickers if ticker not in manifest_tickers]
    return {
        "all_cases_reviewed": True,
        "all_manifests_reviewed": True,
        "manifest_missing_tickers": missing_tickers,
    }, []


def build_scout_context(
    *,
    eval_json_path: Path,
    diagnose_json_path: Path,
    cases_root: Path,
    opportunities_md_path: Path,
) -> dict[str, Any]:
    partial_reasons: list[str] = []

    eval_run = summarize_eval_run(eval_json_path)
    if eval_run["status"] != "ok":
        partial_reasons.append(f"eval_run:{eval_run['status']}:{eval_run['notes']}")

    diagnose_run = summarize_diagnose_run(diagnose_json_path)
    if diagnose_run["status"] != "ok":
        partial_reasons.append(f"diagnose_run:{diagnose_run['status']}:{diagnose_run['notes']}")

    case_review, case_review_errors = build_case_review(cases_root)
    partial_reasons.extend(f"case_review:{reason}" for reason in case_review_errors)

    baseline_signatures: dict[str, str | None] = {
        "last_eval_signature": eval_run["signature"],
        "last_diagnose_signature": diagnose_run["signature"],
        "last_cases_signature": None,
        "last_operational_opportunities_signature": None,
    }

    try:
        baseline_signatures["last_cases_signature"] = compute_cases_signature(cases_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        partial_reasons.append(f"case_review:unreadable_cases_corpus:{exc}")

    try:
        opportunities_text = opportunities_md_path.read_text(encoding="utf-8")
        baseline_signatures["last_operational_opportunities_signature"] = (
            compute_operational_opportunities_signature(opportunities_text)
        )
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as exc:
        partial_reasons.append(f"case_review:unreadable_opportunities_md:{exc}")

    partial_pass = bool(partial_reasons)

    return {
        "eval_run": eval_run,
        "diagnose_run": diagnose_run,
        "baseline_signatures": baseline_signatures,
        "case_review": case_review,
        "partial_pass": partial_pass,
        "partial_reasons": partial_reasons,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build repo-tracked scout context from artifacts.")
    parser.add_argument("--eval-json", required=True)
    parser.add_argument("--diagnose-json", required=True)
    parser.add_argument("--cases-root", required=True)
    parser.add_argument("--opportunities-md", required=True)
    parser.add_argument("--output-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    context = build_scout_context(
        eval_json_path=Path(args.eval_json).expanduser(),
        diagnose_json_path=Path(args.diagnose_json).expanduser(),
        cases_root=Path(args.cases_root).expanduser(),
        opportunities_md_path=Path(args.opportunities_md).expanduser(),
    )

    output_path = Path(args.output_json).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(context, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
