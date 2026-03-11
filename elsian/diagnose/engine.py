"""BL-069: Diagnose engine — aggregate gap patterns from existing artifacts.

Read-only. Consumes extraction_result.json + expected.json + case.json
(and optionally run_metrics.json) to produce a structured hotspot report
without re-running the extraction pipeline.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from elsian.evaluate.evaluator import evaluate
from elsian.models.field import FieldResult, Provenance
from elsian.models.result import ExtractionResult, PeriodResult

CASES_DIR_DEFAULT = Path(__file__).resolve().parent.parent.parent / "cases"


# ── Artifact loaders (read-only) ──────────────────────────────────────


def _load_extraction_result(case_dir: Path) -> ExtractionResult | None:
    """Load ExtractionResult from extraction_result.json, or None if absent."""
    path = case_dir / "extraction_result.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    result = ExtractionResult(
        schema_version=data.get("schema_version", "2.0"),
        ticker=data.get("ticker", ""),
        currency=data.get("currency", "USD"),
    )
    result.filings_used = data.get("filings_used", 0)
    for pk, pv in data.get("periods", {}).items():
        pr = PeriodResult(
            fecha_fin=pv.get("fecha_fin", ""),
            tipo_periodo=pv.get("tipo_periodo", ""),
        )
        for fname, fdata in pv.get("fields", {}).items():
            pr.fields[fname] = FieldResult(
                value=fdata.get("value", 0),
                provenance=Provenance(
                    source_filing=fdata.get("source_filing", ""),
                    source_location=fdata.get("source_location", ""),
                ),
                scale=fdata.get("scale", "raw"),
                confidence=fdata.get("confidence", "high"),
            )
        result.periods[pk] = pr
    return result


def _load_case_meta(case_dir: Path) -> dict[str, Any]:
    """Load minimal case metadata from case.json."""
    path = case_dir / "case.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_run_metrics(case_dir: Path) -> dict[str, Any] | None:
    """Load run_metrics.json if present, or None."""
    path = case_dir / "run_metrics.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ── Per-case evaluation ───────────────────────────────────────────────


def collect_case_eval(case_dir: Path) -> dict[str, Any] | None:
    """Evaluate one case and return a per-case summary dict.

    Returns None when the case has no expected.json (nothing to compare).
    Returns a dict with ``skipped=True`` when extraction_result.json is absent.

    Args:
        case_dir: Path to the case directory.

    Returns:
        Per-case summary dict, or None if evaluable data is missing.
    """
    ticker = case_dir.name
    expected_path = case_dir / "expected.json"
    if not expected_path.exists():
        return None

    case_meta = _load_case_meta(case_dir)
    source_hint = case_meta.get("source_hint", "")

    extraction = _load_extraction_result(case_dir)
    if extraction is None:
        return {
            "ticker": ticker,
            "skipped": True,
            "skip_reason": "no extraction_result.json",
            "source_hint": source_hint,
            "score": 0.0,
            "matched": 0,
            "wrong": 0,
            "missed": 0,
            "extra": 0,
            "total_expected": 0,
            "fatal": False,
            "details": [],
        }

    run_metrics = _load_run_metrics(case_dir)
    fatal = bool(
        run_metrics and run_metrics.get("final_status", {}).get("fatal", False)
    )

    report = evaluate(extraction, str(expected_path))

    details = [
        {
            "field": d.field_name,
            "period": d.period,
            "gap_type": d.status,  # "wrong" | "missed"
            "expected": d.expected,
            "actual": d.actual,
        }
        for d in report.details
        if d.status != "matched"
    ]

    return {
        "ticker": ticker,
        "skipped": False,
        "skip_reason": None,
        "source_hint": source_hint,
        "score": report.score,
        "matched": report.matched,
        "wrong": report.wrong,
        "missed": report.missed,
        "extra": report.extra,
        "total_expected": report.total_expected,
        "fatal": fatal,
        "details": details,
    }


# ── Aggregation ───────────────────────────────────────────────────────


def aggregate_hotspots(case_evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group wrong+missed entries by (field, gap_type) and rank by occurrences.

    Args:
        case_evals: List of per-case dicts from ``collect_case_eval``.

    Returns:
        Ranked list of hotspot dicts; highest occurrences first.
    """
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"occurrences": 0, "tickers": set(), "evidence": []}
    )

    for case in case_evals:
        if case.get("skipped"):
            continue
        for d in case.get("details", []):
            key = (d["field"], d["gap_type"])
            g = groups[key]
            g["occurrences"] += 1
            g["tickers"].add(case["ticker"])
            if len(g["evidence"]) < 3:  # cap evidence at 3 samples
                g["evidence"].append(
                    {
                        "ticker": case["ticker"],
                        "period": d["period"],
                        "expected": d["expected"],
                        "actual": d["actual"],
                    }
                )

    ranked = []
    for rank, ((field, gap_type), g) in enumerate(
        sorted(groups.items(), key=lambda x: -x[1]["occurrences"]), start=1
    ):
        ranked.append(
            {
                "rank": rank,
                "field": field,
                "gap_type": gap_type,
                "occurrences": g["occurrences"],
                "affected_tickers": sorted(g["tickers"]),
                "evidence": g["evidence"],
            }
        )

    return ranked


# ── Report builder ────────────────────────────────────────────────────


def build_report(cases_dir: Path | None = None) -> dict[str, Any]:
    """Walk all cases, collect evals, return structured diagnose report.

    Args:
        cases_dir: Root cases directory. Defaults to the canonical ``cases/``
            directory next to the ``elsian/`` package.

    Returns:
        Diagnose report dict (``schema_version: diagnose_v1``).
    """
    if cases_dir is None:
        cases_dir = CASES_DIR_DEFAULT

    case_evals: list[dict[str, Any]] = []
    for d in sorted(cases_dir.iterdir()):
        if not d.is_dir() or not (d / "case.json").exists():
            continue
        evaluated = collect_case_eval(d)
        if evaluated is not None:
            case_evals.append(evaluated)

    tickers_with_eval = [c for c in case_evals if not c.get("skipped")]
    tickers_skipped = [c for c in case_evals if c.get("skipped")]

    total_expected = sum(c["total_expected"] for c in tickers_with_eval)
    total_matched = sum(c["matched"] for c in tickers_with_eval)
    total_wrong = sum(c["wrong"] for c in tickers_with_eval)
    total_missed = sum(c["missed"] for c in tickers_with_eval)
    total_extra = sum(c["extra"] for c in tickers_with_eval)
    overall_score = (
        round(total_matched / total_expected * 100, 2) if total_expected else 0.0
    )

    hotspots = aggregate_hotspots(case_evals)

    by_ticker: dict[str, Any] = {
        c["ticker"]: {
            "score": c["score"],
            "matched": c["matched"],
            "total_expected": c["total_expected"],
            "wrong": c["wrong"],
            "missed": c["missed"],
            "extra": c["extra"],
            "source_hint": c["source_hint"],
            "skipped": c.get("skipped", False),
            "skip_reason": c.get("skip_reason"),
            "fatal": c.get("fatal", False),
        }
        for c in case_evals
    }

    by_source_acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "tickers": [],
            "total_wrong": 0,
            "total_missed": 0,
            "total_expected": 0,
            "total_matched": 0,
        }
    )
    for c in tickers_with_eval:
        sh = c["source_hint"] or "unknown"
        by_source_acc[sh]["tickers"].append(c["ticker"])
        by_source_acc[sh]["total_wrong"] += c["wrong"]
        by_source_acc[sh]["total_missed"] += c["missed"]
        by_source_acc[sh]["total_expected"] += c["total_expected"]
        by_source_acc[sh]["total_matched"] += c["matched"]

    by_source_hint: dict[str, Any] = {
        sh: {
            "tickers": sorted(data["tickers"]),
            "avg_score_pct": round(
                data["total_matched"] / data["total_expected"] * 100, 2
            )
            if data["total_expected"]
            else 0.0,
            "total_wrong": data["total_wrong"],
            "total_missed": data["total_missed"],
            "total_expected": data["total_expected"],
        }
        for sh, data in sorted(by_source_acc.items())
    }

    return {
        "schema_version": "diagnose_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases_dir": str(cases_dir),
        "summary": {
            "tickers_analyzed": len(case_evals),
            "tickers_with_eval": len(tickers_with_eval),
            "tickers_skipped": len(tickers_skipped),
            "total_expected": total_expected,
            "total_matched": total_matched,
            "total_wrong": total_wrong,
            "total_missed": total_missed,
            "total_extra": total_extra,
            "overall_score_pct": overall_score,
        },
        "hotspots": hotspots,
        "by_ticker": by_ticker,
        "by_source_hint": by_source_hint,
    }
