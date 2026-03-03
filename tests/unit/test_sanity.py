"""Unit tests for elsian.normalize.sanity module."""

from __future__ import annotations

import unittest

from elsian.models.field import FieldResult, Provenance
from elsian.models.result import ExtractionResult, PeriodResult
from elsian.normalize.sanity import SanityWarning, run_sanity_checks


def _fr(value: float) -> FieldResult:
    """Shorthand to build a FieldResult with only a value."""
    return FieldResult(value=value, provenance=Provenance(), scale="raw", confidence="high")


def _make_result(periods: dict[str, dict[str, float]]) -> ExtractionResult:
    """Build a minimal ExtractionResult from {period: {field: value}} mapping."""
    er = ExtractionResult(ticker="TEST", currency="USD")
    for pk, fields in periods.items():
        pr = PeriodResult(fecha_fin="", tipo_periodo="anual")
        for fname, val in fields.items():
            pr.fields[fname] = _fr(val)
        er.periods[pk] = pr
    return er


class TestCapexPositive(unittest.TestCase):
    """CAPEX positive → warning + auto-fix (sign flipped)."""

    def test_capex_positive_flipped(self) -> None:
        result = _make_result({"FY2024": {"capex": 500.0, "ingresos": 1000.0}})
        warnings = run_sanity_checks(result)
        capex_warnings = [w for w in warnings if w.warning_type == "capex_positive"]
        self.assertEqual(len(capex_warnings), 1)
        self.assertIn("CAPEX positive", capex_warnings[0].message)
        # Value should have been flipped in-place
        self.assertEqual(result.periods["FY2024"].fields["capex"].value, -500.0)

    def test_capex_negative_no_warning(self) -> None:
        result = _make_result({"FY2024": {"capex": -500.0, "ingresos": 1000.0}})
        warnings = run_sanity_checks(result)
        capex_warnings = [w for w in warnings if w.warning_type == "capex_positive"]
        self.assertEqual(len(capex_warnings), 0)


class TestRevenueNegative(unittest.TestCase):
    """Revenue negative → warning."""

    def test_revenue_negative_warning(self) -> None:
        result = _make_result({"FY2024": {"ingresos": -100.0}})
        warnings = run_sanity_checks(result)
        rev_warnings = [w for w in warnings if w.warning_type == "revenue_negative"]
        self.assertEqual(len(rev_warnings), 1)
        self.assertIn("Revenue negative", rev_warnings[0].message)

    def test_revenue_positive_no_warning(self) -> None:
        result = _make_result({"FY2024": {"ingresos": 5000.0}})
        warnings = run_sanity_checks(result)
        rev_warnings = [w for w in warnings if w.warning_type == "revenue_negative"]
        self.assertEqual(len(rev_warnings), 0)


class TestGrossProfitGreaterThanRevenue(unittest.TestCase):
    """gross_profit > revenue → warning."""

    def test_gp_gt_revenue_warning(self) -> None:
        result = _make_result({"FY2024": {"ingresos": 1000.0, "gross_profit": 1500.0}})
        warnings = run_sanity_checks(result)
        gp_warnings = [w for w in warnings if w.warning_type == "gp_gt_revenue"]
        self.assertEqual(len(gp_warnings), 1)
        self.assertIn("gross_profit", gp_warnings[0].message)

    def test_gp_lt_revenue_no_warning(self) -> None:
        result = _make_result({"FY2024": {"ingresos": 1000.0, "gross_profit": 800.0}})
        warnings = run_sanity_checks(result)
        gp_warnings = [w for w in warnings if w.warning_type == "gp_gt_revenue"]
        self.assertEqual(len(gp_warnings), 0)


class TestYoyJump(unittest.TestCase):
    """YoY >10× jump → warning."""

    def test_yoy_jump_warning(self) -> None:
        result = _make_result({
            "FY2023": {"ingresos": 100.0},
            "FY2024": {"ingresos": 1500.0},  # 15× jump
        })
        warnings = run_sanity_checks(result)
        yoy_warnings = [w for w in warnings if w.warning_type == "yoy_jump"]
        self.assertEqual(len(yoy_warnings), 1)
        self.assertIn("ratio=15.0x", yoy_warnings[0].message)

    def test_yoy_within_range_no_warning(self) -> None:
        result = _make_result({
            "FY2023": {"ingresos": 100.0},
            "FY2024": {"ingresos": 500.0},  # 5× — within range
        })
        warnings = run_sanity_checks(result)
        yoy_warnings = [w for w in warnings if w.warning_type == "yoy_jump"]
        self.assertEqual(len(yoy_warnings), 0)

    def test_yoy_with_zero_previous_no_warning(self) -> None:
        result = _make_result({
            "FY2023": {"ingresos": 0.0},
            "FY2024": {"ingresos": 1500.0},
        })
        warnings = run_sanity_checks(result)
        yoy_warnings = [w for w in warnings if w.warning_type == "yoy_jump"]
        self.assertEqual(len(yoy_warnings), 0)

    def test_yoy_multiple_fields(self) -> None:
        result = _make_result({
            "FY2023": {"ingresos": 100.0, "ebit": 50.0, "net_income": 30.0},
            "FY2024": {"ingresos": 1500.0, "ebit": 600.0, "net_income": 400.0},
        })
        warnings = run_sanity_checks(result)
        yoy_warnings = [w for w in warnings if w.warning_type == "yoy_jump"]
        # ingresos: 15x, ebit: 12x, net_income: 13.3x — all >10x
        self.assertEqual(len(yoy_warnings), 3)


class TestCleanCase(unittest.TestCase):
    """No anomalies → empty warnings list."""

    def test_clean_case_no_warnings(self) -> None:
        result = _make_result({
            "FY2023": {
                "ingresos": 1000.0,
                "gross_profit": 600.0,
                "capex": -200.0,
                "ebit": 400.0,
                "net_income": 300.0,
            },
            "FY2024": {
                "ingresos": 1100.0,
                "gross_profit": 660.0,
                "capex": -220.0,
                "ebit": 440.0,
                "net_income": 330.0,
            },
        })
        warnings = run_sanity_checks(result)
        self.assertEqual(warnings, [])


class TestQuarterlyPeriodsSkippedInYoY(unittest.TestCase):
    """YoY checks only run on FYxxxx periods, not quarterly."""

    def test_quarterly_not_compared(self) -> None:
        result = _make_result({
            "Q1_2024": {"ingresos": 10.0},
            "Q2_2024": {"ingresos": 5000.0},  # Would be >10x if compared
        })
        warnings = run_sanity_checks(result)
        yoy_warnings = [w for w in warnings if w.warning_type == "yoy_jump"]
        self.assertEqual(len(yoy_warnings), 0)


if __name__ == "__main__":
    unittest.main()
