"""Tests for data models."""

import json

from elsian.models.field import Provenance, FieldCandidate, FieldResult
from elsian.models.filing import Filing, FilingMetadata
from elsian.models.case import CaseConfig
from elsian.models.result import (
    PeriodResult, ExtractionResult, EvalMatch, EvalReport, PhaseResult,
)


def test_provenance_to_dict_minimal():
    p = Provenance(source_filing="test.md")
    d = p.to_dict()
    assert d == {"source_filing": "test.md"}


def test_provenance_to_dict_full():
    p = Provenance(
        source_filing="test.md",
        source_location="table:is:row3",
        table_index=2,
        table_title="Income Statement",
        row_label="Revenue",
        col_label="FY2024",
        row=3, col=1,
        raw_text="1,289,897",
    )
    d = p.to_dict()
    assert d["table_index"] == 2
    assert d["row_label"] == "Revenue"
    assert d["raw_text"] == "1,289,897"


def test_field_result_to_dict():
    fr = FieldResult(
        value=1289897.0,
        provenance=Provenance(source_filing="10k.md", source_location="table:is:r3"),
        scale="thousands",
        confidence="high",
    )
    d = fr.to_dict()
    assert d["value"] == 1289897.0
    assert d["scale"] == "thousands"
    assert d["source_filing"] == "10k.md"


def test_field_candidate_defaults():
    fc = FieldCandidate(canonical_name="ingresos", value=100.0, period="FY2024")
    assert fc.source_type == "table"
    assert fc.confidence == "high"


def test_filing_accession_nodash():
    f = Filing(accession="0001-23-456789")
    assert f.accession_nodash == "000123456789"


def test_extraction_result_to_dict():
    er = ExtractionResult(ticker="TZOO", currency="USD")
    pr = PeriodResult(fecha_fin="2024-12-31", tipo_periodo="anual")
    pr.fields["ingresos"] = FieldResult(
        value=83902.0,
        provenance=Provenance(source_filing="10k.md"),
    )
    er.periods["FY2024"] = pr
    d = er.to_dict()
    assert d["ticker"] == "TZOO"
    assert d["periods"]["FY2024"]["fields"]["ingresos"]["value"] == 83902.0


def test_eval_report_to_dict():
    r = EvalReport(ticker="TEST", matched=10, total_expected=12, score=83.33)
    d = r.to_dict()
    assert d["score"] == 83.33


def test_eval_report_to_dict_includes_readiness_fields():
    """EvalReport.to_dict() must expose BL-064 readiness fields."""
    r = EvalReport(
        ticker="TEST",
        matched=10,
        total_expected=12,
        score=83.33,
        readiness_score=72.5,
        validator_confidence_score=80.0,
        provenance_coverage_pct=90.0,
        extra_penalty=5.0,
    )
    d = r.to_dict()
    assert d["readiness_score"] == 72.5
    assert d["validator_confidence_score"] == 80.0
    assert d["provenance_coverage_pct"] == 90.0
    assert d["extra_penalty"] == 5.0


def test_case_config_defaults():
    c = CaseConfig()
    assert c.source_hint == "sec"
    assert c.period_scope == "FULL"
    assert c.fiscal_year_end_month == 12


def test_case_config_from_file_reads_extended_contract_keys(tmp_path):
    case_dir = tmp_path / "TEST"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "company_name": "Test Corp",
                "source_hint": "eu_manual",
                "currency": "EUR",
                "market": "Euronext Paris",
                "country": "FR",
                "accounting_standard": "IFRS",
                "period_scope": "FULL",
                "fiscal_year_end_month": 12,
                "filings_expected_count": 3,
                "filings_sources": [
                    {
                        "url": "https://example.com/report.pdf",
                        "filename": "report.pdf",
                        "filing_type": "ANNUAL_REPORT",
                    }
                ],
                "selection_overrides": {"stable_tiebreaker": {"tbl_order": "ascending_table_number"}},
                "config_overrides": {"prefer_ixbrl": False},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    case = CaseConfig.from_file(case_dir)

    assert case.company_name == "Test Corp"
    assert case.market == "Euronext Paris"
    assert case.country == "FR"
    assert case.accounting_standard == "IFRS"
    assert case.filings_expected_count == 3
    assert case.filings_sources[0]["filename"] == "report.pdf"
    assert case.selection_overrides["stable_tiebreaker"]["tbl_order"] == "ascending_table_number"
    assert case.config_overrides["prefer_ixbrl"] is False
    assert case.extra == {}
