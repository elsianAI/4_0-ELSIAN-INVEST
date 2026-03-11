"""BL-069: Render diagnose_report dict to human-readable Markdown.

The report is produced from on-the-fly re-extraction; it does not depend
on any persisted ``extraction_result.json`` artefact.
"""

from __future__ import annotations

from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    """Produce a Markdown report from a diagnose report dict.

    Args:
        report: Output of ``engine.build_report()``.

    Returns:
        Markdown string suitable for writing to ``diagnose_report.md``.
    """
    lines: list[str] = []

    summary = report.get("summary", {})
    generated = report.get("generated_at", "")

    lines.append("# ELSIAN Diagnose Report")
    lines.append(f"\n_Generated: {generated}_\n")

    lines.append("## Summary\n")
    lines.append(f"- Tickers analyzed: **{summary.get('tickers_analyzed', 0)}**")
    lines.append(f"- Tickers evaluated: **{summary.get('tickers_with_eval', 0)}**")
    lines.append(f"- Tickers skipped: **{summary.get('tickers_skipped', 0)}** (no expected.json)")
    lines.append(f"- Overall score: **{summary.get('overall_score_pct', 0):.1f}%**")
    lines.append(f"  - Expected: {summary.get('total_expected', 0)}")
    lines.append(f"  - Matched: {summary.get('total_matched', 0)}")
    lines.append(f"  - Wrong: {summary.get('total_wrong', 0)}")
    lines.append(f"  - Missed: {summary.get('total_missed', 0)}")
    lines.append(f"  - Extra: {summary.get('total_extra', 0)}")
    lines.append("")

    hotspots = report.get("hotspots", [])
    if hotspots:
        lines.append("## Top Hotspots\n")
        lines.append(
            "Ranked by occurrence count across all evaluated tickers. "
            "``Root Cause Hint`` is a heuristic signal to prioritise next BL targets "
            "without manual ticker review.\n"
        )
        lines.append("| Rank | Field | Category | Gap Type | Root Cause Hint | Occ | Affected Tickers |")
        lines.append("|-----:|-------|----------|----------|-----------------|----:|-----------------|")
        for h in hotspots[:20]:
            tickers_str = ", ".join(h.get("affected_tickers", []))
            lines.append(
                f"| {h['rank']} | `{h['field']}` | {h.get('field_category', '')} "
                f"| {h['gap_type']} | **{h.get('root_cause_hint', '')}** "
                f"| {h['occurrences']} | {tickers_str} |"
            )
        lines.append("")

        lines.append("### Evidence (top 5 hotspots)\n")
        for h in hotspots[:5]:
            lines.append(
                f"**#{h['rank']} `{h['field']}` ({h['gap_type']}) — "
                f"hint: `{h.get('root_cause_hint', '')}`**\n"
            )
            for ev in h.get("evidence", []):
                actual_str = str(ev["actual"]) if ev.get("actual") is not None else "—"
                lines.append(
                    f"- {ev['ticker']} / {ev['period']}: "
                    f"expected=`{ev['expected']}`, actual=`{actual_str}`"
                )
            lines.append("")

    by_ticker = report.get("by_ticker", {})
    if by_ticker:
        lines.append("## Per-Ticker Summary\n")
        lines.append("| Ticker | Source | Score | Matched | Expected | Wrong | Missed | Extra |")
        lines.append("|--------|--------|------:|--------:|---------:|------:|-------:|------:|")
        for ticker, d in sorted(by_ticker.items()):
            if d.get("skipped"):
                reason = d.get("skip_reason", "") or ""
                lines.append(
                    f"| {ticker} | {d.get('source_hint', '')} "
                    f"| — | — | — | — | — | — | _(skipped: {reason})_ |"
                )
            else:
                fatal_flag = " ⚠FATAL" if d.get("fatal") else ""
                lines.append(
                    f"| {ticker}{fatal_flag} | {d.get('source_hint', '')} "
                    f"| {d['score']:.1f}% "
                    f"| {d['matched']} | {d['total_expected']} "
                    f"| {d['wrong']} | {d['missed']} | {d['extra']} |"
                )
        lines.append("")

    by_source = report.get("by_source_hint", {})
    if by_source:
        lines.append("## By Source Hint\n")
        lines.append("| Source | Tickers | Avg Score | Wrong | Missed | Total Expected |")
        lines.append("|--------|---------|----------:|------:|-------:|---------------:|")
        for sh, d in sorted(by_source.items()):
            tickers_str = ", ".join(d.get("tickers", []))
            lines.append(
                f"| {sh} | {tickers_str} | {d.get('avg_score_pct', 0):.1f}% "
                f"| {d['total_wrong']} | {d['total_missed']} | {d['total_expected']} |"
            )
        lines.append("")

    root_cause_summary = report.get("root_cause_summary", {})
    if root_cause_summary:
        lines.append("## Root Cause Hint Summary\n")
        lines.append(
            "Heuristic summary of gap patterns. Use to identify dominant failure "
            "modes before ticker-by-ticker inspection.\n"
        )
        lines.append("| Root Cause Hint | Total Gap Occurrences |")
        lines.append("|-----------------|----------------------:|")
        for hint, count in root_cause_summary.items():
            lines.append(f"| `{hint}` | {count} |")
        lines.append("")

    by_period = report.get("by_period_type", {})
    if by_period:
        lines.append("## By Period Type\n")
        lines.append("| Period Type | Occurrences | Wrong | Missed | Affected Tickers |")
        lines.append("|-------------|------------:|------:|-------:|-----------------|")
        for tipo, d in by_period.items():
            tickers_str = ", ".join(d.get("affected_tickers", []))
            lines.append(
                f"| {tipo} | {d['occurrences']} | {d['wrong']} | {d['missed']} "
                f"| {tickers_str} |"
            )
        lines.append("")

    by_cat = report.get("by_field_category", {})
    if by_cat:
        lines.append("## By Field Category\n")
        lines.append("| Category | Occurrences | Wrong | Missed | Fields with Gaps |")
        lines.append("|----------|------------:|------:|-------:|-----------------|")
        for cat, d in by_cat.items():
            fields_str = ", ".join(f"`{f}`" for f in d.get("fields_with_gaps", []))
            lines.append(
                f"| {cat} | {d['occurrences']} | {d['wrong']} | {d['missed']} "
                f"| {fields_str} |"
            )
        lines.append("")

    return "\n".join(lines)
