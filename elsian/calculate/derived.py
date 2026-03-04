"""derived.py — Derived financial metrics calculator for ELSIAN 4.0.

Ported and adapted from 3.0's tp_calculator.py (scripts/runners/tp_calculator.py).

Input format (4.0 extraction_result):
    {
        "periods": {
            "FY2024": {
                "tipo_periodo": "anual",
                "fecha_fin": "2024-12-31",
                "fields": {
                    "ingresos": {"value": 83902},
                    "ebit":     {"value": 7145},
                    ...
                }
            },
            "Q1-2024": { ... },
        }
    }

Formulas:
    TTM  = 4-quarter sum | semestral (FY+H1_new-H1_old) | FY0 fallback
    FCF  = CFO - |capex|
    EV   = market_cap + total_debt - cash_and_equivalents
    Margins: gross, operating, net, FCF (% of revenue)
    Returns: ROIC (NOPAT/IC, tax=21%), ROE, ROA
    Multiples: EV/EBIT, EV/FCF, P/FCF, FCF_yield
    net_debt = total_debt - cash_and_equivalents
    Per-share: EPS, FCF/share, BV/share

Null propagation: all formulas return None when any required input is None.
"""
from __future__ import annotations

import calendar
import datetime
import re
from typing import Any


# ── TTM summable fields (4.0 canonical names) ───────────────────────────────

_TTM_SUMMABLE: tuple[str, ...] = (
    "ingresos",
    "ebit",
    "net_income",
    "cfo",
    "capex",
    "gross_profit",
    "cost_of_revenue",
)

# Fields required for FY0 eligibility (ingresos + at least 3 of 5)
_FY0_KEY_FIELDS: tuple[str, ...] = (
    "ingresos",
    "ebit",
    "net_income",
    "cfo",
    "capex",
)


# ── Period classification and sorting ───────────────────────────────────────

def _period_type(key: str) -> str:
    """Classify a period key as 'annual', 'quarterly', 'semestral', or 'unknown'."""
    k = key.upper()
    if re.match(r"^FY\d{4}$", k):
        return "annual"
    if re.match(r"^Q[1-4]-\d{4}$", k):
        return "quarterly"
    if re.match(r"^H[12]-\d{4}$", k):
        return "semestral"
    return "unknown"


def _period_sort_key(period_key: str, fecha_fin: str | None = None) -> str:
    """Return an ISO-date string suitable for chronological sorting.

    Precedence: fecha_fin (if ISO date) > period_key pattern match.
    """
    if fecha_fin and re.match(r"^\d{4}-\d{2}-\d{2}", fecha_fin):
        return fecha_fin[:10]
    k = period_key.upper()
    # FY2024 -> 2024-12-31
    m = re.match(r"^FY(\d{4})$", k)
    if m:
        return f"{m.group(1)}-12-31"
    # Q3-2024 -> 2024-09-30
    m = re.match(r"^Q([1-4])-(\d{4})$", k)
    if m:
        q, year = int(m.group(1)), int(m.group(2))
        month = q * 3
        day = calendar.monthrange(year, month)[1]
        return f"{year}-{month:02d}-{day:02d}"
    # H1-2024 -> 2024-06-30
    m = re.match(r"^H1-(\d{4})$", k)
    if m:
        return f"{m.group(1)}-06-30"
    # H2-2024 -> 2024-12-31
    m = re.match(r"^H2-(\d{4})$", k)
    if m:
        return f"{m.group(1)}-12-31"
    return period_key


def _extract_year(period_key: str) -> int | None:
    """Extract the fiscal year integer from a period key (FY2024, Q1-2024, H1-2024)."""
    m = re.search(r"(\d{4})", period_key)
    return int(m.group(1)) if m else None


def _extract_quarter(period_key: str) -> tuple[int | None, int | None]:
    """Return (year, quarter_number) for a Q*-YYYY key, else (None, None)."""
    m = re.match(r"^Q([1-4])-(\d{4})$", period_key.upper())
    if m:
        return int(m.group(2)), int(m.group(1))
    return None, None


# ── Value extraction from 4.0 field dicts ───────────────────────────────────

def _get_val(fields: dict[str, Any], field: str) -> float | None:
    """Extract a numeric value from a 4.0 fields dict.

    Handles both raw numbers and ``{"value": N}`` wrapper dicts.
    Returns None for missing, null, or boolean-typed entries.
    """
    entry = fields.get(field)
    if entry is None:
        return None
    if isinstance(entry, bool):
        return None
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        val = entry.get("value")
        if isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return float(val)
    return None


# ── Period parsing ───────────────────────────────────────────────────────────

def _parse_periods(
    extraction_result: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split extraction_result['periods'] into (annual, quarterly, semestral) lists.

    Each entry is a plain dict:
        {"period_key": str, "fecha_fin": str|None, "tipo_periodo": str, "fields": dict}
    """
    annual: list[dict] = []
    quarterly: list[dict] = []
    semestral: list[dict] = []

    for key, period_data in extraction_result.get("periods", {}).items():
        entry: dict[str, Any] = {
            "period_key": key,
            "fecha_fin": period_data.get("fecha_fin"),
            "tipo_periodo": period_data.get("tipo_periodo", ""),
            "fields": period_data.get("fields", {}),
        }
        pt = _period_type(key)
        if pt == "annual":
            annual.append(entry)
        elif pt == "quarterly":
            quarterly.append(entry)
        elif pt == "semestral":
            semestral.append(entry)

    return annual, quarterly, semestral


# ── FY0 eligibility ──────────────────────────────────────────────────────────

def _find_eligible_fy0(annual: list[dict]) -> dict | None:
    """Return the most recent annual period eligible as FY0.

    Eligibility: ingresos is non-null AND at least 3 of 5 key P&L/CF fields
    are populated. Periods are evaluated from most-recent to oldest.
    """
    sorted_annual = sorted(
        annual,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )
    for candidate in reversed(sorted_annual):
        fields = candidate["fields"]
        if _get_val(fields, "ingresos") is None:
            continue
        populated = sum(1 for f in _FY0_KEY_FIELDS if _get_val(fields, f) is not None)
        if populated >= 3:
            return candidate
    return None


# ── TTM: consecutive-quarter validation ─────────────────────────────────────

def _quarters_are_consecutive(quarters: list[dict]) -> bool:
    """Check that 4 quarters are consecutive (span ~12 months, no big gaps)."""
    if len(quarters) < 2:
        return False
    dates: list[datetime.date] = []
    for q in quarters:
        key = _period_sort_key(q["period_key"], q.get("fecha_fin"))
        try:
            dates.append(datetime.date.fromisoformat(key))
        except (ValueError, TypeError):
            return False
    for i in range(1, len(dates)):
        gap = (dates[i] - dates[i - 1]).days
        if gap > 120 or gap < 30:
            return False
    total_span = (dates[-1] - dates[0]).days
    return 240 <= total_span <= 460


# ── TTM: synthetic Q4 ────────────────────────────────────────────────────────

def _build_synthetic_q4(
    annual: list[dict], quarters: list[dict]
) -> list[dict]:
    """Insert synthetic Q4 entries (FY - (Q1+Q2+Q3)) when Q4 is missing."""
    annual_by_year: dict[int, dict] = {}
    for a in annual:
        year = _extract_year(a["period_key"])
        if year is not None:
            annual_by_year[year] = a

    quarters_by_year: dict[int, dict[int, dict]] = {}
    for q in quarters:
        year, q_num = _extract_quarter(q["period_key"])
        if year is None or q_num is None:
            continue
        quarters_by_year.setdefault(year, {})
        quarters_by_year[year][q_num] = q

    synthetic: list[dict] = []
    for year, a in annual_by_year.items():
        q_map = quarters_by_year.get(year, {})
        if 4 in q_map:
            continue
        if not all(qn in q_map for qn in (1, 2, 3)):
            continue
        q1, q2, q3 = q_map[1], q_map[2], q_map[3]
        synth_fields: dict[str, Any] = {}
        for field in _TTM_SUMMABLE:
            a_val = _get_val(a["fields"], field)
            q_vals = [_get_val(q["fields"], field) for q in (q1, q2, q3)]
            if a_val is not None and all(v is not None for v in q_vals):
                synth_fields[field] = {"value": a_val - sum(q_vals)}
        # Require revenue so the synthetic quarter is financially meaningful
        if _get_val(synth_fields, "ingresos") is None:
            continue
        synthetic.append({
            "period_key": f"Q4-{year}",
            "fecha_fin": f"{year}-12-31",
            "tipo_periodo": "trimestral",
            "fields": synth_fields,
            "_synthetic_q4": True,
        })

    if not synthetic:
        return quarters
    return sorted(
        [*quarters, *synthetic],
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )


# ── TTM: semestral strategy ──────────────────────────────────────────────────

def _ttm_semestral(
    annual: list[dict], semestral: list[dict]
) -> dict[str, Any] | None:
    """Compute TTM from semestral data: TTM = FY_prior + H1_new - H1_old.

    Returns a TTM dict (metodo='semestral_FY_H1') or None if insufficient data.
    """
    h1_entries = [
        s for s in semestral if s["period_key"].upper().startswith("H1")
    ]
    h1_entries = sorted(
        h1_entries,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )
    if len(h1_entries) < 2:
        return None

    h1_new, h1_old = h1_entries[-1], h1_entries[-2]
    h1_new_year = _extract_year(h1_new["period_key"])
    h1_old_year = _extract_year(h1_old["period_key"])
    if h1_new_year is None or h1_old_year is None:
        return None
    if h1_new_year - h1_old_year != 1:
        return None

    # Find the annual period matching the prior year
    fy_prior: dict | None = None
    for a in sorted(
        annual,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    ):
        if _extract_year(a["period_key"]) == h1_old_year:
            fy_prior = a
            break
    if fy_prior is None:
        return None

    # Require ebit and cfo in all three sources
    for src in (fy_prior, h1_old, h1_new):
        for f in ("ebit", "cfo"):
            if _get_val(src["fields"], f) is None:
                return None

    res: dict[str, Any] = {
        "metodo": "semestral_FY_H1",
        "nota": (
            f"TTM = FY{h1_old_year} + H1-{h1_new_year} - H1-{h1_old_year}"
        ),
        "fecha_fin": h1_new.get("fecha_fin"),
    }
    for field in _TTM_SUMMABLE:
        fy_v = _get_val(fy_prior["fields"], field)
        h1o_v = _get_val(h1_old["fields"], field)
        h1n_v = _get_val(h1_new["fields"], field)
        if fy_v is not None and h1o_v is not None and h1n_v is not None:
            res[field] = fy_v + h1n_v - h1o_v
        else:
            res[field] = None
    return res


# ── TTM: main cascade ────────────────────────────────────────────────────────

def _ttm(
    annual: list[dict],
    quarterly: list[dict],
    semestral: list[dict],
) -> dict[str, Any]:
    """Compute TTM using three cascading strategies.

    Priority:
        1. suma_4_trimestres -- standard 4-quarter rolling sum
        2. semestral_FY_H1  -- FY + H1_new - H1_old (semi-annual reporters)
        3. FY0_fallback      -- most recent eligible full-year annual
    """
    result: dict[str, Any] = {f: None for f in _TTM_SUMMABLE}
    result.update({"metodo": "no_disponible", "nota": None, "fecha_fin": None})

    # Strategy 1 -- rolling 4-quarter sum
    quarters_sorted = sorted(
        quarterly,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )
    quarters_sorted = _build_synthetic_q4(annual, quarters_sorted)

    if len(quarters_sorted) >= 4:
        last_4 = quarters_sorted[-4:]
        if not _quarters_are_consecutive(last_4):
            labels = [q["period_key"] for q in last_4]
            result["nota"] = (
                f"4 quarters available but NOT consecutive: {labels}. TTM rejected."
            )
        else:
            for field in _TTM_SUMMABLE:
                vals = [_get_val(q["fields"], field) for q in last_4]
                if all(v is not None for v in vals):
                    result[field] = sum(vals)
            result["metodo"] = "suma_4_trimestres"
            result["fecha_fin"] = last_4[-1].get("fecha_fin")
            labels = [
                q["period_key"] + ("*" if q.get("_synthetic_q4") else "")
                for q in last_4
            ]
            result["nota"] = f"TTM from quarters: {labels}"

    def _sparse(r: dict) -> bool:
        """True if quarterly TTM has revenue but no P&L/CF (semi-annual reporter)."""
        if r.get("metodo") != "suma_4_trimestres":
            return False
        key_fields = ("ebit", "net_income", "cfo")
        return r.get("ingresos") is not None and all(
            r.get(f) is None for f in key_fields
        )

    # Strategy 2 -- semestral upgrade
    if _sparse(result) or result["metodo"] == "no_disponible":
        sem = _ttm_semestral(annual, semestral)
        if sem is not None:
            if result["metodo"] == "suma_4_trimestres":
                sem["nota"] = (
                    "Quarterly TTM sparse (revenue only). Upgraded to semestral: "
                    + (sem.get("nota") or "")
                )
            return sem

    # Strategy 3 -- FY0 fallback
    if result["metodo"] == "no_disponible" and annual:
        fy0 = _find_eligible_fy0(annual)
        if fy0 is None:
            prev = result.get("nota") or ""
            result["nota"] = (
                prev
                + " FY0 fallback rejected: no eligible annual with >=3 key fields."
            ).strip()
            return result
        for field in _TTM_SUMMABLE:
            result[field] = _get_val(fy0["fields"], field)
        result["metodo"] = "FY0_fallback"
        result["fecha_fin"] = fy0.get("fecha_fin")
        prev = result.get("nota") or ""
        result["nota"] = (
            prev + " Fallback to FY0."
            if "NOT consecutive" in prev
            else "TTM not available, using FY0"
        )

    return result


# ── Math helpers ─────────────────────────────────────────────────────────────

def _safe_div(
    num: float | None,
    den: float | None,
    *,
    multiply_100: bool = False,
) -> float | None:
    """Safe division. Returns None if any input is None or denominator <= 0."""
    if num is None or den is None or den <= 0:
        return None
    r = num / den
    return round(r * 100 if multiply_100 else r, 4)


def _safe_add(*args: float | None) -> float | None:
    """Sum that returns None if any argument is None."""
    if any(a is None for a in args):
        return None
    return sum(args)  # type: ignore[arg-type]


def _safe_sub(a: float | None, b: float | None) -> float | None:
    """Subtraction that returns None if any input is None."""
    if a is None or b is None:
        return None
    return a - b


# ── Formula implementations ──────────────────────────────────────────────────

def _fcf(cfo: float | None, capex: float | None) -> float | None:
    """FCF = CFO - |capex|. Null-safe."""
    if cfo is None or capex is None:
        return None
    return cfo - abs(capex)


def _ev(
    market_cap: float | None,
    debt: float | None,
    cash: float | None,
) -> float | None:
    """EV = market_cap + total_debt - cash. Fail-closed: None if any input is None."""
    if market_cap is None or debt is None or cash is None:
        return None
    return market_cap + debt - cash


def _margins(
    ingresos: float | None,
    gross_profit: float | None,
    cost_of_revenue: float | None,
    ebit: float | None,
    net_income: float | None,
    fcf: float | None,
) -> dict[str, float | None]:
    """Compute gross, operating, net, and FCF margins (as percentages)."""
    if not ingresos or ingresos <= 0:
        return {
            "gross_margin": None,
            "operating_margin": None,
            "net_margin": None,
            "fcf_margin": None,
        }
    gross: float | None
    if gross_profit is not None:
        gross = round(gross_profit / ingresos * 100, 2)
    elif cost_of_revenue is not None:
        gross = round((ingresos - cost_of_revenue) / ingresos * 100, 2)
    else:
        gross = None
    return {
        "gross_margin": gross,
        "operating_margin": (
            round(ebit / ingresos * 100, 2) if ebit is not None else None
        ),
        "net_margin": (
            round(net_income / ingresos * 100, 2) if net_income is not None else None
        ),
        "fcf_margin": (
            round(fcf / ingresos * 100, 2) if fcf is not None else None
        ),
    }


def _returns(
    ebit: float | None,
    tax_rate: float,
    invested_capital: float | None,
    net_income: float | None,
    equity: float | None,
    total_assets: float | None,
) -> dict[str, float | None]:
    """Compute ROIC (NOPAT/IC at 21% tax), ROE, and ROA (as percentages)."""
    roic: float | None = None
    if ebit is not None and invested_capital is not None and invested_capital > 0:
        nopat = ebit * (1.0 - tax_rate)
        roic = round(nopat / invested_capital * 100, 2)
    roe: float | None = None
    if net_income is not None and equity is not None and equity > 0:
        roe = round(net_income / equity * 100, 2)
    roa: float | None = None
    if net_income is not None and total_assets is not None and total_assets > 0:
        roa = round(net_income / total_assets * 100, 2)
    return {"roic": roic, "roe": roe, "roa": roa}


def _multiples(
    ev: float | None,
    ebit: float | None,
    fcf: float | None,
    market_cap: float | None,
) -> dict[str, float | None]:
    """EV/EBIT, EV/FCF, P/FCF, FCF_yield. None when denominator <= 0."""
    return {
        "ev_ebit": _safe_div(ev, ebit) if ebit and ebit > 0 else None,
        "ev_fcf": _safe_div(ev, fcf) if fcf and fcf > 0 else None,
        "p_fcf": _safe_div(market_cap, fcf) if fcf and fcf > 0 else None,
        "fcf_yield": (
            _safe_div(fcf, market_cap, multiply_100=True)
            if fcf and market_cap and market_cap > 0
            else None
        ),
    }


def _per_share(
    net_income: float | None,
    fcf: float | None,
    equity: float | None,
    shares: float | None,
) -> dict[str, float | None]:
    """EPS, FCF/share, BV/share. All None when shares is None or <= 0."""
    if not shares or shares <= 0:
        return {"eps": None, "fcf_per_share": None, "bv_per_share": None}
    return {
        "eps": round(net_income / shares, 4) if net_income is not None else None,
        "fcf_per_share": round(fcf / shares, 4) if fcf is not None else None,
        "bv_per_share": round(equity / shares, 4) if equity is not None else None,
    }


# ── Market data extraction ───────────────────────────────────────────────────

def _extract_market_data(market_data: dict[str, Any]) -> dict[str, float | None]:
    """Normalise market_data dict to {market_cap, shares_outstanding, price}.

    Accepts flat dict (e.g. from market_data.py MarketSnapshot serialised as JSON).
    """
    result: dict[str, float | None] = {
        "market_cap": None,
        "shares_outstanding": None,
        "price": None,
    }
    if not market_data:
        return result
    result["market_cap"] = (
        market_data.get("market_cap") or market_data.get("market_cap_usd")
    )
    result["shares_outstanding"] = market_data.get("shares_outstanding")
    result["price"] = market_data.get("price") or market_data.get("precio")
    return result


# ── Latest balance sheet helper ──────────────────────────────────────────────

def _latest_bs_fields(annual: list[dict]) -> dict[str, Any]:
    """Return the fields dict of the most-recent annual period."""
    if not annual:
        return {}
    most_recent = max(
        annual,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )
    return most_recent["fields"]


# ── Public API ───────────────────────────────────────────────────────────────

def calculate(
    extraction_result: dict[str, Any],
    market_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate derived financial metrics from a 4.0 extraction_result.

    Args:
        extraction_result: 4.0 format dict with a ``periods`` key.
        market_data: Optional flat dict with ``market_cap``, ``shares_outstanding``,
            and/or ``price``. Values assumed to be in the same unit as the
            extraction_result (caller's responsibility for unit consistency).

    Returns:
        Dict with two top-level keys::

            {
                "ttm": {...},            # TTM computed values + metodo/nota
                "derived_metrics": {...} # All derived metrics, None for unavailable
            }
    """
    mkt = _extract_market_data(market_data or {})
    market_cap: float | None = mkt["market_cap"]
    shares: float | None = mkt["shares_outstanding"]

    annual, quarterly, semestral = _parse_periods(extraction_result)

    # ── TTM ──
    ttm = _ttm(annual, quarterly, semestral)
    ttm_method = ttm.get("metodo", "no_disponible")
    use_ttm = (
        ttm_method in ("suma_4_trimestres", "semestral_FY_H1", "FY0_fallback")
        and ttm.get("ingresos") is not None
    )

    # ── Income / CF data source: TTM when available, FY0 when not ──
    if use_ttm:
        ingresos = ttm.get("ingresos")
        ebit = ttm.get("ebit")
        net_income = ttm.get("net_income")
        cfo = ttm.get("cfo")
        capex = ttm.get("capex")
        gross_profit = ttm.get("gross_profit")
        cost_of_revenue = ttm.get("cost_of_revenue")
    else:
        fy0 = _find_eligible_fy0(annual)
        f0 = fy0["fields"] if fy0 else {}
        ingresos = _get_val(f0, "ingresos")
        ebit = _get_val(f0, "ebit")
        net_income = _get_val(f0, "net_income")
        cfo = _get_val(f0, "cfo")
        capex = _get_val(f0, "capex")
        gross_profit = _get_val(f0, "gross_profit")
        cost_of_revenue = _get_val(f0, "cost_of_revenue")

    # ── Balance sheet (most-recent annual) ──
    bs = _latest_bs_fields(annual)
    total_assets = _get_val(bs, "total_assets")
    total_liabilities = _get_val(bs, "total_liabilities")  # noqa: F841 (available for future use)
    equity = _get_val(bs, "total_equity")
    debt = _get_val(bs, "total_debt")
    cash = _get_val(bs, "cash_and_equivalents")

    # Shares fallback: extraction_result balance sheet
    if shares is None:
        shares = _get_val(bs, "shares_outstanding")

    # ── Derived calculations ──
    fcf = _fcf(cfo, capex)
    ev = _ev(market_cap, debt, cash)
    mrg = _margins(ingresos, gross_profit, cost_of_revenue, ebit, net_income, fcf)
    invested_capital = _safe_add(debt, equity)
    ret = _returns(ebit, 0.21, invested_capital, net_income, equity, total_assets)
    mult = _multiples(ev, ebit, fcf, market_cap)
    net_debt = _safe_sub(debt, cash)
    ps = _per_share(net_income, fcf, equity, shares)

    # periodo_base label
    if use_ttm:
        periodo_base = ttm_method
    elif _find_eligible_fy0(annual):
        periodo_base = "FY0"
    else:
        periodo_base = "no_disponible"

    derived: dict[str, Any] = {
        "gross_margin_pct": mrg["gross_margin"],
        "operating_margin_pct": mrg["operating_margin"],
        "net_margin_pct": mrg["net_margin"],
        "fcf_margin_pct": mrg["fcf_margin"],
        "fcf_yield_pct": mult["fcf_yield"],
        "ev_ebit": mult["ev_ebit"],
        "ev_fcf": mult["ev_fcf"],
        "p_fcf": mult["p_fcf"],
        "roic_pct": ret["roic"],
        "roe_pct": ret["roe"],
        "roa_pct": ret["roa"],
        "net_debt": net_debt,
        "ev": ev,
        "fcf": fcf,
        "eps": ps["eps"],
        "fcf_per_share": ps["fcf_per_share"],
        "bv_per_share": ps["bv_per_share"],
        "periodo_base": periodo_base,
        "nota": (
            f"Calculated by derived.py. "
            f"periodo_base={periodo_base}. "
            "Null propagation applied."
        ),
    }

    return {"ttm": ttm, "derived_metrics": derived}
