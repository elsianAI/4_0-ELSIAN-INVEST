"""Tests for narrative extraction ported from 3.0."""

from pathlib import Path

import pytest

from elsian.extract.narrative import extract_from_narrative, NarrativeField


def _require_path(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"required filing fixture is not present in this checkout: {path}")
    return path


def test_pattern_label_verb_value():
    text = "Revenue amounted to $83,902 million for FY2024."
    fields = extract_from_narrative(text)
    assert len(fields) >= 1
    f = fields[0]
    assert f.value == 83902.0
    assert f.scale == "millions"


def test_pattern_value_label():
    text = "The company reported $185.2 million in revenue."
    fields = extract_from_narrative(text)
    assert len(fields) >= 1
    assert any(f.value == 185.2 for f in fields)


def test_non_gaap_excluded():
    text = "Non-GAAP revenue amounted to $100 million."
    fields = extract_from_narrative(text)
    assert len(fields) == 0


def test_comparative_prefix_excluded():
    text = "compared to revenue of $500 million in 2023."
    fields = extract_from_narrative(text)
    assert len(fields) == 0


def test_period_detection():
    text = "In FY2024, revenue amounted to $1,000 million."
    fields = extract_from_narrative(text)
    if fields:
        assert fields[0].period_hint == "FY2024"


def test_extracts_historical_revenue_table():
    text = (
        "                         2024  2023   2022   2021   2020\n"
        "COMPANY AND GROUP PERFORMANCE\n"
        "Revenues (as reported – in millions of euros) 10,280 8,345 8,154 7,115 5,732\n"
    )
    fields = extract_from_narrative(text, source_filename="SRC_013_PRESENTATION_2024.txt")
    by_period = {
        f.period_hint: f.value
        for f in fields
        if f.label == "Revenues"
    }
    assert by_period["FY2022"] == 8154.0
    assert by_period["FY2021"] == 7115.0


def test_extracts_dividend_history_table():
    text = (
        "6.5.2. Dividends paid in respect of the last five financial years\n"
        "Dividend for financial year* Gross dividend per share Total amount** Distribution rate***\n"
        "2019                                €2.40    €140,925,600.00    35%\n"
        "2020                                €2.40    €140,953,440.00    43%\n"
        "2021                                €3.30   €186,947,469.86(1)  35%\n"
        "2022                                €3.85    €227,615,241.70    36%\n"
    )
    fields = extract_from_narrative(text, source_filename="SRC_013_PRESENTATION_2024.txt")
    by_period = {
        f.period_hint: f.value
        for f in fields
        if f.label == "Gross dividend per share"
    }
    assert by_period["FY2021"] == 3.30
    assert by_period["FY2022"] == 3.85


def test_extracts_fcf_cover_bullet_with_source_year_fallback():
    text = "• €703M Net Free cash flow"
    fields = extract_from_narrative(
        text, source_filename="SRC_004_ANNUAL_REPORT_2022-12-31.txt"
    )
    assert any(
        f.label.lower() == "net free cash flow"
        and f.period_hint == "FY2022"
        and f.value == 703.0
        and f.scale == "millions"
        for f in fields
    )


def test_extracts_tep_real_world_patterns():
    base = Path("cases/TEP/filings")

    revenue_text = _require_path(base / "SRC_013_PRESENTATION_2024.txt").read_text(errors="ignore")
    revenue_fields = extract_from_narrative(
        revenue_text, source_filename="SRC_013_PRESENTATION_2024.txt"
    )
    revenue_by_period = {
        f.period_hint: f.value
        for f in revenue_fields
        if f.label == "Revenues"
    }
    assert revenue_by_period["FY2022"] == 8154.0
    assert revenue_by_period["FY2021"] == 7115.0

    dividends_by_period = {
        f.period_hint: f.value
        for f in revenue_fields
        if f.label == "Gross dividend per share"
    }
    assert dividends_by_period["FY2021"] == 3.30

    fcf_text = _require_path(base / "SRC_005_ANNUAL_REPORT_2021-12-31.txt").read_text(
        errors="ignore"
    )
    fcf_fields = extract_from_narrative(
        fcf_text, source_filename="SRC_005_ANNUAL_REPORT_2021-12-31.txt"
    )
    assert any(
        f.label.lower() == "net free cash flow"
        and f.period_hint == "FY2021"
        and f.value == 661.0
        for f in fcf_fields
    )
