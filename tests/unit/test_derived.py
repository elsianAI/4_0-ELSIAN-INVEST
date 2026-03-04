"""tests/unit/test_derived.py — Unit tests for elsian.calculate.derived.

Coverage:
    TTM strategies (4Q sum, semestral, FY0 fallback, no_disponible)
    Null propagation (FCF, EV, margins, returns, multiples, per-share)
    Edge cases (negative capex, zero revenue, zero equity, missing shares)
    Helper functions (_period_type, _period_sort_key, _get_val, etc.)
"""
from __future__ import annotations

import pytest

from elsian.calculate.derived import (
    _fcf,
    _ev,
    _margins,
    _returns,
    _multiples,
    _per_share,
    _safe_div,
    _safe_add,
    _safe_sub,
    _period_type,
    _period_sort_key,
    _get_val,
    _find_eligible_fy0,
    _quarters_are_consecutive,
    _build_synthetic_q4,
    _ttm_semestral,
    calculate,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_er(periods: dict) -> dict:
    """Wrap periods into a minimal extraction_result dict."""
    return {"periods": periods}


def _fy(year: int, fields: dict) -> dict:
    """Build a single annual period entry."""
    return {
        f"FY{year}": {
            "tipo_periodo": "anual",
            "fecha_fin": f"{year}-12-31",
            "fields": fields,
        }
    }


def _q(year: int, q: int, fields: dict) -> dict:
    """Build a single quarterly period entry."""
    month = q * 3
    import calendar as cal
    day = cal.monthrange(year, month)[1]
    return {
        f"Q{q}-{year}": {
            "tipo_periodo": "trimestral",
            "fecha_fin": f"{year}-{month:02d}-{day:02d}",
            "fields": fields,
        }
    }


def _h1(year: int, fields: dict) -> dict:
    return {
        f"H1-{year}": {
            "tipo_periodo": "semestral",
            "fecha_fin": f"{year}-06-30",
            "fields": fields,
        }
    }


def _fval(v: float) -> dict:
    """Wrap a float into a 4.0 field value dict."""
    return {"value": v}


# ── 1. _period_type ──────────────────────────────────────────────────────────

class TestPeriodType:
    def test_annual(self):
        assert _period_type("FY2024") == "annual"

    def test_quarterly(self):
        assert _period_type("Q3-2023") == "quarterly"

    def test_semestral(self):
        assert _period_type("H1-2024") == "semestral"
        assert _period_type("H2-2024") == "semestral"

    def test_unknown(self):
        assert _period_type("2024") == "unknown"
        assert _period_type("TTM") == "unknown"


# ── 2. _period_sort_key ──────────────────────────────────────────────────────

class TestPeriodSortKey:
    def test_annual_key(self):
        assert _period_sort_key("FY2024") == "2024-12-31"

    def test_quarterly_key(self):
        assert _period_sort_key("Q2-2024") == "2024-06-30"
        assert _period_sort_key("Q4-2023") == "2023-12-31"

    def test_semestral_h1(self):
        assert _period_sort_key("H1-2024") == "2024-06-30"

    def test_semestral_h2(self):
        assert _period_sort_key("H2-2024") == "2024-12-31"

    def test_fecha_fin_takes_precedence(self):
        assert _period_sort_key("FY2024", "2024-09-30") == "2024-09-30"


# ── 3. _get_val ──────────────────────────────────────────────────────────────

class TestGetVal:
    def test_dict_wrapper(self):
        assert _get_val({"ingresos": {"value": 1000}}, "ingresos") == 1000.0

    def test_raw_number(self):
        assert _get_val({"capex": -500}, "capex") == -500.0

    def test_missing_field(self):
        assert _get_val({}, "ingresos") is None

    def test_boolean_rejected(self):
        assert _get_val({"flag": True}, "flag") is None

    def test_none_value(self):
        assert _get_val({"ingresos": None}, "ingresos") is None


# ── 4. _safe_div / _safe_add / _safe_sub ─────────────────────────────────────

class TestMathHelpers:
    def test_safe_div_normal(self):
        assert _safe_div(100.0, 4.0) == 25.0

    def test_safe_div_none_numerator(self):
        assert _safe_div(None, 4.0) is None

    def test_safe_div_none_denominator(self):
        assert _safe_div(100.0, None) is None

    def test_safe_div_zero_denominator(self):
        assert _safe_div(100.0, 0.0) is None

    def test_safe_div_negative_denominator(self):
        assert _safe_div(100.0, -5.0) is None

    def test_safe_div_multiply_100(self):
        assert _safe_div(1.0, 4.0, multiply_100=True) == 25.0

    def test_safe_add_normal(self):
        assert _safe_add(100.0, 200.0) == 300.0

    def test_safe_add_none(self):
        assert _safe_add(100.0, None) is None

    def test_safe_sub_normal(self):
        assert _safe_sub(500.0, 300.0) == 200.0

    def test_safe_sub_none(self):
        assert _safe_sub(None, 100.0) is None


# ── 5. _fcf ──────────────────────────────────────────────────────────────────

class TestFcf:
    def test_positive_capex_stored_negative(self):
        # capex convention: negative in filing -> |capex| = 500
        assert _fcf(1000.0, -500.0) == pytest.approx(500.0)

    def test_positive_capex_stored_positive(self):
        # Some filings show capex as positive
        assert _fcf(1000.0, 500.0) == pytest.approx(500.0)

    def test_null_cfo_propagates(self):
        assert _fcf(None, -500.0) is None

    def test_null_capex_propagates(self):
        assert _fcf(1000.0, None) is None

    def test_negative_fcf(self):
        # CFO < |capex| -> negative FCF
        assert _fcf(100.0, -800.0) == pytest.approx(-700.0)


# ── 6. _ev ───────────────────────────────────────────────────────────────────

class TestEv:
    def test_normal(self):
        # EV = 5000 + 1000 - 500 = 5500
        assert _ev(5000.0, 1000.0, 500.0) == pytest.approx(5500.0)

    def test_null_market_cap_propagates(self):
        assert _ev(None, 1000.0, 500.0) is None

    def test_null_debt_propagates(self):
        assert _ev(5000.0, None, 500.0) is None

    def test_null_cash_propagates(self):
        assert _ev(5000.0, 1000.0, None) is None


# ── 7. _margins ──────────────────────────────────────────────────────────────

class TestMargins:
    def test_gross_margin_from_gross_profit(self):
        r = _margins(1000.0, 600.0, None, None, None, None)
        assert r["gross_margin"] == pytest.approx(60.0)

    def test_gross_margin_from_cost_of_revenue(self):
        r = _margins(1000.0, None, 400.0, None, None, None)
        assert r["gross_margin"] == pytest.approx(60.0)

    def test_operating_margin(self):
        r = _margins(1000.0, None, None, 150.0, None, None)
        assert r["operating_margin"] == pytest.approx(15.0)

    def test_net_margin(self):
        r = _margins(1000.0, None, None, None, 80.0, None)
        assert r["net_margin"] == pytest.approx(8.0)

    def test_fcf_margin(self):
        r = _margins(1000.0, None, None, None, None, 70.0)
        assert r["fcf_margin"] == pytest.approx(7.0)

    def test_zero_revenue_returns_all_none(self):
        r = _margins(0.0, 600.0, None, 150.0, 80.0, 70.0)
        assert all(v is None for v in r.values())

    def test_null_revenue_returns_all_none(self):
        r = _margins(None, 600.0, None, 150.0, 80.0, 70.0)
        assert all(v is None for v in r.values())

    def test_null_individual_metric_propagates(self):
        r = _margins(1000.0, None, None, None, None, None)
        assert r["gross_margin"] is None
        assert r["operating_margin"] is None


# ── 8. _returns ──────────────────────────────────────────────────────────────

class TestReturns:
    def test_roic(self):
        # NOPAT = 100 * 0.79 = 79; IC = 500; ROIC = 15.8%
        r = _returns(100.0, 0.21, 500.0, None, None, None)
        assert r["roic"] == pytest.approx(15.8)

    def test_roe(self):
        # ROE = 80 / 400 * 100 = 20%
        r = _returns(None, 0.21, None, 80.0, 400.0, None)
        assert r["roe"] == pytest.approx(20.0)

    def test_roa(self):
        # ROA = 80 / 1000 * 100 = 8%
        r = _returns(None, 0.21, None, 80.0, None, 1000.0)
        assert r["roa"] == pytest.approx(8.0)

    def test_null_ebit_roic_none(self):
        r = _returns(None, 0.21, 500.0, None, None, None)
        assert r["roic"] is None

    def test_zero_equity_roe_none(self):
        r = _returns(None, 0.21, None, 80.0, 0.0, None)
        assert r["roe"] is None

    def test_negative_equity_roe_none(self):
        r = _returns(None, 0.21, None, 80.0, -100.0, None)
        assert r["roe"] is None


# ── 9. _multiples ────────────────────────────────────────────────────────────

class TestMultiples:
    def test_ev_ebit(self):
        r = _multiples(5500.0, 100.0, None, None)
        assert r["ev_ebit"] == pytest.approx(55.0)

    def test_ev_fcf(self):
        r = _multiples(5500.0, None, 200.0, None)
        assert r["ev_fcf"] == pytest.approx(27.5)

    def test_p_fcf(self):
        r = _multiples(None, None, 200.0, 4000.0)
        assert r["p_fcf"] == pytest.approx(20.0)

    def test_negative_ebit_gives_none(self):
        r = _multiples(5500.0, -100.0, None, None)
        assert r["ev_ebit"] is None

    def test_null_ev_gives_none(self):
        r = _multiples(None, 100.0, None, None)
        assert r["ev_ebit"] is None

    def test_fcf_yield(self):
        # FCF=200, mcap=4000 -> yield = 5%
        r = _multiples(None, None, 200.0, 4000.0)
        assert r["fcf_yield"] == pytest.approx(5.0)


# ── 10. _per_share ───────────────────────────────────────────────────────────

class TestPerShare:
    def test_eps(self):
        r = _per_share(80.0, None, None, 40.0)
        assert r["eps"] == pytest.approx(2.0)

    def test_fcf_per_share(self):
        r = _per_share(None, 120.0, None, 40.0)
        assert r["fcf_per_share"] == pytest.approx(3.0)

    def test_bv_per_share(self):
        r = _per_share(None, None, 400.0, 40.0)
        assert r["bv_per_share"] == pytest.approx(10.0)

    def test_null_shares_all_none(self):
        r = _per_share(80.0, 120.0, 400.0, None)
        assert all(v is None for v in r.values())

    def test_zero_shares_all_none(self):
        r = _per_share(80.0, 120.0, 400.0, 0.0)
        assert all(v is None for v in r.values())


# ── 11. _find_eligible_fy0 ───────────────────────────────────────────────────

class TestFindEligibleFy0:
    def _entry(self, key: str, fields: dict) -> dict:
        return {"period_key": key, "fecha_fin": None, "tipo_periodo": "anual", "fields": fields}

    def test_returns_most_recent(self):
        full_fields = {
            "ingresos": _fval(1000), "ebit": _fval(100),
            "net_income": _fval(80), "cfo": _fval(90), "capex": _fval(-50),
        }
        a2023 = self._entry("FY2023", full_fields)
        a2024 = self._entry("FY2024", full_fields)
        result = _find_eligible_fy0([a2023, a2024])
        assert result["period_key"] == "FY2024"

    def test_missing_ingresos_excluded(self):
        partial = {
            "ebit": _fval(100), "net_income": _fval(80),
            "cfo": _fval(90), "capex": _fval(-50),
        }
        a = self._entry("FY2024", partial)
        assert _find_eligible_fy0([a]) is None

    def test_too_few_fields_excluded(self):
        # Only ingresos populated (< 3 key fields)
        a = self._entry("FY2024", {"ingresos": _fval(1000)})
        assert _find_eligible_fy0([a]) is None

    def test_exactly_3_key_fields_accepted(self):
        fields = {
            "ingresos": _fval(1000),
            "ebit": _fval(100),
            "net_income": _fval(80),
            "cfo": _fval(90),
        }
        a = self._entry("FY2024", fields)
        assert _find_eligible_fy0([a]) is not None


# ── 12. _quarters_are_consecutive ────────────────────────────────────────────

class TestQuartersAreConsecutive:
    def _qentry(self, key: str) -> dict:
        return {"period_key": key, "fecha_fin": None, "fields": {}}

    def test_four_consecutive(self):
        qs = [self._qentry(k) for k in ("Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024")]
        assert _quarters_are_consecutive(qs) is True

    def test_non_consecutive_cross_era(self):
        qs = [self._qentry(k) for k in ("Q1-2022", "Q2-2024", "Q3-2024", "Q4-2024")]
        assert _quarters_are_consecutive(qs) is False

    def test_one_quarter_is_false(self):
        qs = [self._qentry("Q1-2024")]
        assert _quarters_are_consecutive(qs) is False


# ── 13. TTM via calculate() — 4Q strategy ────────────────────────────────────

class TestCalculateTtm4Q:
    def _build_er_with_4q(self, vals: list[float]) -> dict:
        """Build extraction_result with FY2023 + 4 quarters of 2024."""
        import calendar as cal

        periods: dict = {}
        # Annual anchor (not used in 4Q TTM, but present in the extraction_result)
        periods["FY2023"] = {
            "tipo_periodo": "anual", "fecha_fin": "2023-12-31",
            "fields": {
                "ingresos": _fval(800.0), "ebit": _fval(80.0),
                "net_income": _fval(64.0), "cfo": _fval(96.0), "capex": _fval(-40.0),
            },
        }
        # 4 complete quarters
        for q_num, v in zip(range(1, 5), vals):
            month = q_num * 3
            day = cal.monthrange(2024, month)[1]
            periods[f"Q{q_num}-2024"] = {
                "tipo_periodo": "trimestral",
                "fecha_fin": f"2024-{month:02d}-{day:02d}",
                "fields": {
                    "ingresos": _fval(v), "ebit": _fval(v * 0.1),
                    "net_income": _fval(v * 0.08), "cfo": _fval(v * 0.12),
                    "capex": _fval(-v * 0.05),
                },
            }
        return {"periods": periods}

    def test_ttm_method_is_4q(self):
        er = self._build_er_with_4q([250.0, 260.0, 270.0, 280.0])
        out = calculate(er)
        assert out["ttm"]["metodo"] == "suma_4_trimestres"

    def test_ttm_ingresos_sum(self):
        er = self._build_er_with_4q([250.0, 260.0, 270.0, 280.0])
        out = calculate(er)
        assert out["ttm"]["ingresos"] == pytest.approx(1060.0)

    def test_derived_metrics_present(self):
        er = self._build_er_with_4q([250.0, 260.0, 270.0, 280.0])
        out = calculate(er)
        dm = out["derived_metrics"]
        assert dm["operating_margin_pct"] is not None
        assert dm["fcf"] is not None
        assert dm["periodo_base"] == "suma_4_trimestres"


# ── 14. TTM via calculate() — FY0 fallback ───────────────────────────────────

class TestCalculateFy0Fallback:
    def _er(self) -> dict:
        fields = {
            "ingresos": _fval(1000), "ebit": _fval(100),
            "net_income": _fval(80), "cfo": _fval(120), "capex": _fval(-50),
            "total_assets": _fval(2000), "total_equity": _fval(800),
            "total_debt": _fval(400), "cash_and_equivalents": _fval(200),
        }
        return _make_er({
            "FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}
        })

    def test_ttm_method_is_fy0_fallback(self):
        out = calculate(self._er())
        assert out["ttm"]["metodo"] == "FY0_fallback"

    def test_fcf_computed(self):
        out = calculate(self._er())
        # FCF = CFO - |capex| = 120 - 50 = 70
        assert out["derived_metrics"]["fcf"] == pytest.approx(70.0)

    def test_net_debt(self):
        out = calculate(self._er())
        # net_debt = debt - cash = 400 - 200 = 200
        assert out["derived_metrics"]["net_debt"] == pytest.approx(200.0)

    def test_operating_margin(self):
        out = calculate(self._er())
        # 100/1000 * 100 = 10%
        assert out["derived_metrics"]["operating_margin_pct"] == pytest.approx(10.0)

    def test_roic(self):
        out = calculate(self._er())
        # IC = debt + equity = 400 + 800 = 1200
        # NOPAT = 100 * 0.79 = 79
        # ROIC = 79/1200 * 100 = 6.5833...
        assert out["derived_metrics"]["roic_pct"] == pytest.approx(79.0 / 1200.0 * 100, rel=1e-3)

    def test_roe(self):
        out = calculate(self._er())
        # ROE = 80/800 * 100 = 10%
        assert out["derived_metrics"]["roe_pct"] == pytest.approx(10.0)

    def test_roa(self):
        out = calculate(self._er())
        # ROA = 80/2000 * 100 = 4%
        assert out["derived_metrics"]["roa_pct"] == pytest.approx(4.0)


# ── 15. TTM via calculate() — no_disponible ──────────────────────────────────

class TestCalculateNoDisponible:
    def test_empty_extraction_result(self):
        out = calculate({"periods": {}})
        assert out["ttm"]["metodo"] == "no_disponible"
        dm = out["derived_metrics"]
        assert dm["fcf"] is None
        assert dm["ev"] is None
        assert dm["roic_pct"] is None
        assert dm["periodo_base"] == "no_disponible"


# ── 16. Null propagation throughout calculate() ──────────────────────────────

class TestNullPropagation:
    def test_ev_null_when_no_market_data(self):
        fields = {
            "ingresos": _fval(1000), "ebit": _fval(100),
            "net_income": _fval(80), "cfo": _fval(120), "capex": _fval(-50),
            "total_debt": _fval(400), "cash_and_equivalents": _fval(200),
        }
        er = _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})
        out = calculate(er)
        # No market_data -> market_cap is None -> EV is None
        assert out["derived_metrics"]["ev"] is None
        assert out["derived_metrics"]["ev_ebit"] is None

    def test_per_share_null_without_shares(self):
        fields = {"ingresos": _fval(1000), "ebit": _fval(100), "net_income": _fval(80),
                  "cfo": _fval(120), "capex": _fval(-50)}
        er = _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})
        out = calculate(er)
        assert out["derived_metrics"]["eps"] is None

    def test_fcf_null_when_capex_missing(self):
        fields = {"ingresos": _fval(1000), "ebit": _fval(100),
                  "net_income": _fval(80), "cfo": _fval(120)}
        er = _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})
        out = calculate(er)
        assert out["derived_metrics"]["fcf"] is None

    def test_gross_margin_null_when_no_gross_data(self):
        fields = {"ingresos": _fval(1000), "ebit": _fval(100),
                  "net_income": _fval(80), "cfo": _fval(120), "capex": _fval(-50)}
        er = _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})
        out = calculate(er)
        assert out["derived_metrics"]["gross_margin_pct"] is None


# ── 17. Market data input to calculate() ─────────────────────────────────────

class TestMarketDataInput:
    def _er_with_bs(self) -> dict:
        fields = {
            "ingresos": _fval(1000), "ebit": _fval(100),
            "net_income": _fval(80), "cfo": _fval(120), "capex": _fval(-50),
            "total_assets": _fval(2000), "total_equity": _fval(800),
            "total_debt": _fval(400), "cash_and_equivalents": _fval(200),
        }
        return _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})

    def test_ev_with_market_cap(self):
        er = self._er_with_bs()
        out = calculate(er, {"market_cap": 5000.0})
        # EV = 5000 + 400 - 200 = 5200
        assert out["derived_metrics"]["ev"] == pytest.approx(5200.0)

    def test_multiples_with_market_cap(self):
        er = self._er_with_bs()
        out = calculate(er, {"market_cap": 5000.0})
        dm = out["derived_metrics"]
        # EV/EBIT = 5200/100 = 52
        assert dm["ev_ebit"] == pytest.approx(52.0)

    def test_eps_with_shares(self):
        er = self._er_with_bs()
        out = calculate(er, {"market_cap": 5000.0, "shares_outstanding": 40.0})
        # EPS = 80/40 = 2.0
        assert out["derived_metrics"]["eps"] == pytest.approx(2.0)


# ── 18. Gross margin derived from cost_of_revenue ────────────────────────────

class TestGrossMarginFromCogs:
    def test_gross_margin_from_cost_of_revenue(self):
        fields = {
            "ingresos": _fval(1000), "cost_of_revenue": _fval(400),
            "ebit": _fval(100), "net_income": _fval(80),
            "cfo": _fval(120), "capex": _fval(-50),
        }
        er = _make_er({"FY2024": {"tipo_periodo": "anual", "fecha_fin": "2024-12-31", "fields": fields}})
        out = calculate(er)
        # gross_margin = (1000-400)/1000 * 100 = 60%
        assert out["derived_metrics"]["gross_margin_pct"] == pytest.approx(60.0)


# ── 19. Synthetic Q4 via _build_synthetic_q4 ─────────────────────────────────

class TestSyntheticQ4:
    def _annual_entry(self, year: int, ingresos: float) -> dict:
        return {
            "period_key": f"FY{year}", "fecha_fin": f"{year}-12-31",
            "tipo_periodo": "anual",
            "fields": {"ingresos": _fval(ingresos)},
        }

    def _q_entry(self, year: int, q: int, ingresos: float) -> dict:
        month = q * 3
        import calendar as cal
        day = cal.monthrange(year, month)[1]
        return {
            "period_key": f"Q{q}-{year}",
            "fecha_fin": f"{year}-{month:02d}-{day:02d}",
            "tipo_periodo": "trimestral",
            "fields": {"ingresos": _fval(ingresos)},
        }

    def test_synthetic_q4_created(self):
        annual = [self._annual_entry(2024, 1000.0)]
        qs = [
            self._q_entry(2024, 1, 200.0),
            self._q_entry(2024, 2, 250.0),
            self._q_entry(2024, 3, 230.0),
        ]
        result = _build_synthetic_q4(annual, qs)
        keys = [e["period_key"] for e in result]
        assert "Q4-2024" in keys
        q4 = next(e for e in result if e["period_key"] == "Q4-2024")
        assert _get_val(q4["fields"], "ingresos") == pytest.approx(320.0)

    def test_no_synthetic_when_q4_exists(self):
        annual = [self._annual_entry(2024, 1000.0)]
        qs = [
            self._q_entry(2024, 1, 200.0),
            self._q_entry(2024, 2, 250.0),
            self._q_entry(2024, 3, 230.0),
            self._q_entry(2024, 4, 320.0),
        ]
        result = _build_synthetic_q4(annual, qs)
        synth = [e for e in result if e.get("_synthetic_q4")]
        assert synth == []


# ── 20. _ttm_semestral ───────────────────────────────────────────────────────

class TestTtmSemestral:
    def _a(self, year: int, ingresos: float, ebit: float, cfo: float) -> dict:
        return {
            "period_key": f"FY{year}", "fecha_fin": f"{year}-12-31",
            "tipo_periodo": "anual",
            "fields": {
                "ingresos": _fval(ingresos),
                "ebit": _fval(ebit),
                "cfo": _fval(cfo),
            },
        }

    def _h1(self, year: int, ingresos: float, ebit: float, cfo: float) -> dict:
        return {
            "period_key": f"H1-{year}", "fecha_fin": f"{year}-06-30",
            "tipo_periodo": "semestral",
            "fields": {
                "ingresos": _fval(ingresos),
                "ebit": _fval(ebit),
                "cfo": _fval(cfo),
            },
        }

    def test_semestral_ttm_computed(self):
        # TTM = FY2023 + H1-2024 - H1-2023
        # ingresos = 1000 + 550 - 500 = 1050
        annual = [self._a(2023, 1000.0, 100.0, 120.0)]
        sem = [self._h1(2023, 500.0, 50.0, 60.0), self._h1(2024, 550.0, 55.0, 65.0)]
        result = _ttm_semestral(annual, sem)
        assert result is not None
        assert result["metodo"] == "semestral_FY_H1"
        assert result["ingresos"] == pytest.approx(1050.0)

    def test_returns_none_when_ebit_missing(self):
        annual = [self._a(2023, 1000.0, 100.0, 120.0)]
        # H1 entries are missing ebit
        sem = [
            {"period_key": "H1-2023", "fecha_fin": "2023-06-30", "tipo_periodo": "semestral",
             "fields": {"ingresos": _fval(500.0), "cfo": _fval(60.0)}},
            {"period_key": "H1-2024", "fecha_fin": "2024-06-30", "tipo_periodo": "semestral",
             "fields": {"ingresos": _fval(550.0), "cfo": _fval(65.0)}},
        ]
        assert _ttm_semestral(annual, sem) is None
