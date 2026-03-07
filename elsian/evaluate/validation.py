"""validation.py — Autonomous Truth Pack validator for ELSIAN 4.0.

Ported and adapted from 3.0's scripts/runners/tp_validator.py.

Executes quality gates on extraction_result.json + derived metrics
WITHOUT requiring expected.json.  This is intrinsic consistency validation
(data quality, not accuracy vs ground truth).

Gates:
  N1) BALANCE_IDENTITY:   Assets ≈ Liabilities + Equity (±2%)
  N2) CASHFLOW_IDENTITY:  CFO + CFI + CFF ≈ ΔCash (±5%)
                          cfi/cff/delta_cash are canonical fields (26-field set).
                          Gate SKIPs only when all 13 tickers provide these fields.
  N3) UNIDADES_SANITY:    No 1000x jumps between consecutive annual periods.
                          Distinct from sanity.py's 10x YoY check:
                          1000x = unit-error indicator (thousands vs raw).
  N4) EV_SANITY:          EV >= 0 (from derived_metrics["ev"])
  N5) MARGIN_SANITY:      Margins within sector ranges (from derived_metrics)
  N6) TTM_SANITY:         TTM revenue consistent with FY0 (ratio 0.5-2.0)
  N7) TTM_CONSECUTIVE:    Quarters consecutive if method=suma_4_trimestres
  N8) RECENCY_SANITY:     FY base no more than 2 years old
  N9) DATA_COMPLETENESS:  % null canonical fields in extraction_result

NOT duplicated from elsian/normalize/sanity.py:
  - capex sign flip (sanity.py auto-fixes this)
  - revenue negative (sanity.py warns)
  - gross_profit > revenue (sanity.py warns)
  - YoY jumps >10x (sanity.py warns) -- N3 catches 1000x (unit errors only)

Confidence score: 100 - 15xFAIL - 5xWARN - 10xSKIP
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any


# -- Sector margin ranges ----------------------------------------------------
# Each entry: {"gross": (min%, max%), "operating": (min%, max%), "net": (min%, max%)}

SECTOR_MARGINS: dict[str, dict[str, tuple[float, float]]] = {
    "default":               {"gross": (-10, 90),  "operating": (-50, 60),   "net": (-100, 50)},
    # Technology / Software
    "Software":              {"gross": (50, 95),   "operating": (-30, 55),   "net": (-50, 45)},
    "SaaS":                  {"gross": (55, 95),   "operating": (-40, 50),   "net": (-60, 40)},
    "Semiconductors":        {"gross": (30, 80),   "operating": (-20, 55),   "net": (-30, 50)},
    "Technology Hardware":   {"gross": (15, 65),   "operating": (-15, 35),   "net": (-25, 30)},
    # Healthcare / Biotech
    "Biotechnology":         {"gross": (40, 95),   "operating": (-200, 50),  "net": (-250, 45)},
    "Pharmaceuticals":       {"gross": (50, 90),   "operating": (-30, 50),   "net": (-40, 40)},
    "Medical Devices":       {"gross": (40, 80),   "operating": (-20, 40),   "net": (-30, 35)},
    "Healthcare Services":   {"gross": (10, 60),   "operating": (-15, 25),   "net": (-20, 20)},
    # Consumer / Retail
    "Retail":                {"gross": (15, 55),   "operating": (-10, 20),   "net": (-15, 15)},
    "Consumer Staples":      {"gross": (20, 60),   "operating": (0, 25),     "net": (-5, 20)},
    "Restaurants":           {"gross": (20, 70),   "operating": (-10, 25),   "net": (-15, 18)},
    # Industrial / Energy
    "Industrials":           {"gross": (15, 55),   "operating": (-10, 25),   "net": (-15, 20)},
    "Energy":                {"gross": (10, 70),   "operating": (-30, 40),   "net": (-40, 30)},
    "Mining":                {"gross": (10, 65),   "operating": (-25, 45),   "net": (-35, 35)},
    # Financial
    "Financial Services":    {"gross": (20, 95),   "operating": (-20, 55),   "net": (-25, 45)},
    "Insurance":             {"gross": (10, 60),   "operating": (-10, 30),   "net": (-15, 25)},
    "REITs":                 {"gross": (20, 80),   "operating": (-10, 50),   "net": (-15, 40)},
    # Other
    "Telecom":               {"gross": (30, 70),   "operating": (-10, 35),   "net": (-20, 25)},
    "Media & Entertainment": {"gross": (25, 75),   "operating": (-20, 35),   "net": (-30, 30)},
}

# Gate sequence with criticality flags
_GATE_DEFS: list[dict[str, Any]] = [
    {"name": "BALANCE_IDENTITY",   "critical": True},
    {"name": "CASHFLOW_IDENTITY",  "critical": True},
    {"name": "UNIDADES_SANITY",    "critical": False},
    {"name": "EV_SANITY",          "critical": False},
    {"name": "MARGIN_SANITY",      "critical": False},
    {"name": "TTM_SANITY",         "critical": False},
    {"name": "TTM_CONSECUTIVE",    "critical": True},
    {"name": "RECENCY_SANITY",     "critical": False},
    {"name": "DATA_COMPLETENESS",  "critical": False},
]

# The 29 canonical fields used for DATA_COMPLETENESS
_CANONICAL_FIELDS: tuple[str, ...] = (
    "ingresos", "cost_of_revenue", "gross_profit", "ebitda", "ebit",
    "net_income", "eps_basic", "eps_diluted", "total_assets", "total_liabilities",
    "total_equity", "cash_and_equivalents", "total_debt", "cfo", "capex", "fcf",
    "dividends_per_share", "shares_outstanding", "research_and_development",
    "sga", "depreciation_amortization", "interest_expense", "income_tax",
    "cfi", "cff", "delta_cash",
    "accounts_receivable", "inventories", "accounts_payable",
)


# -- Value extraction helpers ------------------------------------------------

def _num(val: Any) -> float | None:
    """Return numeric value only (not bool, not dict)."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _get_val(fields: dict[str, Any], field: str) -> float | None:
    """Extract numeric value from a 4.0 fields dict.

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


# -- Period parsing ----------------------------------------------------------

def _period_type(key: str) -> str:
    """Classify period key as 'annual', 'quarterly', 'semestral', or 'unknown'."""
    k = key.upper()
    if re.match(r"^FY\d{4}$", k):
        return "annual"
    if re.match(r"^Q[1-4]-\d{4}$", k):
        return "quarterly"
    if re.match(r"^H[12]-\d{4}$", k):
        return "semestral"
    return "unknown"


def _period_sort_key(period_key: str, fecha_fin: str | None = None) -> str:
    """Return ISO date string suitable for chronological sorting."""
    if fecha_fin and re.match(r"^\d{4}-\d{2}-\d{2}", fecha_fin):
        return fecha_fin[:10]
    k = period_key.upper()
    m = re.match(r"^FY(\d{4})$", k)
    if m:
        return f"{m.group(1)}-12-31"
    m = re.match(r"^Q([1-4])-(\d{4})$", k)
    if m:
        q, year = int(m.group(1)), int(m.group(2))
        month = q * 3
        _days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return f"{year}-{month:02d}-{_days[month - 1]:02d}"
    m = re.match(r"^H1-(\d{4})$", k)
    if m:
        return f"{m.group(1)}-06-30"
    m = re.match(r"^H2-(\d{4})$", k)
    if m:
        return f"{m.group(1)}-12-31"
    return period_key


def _parse_periods(
    extraction_result: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Split extraction_result['periods'] into (annual, quarterly, semestral) lists."""
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


def _sorted_annual(annual: list[dict]) -> list[dict]:
    """Return annual periods sorted chronologically (oldest first)."""
    return sorted(
        annual,
        key=lambda e: _period_sort_key(e["period_key"], e.get("fecha_fin")),
    )


def _extract_year_from_period(entry: dict) -> int | None:
    """Extract fiscal year integer from a period entry (fecha_fin or period_key)."""
    fecha = (entry.get("fecha_fin") or "").strip()
    if fecha:
        m = re.search(r"(19|20)\d{2}", fecha)
        if m:
            return int(m.group(0))
    key = (entry.get("period_key") or "").strip()
    if key:
        m = re.search(r"(19|20)\d{2}", key)
        if m:
            return int(m.group(0))
    return None


# -- Gate implementations ----------------------------------------------------

def _gate_balance_identity(annual: list[dict]) -> dict:
    """N1: Assets approx Liabilities + Equity (+-2%). Uses most-recent annual FY.

    Belt-and-suspenders imputation: if exactly 2 of 3 BS fields present,
    the third is derived and the gate runs with a note.
    """
    sorted_ann = _sorted_annual(annual)
    assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None

    for entry in reversed(sorted_ann):
        fields = entry["fields"]
        a = _get_val(fields, "total_assets")
        li = _get_val(fields, "total_liabilities")
        eq = _get_val(fields, "total_equity")
        if a is not None or li is not None or eq is not None:
            assets, liabilities, equity = a, li, eq
            break

    if assets is None and liabilities is None and equity is None:
        return {
            "name": "BALANCE_IDENTITY",
            "status": "SKIP",
            "note": "No annual period has any balance sheet fields",
        }

    # Belt-and-suspenders imputation when exactly 2 of 3 are present
    imputed_field: str | None = None
    count_present = sum(1 for x in (assets, liabilities, equity) if x is not None)
    if count_present == 2:
        if assets is not None and equity is not None and liabilities is None:
            liabilities = assets - equity
            imputed_field = "total_liabilities"
        elif assets is not None and liabilities is not None and equity is None:
            equity = assets - liabilities
            imputed_field = "total_equity"
        elif liabilities is not None and equity is not None and assets is None:
            assets = liabilities + equity
            imputed_field = "total_assets"

    if assets is None or liabilities is None or equity is None:
        return {
            "name": "BALANCE_IDENTITY",
            "status": "FAIL",
            "note": "Missing balance sheet data -- critical gate cannot be evaluated",
        }

    expected = liabilities + equity
    if expected == 0:
        return {"name": "BALANCE_IDENTITY", "status": "SKIP", "note": "L+E = 0, cannot divide"}

    diff_pct = abs(assets - expected) / abs(expected)
    imp_note = f" (imputed {imputed_field})" if imputed_field else ""

    if diff_pct <= 0.02:
        return {
            "name": "BALANCE_IDENTITY",
            "status": "PASS",
            "note": f"Diff: {diff_pct:.2%}{imp_note}",
            "actual_value": diff_pct,
        }
    return {
        "name": "BALANCE_IDENTITY",
        "status": "FAIL",
        "note": f"Diff: {diff_pct:.2%} > 2%{imp_note}",
        "actual_value": diff_pct,
    }


def _gate_cashflow_identity(annual: list[dict]) -> dict:
    """N2: CFO + CFI + CFF approx DeltaCash (+-5%). Most-recent FY with complete CF data.

    NOTE: cfi, cff, and delta_cash are NOT in the 22 canonical fields.
    This gate SKIPs gracefully when those fields are absent (common in 4.0).
    Intentionally non-critical -- a SKIP does not cascade to overall FAIL.
    DISTINCT from sanity.py (capex sign, revenue sign, gp>revenue, yoy 10x).
    """
    sorted_ann = _sorted_annual(annual)
    if not sorted_ann:
        return {"name": "CASHFLOW_IDENTITY", "status": "SKIP", "note": "No annual data"}

    fy0: dict | None = None
    source_note = ""
    for entry in reversed(sorted_ann):
        fields = entry["fields"]
        cfo = _get_val(fields, "cfo")
        cfi = _get_val(fields, "cfi")
        cff = _get_val(fields, "cff")
        if cfo is not None and cfi is not None and cff is not None:
            fy0 = entry
            source_note = "Using " + entry["period_key"]
            break

    if fy0 is None:
        return {
            "name": "CASHFLOW_IDENTITY",
            "status": "SKIP",
            "note": (
                "No annual period has complete CF components (cfo+cfi+cff). "
                "cfi and cff are not in the 22 canonical fields -- "
                "this gate is optional for most 4.0 tickers."
            ),
        }

    fields = fy0["fields"]
    cfo = _get_val(fields, "cfo")
    cfi = _get_val(fields, "cfi")
    cff = _get_val(fields, "cff")
    delta_cash = _get_val(fields, "delta_cash")
    bridge = (cfo or 0.0) + (cfi or 0.0) + (cff or 0.0)

    if delta_cash is None:
        return {
            "name": "CASHFLOW_IDENTITY",
            "status": "SKIP",
            "note": (
                f"CF components present (bridge={bridge:,.0f}), "
                f"but no delta_cash to cross-check. {source_note}"
            ),
        }

    abs_diff = abs(bridge - delta_cash)
    denominator = max(abs(delta_cash), abs(bridge), 1.0)
    rel_diff = abs_diff / denominator
    absolute_tolerance = max(50_000.0, 0.005 * denominator)
    audit = (
        f"bridge={bridge:,.0f} (CFO={cfo:,.0f}+CFI={cfi:,.0f}+CFF={cff:,.0f}), "
        f"delta_cash={delta_cash:,.0f}, "
        f"abs_diff={abs_diff:,.0f}, rel_diff={rel_diff:.2%}. {source_note}"
    )

    if rel_diff <= 0.05 or abs_diff <= absolute_tolerance:
        return {"name": "CASHFLOW_IDENTITY", "status": "PASS", "note": audit}
    if rel_diff <= 0.10:
        return {
            "name": "CASHFLOW_IDENTITY",
            "status": "WARNING",
            "note": "Moderate CF deviation (possible FX/other adjustments). " + audit,
        }
    return {"name": "CASHFLOW_IDENTITY", "status": "FAIL", "note": audit}


def _gate_unidades_sanity(annual: list[dict]) -> dict:
    """N3: No 1000x jumps between consecutive annual periods.

    Detects unit-error anomalies (e.g. one year in thousands, next in raw).
    DISTINCT from sanity.py YoY check:
      - sanity.py: >10x  -- suspicious business change
      - This gate: >1000x -- almost certainly a unit conversion error
    """
    sorted_ann = _sorted_annual(annual)
    anomalies: list[str] = []

    for i in range(1, len(sorted_ann)):
        prev = sorted_ann[i - 1]
        curr = sorted_ann[i]
        for field in ("ingresos", "ebit", "net_income", "cfo"):
            p_val = _get_val(prev["fields"], field)
            c_val = _get_val(curr["fields"], field)
            if p_val is not None and c_val is not None and p_val != 0:
                ratio = abs(c_val / p_val)
                if ratio >= 1000 or ratio <= 0.001:
                    anomalies.append(
                        field + ": " + prev["period_key"] + "-->" + curr["period_key"]
                        + " ratio=" + str(int(ratio)) + "x"
                    )

    if not anomalies:
        return {
            "name": "UNIDADES_SANITY",
            "status": "PASS",
            "note": "No 1000x unit-error jumps detected",
        }
    return {
        "name": "UNIDADES_SANITY",
        "status": "FAIL",
        "note": "Unit-error anomalies (1000x): " + "; ".join(anomalies[:3]),
    }


def _gate_ev_sanity(derived_metrics: dict) -> dict:
    """N4: EV >= 0.  Uses derived_metrics['ev'] from calculate()."""
    ev = _num(derived_metrics.get("ev"))
    if ev is None:
        return {
            "name": "EV_SANITY",
            "status": "SKIP",
            "note": "EV not calculated (needs market_cap + total_debt + cash_and_equivalents)",
        }
    if ev >= 0:
        return {"name": "EV_SANITY", "status": "PASS", "note": f"EV = {ev:,.0f}"}
    return {
        "name": "EV_SANITY",
        "status": "WARNING",
        "note": f"Negative EV = {ev:,.0f} (cash > market_cap + debt)",
    }


def _resolve_sector_margins(sector: str | None) -> tuple[dict, str]:
    """Return (margin_ranges, sector_used) for the given sector string."""
    if sector and sector in SECTOR_MARGINS:
        return SECTOR_MARGINS[sector], sector
    return SECTOR_MARGINS["default"], "default"


def _gate_margin_sanity(derived_metrics: dict, sector: str | None) -> dict:
    """N5: Margins within sector-specific ranges.  Uses derived_metrics from calculate()."""
    ranges, sector_used = _resolve_sector_margins(sector)
    issues: list[str] = []

    for metric_type, key in [
        ("gross",     "gross_margin_pct"),
        ("operating", "operating_margin_pct"),
        ("net",       "net_margin_pct"),
    ]:
        val = derived_metrics.get(key)
        if val is not None:
            lo, hi = ranges[metric_type]
            if val < lo or val > hi:
                issues.append(f"{key}={val:.1f}% outside [{lo},{hi}] (sector={sector_used})")

    if not issues:
        return {
            "name": "MARGIN_SANITY",
            "status": "PASS",
            "note": f"Margins within expected ranges (sector={sector_used})",
        }
    return {"name": "MARGIN_SANITY", "status": "WARNING", "note": "; ".join(issues)}


def _gate_ttm_sanity(ttm: dict, annual: list[dict]) -> dict:
    """N6: TTM revenue consistent with FY0 revenue (ratio 0.5-2.0)."""
    if not ttm or ttm.get("metodo") == "no_disponible":
        return {"name": "TTM_SANITY", "status": "SKIP", "note": "TTM not calculated"}

    sorted_ann = _sorted_annual(annual)
    if not sorted_ann:
        return {"name": "TTM_SANITY", "status": "SKIP", "note": "No annual data to compare"}

    fy0_fields = sorted_ann[-1]["fields"]
    ttm_rev = _num(ttm.get("ingresos"))
    fy0_rev = _get_val(fy0_fields, "ingresos")

    if ttm_rev is None or fy0_rev is None or fy0_rev == 0:
        return {"name": "TTM_SANITY", "status": "SKIP", "note": "Cannot compare TTM vs FY0 revenue"}

    ratio = ttm_rev / fy0_rev
    if 0.5 <= ratio <= 2.0:
        return {"name": "TTM_SANITY", "status": "PASS", "note": f"TTM/FY0 revenue ratio: {ratio:.2f}"}
    return {
        "name": "TTM_SANITY",
        "status": "WARNING",
        "note": f"TTM/FY0 revenue ratio: {ratio:.2f} -- unusually large deviation",
    }


def _gate_ttm_consecutive(ttm: dict) -> dict:
    """N7: Validate TTM quarters are consecutive (when method=suma_4_trimestres)."""
    if not ttm:
        return {"name": "TTM_CONSECUTIVE", "status": "SKIP", "note": "TTM not available"}

    metodo = ttm.get("metodo", "no_disponible")
    if metodo == "no_disponible":
        return {"name": "TTM_CONSECUTIVE", "status": "SKIP", "note": "TTM not calculated"}

    nota = ttm.get("nota") or ""

    if metodo != "suma_4_trimestres":
        if "NOT consecutive" in nota or "NO consecutivos" in nota:
            return {
                "name": "TTM_CONSECUTIVE",
                "status": "WARNING",
                "note": "FY0_fallback triggered by non-consecutive quarters: " + nota,
            }
        return {
            "name": "TTM_CONSECUTIVE",
            "status": "PASS",
            "note": "TTM method: " + metodo + " -- not based on quarterly sum",
        }

    if "NOT consecutive" in nota or "NO consecutivos" in nota or "rechazado" in nota:
        return {
            "name": "TTM_CONSECUTIVE",
            "status": "FAIL",
            "note": "TTM quarters not consecutive: " + nota,
        }
    return {
        "name": "TTM_CONSECUTIVE",
        "status": "PASS",
        "note": "TTM passed consecutiveness check. " + nota,
    }


def _gate_recency_sanity(annual: list[dict]) -> dict:
    """N8: FY base not more than 2 years old."""
    years = [y for y in (_extract_year_from_period(a) for a in annual) if y is not None]
    if not years:
        return {
            "name": "RECENCY_SANITY",
            "status": "SKIP",
            "note": "No annual period year available",
        }

    base_year = max(years)
    current_year = dt.datetime.now(dt.timezone.utc).year
    age = current_year - base_year

    if age > 2:
        return {
            "name": "RECENCY_SANITY",
            "status": "WARNING",
            "note": f"FY base is {age} years old (base={base_year}, current={current_year})",
            "base_year": base_year,
        }
    return {
        "name": "RECENCY_SANITY",
        "status": "PASS",
        "note": f"FY base recency OK (base={base_year}, current={current_year})",
        "base_year": base_year,
    }


def _gate_data_completeness(extraction_result: dict) -> dict:
    """N9: Percentage of non-null canonical fields across all periods."""
    periods = extraction_result.get("periods", {})
    if not periods:
        return {
            "name": "DATA_COMPLETENESS",
            "status": "WARNING",
            "note": "No periods in extraction_result",
            "completeness_pct": 0.0,
        }

    total = 0
    present = 0
    for period_data in periods.values():
        fields = period_data.get("fields", {})
        for cfield in _CANONICAL_FIELDS:
            total += 1
            if _get_val(fields, cfield) is not None:
                present += 1

    completeness_pct = (present / total * 100.0) if total > 0 else 0.0
    status = "PASS" if completeness_pct >= 50 else "WARNING"

    return {
        "name": "DATA_COMPLETENESS",
        "status": status,
        "note": (
            f"Overall: {completeness_pct:.0f}% fields present "
            f"({present}/{total} canonical field-period pairs)"
        ),
        "completeness_pct": round(completeness_pct, 1),
    }


# -- Confidence and overall status -------------------------------------------

def _calc_confidence(gates: list[dict]) -> float:
    """Confidence: 100 - 15xFAIL - 5xWARN - 10xSKIP, clamped to [0, 100]."""
    score = 100.0
    for g in gates:
        status = g.get("status", "SKIP")
        if status == "FAIL":
            score -= 15
        elif status == "WARNING":
            score -= 5
        elif status == "SKIP":
            score -= 10
    return max(0.0, min(100.0, round(score, 1)))


def _overall_status(gates: list[dict]) -> str:
    """PASS / PARTIAL / FAIL based on gate results and criticality flags."""
    has_critical_fail = any(g.get("status") == "FAIL" and g.get("critical") for g in gates)
    has_critical_skip = any(g.get("status") == "SKIP" and g.get("critical") for g in gates)
    has_any_fail = any(g.get("status") == "FAIL" for g in gates)
    has_warning = any(g.get("status") == "WARNING" for g in gates)

    if has_critical_fail or has_critical_skip:
        return "FAIL"
    if has_any_fail or has_warning:
        return "PARTIAL"
    return "PASS"


# -- Auxiliary finders -------------------------------------------------------

def _find_faltantes_criticos(derived_metrics: dict) -> list[dict]:
    """Find critically missing derived metrics that block downstream analysis."""
    missing: list[dict] = []
    if derived_metrics.get("ev") is None:
        missing.append({
            "item": "enterprise_value",
            "impacto": "Cannot calculate EV multiples",
            "como_conseguirlo": "Need market_cap + total_debt + cash_and_equivalents",
        })
    if derived_metrics.get("fcf") is None:
        missing.append({
            "item": "free_cash_flow",
            "impacto": "Cannot calculate FCF metrics",
            "como_conseguirlo": "Need cfo and capex in extraction_result",
        })
    return missing


def _find_limitaciones(ttm: dict, annual: list[dict]) -> list[str]:
    """Find data limitations worth reporting to the caller."""
    limitations: list[str] = []
    metodo = ttm.get("metodo", "no_disponible") if ttm else "no_disponible"
    if metodo == "FY0_fallback":
        limitations.append("TTM calculated from FY0 only (no quarterly data)")
    elif metodo == "no_disponible":
        limitations.append("TTM not available")
    if len(annual) < 3:
        limitations.append(f"Only {len(annual)} years of annual data (recommended: 5)")
    return limitations


# -- Public API --------------------------------------------------------------

def validate(
    extraction_result: dict,
    derived: dict | None = None,
    sector: str | None = None,
) -> dict:
    """Validate an extraction_result autonomously (no expected.json required).

    Executes 9 quality gates measuring intrinsic consistency and data health.

    Args:
        extraction_result: 4.0 format dict with ``periods`` key.
        derived: Output of ``elsian.calculate.derived.calculate()``, containing
            ``"ttm"`` and ``"derived_metrics"`` keys.  If None, gates that
            require derived metrics will SKIP.
        sector: Optional sector name for margin range lookup (e.g. ``"Software"``,
            ``"Retail"``).  Falls back to ``"default"`` if None or unrecognised.

    Returns:
        Dict with keys:
            - ``"status"``: ``"PASS"`` | ``"PARTIAL"`` | ``"FAIL"``
            - ``"confidence_score"``: float in [0, 100]
            - ``"gates"``: list of per-gate result dicts
            - ``"warnings"``: human-readable warning strings
            - ``"faltantes_criticos"``: missing critical derived items
            - ``"limitaciones"``: data limitation strings
    """
    derived = derived or {}
    ttm: dict = derived.get("ttm") or {}
    derived_metrics: dict = derived.get("derived_metrics") or {}

    annual, _quarterly, _semestral = _parse_periods(extraction_result)

    gate_funcs: dict[str, Any] = {
        "BALANCE_IDENTITY":  lambda: _gate_balance_identity(annual),
        "CASHFLOW_IDENTITY": lambda: _gate_cashflow_identity(annual),
        "UNIDADES_SANITY":   lambda: _gate_unidades_sanity(annual),
        "EV_SANITY":         lambda: _gate_ev_sanity(derived_metrics),
        "MARGIN_SANITY":     lambda: _gate_margin_sanity(derived_metrics, sector),
        "TTM_SANITY":        lambda: _gate_ttm_sanity(ttm, annual),
        "TTM_CONSECUTIVE":   lambda: _gate_ttm_consecutive(ttm),
        "RECENCY_SANITY":    lambda: _gate_recency_sanity(annual),
        "DATA_COMPLETENESS": lambda: _gate_data_completeness(extraction_result),
    }

    gates: list[dict] = []
    warnings: list[str] = []

    for gate_def in _GATE_DEFS:
        name = gate_def["name"]
        func = gate_funcs.get(name)
        if func is None:
            continue
        gate_result = func()
        gate_result["critical"] = gate_def["critical"]
        gates.append(gate_result)

        if gate_result["status"] == "WARNING":
            warnings.append(name + ": " + gate_result.get("note", ""))
        elif gate_result["status"] == "FAIL":
            warnings.append("CRITICAL -- " + name + ": " + gate_result.get("note", ""))

    overall = _overall_status(gates)
    confidence = _calc_confidence(gates)

    return {
        "status": overall,
        "confidence_score": confidence,
        "gates": gates,
        "warnings": warnings,
        "faltantes_criticos": _find_faltantes_criticos(derived_metrics),
        "limitaciones": _find_limitaciones(ttm, annual),
    }
