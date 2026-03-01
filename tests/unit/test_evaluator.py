"""Tests for the evaluation framework."""

import json
import tempfile

from elsian.models.field import FieldResult, Provenance
from elsian.models.result import PeriodResult, ExtractionResult
from elsian.evaluate.evaluator import evaluate, _values_match


def test_values_match_exact():
    assert _values_match(100.0, 100.0) is True


def test_values_match_within_tolerance():
    assert _values_match(100.0, 100.5) is True


def test_values_match_outside_tolerance():
    assert _values_match(100.0, 102.0) is False


def test_values_match_zero():
    assert _values_match(0.0, 0.0) is True
    assert _values_match(0.0, 0.001) is True
    assert _values_match(0.0, 1.0) is False


def test_evaluate_perfect():
    expected = {
        "periods": {
            "FY2024": {
                "fields": {
                    "ingresos": {"value": 1000.0},
                    "net_income": {"value": 200.0},
                }
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(expected, f)
        f.flush()

        er = ExtractionResult(ticker="TEST")
        pr = PeriodResult()
        pr.fields["ingresos"] = FieldResult(value=1000.0)
        pr.fields["net_income"] = FieldResult(value=200.0)
        er.periods["FY2024"] = pr

        report = evaluate(er, f.name)
        assert report.score == 100.0
        assert report.matched == 2
        assert report.missed == 0


def test_evaluate_with_miss():
    expected = {
        "periods": {
            "FY2024": {
                "fields": {
                    "ingresos": {"value": 1000.0},
                    "net_income": {"value": 200.0},
                }
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(expected, f)
        f.flush()

        er = ExtractionResult(ticker="TEST")
        pr = PeriodResult()
        pr.fields["ingresos"] = FieldResult(value=1000.0)
        er.periods["FY2024"] = pr

        report = evaluate(er, f.name)
        assert report.score == 50.0
        assert report.matched == 1
        assert report.missed == 1
