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


def test_evaluate_matches_supported_derived_fields():
    expected = {
        "periods": {
            "FY2024": {
                "fields": {
                    "ebitda": {"value": 120.0},
                    "fcf": {"value": 60.0},
                }
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(expected, f)
        f.flush()

        er = ExtractionResult(ticker="TEST")
        pr = PeriodResult()
        pr.fields["ebit"] = FieldResult(value=100.0)
        pr.fields["depreciation_amortization"] = FieldResult(value=20.0)
        pr.fields["cfo"] = FieldResult(value=90.0)
        pr.fields["capex"] = FieldResult(value=-30.0)
        er.periods["FY2024"] = pr

        report = evaluate(er, f.name)
        assert report.score == 100.0
        assert report.matched == 2
        assert report.missed == 0


def test_evaluate_prefers_derived_actual_when_expected_marks_field_derived():
    expected = {
        "periods": {
            "Q1-2023": {
                "fields": {
                    "ebitda": {"value": 18236.0, "source_filing": "DERIVED"},
                }
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(expected, f)
        f.flush()

        er = ExtractionResult(ticker="GCT")
        pr = PeriodResult()
        pr.fields["ebit"] = FieldResult(value=17856.0)
        pr.fields["depreciation_amortization"] = FieldResult(value=380.0)
        pr.fields["ebitda"] = FieldResult(value=19847.0)
        er.periods["Q1-2023"] = pr

        report = evaluate(er, f.name)
        assert report.score == 100.0
        assert report.matched == 1
        assert report.wrong == 0


# ---------------------------------------------------------------------------
# Readiness v1 (BL-064)
# ---------------------------------------------------------------------------

from elsian.evaluate.evaluator import (
    _compute_provenance_coverage,
    _compute_readiness,
)
from elsian.models.field import Provenance


def test_compute_readiness_formula():
    """Verify readiness formula with known inputs."""
    rs, ep = _compute_readiness(
        score=100.0,
        required_fields_coverage_pct=100.0,
        validator_confidence_score=100.0,
        provenance_coverage_pct=100.0,
        extra=0,
        total_expected=2,
    )
    assert rs == 100.0
    assert ep == 0.0


def test_compute_readiness_extra_penalty_capped():
    """Extra penalty is capped at 15."""
    rs, ep = _compute_readiness(
        score=100.0,
        required_fields_coverage_pct=100.0,
        validator_confidence_score=100.0,
        provenance_coverage_pct=100.0,
        extra=100,
        total_expected=2,
    )
    assert ep == 15.0
    assert rs == 85.0


def test_compute_readiness_never_negative():
    """Readiness score is clamped to 0."""
    rs, ep = _compute_readiness(
        score=0.0,
        required_fields_coverage_pct=0.0,
        validator_confidence_score=0.0,
        provenance_coverage_pct=0.0,
        extra=100,
        total_expected=1,
    )
    assert rs == 0.0


def test_provenance_coverage_no_fields():
    er = ExtractionResult(ticker="T")
    assert _compute_provenance_coverage(er, {}) == 0.0


def test_provenance_coverage_full():
    er = ExtractionResult(ticker="T")
    pr = PeriodResult()
    pr.fields["ingresos"] = FieldResult(
        value=100.0,
        provenance=Provenance(source_filing="f.md", extraction_method="table"),
    )
    er.periods["FY2024"] = pr

    expected_periods = {"FY2024": {"fields": {"ingresos": {"value": 100.0}}}}
    pct = _compute_provenance_coverage(er, expected_periods)
    assert pct == 100.0


def test_provenance_coverage_partial():
    er = ExtractionResult(ticker="T")
    pr = PeriodResult()
    pr.fields["ingresos"] = FieldResult(
        value=100.0,
        provenance=Provenance(source_filing="f.md", extraction_method="table"),
    )
    pr.fields["net_income"] = FieldResult(
        value=10.0,
        provenance=Provenance(source_filing="", extraction_method=""),
    )
    er.periods["FY2024"] = pr

    expected_periods = {
        "FY2024": {
            "fields": {
                "ingresos": {"value": 100.0},
                "net_income": {"value": 10.0},
            }
        }
    }
    pct = _compute_provenance_coverage(er, expected_periods)
    assert pct == 50.0


def test_readiness_fields_on_eval_report():
    """EvalReport produced by evaluate() must carry readiness v1 fields."""
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
        pr.fields["ingresos"] = FieldResult(
            value=1000.0,
            provenance=Provenance(source_filing="10k.md", extraction_method="table"),
        )
        pr.fields["net_income"] = FieldResult(
            value=200.0,
            provenance=Provenance(source_filing="10k.md", extraction_method="table"),
        )
        er.periods["FY2024"] = pr

        report = evaluate(er, f.name)
        assert report.score == 100.0
        # Readiness fields must be present and typed
        assert isinstance(report.readiness_score, float)
        assert isinstance(report.validator_confidence_score, float)
        assert isinstance(report.provenance_coverage_pct, float)
        assert isinstance(report.extra_penalty, float)
        # With perfect extraction and full provenance, readiness must be > 0
        assert report.readiness_score > 0.0
        assert report.provenance_coverage_pct == 100.0
        # to_dict includes readiness
        d = report.to_dict()
        assert "readiness_score" in d
        assert "validator_confidence_score" in d
        assert "provenance_coverage_pct" in d
        assert "extra_penalty" in d
