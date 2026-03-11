"""Onboarding helper for ELSIAN 4.0 — development/QA entrypoint.

Composes discover -> acquire -> convert -> preflight -> draft steps using
existing project pieces.  This is NOT a PipelinePhase; it is a narrow
helper designed for development and QA use only.

No new PipelinePhase, no new service layer, no ``elsian run`` wrapping.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"

# Status literals
StepStatus = str  # "ok" | "warning" | "skipped" | "fatal"


# ── Internal builders ─────────────────────────────────────────────────


def _step_result(
    status: StepStatus,
    evidence: dict[str, Any] | None = None,
    gaps: list[str] | None = None,
    next_step_override: str | None = None,
) -> dict[str, Any]:
    """Build a step result dict with only populated keys."""
    r: dict[str, Any] = {"status": status}
    if evidence:
        r["evidence"] = evidence
    if gaps:
        r["gaps"] = gaps
    if next_step_override:
        r["next_step_override"] = next_step_override
    return r


# ── Step runners ──────────────────────────────────────────────────────


def _run_discover_step(
    ticker: str,
    case_dir: Path,
    allow_network: bool,
) -> dict[str, Any]:
    """Discover step: reuse existing case.json or run discovery."""
    case_file = case_dir / "case.json"

    if case_file.exists():
        try:
            data = json.loads(case_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return _step_result(
                "fatal",
                evidence={"error": f"case.json unreadable: {exc}"},
                gaps=["case.json exists but cannot be parsed"],
            )
        return _step_result(
            "ok",
            evidence={
                "reused_existing_case": True,
                "source_hint": data.get("source_hint"),
                "exchange": data.get("exchange"),
                "currency": data.get("currency"),
                "period_scope": data.get("period_scope"),
            },
        )

    if not allow_network:
        return _step_result(
            "skipped",
            evidence={"reason": "no case.json and network not allowed (default)"},
            gaps=["case.json missing -- run `elsian discover TICKER` or create manually"],
            next_step_override="Run `elsian discover TICKER` to auto-generate case.json",
        )

    # Network path: run TickerDiscoverer
    try:
        from elsian.discover.discover import TickerDiscoverer, parse_ticker_suffix

        discoverer = TickerDiscoverer()
        result = discoverer.discover(ticker)
        base_ticker, _ = parse_ticker_suffix(ticker)
        target_dir = CASES_DIR / base_ticker.upper()
        target_dir.mkdir(parents=True, exist_ok=True)
        case_dict = result.to_case_dict()
        (target_dir / "case.json").write_text(
            json.dumps(case_dict, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        gaps = [f"discovery_warning: {w}" for w in result.warnings]
        return _step_result(
            "warning" if gaps else "ok",
            evidence={
                "reused_existing_case": False,
                "source_hint": result.source_hint,
                "exchange": result.exchange,
                "currency": result.currency,
                "period_scope": result.period_scope,
            },
            gaps=gaps if gaps else None,
        )
    except Exception as exc:
        logger.warning("discover step error: %s", exc)
        return _step_result(
            "fatal",
            evidence={"error": str(exc)},
            gaps=["discover failed -- create case.json manually"],
        )


def _run_acquire_step(case: Any, case_dir: Path) -> dict[str, Any]:
    """Acquire step: call fetcher.acquire() and capture metrics/gaps."""
    try:
        from elsian.acquire.registry import get_fetcher

        fetcher = get_fetcher(case)
        if not hasattr(fetcher, "acquire"):
            return _step_result(
                "warning",
                evidence={
                    "reason": (
                        f"fetcher {type(fetcher).__name__} has no acquire() method"
                    )
                },
                gaps=["fetcher does not support acquire(); add filings manually"],
            )
        result = fetcher.acquire(case)
        manifest_path = case_dir / "filings_manifest.json"
        manifest_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return _step_result(
            "warning" if result.gaps else "ok",
            evidence={
                "filings_downloaded": result.filings_downloaded,
                "source": result.source,
                "coverage_pct": result.filings_coverage_pct,
            },
            gaps=list(result.gaps) if result.gaps else None,
        )
    except Exception as exc:
        logger.warning("acquire step error: %s", exc)
        return _step_result(
            "fatal",
            evidence={"error": str(exc)},
            gaps=["acquire failed"],
        )


def _run_convert_step(case_dir: Path, force: bool = False) -> dict[str, Any]:
    """Convert step: transform raw filings (.htm/.pdf) to clean text.

    Reuses ``elsian.convert`` converters directly — no second implementation.
    """
    from elsian.convert.html_to_markdown import convert as _html_to_md
    from elsian.convert.pdf_to_text import extract_pdf_text

    filings_dir = case_dir / "filings"
    if not filings_dir.exists():
        return _step_result(
            "skipped",
            evidence={"reason": "no filings/ directory"},
            gaps=["no filings to convert -- run acquire first"],
        )

    converted = skipped = failed = total = 0

    for filing_path in sorted(filings_dir.iterdir()):
        if not filing_path.is_file():
            continue
        suffix = filing_path.suffix.lower()

        if suffix == ".htm":
            total += 1
            out_path = filings_dir / f"{filing_path.stem}.clean.md"
            if out_path.exists() and not force:
                skipped += 1
                continue
            try:
                clean_md = _html_to_md(filing_path)
                if clean_md:
                    out_path.write_text(clean_md, encoding="utf-8")
                    converted += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.warning("Convert failed %s: %s", filing_path.name, exc)
                failed += 1

        elif suffix == ".pdf":
            total += 1
            out_path = filings_dir / f"{filing_path.stem}.txt"
            if out_path.exists() and not force:
                skipped += 1
                continue
            try:
                content = filing_path.read_bytes()
                text = extract_pdf_text(content)
                out_path.write_text(text, encoding="utf-8")
                converted += 1
            except Exception as exc:
                logger.warning("Convert failed %s: %s", filing_path.name, exc)
                failed += 1

    if total == 0:
        return _step_result(
            "skipped",
            evidence={"total": 0, "converted": 0, "skipped": 0, "failed": 0},
            gaps=["no .htm or .pdf filings found -- run acquire first"],
        )

    if failed == total:
        status: StepStatus = "fatal"
    elif failed > 0:
        status = "warning"
    else:
        status = "ok"

    return _step_result(
        status,
        evidence={"total": total, "converted": converted, "skipped": skipped, "failed": failed},
        gaps=[f"{failed} filing(s) failed to convert"] if failed else None,
    )


def _run_preflight_step(case_dir: Path) -> dict[str, Any]:
    """Preflight step: run preflight diagnostics on first converted filing."""
    from elsian.analyze.preflight import preflight as _preflight

    filings_dir = case_dir / "filings"
    if not filings_dir.exists():
        return _step_result(
            "skipped",
            evidence={"reason": "no filings/ directory"},
        )

    candidates = sorted(filings_dir.glob("*.clean.md")) + sorted(filings_dir.glob("*.txt"))
    if not candidates:
        return _step_result(
            "skipped",
            evidence={"reason": "no converted filings (.clean.md or .txt) found"},
            gaps=["run convert step first"],
        )

    first = candidates[0]
    try:
        text = first.read_text(encoding="utf-8", errors="replace")
        pf = _preflight(text)
        pf_dict = pf.to_dict()
    except Exception as exc:
        return _step_result(
            "warning",
            evidence={"sampled_file": first.name, "error": str(exc)},
            gaps=["preflight analysis failed on sampled file"],
        )

    gaps: list[str] = []
    if not pf_dict.get("language"):
        gaps.append("language not detected")
    if not pf_dict.get("accounting_standard"):
        gaps.append("accounting_standard not detected")
    if not pf_dict.get("currency"):
        gaps.append("currency not detected")

    evidence: dict[str, Any] = {
        "sampled_file": first.name,
        "total_converted": len(candidates),
    }
    for key in ("language", "accounting_standard", "currency", "sections_detected"):
        val = pf_dict.get(key)
        if val:
            evidence[key] = val

    return _step_result(
        "warning" if gaps else "ok",
        evidence=evidence,
        gaps=gaps if gaps else None,
    )


def _run_draft_step(case: Any, case_dir: Path) -> dict[str, Any]:
    """Draft step: generate expected_draft.json via curate helpers."""
    from elsian.extract.phase import ExtractPhase
    from elsian.curate_draft import (
        build_expected_draft_from_extraction,
        compare_draft_vs_expected,
    )

    filings_dir = case_dir / "filings"
    has_converted = filings_dir.exists() and (
        any(filings_dir.glob("*.clean.md")) or any(filings_dir.glob("*.txt"))
    )
    if not has_converted:
        return _step_result(
            "skipped",
            evidence={"reason": "no converted filings"},
            gaps=["run convert step first"],
        )

    try:
        phase = ExtractPhase()
        result = phase.extract(str(case_dir))
    except Exception as exc:
        logger.warning("draft/extract error: %s", exc)
        return _step_result(
            "fatal",
            evidence={"error": str(exc)},
            gaps=["extraction failed; cannot generate draft"],
        )

    expected_path = case_dir / "expected.json"
    expected: dict[str, Any] | None = None
    if expected_path.exists():
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        draft = build_expected_draft_from_extraction(
            result,
            ticker=case.ticker or case_dir.name,
            currency=getattr(result, "currency", None) or getattr(case, "currency", "USD"),
            expected=expected,
        )
    except Exception as exc:
        logger.warning("draft build error: %s", exc)
        return _step_result(
            "fatal",
            evidence={"error": str(exc)},
            gaps=["draft build failed"],
        )

    out_path = case_dir / "expected_draft.json"
    out_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")

    periods = draft.get("periods", {})
    total_missing = sum(
        len(pdata.get("_gaps", {}).get("missing_canonicals", []))
        for pdata in periods.values()
    )
    validation = draft.get("_validation") or {}

    evidence: dict[str, Any] = {
        "periods": len(periods),
        "draft_path": str(out_path),
    }
    if validation:
        evidence["validation_status"] = validation.get("status")
        evidence["confidence_score"] = validation.get("confidence_score")

    if expected is not None:
        comparison = compare_draft_vs_expected(draft, expected)
        evidence["vs_expected"] = {
            "coverage_pct": comparison.get("coverage_pct"),
            "value_match_pct": comparison.get("value_match_pct"),
        }

    gaps: list[str] = []
    if total_missing:
        n_periods = sum(
            1
            for pdata in periods.values()
            if pdata.get("_gaps", {}).get("missing_canonicals")
        )
        gaps.append(
            f"{total_missing} canonical field(s) not auto-populated "
            f"across {n_periods} period(s)"
        )
    for w in validation.get("warnings", []):
        gaps.append(str(w))

    draft_status: StepStatus = "ok" if not gaps else "warning"
    return _step_result(draft_status, evidence=evidence, gaps=gaps if gaps else None)


# ── Overall classification ────────────────────────────────────────────


def _classify_overall(
    steps: dict[str, dict[str, Any]],
) -> tuple[str, list[str], list[str], str]:
    """Derive overall_status, blockers, warnings, and next_step from step results.

    Returns:
        (overall_status, blockers, warnings, next_step)
    """
    statuses = [s["status"] for s in steps.values()]
    blockers: list[str] = []
    warnings_list: list[str] = []

    if "fatal" in statuses:
        overall = "fatal"
    elif "warning" in statuses:
        overall = "warning"
    elif all(s in ("ok", "skipped") for s in statuses):
        overall = "ok" if "ok" in statuses else "skipped"
    else:
        overall = "warning"

    for step_name, step_data in steps.items():
        if step_data["status"] == "fatal":
            err = (step_data.get("evidence") or {}).get("error", "fatal error")
            blockers.append(f"{step_name}: {err}")
        for gap in step_data.get("gaps") or []:
            target = blockers if step_data["status"] == "fatal" else warnings_list
            target.append(f"{step_name}: {gap}")

    # Determine next step hint
    if overall == "ok":
        next_step = "Review expected_draft.json and promote to expected.json"
    elif "discover" in steps and steps["discover"]["status"] in ("fatal", "skipped"):
        next_step = "Create case.json -- run `elsian discover TICKER`"
    elif "acquire" in steps and steps["acquire"]["status"] == "fatal":
        next_step = "Fix acquire errors and re-run with --with-acquire"
    elif "convert" in steps and steps["convert"]["status"] == "fatal":
        next_step = "Check convert failures; inspect filings/ for corrupt files"
    elif "convert" in steps and steps["convert"]["status"] == "warning":
        next_step = "Re-run with --force to retry failed conversions"
    elif "draft" in steps and steps["draft"]["status"] != "ok":
        next_step = "Review draft gaps before promoting to expected.json"
    else:
        next_step = "Review warnings before continuing"

    return overall, blockers, warnings_list, next_step


# ── Public API ────────────────────────────────────────────────────────


def run_onboarding(
    ticker: str,
    *,
    case_dir: Path | None = None,
    with_acquire: bool = False,
    force_convert: bool = False,
    allow_network_discover: bool = False,
) -> dict[str, Any]:
    """Run the onboarding sequence for a ticker.

    Composes: discover -> [acquire] -> convert -> preflight -> draft.

    Args:
        ticker: Ticker symbol (e.g. "TZOO", "KAR", "KAR.AX").
        case_dir: Override for the case directory. Defaults to
            ``cases/<BASE_TICKER>/``.
        with_acquire: Run the acquire step (requires network).
        force_convert: Re-convert even if .clean.md already exists.
        allow_network_discover: Allow network calls when no case.json found.

    Returns:
        Dict with keys: original_ticker, canonical_ticker, case_dir,
        steps, summary.
    """
    from elsian.models.case import CaseConfig
    from elsian.discover.discover import parse_ticker_suffix

    base_ticker, _suffix = parse_ticker_suffix(ticker)
    canonical_ticker = base_ticker.upper()

    effective_case_dir = case_dir if case_dir is not None else CASES_DIR / canonical_ticker

    steps: dict[str, dict[str, Any]] = {}

    # ── Discover ─────────────────────────────────────────────────────
    steps["discover"] = _run_discover_step(
        ticker, effective_case_dir, allow_network=allow_network_discover
    )

    # Abort early if discover was fatal (e.g. corrupt / unreadable case.json) or
    # the file is simply missing.  Both conditions mean CaseConfig.from_file cannot
    # run safely — and subsequent steps have no basis to proceed.
    if steps["discover"]["status"] == "fatal" or not (effective_case_dir / "case.json").exists():
        overall, blockers, warnings_list, next_step = _classify_overall(steps)
        return _build_report(ticker, canonical_ticker, effective_case_dir, steps, overall, blockers, warnings_list, next_step)

    case = CaseConfig.from_file(effective_case_dir)
    if case.ticker:
        canonical_ticker = case.ticker

    # ── Acquire (optional) ──────────────────────────────────────────
    if with_acquire:
        steps["acquire"] = _run_acquire_step(case, effective_case_dir)
        if steps["acquire"]["status"] == "fatal":
            overall, blockers, warnings_list, next_step = _classify_overall(steps)
            return _build_report(ticker, canonical_ticker, effective_case_dir, steps, overall, blockers, warnings_list, next_step)

    # ── Convert ──────────────────────────────────────────────────────
    steps["convert"] = _run_convert_step(effective_case_dir, force=force_convert)

    # Abort if convert is fatal: preflight and draft would silently consume stale
    # artefacts from a previous run, producing misleading results.
    if steps["convert"]["status"] == "fatal":
        overall, blockers, warnings_list, next_step = _classify_overall(steps)
        return _build_report(ticker, canonical_ticker, effective_case_dir, steps, overall, blockers, warnings_list, next_step)

    # ── Preflight ────────────────────────────────────────────────────
    steps["preflight"] = _run_preflight_step(effective_case_dir)

    # ── Draft ────────────────────────────────────────────────────────
    steps["draft"] = _run_draft_step(case, effective_case_dir)

    # ── Summary ──────────────────────────────────────────────────────
    overall, blockers, warnings_list, next_step = _classify_overall(steps)  # type: ignore[assignment]
    return _build_report(ticker, canonical_ticker, effective_case_dir, steps, overall, blockers, warnings_list, next_step)


def _build_report(
    original_ticker: str,
    canonical_ticker: str,
    case_dir: Path,
    steps: dict[str, dict[str, Any]],
    overall: str,
    blockers: list[str],
    warnings_list: list[str],
    next_step: str,
) -> dict[str, Any]:
    """Pack results into the canonical report structure."""
    return {
        "original_ticker": original_ticker,
        "canonical_ticker": canonical_ticker,
        "case_dir": str(case_dir),
        "steps": steps,
        "summary": {
            "overall_status": overall,
            "blockers": blockers,
            "warnings": warnings_list,
            "next_step": next_step,
        },
    }


def render_report_md(report: dict[str, Any]) -> str:
    """Render an onboarding report as human-readable Markdown."""
    ticker = report.get("canonical_ticker", "UNKNOWN")
    lines = [
        f"# Onboarding Report — {ticker}",
        "",
        f"- **Original ticker:** {report.get('original_ticker', ticker)}",
        f"- **Case directory:** {report.get('case_dir', '')}",
        "",
        "## Summary",
    ]
    summary = report.get("summary", {})
    lines.append(f"- **Overall status:** {summary.get('overall_status', 'unknown').upper()}")
    lines.append(f"- **Next step:** {summary.get('next_step', '')}")
    if summary.get("blockers"):
        lines.extend(["", "### Blockers"])
        for b in summary["blockers"]:
            lines.append(f"- {b}")
    if summary.get("warnings"):
        lines.extend(["", "### Warnings"])
        for w in summary["warnings"]:
            lines.append(f"- {w}")
    lines.extend(["", "## Steps"])
    for step_name, step_data in report.get("steps", {}).items():
        status = step_data.get("status", "unknown").upper()
        lines.append("")
        lines.append(f"### {step_name} — {status}")
        for k, v in (step_data.get("evidence") or {}).items():
            lines.append(f"- {k}: {v}")
        if step_data.get("gaps"):
            lines.append("**Gaps:**")
            for g in step_data["gaps"]:
                lines.append(f"- {g}")
        if step_data.get("next_step_override"):
            lines.append(f"**Next:** {step_data['next_step_override']}")
    return "\n".join(lines) + "\n"
