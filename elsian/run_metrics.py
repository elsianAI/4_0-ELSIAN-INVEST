"""Narrow helper: serialize run_metrics.json per elsian run execution.

Scope (BL-068): collect structured runtime events from pipeline phase results
and write a single JSON artefact per run. No global logger, no framework,
no business logic, no side effects beyond writing the file.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from elsian.context import PipelineContext


def _build_acquire_aggregate(phase_result: Any) -> dict[str, Any]:
    """Extract acquire aggregates from AcquirePhase result.data if present."""
    data = phase_result.data  # AcquisitionResult or None
    if data is None:
        return {}
    return {
        "filings_downloaded": getattr(data, "filings_downloaded", 0),
        "filings_failed": getattr(data, "filings_failed", 0),
        "filings_coverage_pct": getattr(data, "filings_coverage_pct", 0.0),
        "cache_hit": getattr(data, "cache_hit", False),
        "retries_total": getattr(data, "retries_total", 0),
        "throttle_ms": getattr(data, "throttle_ms", 0.0),
        "gaps_count": len(getattr(data, "gaps", [])),
        "source_kind": getattr(data, "source_kind", ""),
    }


def build_run_metrics(
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    ticker: str,
    source_hint: str,
    with_acquire: bool,
    skip_assemble: bool,
    force: bool,
    context: "PipelineContext",
    eval_ok: bool | None,
) -> dict[str, Any]:
    """Build the run_metrics dict from completed pipeline results.

    Args:
        run_id: Unique identifier for this run (UUID4 string).
        started_at: ISO8601 UTC timestamp when the run started.
        finished_at: ISO8601 UTC timestamp when the run finished.
        ticker: Ticker symbol.
        source_hint: Source hint from case config.
        with_acquire: Whether AcquirePhase was included.
        skip_assemble: Whether AssemblePhase was skipped.
        force: Whether --force flag was set.
        context: Completed PipelineContext with phase_results populated.
        eval_ok: Whether evaluation passed (score == 100%).

    Returns:
        Dict suitable for JSON serialisation as run_metrics.json.
    """
    try:
        t_start = datetime.fromisoformat(started_at)
        t_end = datetime.fromisoformat(finished_at)
        duration_ms = (t_end - t_start).total_seconds() * 1000
    except Exception:
        duration_ms = 0.0

    phase_results = context.phase_results
    fatal = any(r.is_fatal for r in phase_results)

    # Final severity: worst across all phases
    severities = {r.severity for r in phase_results}
    if fatal or "fatal" in severities:
        final_severity = "fatal"
    elif "error" in severities:
        final_severity = "error"
    elif "warning" in severities:
        final_severity = "warning"
    else:
        final_severity = "ok"

    # Build phases list -- one entry per phase that ran
    phases: list[dict[str, Any]] = []
    for r in phase_results:
        phases.append({
            "name": r.phase_name,
            "severity": r.severity,
            "duration_ms": round(r.duration_ms, 3),
            "message": r.message,
            "diagnostics": r.diagnostics if r.diagnostics else {},
        })

    # Build aggregates -- only for phases that actually ran
    aggregates: dict[str, Any] = {}

    acquire_r = next(
        (r for r in phase_results if r.phase_name == "AcquirePhase"), None
    )
    if acquire_r is not None:
        aggregates["acquire"] = _build_acquire_aggregate(acquire_r)

    convert_r = next(
        (r for r in phase_results if r.phase_name == "ConvertPhase"), None
    )
    if convert_r is not None:
        d = convert_r.diagnostics or {}
        aggregates["convert"] = {
            "total": d.get("total", 0),
            "converted": d.get("converted", 0),
            "skipped": d.get("skipped", 0),
            "failed": d.get("failed", 0),
        }

    extract_r = next(
        (r for r in phase_results if r.phase_name == "ExtractPhase"), None
    )
    if extract_r is not None:
        d = extract_r.diagnostics or {}
        aggregates["extract"] = {
            "filings_used": d.get("filings_used", 0),
            "periods": d.get("periods", 0),
            "fields": d.get("fields", 0),
        }

    eval_r = next(
        (r for r in phase_results if r.phase_name == "EvaluatePhase"), None
    )
    if eval_r is not None:
        if eval_r.data is None and not eval_r.diagnostics:
            # EvaluatePhase ran but skipped (no expected.json): no data, no diagnostics
            aggregates["evaluate"] = {"skipped": True}
        else:
            d = eval_r.diagnostics or {}
            data = eval_r.data  # EvalReport or None
            aggregates["evaluate"] = {
                "skipped": False,
                "score": d.get("score", 0.0),
                "matched": d.get("matched", 0),
                "total_expected": d.get("total_expected", 0),
                "wrong": d.get("wrong", 0),
                "missed": d.get("missed", 0),
                "extra": d.get("extra", 0),
                "filings_coverage_pct": (
                    getattr(data, "filings_coverage_pct", 0.0) if data else 0.0
                ),
                "required_fields_coverage_pct": (
                    getattr(data, "required_fields_coverage_pct", 0.0) if data else 0.0
                ),
            }

    assemble_r = next(
        (r for r in phase_results if r.phase_name == "AssemblePhase"), None
    )
    if skip_assemble:
        aggregates["assemble"] = {"written": False, "skipped": True, "path": None}
    elif assemble_r is not None:
        d = assemble_r.diagnostics or {}
        is_ok = assemble_r.severity == "ok"
        aggregates["assemble"] = {
            "written": is_ok,
            "skipped": False,
            "path": d.get("truth_pack_path"),
        }
    else:
        aggregates["assemble"] = {"written": False, "skipped": False, "path": None}

    return {
        "schema_version": "run_metrics_v1",
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": round(duration_ms, 3),
        "ticker": ticker,
        "command": "run",
        "flags": {
            "with_acquire": with_acquire,
            "skip_assemble": skip_assemble,
            "force": force,
        },
        "source_hint": source_hint,
        "final_status": {
            "fatal": fatal,
            "eval_ok": eval_ok,
            "severity": final_severity,
        },
        "phases": phases,
        "aggregates": aggregates,
    }


def write_run_metrics(
    case_dir: Path,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    ticker: str,
    source_hint: str,
    with_acquire: bool,
    skip_assemble: bool,
    force: bool,
    context: "PipelineContext",
    eval_ok: bool | None,
) -> Path:
    """Build and write run_metrics.json to case_dir.

    Args:
        case_dir: Directory where run_metrics.json will be written.
        All other args: forwarded verbatim to build_run_metrics().

    Returns:
        Path to the written file.
    """
    metrics = build_run_metrics(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        ticker=ticker,
        source_hint=source_hint,
        with_acquire=with_acquire,
        skip_assemble=skip_assemble,
        force=force,
        context=context,
        eval_ok=eval_ok,
    )
    out = Path(case_dir) / "run_metrics.json"
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
