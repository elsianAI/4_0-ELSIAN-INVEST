"""Tests for elsian.evaluate.validate_expected."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from elsian.evaluate.validate_expected import validate_expected, validate_all_cases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(tmp_dir: str, data: dict, name: str = "expected.json") -> str:
    """Write *data* as JSON into *tmp_dir* and return the path."""
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return path


def _minimal_valid() -> dict:
    """Return the smallest expected.json that passes all rules."""
    return {
        "version": "1.0",
        "ticker": "TEST",
        "currency": "USD",
        "periods": {
            "FY2024": {
                "fecha_fin": "2024-12-31",
                "tipo_periodo": "anual",
                "fields": {
                    "ingresos": {
                        "value": 100000,
                        "source_filing": "SRC_001_10-K_FY2024.clean.md",
                    },
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Core validation rules
# ---------------------------------------------------------------------------

class TestValidExpected:
    """A fully valid expected.json → no errors."""

    def test_valid_returns_empty_list(self, tmp_path):
        path = _write_json(str(tmp_path), _minimal_valid())
        assert validate_expected(path) == []


class TestMissingVersion:
    """Rule 1: 'version' is mandatory."""

    def test_no_version(self, tmp_path):
        data = _minimal_valid()
        del data["version"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing 'version'" in e for e in errors)


class TestMissingTicker:
    """Rule 2: 'ticker' is mandatory."""

    def test_no_ticker(self, tmp_path):
        data = _minimal_valid()
        del data["ticker"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing 'ticker'" in e for e in errors)


class TestEmptyPeriods:
    """Rule 3: 'periods' must be a non-empty dict."""

    def test_empty_periods(self, tmp_path):
        data = _minimal_valid()
        data["periods"] = {}
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("non-empty dict" in e for e in errors)

    def test_missing_periods(self, tmp_path):
        data = _minimal_valid()
        del data["periods"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("non-empty dict" in e for e in errors)


class TestEmptyFields:
    """Rule 4: each period must have 'fields' as non-empty dict."""

    def test_no_fields_key(self, tmp_path):
        data = _minimal_valid()
        del data["periods"]["FY2024"]["fields"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("non-empty dict" in e and "FY2024" in e for e in errors)

    def test_empty_fields(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"] = {}
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("non-empty dict" in e and "FY2024" in e for e in errors)


class TestMissingValue:
    """Rule 5: every field must have 'value' (may be 0, not None)."""

    def test_missing_value(self, tmp_path):
        data = _minimal_valid()
        del data["periods"]["FY2024"]["fields"]["ingresos"]["value"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing or null 'value'" in e for e in errors)

    def test_null_value(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"]["ingresos"]["value"] = None
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing or null 'value'" in e for e in errors)

    def test_zero_value_ok(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"]["ingresos"]["value"] = 0
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        # zero is allowed — only warnings about ingresos ≤ 0, not an error
        hard_errors = [e for e in errors if not e.startswith("[WARNING]")]
        assert hard_errors == []


class TestMissingSourceFiling:
    """Rule 6: every field must have a non-empty 'source_filing'."""

    def test_missing_source_filing(self, tmp_path):
        data = _minimal_valid()
        del data["periods"]["FY2024"]["fields"]["ingresos"]["source_filing"]
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing 'source_filing'" in e for e in errors)

    def test_empty_source_filing(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"]["ingresos"]["source_filing"] = ""
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("missing 'source_filing'" in e for e in errors)


class TestRestatementIncomplete:
    """Rule 7: if restatement present, all sub-fields are required."""

    def test_incomplete_restatement(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"]["ingresos"]["restatement"] = {
            "applied": True,
            # missing: trigger, evidence_filing, evidence_text,
            # original_source_filing, original_value
        }
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        missing_fields = {"trigger", "evidence_filing", "evidence_text",
                          "original_source_filing", "original_value"}
        for mf in missing_fields:
            assert any(mf in e for e in errors), f"Expected error about '{mf}'"


class TestRestatementSameSourceFiling:
    """Rule 8: original_source_filing must differ from source_filing."""

    def test_same_source(self, tmp_path):
        data = _minimal_valid()
        sf = "SRC_001_10-K_FY2024.clean.md"
        data["periods"]["FY2024"]["fields"]["ingresos"]["restatement"] = {
            "applied": True,
            "trigger": "test",
            "evidence_filing": sf,
            "evidence_text": "text",
            "original_source_filing": sf,
            "original_value": 999,
        }
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        assert any("should differ" in e for e in errors)


class TestSanityWarnings:
    """Sanity checks produce [WARNING] prefixed messages."""

    def test_negative_revenue_warning(self, tmp_path):
        data = _minimal_valid()
        data["periods"]["FY2024"]["fields"]["ingresos"]["value"] = -500
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        warnings = [e for e in errors if e.startswith("[WARNING]")]
        assert any("ingresos" in w for w in warnings)

    def test_balance_sheet_mismatch_warning(self, tmp_path):
        data = _minimal_valid()
        fields = data["periods"]["FY2024"]["fields"]
        fields["total_assets"] = {"value": 1000, "source_filing": "SRC.md"}
        fields["total_liabilities"] = {"value": 400, "source_filing": "SRC.md"}
        fields["total_equity"] = {"value": 500, "source_filing": "SRC.md"}
        # 1000 vs 400+500=900 → 11.1% off → warning
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        warnings = [e for e in errors if e.startswith("[WARNING]")]
        assert any("total_assets" in w for w in warnings)

    def test_balanced_sheet_no_warning(self, tmp_path):
        data = _minimal_valid()
        fields = data["periods"]["FY2024"]["fields"]
        fields["total_assets"] = {"value": 1000, "source_filing": "SRC.md"}
        fields["total_liabilities"] = {"value": 600, "source_filing": "SRC.md"}
        fields["total_equity"] = {"value": 400, "source_filing": "SRC.md"}
        # 1000 vs 600+400=1000 → 0% → no warning
        path = _write_json(str(tmp_path), data)
        errors = validate_expected(path)
        warnings = [e for e in errors if "[WARNING]" in e and "total_assets" in e]
        assert warnings == []

    def test_adtn_promoted_quarters_no_balance_identity_warning(self):
        repo_root = Path(__file__).resolve().parents[2]
        expected_path = repo_root / "cases" / "ADTN" / "expected.json"

        errors = validate_expected(str(expected_path))
        bs_warnings = [
            e
            for e in errors
            if e.startswith("[WARNING]") and "total_assets" in e
        ]

        assert bs_warnings == []


class TestFileNotFound:
    """Non-existent file returns a single error."""

    def test_missing_file(self):
        errors = validate_expected("/nonexistent/expected.json")
        assert len(errors) == 1
        assert "not found" in errors[0].lower()


class TestInvalidJson:
    """Corrupt JSON returns a single error."""

    def test_bad_json(self, tmp_path):
        bad_path = tmp_path / "expected.json"
        bad_path.write_text("{not valid json", encoding="utf-8")
        errors = validate_expected(str(bad_path))
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]


# ---------------------------------------------------------------------------
# validate_all_cases
# ---------------------------------------------------------------------------

class TestValidateAllCases:
    """Integration test for validate_all_cases with a fixtures directory."""

    def test_with_two_tickers(self, tmp_path):
        # Good ticker
        good_dir = tmp_path / "GOOD"
        good_dir.mkdir()
        _write_json(str(good_dir), _minimal_valid())

        # Bad ticker — missing version & ticker
        bad_dir = tmp_path / "BAD"
        bad_dir.mkdir()
        bad_data = _minimal_valid()
        del bad_data["version"]
        del bad_data["ticker"]
        _write_json(str(bad_dir), bad_data)

        results = validate_all_cases(str(tmp_path))
        assert "GOOD" not in results
        assert "BAD" in results
        assert len(results["BAD"]) >= 2  # at least version + ticker

    def test_empty_dir(self, tmp_path):
        results = validate_all_cases(str(tmp_path))
        assert results == {}

    def test_nonexistent_dir(self):
        results = validate_all_cases("/nonexistent/cases")
        assert results == {}
