"""Tests for SignConvention enforcer."""

from elsian.normalize.signs import enforce_sign


def test_revenue_always_positive():
    assert enforce_sign("ingresos", -100.0) == 100.0
    assert enforce_sign("ingresos", 100.0) == 100.0


def test_capex_always_negative():
    assert enforce_sign("capex", 500.0) == -500.0
    assert enforce_sign("capex", -500.0) == -500.0


def test_net_income_preserves_sign():
    assert enforce_sign("net_income", 100.0) == 100.0
    assert enforce_sign("net_income", -50.0) == -50.0


def test_total_assets_positive():
    assert enforce_sign("total_assets", -1000.0) == 1000.0


def test_fcf_preserves_sign():
    assert enforce_sign("fcf", -200.0) == -200.0
    assert enforce_sign("fcf", 300.0) == 300.0
