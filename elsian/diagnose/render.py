"""BL-069: Render diagnose_report dict to human-readable Markdown."""

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
    lines.append(f"- Tickers skipped: **{summary.get('tickers_skipped', 0)}** (no extraction_result.json)")
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
        lines.append("Ranked by occurrence count across all evaluated tickers. "
                     "Use this table to prioritize next BL targets.\n")
        lines.append("| Rank | Field | Gap Type | Occ | Affected Tickers |")
        lines.append("|-----:|-------|----------|----:|-----------------|")
        for h in hotspots[:20]:
            tickers_str = ", ".join(h.get("affected_tickers", []))
            lines.append(
                f"| {h['rank']} | `{h['field']}` | {h['gap_type']} "
                f"| {h['occurrences']} | {tickers_str} |"
            )
        lines.append("")

        lines.append("### Evidence (top 5 hotspots)\n")
        for h in hotspots[:5]:
            lines.append(f"**#{h['rank']} `{h['field']}` ({h['gap_type']})**\n")
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

    return "\n".join(lines)
