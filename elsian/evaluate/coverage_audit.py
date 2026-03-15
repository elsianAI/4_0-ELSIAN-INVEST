"""Coverage audit for ELSIAN 4.0 cases.

Evaluates whether each case has enough filings for reliable extraction.
Classifies issuers into Domestic_US, FPI_ADR, or NonUS_Local and
checks filing counts against per-class thresholds.

Adapted from 3.0 scripts/runners/prefetch_coverage_audit.py.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

SEC_SOURCE_HINTS: frozenset = frozenset({"sec", "sec_edgar"})
NON_US_SOURCE_HINTS: frozenset = frozenset(
    {"asx", "eu_manual", "manual_http", "edinet", "manual"}
)
US_COUNTRIES: frozenset = frozenset({"US", "USA"})
THRESHOLDS: dict = {
    "Domestic_US": {"annual_min": 3, "total_min": 10},
    "FPI_ADR":     {"annual_min": 2, "total_min": 5},
    "NonUS_Local": {"total_min": 1},
}


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _jread(path: Path) -> dict | None:
    """Read and parse a JSON file. Returns None on any error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def issuer_class(
    source_hint: str,
    country: str | None,
    cik: str | None,
) -> str:
    """Classify an issuer as Domestic_US, FPI_ADR, or NonUS_Local.

    Args:
        source_hint: Fetcher hint from case.json (e.g. 'sec', 'asx').
        country: Country code from case.json (e.g. 'US', 'IL', 'KY').
        cik: SEC CIK from case.json or manifest; None for non-SEC filers.

    Returns:
        One of 'Domestic_US', 'FPI_ADR', 'NonUS_Local'.
    """
    hint = (source_hint or "").lower().strip()
    country_upper = (country or "").upper().strip()

    # Explicit non-US source hint → always NonUS_Local
    if hint in NON_US_SOURCE_HINTS:
        return "NonUS_Local"

    # SEC filer (hint or CIK present)
    if hint in SEC_SOURCE_HINTS or cik:
        if country_upper and country_upper not in US_COUNTRIES:
            return "FPI_ADR"
        return "Domestic_US"

    # Unknown source hint with no CIK → NonUS_Local
    return "NonUS_Local"


def _extract_filing_metrics(manifest: dict | None) -> dict:
    """Extract normalised filing counts from filings_manifest.json.

    Args:
        manifest: Parsed filings_manifest.json dict, or None if missing.

    Returns:
        Dict with keys: total, annual, quarterly, earnings, failed.
    """
    if not manifest:
        return {"total": 0, "annual": 0, "quarterly": 0, "earnings": 0, "failed": 0}
    cov = manifest.get("coverage") or {}
    a = cov.get("annual") or {}
    q = cov.get("quarterly") or {}
    e = cov.get("earnings") or {}
    return {
        "total":     int(manifest.get("filings_downloaded", 0)),
        "annual":    int(a.get("downloaded", 0)) if isinstance(a, dict) else 0,
        "quarterly": int(q.get("downloaded", 0)) if isinstance(q, dict) else 0,
        "earnings":  int(e.get("downloaded", 0)) if isinstance(e, dict) else 0,
        "failed":    int(manifest.get("filings_failed", 0)),
    }


def _check_thresholds(cls: str, metrics: dict) -> list:
    """Return list of unmet threshold descriptions.

    Args:
        cls: Issuer class ('Domestic_US', 'FPI_ADR', 'NonUS_Local').
        metrics: Output of _extract_filing_metrics().

    Returns:
        List of human-readable violations (empty list = all OK).
    """
    thr = THRESHOLDS.get(cls, {})
    req: list = []
    if cls in ("Domestic_US", "FPI_ADR"):
        am = thr.get("annual_min", 0)
        tm = thr.get("total_min", 0)
        if metrics["annual"] < am:
            req.append(f"ANNUAL<{am} (got {metrics['annual']})")
        if metrics["total"] < tm:
            req.append(f"TOTAL<{tm} (got {metrics['total']})")
    else:  # NonUS_Local
        tm = thr.get("total_min", 0)
        if metrics["total"] < tm:
            req.append(f"TOTAL<{tm} (got {metrics['total']})")
    return req


def evaluate_case(case_dir: Path) -> dict:
    """Evaluate filing coverage for a single ticker case.

    Reads case.json and filings_manifest.json from *case_dir*, determines
    the issuer class, checks thresholds, and returns a status dict.

    Args:
        case_dir: Path to the case directory (e.g. ``cases/TZOO/``).

    Returns:
        Dict with keys: ticker, issuer_class, source_hint, country, exchange,
        currency, cik, period_scope, has_manifest, metrics, required_actions,
        status.  ``status`` is one of 'PASS' or 'NEEDS_ACTION'.
    """
    case_data = _jread(case_dir / "case.json") or {}
    manifest = _jread(case_dir / "filings_manifest.json")

    ticker = case_data.get("ticker") or case_dir.name.upper()
    source_hint = case_data.get("source_hint", "")
    country = case_data.get("country", "")
    cik = case_data.get("cik") or (manifest or {}).get("cik")
    if cik is not None:
        cik = str(cik)

    cls = issuer_class(source_hint, country, cik)
    metrics = _extract_filing_metrics(manifest)
    required = _check_thresholds(cls, metrics)

    return {
        "ticker":           ticker,
        "issuer_class":     cls,
        "source_hint":      source_hint,
        "country":          country,
        "exchange":         case_data.get("exchange") or case_data.get("market", ""),
        "currency":         case_data.get("currency", ""),
        "cik":              cik,
        "period_scope":     case_data.get("period_scope", "FULL"),
        "has_manifest":     manifest is not None,
        "metrics":          metrics,
        "required_actions": required,
        "status":           "PASS" if not required else "NEEDS_ACTION",
    }


def build_report(cases_dir: Path) -> dict:
    """Build a coverage report for all cases in *cases_dir*.

    Args:
        cases_dir: Root directory containing one subdirectory per ticker.

    Returns:
        Report dict with keys: version, generated_at, cases_dir, summary,
        cases, pass, needs_action.
    """
    case_dirs = sorted(
        d for d in cases_dir.iterdir()
        if d.is_dir() and (d / "case.json").exists()
    )
    cases = [evaluate_case(d) for d in case_dirs]
    pass_cases = [c for c in cases if c["status"] == "PASS"]
    na_cases = [c for c in cases if c["status"] == "NEEDS_ACTION"]
    summary = {
        "total_tickers":      len(cases),
        "pass_count":         len(pass_cases),
        "needs_action_count": len(na_cases),
        "class_counts": {
            "Domestic_US": sum(1 for c in cases if c["issuer_class"] == "Domestic_US"),
            "FPI_ADR":     sum(1 for c in cases if c["issuer_class"] == "FPI_ADR"),
            "NonUS_Local": sum(1 for c in cases if c["issuer_class"] == "NonUS_Local"),
        },
    }
    return {
        "version":      "1.0",
        "generated_at": _now_iso(),
        "cases_dir":    str(cases_dir),
        "summary":      summary,
        "cases":        cases,
        "pass":         pass_cases,
        "needs_action": na_cases,
    }


def render_markdown(report: dict) -> str:
    """Render a coverage report as Markdown.

    Args:
        report: Output of :func:`build_report`.

    Returns:
        Markdown-formatted string.
    """
    s = report["summary"]
    lines: list = []

    lines.append("# Coverage Audit Report")
    lines.append("")
    lines.append(f"- Generated: `{report['generated_at']}`")
    lines.append(f"- Cases dir: `{report['cases_dir']}`")
    lines.append(f"- Total tickers: **{s['total_tickers']}**")
    lines.append(
        f"- PASS: **{s['pass_count']}** NEEDS_ACTION: **{s['needs_action_count']}**"
    )
    lines.append("")

    cc = s["class_counts"]
    lines.append("| Issuer Class | Count |")
    lines.append("|:------------|------:|")
    for k, v in cc.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## Needs Action")
    lines.append("")
    if not report["needs_action"]:
        lines.append("_None_")
    else:
        lines.append("| Ticker | Class | Annual | Total | Actions |")
        lines.append("|:-------|:------|-------:|------:|:--------|")
        for c in report["needs_action"]:
            m = c["metrics"]
            actions = "; ".join(c["required_actions"]) or "-"
            lines.append(
                f"| `{c['ticker']}` | {c['issuer_class']}"
                f" | {m['annual']} | {m['total']} | {actions} |"
            )
    lines.append("")

    lines.append("## PASS")
    lines.append("")
    if not report["pass"]:
        lines.append("_None_")
    else:
        lines.append("| Ticker | Class | Annual | Quarterly | Earnings | Total |")
        lines.append("|:-------|:------|-------:|----------:|---------:|------:|")
        for c in report["pass"]:
            m = c["metrics"]
            lines.append(
                f"| `{c['ticker']}` | {c['issuer_class']}"
                f" | {m['annual']} | {m['quarterly']} | {m['earnings']} | {m['total']} |"
            )
    lines.append("")

    return "\n".join(lines)
