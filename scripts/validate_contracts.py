"""Validate versioned contracts for tracked ELSIAN artifacts.

This script intentionally validates only git-tracked artifacts under ``cases/``.
That keeps local user work, drafts, and temporary files outside the contract
gate until they are deliberately staged into the repository.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from elsian.models.case import CaseConfig  # noqa: E402


SCHEMAS_DIR = ROOT / "schemas" / "v1"
PROMPT_PATH = ROOT / ".github" / "prompts" / "curate-expected.prompt.md"
FILE_TO_SCHEMA = {
    "case.json": "case",
    "expected.json": "expected",
    "filings_manifest.json": "filings_manifest",
    "extraction_result.json": "extraction_result",
    "truth_pack.json": "truth_pack",
    "source_map.json": "source_map",
}
TASK_KINDS = {"technical", "governance", "mixed"}
VALIDATION_TIERS = {"targeted", "shared-core", "governance-only"}
CLAIMED_BL_STATUSES = {"none", "in_progress", "blocked", "done"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMAS_DIR / f"{name}.schema.json"
    return _load_json(path)


def _canonical_fields() -> tuple[str, ...]:
    common = _load_schema("common")
    return tuple(common["$defs"]["canonicalFieldName"]["enum"])


def _case_schema_keys() -> set[str]:
    return set(_load_schema("case")["properties"].keys())


def _schema_names() -> tuple[str, ...]:
    return (
        "common",
        "case",
        "expected",
        "filings_manifest",
        "extraction_result",
        "truth_pack",
        "source_map",
        "task_manifest",
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _read_git_tracked_paths(*paths: str) -> list[Path]:
    cmd = ["git", "-C", str(ROOT), "ls-files", "--", *paths]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            tracked.append(ROOT / line)
    return tracked


def _validate_root_shape(
    data: Any,
    *,
    required: set[str],
    allowed: set[str],
    path: Path,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(data, dict):
        return [f"{path}: root must be an object"]

    missing = sorted(required - set(data))
    if missing:
        issues.append(f"{path}: missing keys {missing}")

    unknown = sorted(set(data) - allowed)
    if unknown:
        issues.append(f"{path}: unknown keys {unknown}")

    return issues


def validate_case_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={"ticker", "currency", "source_hint", "period_scope"},
        allowed=_case_schema_keys(),
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    canonical_fields = set(_canonical_fields())

    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("currency")):
        issues.append(f"{path}: currency must be a non-empty string")
    if not _is_non_empty_string(data.get("source_hint")):
        issues.append(f"{path}: source_hint must be a non-empty string")
    if data.get("period_scope") not in {"ANNUAL_ONLY", "FULL"}:
        issues.append(f"{path}: period_scope must be ANNUAL_ONLY or FULL")

    nullable_strings = {
        "company_name",
        "exchange",
        "market",
        "country",
        "cik",
        "accounting_standard",
        "sector",
        "raw_filings_dir",
        "web_ir",
    }
    for key in nullable_strings:
        value = data.get(key)
        if value is not None and not _is_non_empty_string(value):
            issues.append(f"{path}: {key} must be null or a non-empty string")

    if "notes" in data and not isinstance(data["notes"], str):
        issues.append(f"{path}: notes must be a string")

    if "fiscal_year_end_month" in data:
        month = data["fiscal_year_end_month"]
        if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= 12:
            issues.append(f"{path}: fiscal_year_end_month must be an integer between 1 and 12")

    if "filings_expected_count" in data:
        count = data["filings_expected_count"]
        if count is not None and (
            not isinstance(count, int) or isinstance(count, bool) or count < 0
        ):
            issues.append(f"{path}: filings_expected_count must be null or a non-negative integer")

    if "use_ixbrl_override" in data and not isinstance(data["use_ixbrl_override"], bool):
        issues.append(f"{path}: use_ixbrl_override must be boolean")

    additive_fields = data.get("additive_fields")
    if additive_fields is not None:
        if not isinstance(additive_fields, list):
            issues.append(f"{path}: additive_fields must be a list")
        else:
            bad = [field for field in additive_fields if field not in canonical_fields]
            if bad:
                issues.append(f"{path}: additive_fields contains unknown canonical fields {bad}")

    filings_sources = data.get("filings_sources")
    if filings_sources is not None:
        if not isinstance(filings_sources, list):
            issues.append(f"{path}: filings_sources must be a list")
        else:
            for idx, source in enumerate(filings_sources):
                loc = f"{path}: filings_sources[{idx}]"
                if not isinstance(source, dict):
                    issues.append(f"{loc} must be an object")
                    continue
                required = {"url", "filename"}
                missing = sorted(required - set(source))
                if missing:
                    issues.append(f"{loc} missing keys {missing}")
                unknown = sorted(set(source) - {"url", "filename", "filing_type", "period_end"})
                if unknown:
                    issues.append(f"{loc} unknown keys {unknown}")
                for key in ("url", "filename", "filing_type", "period_end"):
                    value = source.get(key)
                    if value is not None and not _is_non_empty_string(value):
                        issues.append(f"{loc}.{key} must be a non-empty string")

    for key in ("selection_overrides", "config_overrides"):
        if key in data and not isinstance(data[key], dict):
            issues.append(f"{path}: {key} must be an object")

    return issues


def validate_expected_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={"version", "ticker", "currency", "scale", "periods"},
        allowed={
            "version",
            "ticker",
            "currency",
            "period_scope",
            "restatement_policy",
            "scale",
            "scale_notes",
            "periods",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    canonical_fields = set(_canonical_fields())
    if data.get("version") != "1.0":
        issues.append(f"{path}: version must be '1.0'")
    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("currency")):
        issues.append(f"{path}: currency must be a non-empty string")
    if not _is_non_empty_string(data.get("scale")):
        issues.append(f"{path}: scale must be a non-empty string")
    if "period_scope" in data and data["period_scope"] not in {"ANNUAL_ONLY", "FULL"}:
        issues.append(f"{path}: period_scope must be ANNUAL_ONLY or FULL")

    periods = data.get("periods")
    if not isinstance(periods, dict) or not periods:
        issues.append(f"{path}: periods must be a non-empty object")
        return issues

    for period_key, period_data in periods.items():
        loc = f"{path}:{period_key}"
        if not isinstance(period_data, dict):
            issues.append(f"{loc}: period must be an object")
            continue
        allowed = {"fecha_fin", "tipo_periodo", "fields"}
        extra = [
            key for key in period_data
            if key not in allowed and not key.startswith("_NOTE_")
        ]
        if extra:
            issues.append(f"{loc}: unknown keys {sorted(extra)}")
        if not _is_non_empty_string(period_data.get("fecha_fin")):
            issues.append(f"{loc}: fecha_fin must be a non-empty string")
        if period_data.get("tipo_periodo") not in {"anual", "trimestral", "semestral"}:
            issues.append(f"{loc}: tipo_periodo must be anual, trimestral or semestral")
        fields = period_data.get("fields")
        if not isinstance(fields, dict) or not fields:
            issues.append(f"{loc}: fields must be a non-empty object")
            continue
        for field_name, field_data in fields.items():
            field_loc = f"{loc}:{field_name}"
            if field_name not in canonical_fields:
                issues.append(f"{field_loc}: unknown canonical field")
                continue
            if not isinstance(field_data, dict):
                issues.append(f"{field_loc}: field must be an object")
                continue
            if set(field_data) - {"value", "source_filing", "restatement"}:
                issues.append(f"{field_loc}: unknown keys {sorted(set(field_data) - {'value', 'source_filing', 'restatement'})}")
            if not _is_number(field_data.get("value")):
                issues.append(f"{field_loc}: value must be numeric")
            if not _is_non_empty_string(field_data.get("source_filing")):
                issues.append(f"{field_loc}: source_filing must be a non-empty string")
            restatement = field_data.get("restatement")
            if restatement is not None:
                if not isinstance(restatement, dict):
                    issues.append(f"{field_loc}: restatement must be an object")
                else:
                    required = {
                        "applied",
                        "trigger",
                        "evidence_filing",
                        "evidence_text",
                        "original_source_filing",
                        "original_value",
                    }
                    missing = sorted(required - set(restatement))
                    if missing:
                        issues.append(f"{field_loc}: restatement missing keys {missing}")
                    if set(restatement) - required:
                        issues.append(f"{field_loc}: restatement unknown keys {sorted(set(restatement) - required)}")
                    if not isinstance(restatement.get("applied"), bool):
                        issues.append(f"{field_loc}: restatement.applied must be boolean")
                    for key in ("trigger", "evidence_filing", "evidence_text", "original_source_filing"):
                        if key in restatement and not _is_non_empty_string(restatement.get(key)):
                            issues.append(f"{field_loc}: restatement.{key} must be a non-empty string")
                    if "original_value" in restatement and not _is_number(restatement.get("original_value")):
                        issues.append(f"{field_loc}: restatement.original_value must be numeric")
                    if restatement.get("original_source_filing") == field_data.get("source_filing"):
                        issues.append(f"{field_loc}: original_source_filing must differ from source_filing")

    return issues


def validate_filings_manifest_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={
            "ticker",
            "source",
            "cik",
            "filings_downloaded",
            "filings_failed",
            "filings_coverage_pct",
            "coverage",
            "gaps",
            "notes",
            "download_date",
        },
        allowed={
            "ticker",
            "source",
            "cik",
            "filings_downloaded",
            "filings_failed",
            "filings_coverage_pct",
            "coverage",
            "gaps",
            "notes",
            "download_date",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("source")):
        issues.append(f"{path}: source must be a non-empty string")
    cik = data.get("cik")
    if cik is not None and not _is_non_empty_string(cik):
        issues.append(f"{path}: cik must be null or a non-empty string")
    for key in ("filings_downloaded", "filings_failed"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(f"{path}: {key} must be a non-negative integer")
    if not _is_number(data.get("filings_coverage_pct")):
        issues.append(f"{path}: filings_coverage_pct must be numeric")
    if not isinstance(data.get("coverage"), dict):
        issues.append(f"{path}: coverage must be an object")
    gaps = data.get("gaps")
    if not isinstance(gaps, list) or any(not isinstance(item, str) for item in gaps):
        issues.append(f"{path}: gaps must be a list of strings")
    if "notes" in data and not isinstance(data["notes"], str):
        issues.append(f"{path}: notes must be a string")
    if not _is_non_empty_string(data.get("download_date")):
        issues.append(f"{path}: download_date must be a non-empty string")

    return issues


def _validate_result_periods(
    periods: Any,
    path: Path,
    *,
    require_periods: bool,
    allow_unknown_status: bool = True,
) -> list[str]:
    issues: list[str] = []
    canonical_fields = set(_canonical_fields())
    if not isinstance(periods, dict) or (require_periods and not periods):
        issues.append(f"{path}: periods must be a non-empty object")
        return issues
    for period_key, period_data in periods.items():
        loc = f"{path}:{period_key}"
        if not isinstance(period_data, dict):
            issues.append(f"{loc}: period must be an object")
            continue
        if not isinstance(period_data.get("fecha_fin"), str):
            issues.append(f"{loc}: fecha_fin must be a string")
        tipo_periodo = period_data.get("tipo_periodo")
        if tipo_periodo not in {"anual", "trimestral", "semestral", "unknown"}:
            issues.append(f"{loc}: tipo_periodo must be anual/trimestral/semestral/unknown")
        fields = period_data.get("fields")
        if not isinstance(fields, dict):
            issues.append(f"{loc}: fields must be an object")
            continue
        for field_name, field_data in fields.items():
            field_loc = f"{loc}:{field_name}"
            if field_name not in canonical_fields:
                issues.append(f"{field_loc}: unknown canonical field")
                continue
            if not isinstance(field_data, dict):
                issues.append(f"{field_loc}: field must be an object")
                continue
            if not _is_number(field_data.get("value")):
                issues.append(f"{field_loc}: value must be numeric")
            if not _is_non_empty_string(field_data.get("source_filing")):
                issues.append(f"{field_loc}: source_filing must be a non-empty string")
    return issues


def validate_extraction_result_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={
            "schema_version",
            "ticker",
            "currency",
            "extraction_date",
            "filings_used",
            "periods",
            "audit",
        },
        allowed={
            "schema_version",
            "ticker",
            "currency",
            "extraction_date",
            "filings_used",
            "periods",
            "audit",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    if data.get("schema_version") != "2.0":
        issues.append(f"{path}: schema_version must be '2.0'")
    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("currency")):
        issues.append(f"{path}: currency must be a non-empty string")
    if not _is_non_empty_string(data.get("extraction_date")):
        issues.append(f"{path}: extraction_date must be a non-empty string")
    if not isinstance(data.get("filings_used"), int) or isinstance(data.get("filings_used"), bool):
        issues.append(f"{path}: filings_used must be an integer")
    issues.extend(_validate_result_periods(data.get("periods"), path, require_periods=True))

    audit = data.get("audit")
    if not isinstance(audit, dict):
        issues.append(f"{path}: audit must be an object")
    else:
        required = {"fields_extracted", "fields_discarded", "discarded_reasons"}
        missing = sorted(required - set(audit))
        if missing:
            issues.append(f"{path}: audit missing keys {missing}")
        if set(audit) - required:
            issues.append(f"{path}: audit unknown keys {sorted(set(audit) - required)}")
        for key in ("fields_extracted", "fields_discarded"):
            value = audit.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                issues.append(f"{path}: audit.{key} must be a non-negative integer")
        reasons = audit.get("discarded_reasons")
        if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
            issues.append(f"{path}: audit.discarded_reasons must be a list of strings")

    return issues


def validate_truth_pack_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={
            "schema_version",
            "ticker",
            "currency",
            "assembly_date",
            "sources",
            "financial_data",
            "derived_metrics",
            "market_data",
            "quality",
            "metadata",
        },
        allowed={
            "schema_version",
            "ticker",
            "currency",
            "assembly_date",
            "sources",
            "financial_data",
            "derived_metrics",
            "market_data",
            "quality",
            "metadata",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    if data.get("schema_version") != "TruthPack_v1":
        issues.append(f"{path}: schema_version must be 'TruthPack_v1'")
    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("currency")):
        issues.append(f"{path}: currency must be a non-empty string")
    if not _is_non_empty_string(data.get("assembly_date")):
        issues.append(f"{path}: assembly_date must be a non-empty string")

    sources = data.get("sources")
    if not isinstance(sources, dict):
        issues.append(f"{path}: sources must be an object")
    else:
        required = {"extraction_result", "market_data", "case_config"}
        missing = sorted(required - set(sources))
        if missing:
            issues.append(f"{path}: sources missing keys {missing}")
        if set(sources) - required:
            issues.append(f"{path}: sources unknown keys {sorted(set(sources) - required)}")

    issues.extend(_validate_result_periods(data.get("financial_data"), path, require_periods=True))

    derived = data.get("derived_metrics")
    if not isinstance(derived, dict):
        issues.append(f"{path}: derived_metrics must be an object")
    else:
        required = {"ttm", "fcf", "ev", "margins", "returns", "multiples", "per_share", "net_debt", "periodo_base"}
        missing = sorted(required - set(derived))
        if missing:
            issues.append(f"{path}: derived_metrics missing keys {missing}")

    quality = data.get("quality")
    if not isinstance(quality, dict):
        issues.append(f"{path}: quality must be an object")
    else:
        required = {"validation_status", "confidence_score", "gates_summary", "warnings", "campos_faltantes_criticos"}
        missing = sorted(required - set(quality))
        if missing:
            issues.append(f"{path}: quality missing keys {missing}")

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        issues.append(f"{path}: metadata must be an object")
    else:
        required = {"total_periods", "total_fields", "period_scope", "source_hint", "fiscal_year_end_month"}
        missing = sorted(required - set(metadata))
        if missing:
            issues.append(f"{path}: metadata missing keys {missing}")

    return issues


def validate_source_map_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={
            "schema_version",
            "ticker",
            "generated_at",
            "source_basis",
            "summary",
            "periods",
        },
        allowed={
            "schema_version",
            "ticker",
            "generated_at",
            "source_basis",
            "summary",
            "periods",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    if data.get("schema_version") != "SourceMap_v1":
        issues.append(f"{path}: schema_version must be 'SourceMap_v1'")
    if not _is_non_empty_string(data.get("ticker")):
        issues.append(f"{path}: ticker must be a non-empty string")
    if not _is_non_empty_string(data.get("generated_at")):
        issues.append(f"{path}: generated_at must be a non-empty string")
    if not isinstance(data.get("source_basis"), dict):
        issues.append(f"{path}: source_basis must be an object")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        issues.append(f"{path}: summary must be an object")
    else:
        required = {
            "total_fields",
            "resolved_fields",
            "unresolved_fields",
            "resolution_pct",
            "by_method",
            "by_pointer_kind",
        }
        missing = sorted(required - set(summary))
        if missing:
            issues.append(f"{path}: summary missing keys {missing}")

    periods = data.get("periods")
    if not isinstance(periods, dict) or not periods:
        issues.append(f"{path}: periods must be a non-empty object")
        return issues

    canonical_fields = set(_canonical_fields())
    for period_key, period_data in periods.items():
        loc = f"{path}:{period_key}"
        if not isinstance(period_data, dict):
            issues.append(f"{loc}: period must be an object")
            continue
        if not isinstance(period_data.get("fields"), dict):
            issues.append(f"{loc}: fields must be an object")
            continue
        for field_name, field_data in period_data["fields"].items():
            field_loc = f"{loc}:{field_name}"
            if field_name not in canonical_fields:
                issues.append(f"{field_loc}: unknown canonical field")
                continue
            if not isinstance(field_data, dict):
                issues.append(f"{field_loc}: field must be an object")
                continue
            required = {
                "value",
                "source_filing",
                "source_location",
                "extraction_method",
                "field_name",
                "resolution_status",
            }
            missing = sorted(required - set(field_data))
            if missing:
                issues.append(f"{field_loc}: missing keys {missing}")
            if field_data.get("field_name") != field_name:
                issues.append(f"{field_loc}: field_name must match parent field key")
            if not _is_number(field_data.get("value")):
                issues.append(f"{field_loc}: value must be numeric")
            if field_data.get("resolution_status") == "resolved":
                if "pointer" not in field_data:
                    issues.append(f"{field_loc}: resolved field must include pointer")
                if "click_target" not in field_data:
                    issues.append(f"{field_loc}: resolved field must include click_target")

    return issues


def validate_task_manifest_data(data: Any, path: Path) -> list[str]:
    issues = _validate_root_shape(
        data,
        required={
            "task_id",
            "title",
            "kind",
            "validation_tier",
            "claimed_bl_status",
            "write_set",
        },
        allowed={
            "task_id",
            "title",
            "kind",
            "validation_tier",
            "claimed_bl_status",
            "references",
            "write_set",
            "blocked_surfaces",
            "notes",
        },
        path=path,
    )
    if not isinstance(data, dict):
        return issues

    for key in ("task_id", "title"):
        if not _is_non_empty_string(data.get(key)):
            issues.append(f"{path}: {key} must be a non-empty string")
    if data.get("kind") not in TASK_KINDS:
        issues.append(f"{path}: kind must be one of {sorted(TASK_KINDS)}")
    if data.get("validation_tier") not in VALIDATION_TIERS:
        issues.append(f"{path}: validation_tier must be one of {sorted(VALIDATION_TIERS)}")
    if data.get("claimed_bl_status") not in CLAIMED_BL_STATUSES:
        issues.append(f"{path}: claimed_bl_status must be one of {sorted(CLAIMED_BL_STATUSES)}")
    for key in ("references", "write_set", "blocked_surfaces"):
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or any(not _is_non_empty_string(item) for item in value):
            issues.append(f"{path}: {key} must be a list of non-empty strings")
    if not isinstance(data.get("write_set"), list) or not data["write_set"]:
        issues.append(f"{path}: write_set must be a non-empty list")
    if "notes" in data and not isinstance(data["notes"], str):
        issues.append(f"{path}: notes must be a string")

    return issues


def validate_curate_prompt_contract() -> list[str]:
    issues: list[str] = []
    text = PROMPT_PATH.read_text(encoding="utf-8")
    legacy_needles = (
        "deterministic/cases/${TICKER}",
        "deterministic/config/field_aliases.json",
        "python3 -m deterministic.cli eval ${TICKER}",
        "Los 22 campos canónicos",
        "22 campos canónicos",
        "restated_in_filing",
    )
    for needle in legacy_needles:
        if needle in text:
            issues.append(f"{PROMPT_PATH}: legacy marker still present: {needle}")

    required_needles = (
        "cases/${TICKER}/expected.json",
        "cases/${TICKER}/case.json",
        "config/field_aliases.json",
        "29 campos canónicos",
        "python3 -m elsian eval ${TICKER}",
        "evidence_filing",
    )
    for needle in required_needles:
        if needle not in text:
            issues.append(f"{PROMPT_PATH}: required marker missing: {needle}")

    return issues


def validate_case_model_alignment() -> list[str]:
    issues: list[str] = []
    model_fields = {field.name for field in dataclass_fields(CaseConfig)}
    for case_path in _read_git_tracked_paths("cases"):
        if case_path.name != "case.json":
            continue
        data = _load_json(case_path)
        case = CaseConfig.from_file(case_path.parent)
        if case.case_dir != str(case_path.parent):
            issues.append(f"{case_path}: CaseConfig.case_dir does not round-trip the case directory")
        for key, value in data.items():
            if key not in model_fields:
                issues.append(f"{case_path}: CaseConfig missing attribute for {key}")
                continue
            if getattr(case, key) != value:
                issues.append(
                    f"{case_path}: CaseConfig.{key} does not round-trip "
                    f"(expected {value!r}, got {getattr(case, key)!r})"
                )
        if case.extra:
            issues.append(f"{case_path}: CaseConfig.extra should be empty for tracked keys")
    return issues


VALIDATORS: dict[str, Callable[[Any, Path], list[str]]] = {
    "case": validate_case_data,
    "expected": validate_expected_data,
    "filings_manifest": validate_filings_manifest_data,
    "extraction_result": validate_extraction_result_data,
    "truth_pack": validate_truth_pack_data,
    "source_map": validate_source_map_data,
    "task_manifest": validate_task_manifest_data,
}


def validate_single_contract(schema_name: str, path: Path) -> list[str]:
    data = _load_json(path)
    return VALIDATORS[schema_name](data, path)


def validate_all_contracts() -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}

    for schema_name in _schema_names():
        try:
            _load_schema(schema_name)
        except Exception as exc:
            issues.setdefault(str(SCHEMAS_DIR / f"{schema_name}.schema.json"), []).append(
                f"schema file is not valid JSON: {exc}"
            )

    for artifact_path in _read_git_tracked_paths("cases"):
        schema_name = FILE_TO_SCHEMA.get(artifact_path.name)
        if schema_name is None:
            continue
        artifact_issues = validate_single_contract(schema_name, artifact_path)
        if artifact_issues:
            issues[str(artifact_path.relative_to(ROOT))] = artifact_issues

    prompt_issues = validate_curate_prompt_contract()
    if prompt_issues:
        issues[str(PROMPT_PATH.relative_to(ROOT))] = prompt_issues

    model_issues = validate_case_model_alignment()
    if model_issues:
        issues["CaseConfig"] = model_issues

    return issues


def _print_issues(issues: dict[str, list[str]]) -> None:
    for scope, scope_issues in sorted(issues.items()):
        print(f"[FAIL] {scope}")
        for issue in scope_issues:
            print(f"  - {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate versioned contracts for tracked artifacts.")
    parser.add_argument("--all", action="store_true", help="Validate all tracked contract-bearing artifacts.")
    parser.add_argument(
        "--schema",
        choices=sorted(VALIDATORS),
        help="Validate a single JSON payload against one contract.",
    )
    parser.add_argument(
        "--path",
        help="Path to the JSON file used with --schema.",
    )
    args = parser.parse_args(argv)

    if args.all == (args.schema is not None):
        parser.error("Choose either --all or --schema/--path.")
    if args.schema and not args.path:
        parser.error("--schema requires --path.")

    if args.all:
        issues = validate_all_contracts()
        if issues:
            _print_issues(issues)
            return 1
        tracked_cases = len([p for p in _read_git_tracked_paths("cases") if p.name == "case.json"])
        print(
            "PASS contracts: "
            f"{tracked_cases} tracked cases + tracked derived artifacts + prompt/model alignment"
        )
        return 0

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    issues = validate_single_contract(args.schema, path)
    if issues:
        for issue in issues:
            print(issue)
        return 1
    print(f"PASS {args.schema}: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
