"""Helpers for Discovery Baseline artifacts and signatures."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DISCOVERY_BASELINE_HEADING = "## Discovery Baseline"
DISCOVERY_BASELINE_FIELD_ORDER = (
    "last_scout_pass_at",
    "last_scout_head",
    "last_eval_signature",
    "last_diagnose_signature",
    "last_cases_signature",
    "last_operational_opportunities_signature",
)
DISCOVERY_BASELINE_FIELD_PATTERNS = {
    "last_scout_pass_at": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"),
    "last_scout_head": re.compile(r"^[0-9a-f]{40}$"),
    "last_eval_signature": re.compile(r"^[0-9a-f]{64}$"),
    "last_diagnose_signature": re.compile(r"^[0-9a-f]{64}$"),
    "last_cases_signature": re.compile(r"^[0-9a-f]{64}$"),
    "last_operational_opportunities_signature": re.compile(r"^[0-9a-f]{64}$"),
}
DISCOVERY_BASELINE_FIELD_RE = re.compile(r"^- ([a-z0-9_]+): (.+)$")

EVAL_OUTPUT_REPORT_KEYS = (
    "ticker",
    "total_expected",
    "matched",
    "wrong",
    "missed",
    "extra",
    "score",
    "filings_coverage_pct",
    "required_fields_coverage_pct",
    "readiness_score",
    "validator_confidence_score",
    "provenance_coverage_pct",
    "extra_penalty",
)
HOTSPOT_SIGNATURE_KEYS = (
    "rank",
    "field",
    "field_category",
    "gap_type",
    "occurrences",
    "affected_tickers",
    "evidence",
    "root_cause_hint",
)
OPPORTUNITIES_OPERATIONAL_HEADING = "## Module 1 operational opportunities"
OPPORTUNITIES_NEXT_HEADING_RE = re.compile(r"^##\s+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _report_to_dict(report: Any) -> dict[str, Any]:
    if hasattr(report, "to_dict"):
        payload = report.to_dict()
    elif isinstance(report, Mapping):
        payload = dict(report)
    else:
        raise TypeError(f"Unsupported eval report payload: {type(report)!r}")
    return dict(payload)


def build_eval_output_payload(reports: Sequence[Any]) -> dict[str, Any]:
    normalized = [_report_to_dict(report) for report in reports]
    normalized.sort(key=lambda report: str(report.get("ticker", "")))
    return {
        "schema_version": 1,
        "reports": normalized,
    }


def validate_eval_output_payload(payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if set(payload.keys()) != {"schema_version", "reports"}:
        issues.append("top_level_keys")
        return issues
    if payload.get("schema_version") != 1:
        issues.append("schema_version")
    reports = payload.get("reports")
    if not isinstance(reports, list):
        issues.append("reports_type")
        return issues

    tickers: list[str] = []
    for idx, report in enumerate(reports):
        if not isinstance(report, Mapping):
            issues.append(f"report_type:{idx}")
            continue
        if tuple(report.keys()) != EVAL_OUTPUT_REPORT_KEYS and set(report.keys()) != set(EVAL_OUTPUT_REPORT_KEYS):
            issues.append(f"report_keys:{idx}")
        ticker = report.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            issues.append(f"ticker:{idx}")
        else:
            tickers.append(ticker)

    if tickers != sorted(tickers):
        issues.append("report_order")
    return issues


def compute_eval_signature(reports_or_payload: Sequence[Any] | Mapping[str, Any]) -> str:
    if isinstance(reports_or_payload, Mapping):
        reports = reports_or_payload.get("reports", [])
    else:
        reports = reports_or_payload
    normalized = [_report_to_dict(report) for report in reports]
    normalized.sort(key=lambda report: str(report.get("ticker", "")))
    return sha256_text(canonical_json(normalized))


def compute_diagnose_signature(report: Mapping[str, Any]) -> str:
    hotspots_payload: list[dict[str, Any]] = []
    for hotspot in report.get("hotspots", []):
        if not isinstance(hotspot, Mapping):
            continue
        hotspots_payload.append({key: hotspot.get(key) for key in HOTSPOT_SIGNATURE_KEYS})
    hotspots_payload.sort(
        key=lambda hotspot: (
            hotspot.get("rank") if hotspot.get("rank") is not None else 10**9,
            str(hotspot.get("field", "")),
            str(hotspot.get("gap_type", "")),
        )
    )
    payload = {
        "summary": report.get("summary"),
        "root_cause_summary": report.get("root_cause_summary"),
        "by_period_type": report.get("by_period_type"),
        "by_field_category": report.get("by_field_category"),
        "hotspots": hotspots_payload,
    }
    return sha256_text(canonical_json(payload))


def _normalized_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory_filings(filings_dir: Path) -> list[dict[str, Any]]:
    if not filings_dir.exists():
        return []
    inventory: list[dict[str, Any]] = []
    for filing_path in sorted(path for path in filings_dir.rglob("*") if path.is_file()):
        inventory.append(
            {
                "relative_path": filing_path.relative_to(filings_dir).as_posix(),
                "size": filing_path.stat().st_size,
                "sha256": sha256_bytes(filing_path.read_bytes()),
            }
        )
    return inventory


def build_cases_signature_payload(cases_root: Path) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for case_json_path in sorted(cases_root.glob("*/case.json")):
        case_dir = case_json_path.parent
        entry: dict[str, Any] = {
            "ticker": case_dir.name,
            "case": _normalized_json_file(case_json_path),
        }
        manifest_path = case_dir / "filings_manifest.json"
        if manifest_path.exists():
            entry["filings_manifest"] = _normalized_json_file(manifest_path)
        else:
            entry["filings_inventory"] = _inventory_filings(case_dir / "filings")
        payload.append(entry)
    return payload


def compute_cases_signature(cases_root: Path) -> str:
    return sha256_text(canonical_json(build_cases_signature_payload(cases_root)))


def extract_operational_opportunities_subtree(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    start_idx: int | None = None
    end_idx = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == OPPORTUNITIES_OPERATIONAL_HEADING:
            start_idx = idx
            continue
        if start_idx is not None and idx > start_idx and OPPORTUNITIES_NEXT_HEADING_RE.match(stripped):
            end_idx = idx
            break
    if start_idx is None:
        return ""
    normalized_lines = [line.rstrip() for line in lines[start_idx:end_idx]]
    return "\n".join(normalized_lines).strip()


def compute_operational_opportunities_signature(markdown_text: str) -> str:
    return sha256_text(extract_operational_opportunities_subtree(markdown_text))


def parse_discovery_baseline_block(markdown_text: str) -> dict[str, Any]:
    lines = markdown_text.splitlines()
    heading_indices = [
        idx for idx, line in enumerate(lines) if line.strip() == DISCOVERY_BASELINE_HEADING
    ]
    if not heading_indices:
        return {
            "present": False,
            "valid": True,
            "values": None,
            "violations": [],
        }
    if len(heading_indices) > 1:
        return {
            "present": True,
            "valid": False,
            "values": None,
            "violations": ["project_state_discovery_baseline_duplicated"],
        }

    start_idx = heading_indices[0] + 1
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        if lines[idx].startswith("## "):
            end_idx = idx
            break

    block_lines = [line for line in lines[start_idx:end_idx] if line.strip()]
    parsed_items: list[tuple[str, str]] = []
    violations: list[str] = []
    for line in block_lines:
        match = DISCOVERY_BASELINE_FIELD_RE.match(line.strip())
        if not match:
            violations.append(f"project_state_discovery_baseline_unparseable_line:{line.strip()}")
            continue
        parsed_items.append((match.group(1), match.group(2)))

    parsed_keys = [key for key, _ in parsed_items]
    if parsed_keys != list(DISCOVERY_BASELINE_FIELD_ORDER):
        violations.append("project_state_discovery_baseline_field_order")

    missing_fields = [
        key for key in DISCOVERY_BASELINE_FIELD_ORDER if key not in parsed_keys
    ]
    if missing_fields:
        violations.append(
            f"project_state_discovery_baseline_missing_fields:{','.join(missing_fields)}"
        )

    extra_fields = [
        key for key in parsed_keys if key not in DISCOVERY_BASELINE_FIELD_ORDER
    ]
    if extra_fields:
        violations.append(
            f"project_state_discovery_baseline_extra_fields:{','.join(extra_fields)}"
        )

    values = {key: value for key, value in parsed_items if key in DISCOVERY_BASELINE_FIELD_PATTERNS}
    for key, pattern in DISCOVERY_BASELINE_FIELD_PATTERNS.items():
        value = values.get(key)
        if value is None:
            continue
        if not pattern.match(value):
            violations.append(f"project_state_discovery_baseline_invalid_format:{key}")

    return {
        "present": True,
        "valid": not violations,
        "values": values if values else None,
        "violations": violations,
    }
