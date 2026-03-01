"""Dashboard -- summary table of all cases."""

from __future__ import annotations

from elsian.models.result import DashboardRow


def format_dashboard(rows: list[DashboardRow]) -> str:
    """Format dashboard rows as a text table."""
    if not rows:
        return "No cases found."

    header = f"{'Ticker':<8} {'Source':<8} {'Filings':>7} {'Periods':>7} {'Expected':>8} {'Matched':>7} {'Score':>7}"
    sep = "-" * len(header)
    lines = [header, sep]

    for r in rows:
        lines.append(
            f"{r.ticker:<8} {r.source:<8} {r.filings:>7} {r.periods:>7} "
            f"{r.expected:>8} {r.matched:>7} {r.score:>6.1f}%"
        )

    total_exp = sum(r.expected for r in rows)
    total_match = sum(r.matched for r in rows)
    total_score = (total_match / total_exp * 100) if total_exp > 0 else 0
    lines.append(sep)
    lines.append(
        f"{'TOTAL':<8} {'':<8} {'':>7} {'':>7} "
        f"{total_exp:>8} {total_match:>7} {total_score:>6.1f}%"
    )

    return "\n".join(lines)
