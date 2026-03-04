"""Tests for elsian.evaluate.validation (BL-020).

Covers all 9 gates, helpers, scoring logic, and the public validate() API.
Total tests: 60+
"""

from __future__ import annotations

import pytest

from elsian.evaluate.validation import (
    SECTOR_MARGINS,
    _CANONICAL_FIELDS,
    _GATE_DEFS,
    _calc_confidence,
    _extract_year_from_period,
    _find_faltantes_criticos,
    _find_limitaciones,
    _gate_balance_identity,
    _gate_cashflow_identity,
    _gate_data_completeness,
    _gate_ev_sanity,
    _gate_margin_sanity,
    _gate_recency_sanity,
    _gate_ttm_consecutive,
    _gate_ttm_sanity,
    _gate_unidades_sanity,
    _get_val,
    _num,
    _overall_status,
    _parse_periods,
    _period_sort_key,
    _period_type,
    _sorted_annual,
    validate,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_annual_entry(period_key: str, /, **fields) -> dict:
    """Build a minimal annual period entry dict."""
    return {"period_key": period_key, "fecha_fin": None, "tipo_periodo": "anual", "fields": fields}


def _make_er(periods: dict) -> dict:
    """Wrap periods dict into minimal extraction_result shape."""
    return {"periods": periods}


def _fy(year: int, **fields) -> dict:
    """Return a single annual period in extraction_result['periods'] format."""
    key = f"FY{year}"
    return {key: {"fecha_fin": f"{year}-12-31", "tipo_periodo": "anual", "fields": fields}}


def _val(v) -> dict:
    """Return 4.0 value wrapper."""
    return {"value": v}


# ---------------------------------------------------------------------------
# _num()
# ---------------------------------------------------------------------------

class TestNum:
    def test_integer(self):
        assert _num(42) == 42.0

    def test_float(self):
        assert _num(3.14) == pytest.approx(3.14)

    def test_negative(self):
        assert _num(-100) == -100.0

    def test_zero(self):
        assert _num(0) == 0.0

    def test_bool_rejected(self):
        assert _num(True) is None
        assert _num(False) is None

    def test_string_rejected(self):
        assert _num("100") is None

    def test_none_rejected(self):
        assert _num(None) is None

    def test_dict_rejected(self):
        assert _num({"value": 5}) is None


# ---------------------------------------------------------------------------
# _get_val()
# ---------------------------------------------------------------------------

class TestGetVal:
    def test_raw_number(self):
        assert _get_val({"revenue": 1000}, "revenue") == 1000.0

    def test_wrapper_dict(self):
        assert _get_val({"revenue": {"value": 1000}}, "revenue") == 1000.0

    def test_missing_field(self):
        assert _get_val({}, "revenue") is None

    def test_none_value(self):
        assert _get_val({"revenue": None}, "revenue") is None

    def test_bool_in_wrapper_rejected(self):
        assert _get_val({"flag": {"value": True}}, "flag") is None

    def test_negative_number(self):
        assert _get_val({"capex": -500}, "capex") == -500.0

    def test_zero(self):
        assert _get_val({"x": 0}, "x") == 0.0

    def test_nested_wrapper_no_value_key(self):
        assert _get_val({"x": {"amount": 100}}, "x") is None


# ---------------------------------------------------------------------------
# _period_type()
# ---------------------------------------------------------------------------

class TestPeriodType:
    def test_annual(self):
        assert _period_type("FY2024") == "annual"
        assert _period_type("FY2020") == "annual"

    def test_quarterly(self):
        assert _period_type("Q1-2024") == "quarterly"
        assert _period_type("Q4-2023") == "quarterly"

    def test_semestral(self):
        assert _period_type("H1-2024") == "semestral"
        assert _period_type("H2-2023") == "semestral"

    def test_unknown(self):
        assert _period_type("FY") == "unknown"
        assert _period_type("2024") == "unknown"
        assert _period_type("Q5-2024") == "unknown"


# ---------------------------------------------------------------------------
# _period_sort_key()
# ---------------------------------------------------------------------------

class TestPeriodSortKey:
    def test_fecha_fin_overrides(self):
        assert _period_sort_key("FY2024", "2024-09-30") == "2024-09-30"

    def test_fy_default(self):
        assert _period_sort_key("FY2022") == "2022-12-31"

    def test_q1(self):
        assert _period_sort_key("Q1-2024") == "2024-03-31"

    def test_q4(self):
        assert _period_sort_key("Q4-2023") == "2023-12-31"

    def test_h1(self):
        assert _period_sort_key("H1-2024") == "2024-06-30"

    def test_h2(self):
        assert _period_sort_key("H2-2023") == "2023-12-31"


# ---------------------------------------------------------------------------
# _parse_periods() and _sorted_annual()
# ---------------------------------------------------------------------------

class TestParsePeriods:
    def test_splits_by_type(self):
        er = _make_er({
            "FY2023": {"fecha_fin": None, "tipo_periodo": "anual", "fields": {}},
            "Q1-2024": {"fecha_fin": None, "tipo_periodo": "trimestral", "fields": {}},
            "H2-2023": {"fecha_fin": None, "tipo_periodo": "semestral", "fields": {}},
        })
        annual, quarterly, semestral = _parse_periods(er)
        assert len(annual) == 1
        assert len(quarterly) == 1
        assert len(semestral) == 1

    def test_empty_periods(self):
        annual, quarterly, semestral = _parse_periods({"periods": {}})
        assert annual == quarterly == semestral == []

    def test_sorted_annual_chronological(self):
        er = _make_er({
            "FY2022": {"fecha_fin": "2022-12-31", "tipo_periodo": "anual", "fields": {}},
            "FY2020": {"fecha_fin": "2020-12-31", "tipo_periodo": "anual", "fields": {}},
            "FY2021": {"fecha_fin": "2021-12-31", "tipo_periodo": "anual", "fields": {}},
        })
        annual, _, _ = _parse_periods(er)
        sorted_a = _sorted_annual(annual)
        keys = [e["period_key"] for e in sorted_a]
        assert keys == ["FY2020", "FY2021", "FY2022"]


# ---------------------------------------------------------------------------
# Gate N1: BALANCE_IDENTITY
# ---------------------------------------------------------------------------

class TestGateBalanceIdentity:
    def test_pass_balanced(self):
        annual = [_make_annual_entry("FY2024", total_assets=1000, total_liabilities=600, total_equity=400)]
        result = _gate_balance_identity(annual)
        assert result["status"] == "PASS"

    def test_fail_imbalanced(self):
        annual = [_make_annual_entry("FY2024", total_assets=1000, total_liabilities=700, total_equity=400)]
        result = _gate_balance_identity(annual)
        assert result["status"] == "FAIL"

    def test_skip_no_bs_data(self):
        annual = [_make_annual_entry("FY2024", ingresos=1000)]
        result = _gate_balance_identity(annual)
        assert result["status"] == "SKIP"

    def test_skip_empty(self):
        result = _gate_balance_identity([])
        assert result["status"] == "SKIP"

    def test_imputes_liabilities(self):
        annual = [_make_annual_entry("FY2024", total_assets=1000, total_equity=400)]
        result = _gate_balance_identity(annual)
        # Imputes liabilities=600, checks Identity -> PASS
        assert result["status"] == "PASS"
        assert "imputed" in result["note"]

    def test_imputes_equity(self):
        annual = [_make_annual_entry("FY2024", total_assets=1000, total_liabilities=600)]
        result = _gate_balance_identity(annual)
        assert result["status"] == "PASS"

    def test_fail_only_one_bs_field(self):
        annual = [_make_annual_entry("FY2024", total_assets=1000)]
        result = _gate_balance_identity(annual)
        assert result["status"] == "FAIL"

    def test_wrapper_format(self):
        annual = [_make_annual_entry("FY2024",
            total_assets=_val(1000),
            total_liabilities=_val(600),
            total_equity=_val(400))]
        result = _gate_balance_identity(annual)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate N2: CASHFLOW_IDENTITY
# ---------------------------------------------------------------------------

class TestGateCashflowIdentity:
    def test_skip_no_annual(self):
        result = _gate_cashflow_identity([])
        assert result["status"] == "SKIP"

    def test_skip_missing_cfi_cff(self):
        annual = [_make_annual_entry("FY2024", cfo=500)]
        result = _gate_cashflow_identity(annual)
        assert result["status"] == "SKIP"

    def test_skip_no_delta_cash(self):
        annual = [_make_annual_entry("FY2024", cfo=500, cfi=-100, cff=-200)]
        result = _gate_cashflow_identity(annual)
        assert result["status"] == "SKIP"

    def test_pass_balanced(self):
        annual = [_make_annual_entry("FY2024", cfo=500, cfi=-100, cff=-200, delta_cash=200)]
        result = _gate_cashflow_identity(annual)
        assert result["status"] == "PASS"

    def test_fail_large_deviation(self):
        # Use large numbers so rel_diff dominates over absolute_tolerance threshold
        annual = [_make_annual_entry("FY2024", cfo=500_000, cfi=-100_000, cff=-200_000, delta_cash=1_000_000)]
        result = _gate_cashflow_identity(annual)
        assert result["status"] == "FAIL"

    def test_gate_is_critical(self):
        gate_def = next(g for g in _GATE_DEFS if g["name"] == "CASHFLOW_IDENTITY")
        assert gate_def["critical"] is True


# ---------------------------------------------------------------------------
# Gate N3: UNIDADES_SANITY
# ---------------------------------------------------------------------------

class TestGateUnidadesSanity:
    def test_pass_normal_growth(self):
        a = [
            _make_annual_entry("FY2022", ingresos=1000, ebit=100, net_income=80, cfo=90),
            _make_annual_entry("FY2023", ingresos=1100, ebit=110, net_income=88, cfo=99),
        ]
        result = _gate_unidades_sanity(a)
        assert result["status"] == "PASS"

    def test_fail_1000x_jump(self):
        a = [
            _make_annual_entry("FY2022", ingresos=1000, ebit=100, net_income=80, cfo=90),
            _make_annual_entry("FY2023", ingresos=1_000_000, ebit=100, net_income=80, cfo=90),
        ]
        result = _gate_unidades_sanity(a)
        assert result["status"] == "FAIL"

    def test_fail_inverse_1000x(self):
        a = [
            _make_annual_entry("FY2022", ingresos=1_000_000, ebit=100, net_income=80, cfo=90),
            _make_annual_entry("FY2023", ingresos=1000, ebit=100, net_income=80, cfo=90),
        ]
        result = _gate_unidades_sanity(a)
        assert result["status"] == "FAIL"

    def test_pass_single_period(self):
        a = [_make_annual_entry("FY2024", ingresos=1000)]
        result = _gate_unidades_sanity(a)
        assert result["status"] == "PASS"

    def test_10x_is_not_flagged(self):
        # 10x is sanity.py's territory; this gate only flags 1000x
        a = [
            _make_annual_entry("FY2022", ingresos=1000, ebit=100, net_income=80, cfo=90),
            _make_annual_entry("FY2023", ingresos=10_000, ebit=100, net_income=80, cfo=90),
        ]
        result = _gate_unidades_sanity(a)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate N4: EV_SANITY
# ---------------------------------------------------------------------------

class TestGateEvSanity:
    def test_skip_no_ev(self):
        result = _gate_ev_sanity({})
        assert result["status"] == "SKIP"

    def test_skip_ev_none(self):
        result = _gate_ev_sanity({"ev": None})
        assert result["status"] == "SKIP"

    def test_pass_positive_ev(self):
        result = _gate_ev_sanity({"ev": 1_000_000})
        assert result["status"] == "PASS"

    def test_warning_negative_ev(self):
        result = _gate_ev_sanity({"ev": -50_000})
        assert result["status"] == "WARNING"


# ---------------------------------------------------------------------------
# Gate N5: MARGIN_SANITY
# ---------------------------------------------------------------------------

class TestGateMarginSanity:
    def test_pass_software_typical(self):
        dm = {"gross_margin_pct": 72, "operating_margin_pct": 15, "net_margin_pct": 10}
        result = _gate_margin_sanity(dm, "Software")
        assert result["status"] == "PASS"

    def test_warning_outlier_gross(self):
        dm = {"gross_margin_pct": -50, "operating_margin_pct": 10, "net_margin_pct": 5}
        result = _gate_margin_sanity(dm, "default")
        assert result["status"] == "WARNING"

    def test_fallback_to_default_sector(self):
        dm = {"gross_margin_pct": 50, "operating_margin_pct": 10, "net_margin_pct": 5}
        result = _gate_margin_sanity(dm, "UnknownSector")
        assert result["status"] == "PASS"

    def test_pass_no_margins(self):
        result = _gate_margin_sanity({}, None)
        assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate N6: TTM_SANITY
# ---------------------------------------------------------------------------

class TestGateTtmSanity:
    def test_skip_no_ttm(self):
        result = _gate_ttm_sanity({}, [])
        assert result["status"] == "SKIP"

    def test_skip_no_disponible(self):
        result = _gate_ttm_sanity({"metodo": "no_disponible"}, [])
        assert result["status"] == "SKIP"

    def test_pass_consistent_ratio(self):
        annual = [_make_annual_entry("FY2024", ingresos=1000)]
        ttm = {"metodo": "suma_4_trimestres", "ingresos": 1050, "nota": ""}
        result = _gate_ttm_sanity(ttm, annual)
        assert result["status"] == "PASS"

    def test_warning_large_ratio(self):
        annual = [_make_annual_entry("FY2024", ingresos=1000)]
        ttm = {"metodo": "FY0_fallback", "ingresos": 5000, "nota": ""}
        result = _gate_ttm_sanity(ttm, annual)
        assert result["status"] == "WARNING"


# ---------------------------------------------------------------------------
# Gate N7: TTM_CONSECUTIVE
# ---------------------------------------------------------------------------

class TestGateTtmConsecutive:
    def test_skip_no_ttm(self):
        result = _gate_ttm_consecutive({})
        assert result["status"] == "SKIP"

    def test_skip_no_disponible(self):
        result = _gate_ttm_consecutive({"metodo": "no_disponible", "nota": ""})
        assert result["status"] == "SKIP"

    def test_pass_consecutive(self):
        ttm = {"metodo": "suma_4_trimestres", "nota": "Q1-2024, Q2-2024, Q3-2024, Q4-2024"}
        result = _gate_ttm_consecutive(ttm)
        assert result["status"] == "PASS"

    def test_fail_not_consecutive(self):
        ttm = {"metodo": "suma_4_trimestres", "nota": "NOT consecutive: gap detected"}
        result = _gate_ttm_consecutive(ttm)
        assert result["status"] == "FAIL"

    def test_pass_fy_fallback_without_non_consecutive(self):
        ttm = {"metodo": "FY0_fallback", "nota": "Using FY2024"}
        result = _gate_ttm_consecutive(ttm)
        assert result["status"] == "PASS"

    def test_gate_is_critical(self):
        gate_def = next(g for g in _GATE_DEFS if g["name"] == "TTM_CONSECUTIVE")
        assert gate_def["critical"] is True

    def test_warning_fy_fallback_non_consecutive(self):
        ttm = {"metodo": "FY0_fallback", "nota": "NOT consecutive: missing Q2"}
        result = _gate_ttm_consecutive(ttm)
        assert result["status"] == "WARNING"


# ---------------------------------------------------------------------------
# Gate N8: RECENCY_SANITY
# ---------------------------------------------------------------------------

class TestGateRecencySanity:
    def test_skip_no_data(self):
        result = _gate_recency_sanity([])
        assert result["status"] == "SKIP"

    def test_recent_year_passes(self):
        import datetime
        current = datetime.datetime.now().year
        annual = [_make_annual_entry(f"FY{current}", ingresos=1)]
        result = _gate_recency_sanity(annual)
        assert result["status"] == "PASS"

    def test_old_year_warns(self):
        annual = [_make_annual_entry("FY2010", ingresos=1)]
        result = _gate_recency_sanity(annual)
        assert result["status"] == "WARNING"

    def test_uses_fecha_fin_year(self):
        entry = _make_annual_entry("FY2024")
        entry["fecha_fin"] = "2024-12-31"
        import datetime
        current = datetime.datetime.now().year
        result = _gate_recency_sanity([entry])
        age = current - 2024
        if age > 2:
            assert result["status"] == "WARNING"
        else:
            assert result["status"] == "PASS"


# ---------------------------------------------------------------------------
# Gate N9: DATA_COMPLETENESS
# ---------------------------------------------------------------------------

class TestGateDataCompleteness:
    def test_pass_high_completeness(self):
        er = _make_er(_fy(2024,
            ingresos=1000, cost_of_revenue=500, gross_profit=500, ebit=200,
            net_income=150, total_assets=2000, total_liabilities=1000,
            total_equity=1000, cash_and_equivalents=300, cfo=200,
            capex=-100, shares_outstanding=50, eps_basic=3.0,
            cfi=-50, cff=-100, delta_cash=50,
        ))
        result = _gate_data_completeness(er)
        assert result["status"] == "PASS"
        assert result["completeness_pct"] > 50

    def test_warning_sparse(self):
        er = _make_er(_fy(2024, ingresos=1000))
        result = _gate_data_completeness(er)
        assert result["status"] == "WARNING"
        assert result["completeness_pct"] < 50

    def test_warning_no_periods(self):
        er = _make_er({})
        result = _gate_data_completeness(er)
        assert result["status"] == "WARNING"

    def test_canonical_count(self):
        assert len(_CANONICAL_FIELDS) == 26


# ---------------------------------------------------------------------------
# _calc_confidence()
# ---------------------------------------------------------------------------

class TestCalcConfidence:
    def test_all_pass(self):
        gates = [{"status": "PASS"} for _ in range(5)]
        assert _calc_confidence(gates) == 100.0

    def test_one_fail(self):
        gates = [{"status": "FAIL"}, {"status": "PASS"}, {"status": "PASS"}]
        assert _calc_confidence(gates) == 85.0

    def test_one_warning(self):
        gates = [{"status": "WARNING"}, {"status": "PASS"}]
        assert _calc_confidence(gates) == 95.0

    def test_one_skip(self):
        gates = [{"status": "SKIP"}, {"status": "PASS"}]
        assert _calc_confidence(gates) == 90.0

    def test_clamps_at_zero(self):
        gates = [{"status": "FAIL"} for _ in range(10)]
        assert _calc_confidence(gates) == 0.0

    def test_clamps_at_100(self):
        gates = []
        assert _calc_confidence(gates) == 100.0


# ---------------------------------------------------------------------------
# _overall_status()
# ---------------------------------------------------------------------------

class TestOverallStatus:
    def test_all_pass(self):
        gates = [{"status": "PASS", "critical": True}]
        assert _overall_status(gates) == "PASS"

    def test_critical_fail(self):
        gates = [{"status": "FAIL", "critical": True}]
        assert _overall_status(gates) == "FAIL"

    def test_non_critical_fail_is_partial(self):
        gates = [{"status": "FAIL", "critical": False}]
        assert _overall_status(gates) == "PARTIAL"

    def test_critical_skip_is_fail(self):
        gates = [{"status": "SKIP", "critical": True}]
        assert _overall_status(gates) == "FAIL"

    def test_warning_is_partial(self):
        gates = [{"status": "WARNING", "critical": False}]
        assert _overall_status(gates) == "PARTIAL"


# ---------------------------------------------------------------------------
# _find_faltantes_criticos()
# ---------------------------------------------------------------------------

class TestFindFaltantesCriticos:
    def test_empty_when_complete(self):
        dm = {"ev": 1_000_000, "fcf": 200_000}
        result = _find_faltantes_criticos(dm)
        assert result == []

    def test_flags_missing_ev(self):
        dm = {"ev": None, "fcf": 200_000}
        result = _find_faltantes_criticos(dm)
        items = [r["item"] for r in result]
        assert "enterprise_value" in items

    def test_flags_missing_fcf(self):
        dm = {"ev": 1_000_000}
        result = _find_faltantes_criticos(dm)
        items = [r["item"] for r in result]
        assert "free_cash_flow" in items


# ---------------------------------------------------------------------------
# _find_limitaciones()
# ---------------------------------------------------------------------------

class TestFindLimitaciones:
    def test_no_limitations_when_good(self):
        annual = [_make_annual_entry(f"FY{y}") for y in range(2020, 2025)]
        ttm = {"metodo": "suma_4_trimestres", "nota": ""}
        result = _find_limitaciones(ttm, annual)
        assert result == []

    def test_fy0_fallback_noted(self):
        ttm = {"metodo": "FY0_fallback", "nota": ""}
        result = _find_limitaciones(ttm, [_make_annual_entry("FY2024")] * 5)
        assert any("FY0" in lim for lim in result)

    def test_few_years_noted(self):
        annual = [_make_annual_entry("FY2024")]
        ttm = {"metodo": "suma_4_trimestres", "nota": ""}
        result = _find_limitaciones(ttm, annual)
        assert any("only 1" in lim.lower() or "1 year" in lim.lower() for lim in result)


# ---------------------------------------------------------------------------
# validate() end-to-end
# ---------------------------------------------------------------------------

class TestValidate:
    def _full_er(self) -> dict:
        return _make_er({
            "FY2023": {
                "fecha_fin": "2023-12-31",
                "tipo_periodo": "anual",
                "fields": {
                    "ingresos":           {"value": 83902},
                    "cost_of_revenue":    {"value": 41951},
                    "gross_profit":       {"value": 41951},
                    "ebit":               {"value": 5000},
                    "net_income":         {"value": 4000},
                    "total_assets":       {"value": 50000},
                    "total_liabilities":  {"value": 30000},
                    "total_equity":       {"value": 20000},
                    "cash_and_equivalents": {"value": 5000},
                    "cfo":                {"value": 6000},
                    "capex":              {"value": -1000},
                    "shares_outstanding": {"value": 1000},
                    "eps_basic":          {"value": 4.0},
                },
            },
        })

    def test_returns_expected_keys(self):
        result = validate(self._full_er())
        assert "status" in result
        assert "confidence_score" in result
        assert "gates" in result
        assert "warnings" in result
        assert "faltantes_criticos" in result
        assert "limitaciones" in result

    def test_status_values(self):
        result = validate(self._full_er())
        assert result["status"] in ("PASS", "PARTIAL", "FAIL")

    def test_confidence_in_range(self):
        result = validate(self._full_er())
        assert 0 <= result["confidence_score"] <= 100

    def test_balanced_bs_passes_n1(self):
        result = validate(self._full_er())
        n1 = next(g for g in result["gates"] if g["name"] == "BALANCE_IDENTITY")
        assert n1["status"] == "PASS"

    def test_no_derived_causes_ev_skip(self):
        result = validate(self._full_er())
        n4 = next(g for g in result["gates"] if g["name"] == "EV_SANITY")
        assert n4["status"] == "SKIP"

    def test_with_derived_ev_pass(self):
        derived = {"derived_metrics": {"ev": 500_000, "fcf": 5000}, "ttm": {}}
        result = validate(self._full_er(), derived=derived)
        n4 = next(g for g in result["gates"] if g["name"] == "EV_SANITY")
        assert n4["status"] == "PASS"

    def test_empty_er_doesnt_crash(self):
        result = validate({"periods": {}})
        assert result["status"] in ("PASS", "PARTIAL", "FAIL")

    def test_gates_contain_all_9(self):
        result = validate(self._full_er())
        names = {g["name"] for g in result["gates"]}
        expected = {
            "BALANCE_IDENTITY", "CASHFLOW_IDENTITY", "UNIDADES_SANITY",
            "EV_SANITY", "MARGIN_SANITY", "TTM_SANITY", "TTM_CONSECUTIVE",
            "RECENCY_SANITY", "DATA_COMPLETENESS",
        }
        assert names == expected

    def test_sector_passed_to_margin_gate(self):
        derived = {
            "derived_metrics": {
                "gross_margin_pct": 80,
                "operating_margin_pct": 30,
                "net_margin_pct": 20,
            },
            "ttm": {},
        }
        result_sw = validate(self._full_er(), derived=derived, sector="Software")
        m5 = next(g for g in result_sw["gates"] if g["name"] == "MARGIN_SANITY")
        assert "Software" in m5["note"]

    def test_sector_margins_has_defaults(self):
        assert "default" in SECTOR_MARGINS
        assert "Software" in SECTOR_MARGINS

    def test_gate_defs_count(self):
        assert len(_GATE_DEFS) == 9

    def test_balance_identity_is_critical(self):
        gate_def = next(g for g in _GATE_DEFS if g["name"] == "BALANCE_IDENTITY")
        assert gate_def["critical"] is True
