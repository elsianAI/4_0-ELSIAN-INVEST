"""Scaffolding helper for ELSIAN 4.0 — BL-071.

Generates minimum seeds for:
- Tasks: ``tasks/{TASK_ID}.task_manifest.json`` + ``tasks/{TASK_ID}.task_notes.md``
- Cases: ``cases/{TICKER}/case.json`` + ``cases/{TICKER}/CASE_NOTES.md``

Both flows enforce declaration of ``risks``, ``validation_plan``, and
``acceptance_criteria`` at seed creation time so those fields are never left
implicit.

Not a generic template engine.  Scope: Module 1 tasks and cases only.
No LLM calls, no network calls, no imports from ``engine/`` or ``scripts/``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
CASES_DIR = ROOT / "cases"

# Allowed enum values — must stay in sync with task_manifest.schema.json
TASK_KINDS = ("technical", "governance", "mixed")
VALIDATION_TIERS = ("targeted", "shared-core", "governance-only")
PERIOD_SCOPES = ("FULL",)


# ---------------------------------------------------------------------------
# Task scaffolding
# ---------------------------------------------------------------------------


def build_task_seed(
    *,
    task_id: str,
    title: str,
    kind: str,
    validation_tier: str,
    write_set: list[str],
    risks: list[str],
    validation_plan: str,
    acceptance_criteria: str,
    references: list[str] | None = None,
    blocked_surfaces: list[str] | None = None,
    expected_governance_updates: list[str] | str | None = None,
    notes: str = "",
) -> tuple[dict[str, Any], str]:
    """Return (manifest_dict, notes_md).

    ``manifest_dict`` is schema-conformant (``task_manifest.schema.json``).
    ``notes_md`` is a companion Markdown for human operators.

    Raises:
        ValueError: if any mandatory field is missing or invalid.
    """
    if not task_id or not task_id.strip():
        raise ValueError("task_id must be a non-empty string")
    if not title or not title.strip():
        raise ValueError("title must be a non-empty string")
    if kind not in TASK_KINDS:
        raise ValueError(f"kind must be one of {TASK_KINDS}")
    if validation_tier not in VALIDATION_TIERS:
        raise ValueError(f"validation_tier must be one of {VALIDATION_TIERS}")
    if not write_set:
        raise ValueError("write_set must contain at least one entry")
    if not risks:
        raise ValueError("risks must declare at least one risk (cannot be empty)")
    if not validation_plan or not validation_plan.strip():
        raise ValueError("validation_plan must be a non-empty string")
    if not acceptance_criteria or not acceptance_criteria.strip():
        raise ValueError("acceptance_criteria must be a non-empty string")

    # Embed risks / validation_plan / acceptance_criteria in the `notes` field
    # (the only free-text field the schema allows — additionalProperties: false).
    meta_note = (
        f"RISKS: {'; '.join(risks)} | "
        f"VALIDATION: {validation_plan} | "
        f"ACCEPTANCE: {acceptance_criteria}"
    )
    combined_notes = f"{notes} | {meta_note}" if notes else meta_note

    manifest: dict[str, Any] = {
        "task_id": task_id,
        "title": title,
        "kind": kind,
        "validation_tier": validation_tier,
        "claimed_bl_status": "none",
        "write_set": write_set,
        "notes": combined_notes,
    }
    if references:
        manifest["references"] = references
    if blocked_surfaces:
        manifest["blocked_surfaces"] = blocked_surfaces
    if expected_governance_updates is not None:
        manifest["expected_governance_updates"] = expected_governance_updates

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    risks_lines = "\n".join(f"- {r}" for r in risks)
    write_set_lines = "\n".join(f"- {p}" for p in write_set)
    notes_md = (
        f"# {task_id} — Task Notes\n\n"
        f"**Title:** {title}  \n"
        f"**Kind:** {kind}  \n"
        f"**Validation tier:** {validation_tier}  \n"
        f"**Generated:** {now}\n\n"
        f"## Risks\n\n{risks_lines}\n\n"
        f"## Validation Plan\n\n{validation_plan}\n\n"
        f"## Acceptance Criteria\n\n{acceptance_criteria}\n\n"
        f"## Write Set\n\n{write_set_lines}\n"
    )

    return manifest, notes_md


def write_task_seed(
    *,
    task_id: str,
    title: str,
    kind: str,
    validation_tier: str,
    write_set: list[str],
    risks: list[str],
    validation_plan: str,
    acceptance_criteria: str,
    references: list[str] | None = None,
    blocked_surfaces: list[str] | None = None,
    expected_governance_updates: list[str] | str | None = None,
    notes: str = "",
    output_dir: Path | None = None,
    force: bool = False,
) -> tuple[Path, Path]:
    """Write task manifest JSON and companion notes Markdown.

    Returns:
        ``(manifest_path, notes_path)`` — absolute paths written.

    Raises:
        FileExistsError: if manifest exists and ``force=False``.
        ValueError: propagated from :func:`build_task_seed`.
    """
    out_dir = output_dir or TASKS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / f"{task_id}.task_manifest.json"
    notes_path = out_dir / f"{task_id}.task_notes.md"

    if manifest_path.exists() and not force:
        raise FileExistsError(
            f"{manifest_path} already exists.  Use --force to overwrite."
        )

    manifest, notes_md = build_task_seed(
        task_id=task_id,
        title=title,
        kind=kind,
        validation_tier=validation_tier,
        write_set=write_set,
        risks=risks,
        validation_plan=validation_plan,
        acceptance_criteria=acceptance_criteria,
        references=references,
        blocked_surfaces=blocked_surfaces,
        expected_governance_updates=expected_governance_updates,
        notes=notes,
    )

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    notes_path.write_text(notes_md, encoding="utf-8")

    return manifest_path, notes_path


# ---------------------------------------------------------------------------
# Case scaffolding
# ---------------------------------------------------------------------------


def build_case_seed(
    *,
    ticker: str,
    source_hint: str,
    currency: str,
    period_scope: str = "FULL",
    exchange: str | None = None,
    country: str | None = None,
    cik: str | None = None,
    fiscal_year_end_month: int | None = None,
    notes: str = "",
) -> tuple[dict[str, Any], str]:
    """Return (case_dict, notes_md).

    ``case_dict`` is schema-conformant (``case.schema.json`` /
    ``validate_contracts.py::validate_case_data``).
    ``notes_md`` is a companion Markdown with TODO checklist, risks, and
    acceptance criteria.

    Raises:
        ValueError: if any mandatory field is missing or invalid.
    """
    if not ticker or not ticker.strip():
        raise ValueError("ticker must be a non-empty string")
    if not source_hint or not source_hint.strip():
        raise ValueError("source_hint must be a non-empty string")
    if not currency or not currency.strip():
        raise ValueError("currency must be a non-empty string")
    if period_scope not in PERIOD_SCOPES:
        raise ValueError(f"period_scope must be one of {PERIOD_SCOPES}")

    ticker_upper = ticker.strip().upper()

    case: dict[str, Any] = {
        "ticker": ticker_upper,
        "exchange": exchange,
        "country": country,
        "currency": currency.strip().upper(),
        "cik": cik,
        "source_hint": source_hint.strip().lower(),
        "period_scope": period_scope,
        "filings_expected_count": None,
        "notes": notes or (
            f"[scaffold] {ticker_upper} seed — review CASE_NOTES.md before acquire."
        ),
    }
    if fiscal_year_end_month is not None:
        case["fiscal_year_end_month"] = fiscal_year_end_month

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notes_md = (
        f"# {ticker_upper} — Case Notes\n\n"
        f"**Generated:** {now}  \n"
        f"**Source hint:** {source_hint.strip().lower()}  \n"
        f"**Currency:** {currency.strip().upper()}  \n"
        f"**Period scope:** {period_scope}\n\n"
        "## TODO before acquire\n\n"
        "- [ ] Verify exchange / country in case.json\n"
        "- [ ] Verify CIK (for SEC) or equivalent regulator identifier\n"
        "- [ ] Verify fiscal_year_end_month (default = 12 for Dec-31 FY)\n"
        "- [ ] Set filings_expected_count in case.json\n"
        "- [ ] Verify period_scope is FULL (DEC-031: ANNUAL_ONLY eliminated)\n\n"
        "## Risks\n\n"
        "- [ ] Non-standard fiscal year may require period labeling adjustments\n"
        "- [ ] Currency / scale ambiguity in filings (thousands vs millions)\n"
        "- [ ] Filing format may differ from reference tickers (HTML vs PDF vs iXBRL)\n"
        "- [ ] Source may be unavailable or rate-limited\n\n"
        "## Acceptance Criteria\n\n"
        f"- [ ] Run: elsian acquire {ticker_upper} (exits 0 without gaps)\n"
        f"- [ ] Run: elsian run {ticker_upper} --skip-assemble (exits 0)\n"
        "- [ ] Score >= 85% on first curated expected.json\n\n"
        "## Source Notes\n\n"
        "_Add filing URL, regulator page, or reference ticker here._\n"
    )

    return case, notes_md


def write_case_seed(
    *,
    ticker: str,
    source_hint: str,
    currency: str,
    period_scope: str = "FULL",
    exchange: str | None = None,
    country: str | None = None,
    cik: str | None = None,
    fiscal_year_end_month: int | None = None,
    notes: str = "",
    output_dir: Path | None = None,
    force: bool = False,
) -> tuple[Path, Path]:
    """Write case.json and CASE_NOTES.md for a new ticker.

    Args:
        output_dir: Parent dir to write ``<TICKER>/`` under (default: ``cases/``).
        force: Overwrite existing ``case.json`` without error.

    Returns:
        ``(case_json_path, notes_md_path)`` — absolute paths written.

    Raises:
        FileExistsError: if ``case.json`` exists and ``force=False``.
        ValueError: propagated from :func:`build_case_seed`.
    """
    ticker_upper = ticker.strip().upper()
    case_dir = (output_dir or CASES_DIR) / ticker_upper
    case_dir.mkdir(parents=True, exist_ok=True)

    case_json_path = case_dir / "case.json"
    notes_md_path = case_dir / "CASE_NOTES.md"

    if case_json_path.exists() and not force:
        raise FileExistsError(
            f"{case_json_path} already exists.  Use --force to overwrite."
        )

    case, notes_md = build_case_seed(
        ticker=ticker,
        source_hint=source_hint,
        currency=currency,
        period_scope=period_scope,
        exchange=exchange,
        country=country,
        cik=cik,
        fiscal_year_end_month=fiscal_year_end_month,
        notes=notes,
    )

    case_json_path.write_text(
        json.dumps(case, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    notes_md_path.write_text(notes_md, encoding="utf-8")

    return case_json_path, notes_md_path
