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

CASES_DIR_DEFAULT = Path(__file__).resolve().parent.parent.parent / "cases"

# ── Field category map ─────────────────────────────────────────────────────

_FIELD_CATEGORY: dict[str, str] = {
    # Income statement
    "ingresos": "income_statement",
    "cost_of_revenue": "income_statement",
    "gross_profit": "income_statement",
    "ebitda": "income_statement",
    "ebit": "income_statement",
    "net_income": "income_statement",
    "sga": "income_statement",
    "research_and_development": "income_statement",
    "depreciation_amortization": "income_statement",
    "interest_expense": "income_statement",
    "income_tax": "income_statement",
    # Per-share / equity units
    "eps_basic": "per_share",
    "eps_diluted": "per_share",
    "dividends_per_share": "per_share",
    "shares_outstanding": "per_share",
    # Balance sheet
    "total_assets": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "total_equity": "balance_sheet",
    "cash_and_equivalents": "balance_sheet",
    "total_debt": "balance_sheet",
    # Cash flow
    "cfo": "cash_flow",
    "capex": "cash_flow",
    "fcf": "cash_flow",
}


def field_category(field: str) -> str:
    """Return the diagnostic category for a canonical field name.

    Args:
        field: Canonical field name (from field_aliases.json).

    Returns:
        One of ``'income_statement'``, ``'per_share'``, ``'balance_sheet'``,
        ``'cash_flow'``, or ``'other'`` for unrecognised fields.
    """
    return _FIELD_CATEGORY.get(field, "other")


# ── Artifact loaders (read-only) ──────────────────────────────────────


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

    Re-extracts on the fly using the canonical ``ExtractPhase`` path (same as
    ``cmd_eval``). This guarantees that diagnose hotspots reflect the *current*
    extraction state, not a potentially stale persisted ``extraction_result.json``.

    Returns None when the case has no expected.json (nothing to compare).

    Args:
        case_dir: Path to the case directory.

    Returns:
        Per-case summary dict, or None if no expected.json is present.
    """
    ticker = case_dir.name
    expected_path = case_dir / "expected.json"
    if not expected_path.exists():
        return None

    case_meta = _load_case_meta(case_dir)
    source_hint = case_meta.get("source_hint", "")

    # Re-extract on-the-fly using the same path as cmd_eval.
    # Local import avoids circular dependency between diagnose and extract.
    from elsian.extract.phase import ExtractPhase  # noqa: PLC0415
    extraction = ExtractPhase().extract(str(case_dir))

    run_metrics = _load_run_metrics(case_dir)
    fatal = bool(
        run_metrics and run_metrics.get("final_status", {}).get("fatal", False)
    )

    report = evaluate(extraction, str(expected_path))

    # Load period metadata directly from expected.json for diagnostic clustering.
    expected_data = json.loads(expected_path.read_text(encoding="utf-8"))
    period_tipos: dict[str, str] = {
        pk: pv.get("tipo_periodo", "unknown")
        for pk, pv in expected_data.get("periods", {}).items()
    }
    period_expected_counts: dict[str, int] = {
        pk: len(pv.get("fields", {}))
        for pk, pv in expected_data.get("periods", {}).items()
    }

    # Pre-compute per-period miss count for period-mapping detection.
    period_miss_counts: dict[str, int] = defaultdict(int)
    for ev_detail in report.details:
        if ev_detail.status == "missed":
            period_miss_counts[ev_detail.period] += 1

    details = []
    for d in report.details:
        if d.status == "matched":
            continue
        p_expected = period_expected_counts.get(d.period, 0)
        p_missed = period_miss_counts.get(d.period, 0)
        period_miss_rate = p_missed / p_expected if p_expected > 0 else 0.0
        details.append(
            {
                "field": d.field_name,
                "period": d.period,
                "tipo_periodo": period_tipos.get(d.period, "unknown"),
                "gap_type": d.status,
                "expected": d.expected,
                "actual": d.actual,
                "period_miss_rate": round(period_miss_rate, 3),
            }
        )

    return {
        "ticker": ticker,
        "skipped": False,  # always False: we always re-extract on-the-fly
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


# ── Root-cause hint classifier ────────────────────────────────────────


def _classify_root_cause_hint(
    gap_type: str,
    evidence: list[dict[str, Any]],
    fatal_fraction: float,
    period_mapping_fraction: float,
) -> str:
    """Return a bounded root-cause hint label for a (field, gap_type) hotspot.

    Heuristic only — never claims certainty.  The hint is derived from
    observable ratios and upstream signals available in existing artifacts.

    Args:
        gap_type: ``'missed'`` or ``'wrong'``.
        evidence: Sample evidence dicts; each has ``'expected'`` and ``'actual'``.
        fatal_fraction: Fraction of occurrences where the ticker had a fatal
            upstream error (from ``run_metrics.json``).
        period_mapping_fraction: Fraction of occurrences where the period had
            a high overall miss rate (>50%), suggesting the period was not
            detected and all its fields were dropped.

    Returns:
        A short string label. For ``gap_type='missed'``: one of
        ``'fatal_upstream'``, ``'period_mapping_failure'``,
        ``'missing_extraction'``.  For ``gap_type='wrong'``: one of
        ``'scale_1k'``, ``'scale_001'``, ``'scale_100k'``, ``'scale_100'``,
        ``'sign_mismatch'``, ``'value_deviation'``.
    """
    if gap_type == "missed":
        if fatal_fraction >= 0.5:
            return "fatal_upstream"
        if period_mapping_fraction >= 0.6:
            return "period_mapping_failure"
        return "missing_extraction"

    # gap_type == "wrong": analyse actual/expected ratios across evidence.
    ratios: list[float] = []
    for ev in evidence:
        exp = ev.get("expected")
        act = ev.get("actual")
        if exp is not None and act is not None:
            try:
                exp_f = float(exp)
                if exp_f != 0.0:
                    ratios.append(float(act) / exp_f)
            except (TypeError, ValueError):
                pass

    if not ratios:
        return "value_deviation"

    # Use median so a single outlier sample doesn't dominate.
    median_ratio = sorted(ratios)[len(ratios) // 2]

    if 900.0 <= median_ratio <= 1100.0:
        return "scale_1k"
    if 0.0009 <= median_ratio <= 0.0011:
        return "scale_001"
    if 45000.0 <= median_ratio <= 110000.0:
        return "scale_100k"
    if 90.0 <= median_ratio <= 110.0:
        return "scale_100"
    if -1.05 <= median_ratio <= -0.95:
        return "sign_mismatch"
    return "value_deviation"


# ── Aggregation ───────────────────────────────────────────────────────


def aggregate_hotspots(case_evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group wrong+missed entries by (field, gap_type) and rank by occurrences.

    Also computes ``root_cause_hint`` and ``field_category`` per hotspot using
    observable patterns from the evidence.

    Args:
        case_evals: List of per-case dicts from ``collect_case_eval``.

    Returns:
        Ranked list of hotspot dicts; highest occurrences first.
    """
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "occurrences": 0,
            "tickers": set(),
            "evidence": [],
            "fatal_count": 0,
            "high_period_miss_count": 0,
        }
    )

    for case in case_evals:
        if case.get("skipped"):
            continue
        is_fatal = case.get("fatal", False)
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
            if is_fatal:
                g["fatal_count"] += 1
            # period_miss_rate > 0.5 → likely period was not mapped at all
            if d.get("period_miss_rate", 0.0) > 0.5:
                g["high_period_miss_count"] += 1

    ranked = []
    for rank, ((field, gap_type), g) in enumerate(
        sorted(groups.items(), key=lambda x: -x[1]["occurrences"]), start=1
    ):
        occ = g["occurrences"]
        fatal_frac = g["fatal_count"] / occ if occ > 0 else 0.0
        period_map_frac = g["high_period_miss_count"] / occ if occ > 0 else 0.0

        hint = _classify_root_cause_hint(
            gap_type=gap_type,
            evidence=g["evidence"],
            fatal_fraction=fatal_frac,
            period_mapping_fraction=period_map_frac,
        )

        ranked.append(
            {
                "rank": rank,
                "field": field,
                "field_category": field_category(field),
                "gap_type": gap_type,
                "occurrences": occ,
                "affected_tickers": sorted(g["tickers"]),
                "root_cause_hint": hint,
                "evidence": g["evidence"],
            }
        )

    return ranked


# ── Additional clustering axes ────────────────────────────────────────


def aggregate_by_period_type(case_evals: list[dict[str, Any]]) -> dict[str, Any]:
    """Group gap counts by period type (``'anual'``, ``'trimestral'``, etc.).

    Args:
        case_evals: List of per-case dicts from ``collect_case_eval``.

    Returns:
        Dict keyed by ``tipo_periodo`` value with occurrence counts and
        affected ticker lists, ordered by occurrence count descending.
    """
    acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"occurrences": 0, "wrong": 0, "missed": 0, "tickers": set()}
    )

    for case in case_evals:
        if case.get("skipped"):
            continue
        for d in case.get("details", []):
            tipo = d.get("tipo_periodo", "unknown")
            acc[tipo]["occurrences"] += 1
            if d["gap_type"] == "wrong":
                acc[tipo]["wrong"] += 1
            elif d["gap_type"] == "missed":
                acc[tipo]["missed"] += 1
            acc[tipo]["tickers"].add(case["ticker"])

    return {
        tipo: {
            "occurrences": data["occurrences"],
            "wrong": data["wrong"],
            "missed": data["missed"],
            "affected_tickers": sorted(data["tickers"]),
        }
        for tipo, data in sorted(acc.items(), key=lambda x: -x[1]["occurrences"])
    }


def aggregate_by_field_category(case_evals: list[dict[str, Any]]) -> dict[str, Any]:
    """Group gap counts by field category (income_statement, balance_sheet, …).

    Args:
        case_evals: List of per-case dicts from ``collect_case_eval``.

    Returns:
        Dict keyed by category with occurrence counts, ordered by occurrence
        count descending.
    """
    acc: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"occurrences": 0, "wrong": 0, "missed": 0, "fields": set()}
    )

    for case in case_evals:
        if case.get("skipped"):
            continue
        for d in case.get("details", []):
            cat = field_category(d["field"])
            acc[cat]["occurrences"] += 1
            if d["gap_type"] == "wrong":
                acc[cat]["wrong"] += 1
            elif d["gap_type"] == "missed":
                acc[cat]["missed"] += 1
            acc[cat]["fields"].add(d["field"])

    return {
        cat: {
            "occurrences": data["occurrences"],
            "wrong": data["wrong"],
            "missed": data["missed"],
            "fields_with_gaps": sorted(data["fields"]),
        }
        for cat, data in sorted(acc.items(), key=lambda x: -x[1]["occurrences"])
    }


def _build_root_cause_summary(hotspots: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate total gap occurrences by root-cause hint across all hotspots.

    Args:
        hotspots: Output of ``aggregate_hotspots``.

    Returns:
        Dict mapping hint label → total occurrence count, sorted descending.
    """
    hint_counts: dict[str, int] = defaultdict(int)
    for h in hotspots:
        hint = h.get("root_cause_hint", "unknown")
        hint_counts[hint] += h["occurrences"]
    return dict(sorted(hint_counts.items(), key=lambda x: -x[1]))


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
    by_period_type = aggregate_by_period_type(case_evals)
    by_field_category = aggregate_by_field_category(case_evals)
    root_cause_summary = _build_root_cause_summary(hotspots)

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
        "by_period_type": by_period_type,
        "by_field_category": by_field_category,
        "root_cause_summary": root_cause_summary,
    }
