from __future__ import annotations

from elsian.curate_draft import build_expected_draft_from_extraction


def test_build_expected_draft_from_extraction_exposes_confidence_and_gaps():
    extraction_result = {
        "ticker": "TEST",
        "currency": "USD",
        "periods": {
            "FY2024": {
                "fields": {
                    "ingresos": {
                        "value": 1000,
                        "confidence": "high",
                        "source_filing": "SRC_001.pdf",
                        "source_location": "SRC_001.pdf:income_statement:tbl1",
                        "scale": "as_reported",
                        "extraction_method": "table",
                    },
                    "total_assets": {
                        "value": 500,
                        "confidence": "low",
                        "source_filing": "SRC_001.pdf",
                        "source_location": "SRC_001.pdf:balance_sheet:tbl2",
                        "scale": "as_reported",
                        "extraction_method": "table",
                    },
                    "total_liabilities": {
                        "value": 300,
                        "confidence": "high",
                        "source_filing": "SRC_001.pdf",
                        "source_location": "SRC_001.pdf:balance_sheet:tbl2",
                        "scale": "as_reported",
                        "extraction_method": "table",
                    },
                    "total_equity": {
                        "value": 200,
                        "confidence": "high",
                        "source_filing": "SRC_001.pdf",
                        "source_location": "SRC_001.pdf:balance_sheet:tbl2",
                        "scale": "as_reported",
                        "extraction_method": "table",
                    },
                    "fcf": {
                        "value": 120,
                        "confidence": "manual",
                        "source_filing": "case.json",
                        "source_location": "case.json:manual_overrides:FY2024:fcf",
                        "scale": "as_reported",
                        "extraction_method": "manual",
                    },
                }
            }
        },
    }
    expected = {
        "periods": {
            "FY2024": {
                "fields": {
                    "ingresos": {"value": 1000},
                    "total_assets": {"value": 500},
                    "total_liabilities": {"value": 300},
                    "total_equity": {"value": 200},
                    "fcf": {"value": 120},
                }
            }
        }
    }

    draft = build_expected_draft_from_extraction(
        extraction_result,
        ticker="TEST",
        currency="USD",
        expected=expected,
    )

    assert draft["_generated_by"] == "elsian curate"
    assert draft["_source_mode"] == "pipeline_non_sec"
    assert draft["_confidence_summary"] == {"high": 3, "low": 1}
    assert "missing_canonicals" in draft["_gap_policy"]
    assert "not auto-populated by the deterministic PDF/text draft" in (
        draft["_gap_policy"]["missing_canonicals"]
    )

    period = draft["periods"]["FY2024"]
    assert "fcf" not in period["fields"]
    assert period["_confidence"]["field_counts"] == {"high": 3, "low": 1}
    assert period["_confidence"]["non_high_fields"] == ["total_assets"]
    assert period["_gaps"]["skipped_manual_fields"] == ["fcf"]
    assert period["_gaps"]["missing_count"] == len(period["_gaps"]["missing_canonicals"])
    assert "accounts_payable" in period["_gaps"]["missing_canonicals"]
    assert period["_gaps"]["missing_expected_fields"] == ["fcf"]
    assert period["_gaps"]["extra_fields_vs_expected"] == []

    ingresos = period["fields"]["ingresos"]
    assert ingresos["confidence"] == "high"
    assert ingresos["source_filing"] == "SRC_001.pdf"
    assert ingresos["_source"] == "pipeline"


def test_build_expected_draft_from_extraction_keeps_empty_contract_shape():
    extraction_result = {
        "ticker": "EMPTY",
        "currency": "EUR",
        "periods": {},
    }
    expected = {
        "periods": {
            "FY2024": {
                "fields": {
                    "ingresos": {"value": 100},
                }
            }
        }
    }

    draft = build_expected_draft_from_extraction(
        extraction_result,
        ticker="EMPTY",
        currency="EUR",
        expected=expected,
    )

    assert draft["_generated_by"] == "elsian curate"
    assert draft["_source_mode"] == "pipeline_non_sec"
    assert draft["_confidence_summary"] == {}
    assert "missing_canonicals" in draft["_gap_policy"]
    assert draft["_validation"]["status"] in {"PASS", "WARNING", "FAIL"}
    assert draft["_comparison_to_expected"]["common_periods"] == []
    assert draft["_comparison_to_expected"]["missing_periods"] == ["FY2024"]
    assert draft["periods"] == {}
