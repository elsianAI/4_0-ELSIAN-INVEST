"""Tests for filing metadata detection ported from 3.0."""

from elsian.extract.detect import (
    detect_currency,
    detect_scale,
    detect_language,
    detect_periods,
    detect_filing_type,
    detect_sections,
    analyze_filing,
)


def test_detect_currency_usd():
    assert detect_currency("Revenue was $1,234,000") == "USD"


def test_detect_currency_eur():
    text = "\u20ac100M \u20ac200M \u20ac300M revenue"
    assert detect_currency(text) == "EUR"


def test_detect_scale_millions():
    scale, conf = detect_scale("(in millions)")
    assert scale == "millions"
    assert conf == "high"


def test_detect_scale_thousands():
    scale, conf = detect_scale("amounts in thousands")
    assert scale == "thousands"
    assert conf == "high"


def test_detect_scale_raw():
    scale, conf = detect_scale("some random text")
    assert scale == "raw"
    assert conf == "low"


def test_detect_language_english():
    assert detect_language("Revenue and net income") == "en"


def test_detect_language_french():
    text = "chiffre d\'affaires et r\u00e9sultat net b\u00e9n\u00e9fice"
    assert detect_language(text) == "fr"


def test_detect_periods_fy():
    text = "For the Year Ended December 31, 2024"
    periods = detect_periods(text)
    assert "FY2024" in periods


def test_detect_periods_quarterly():
    text = "Three Months Ended September 30, 2024"
    periods = detect_periods(text)
    assert "Q3-2024" in periods


def test_detect_filing_type_10k():
    assert detect_filing_type("SRC_001_10-K_FY2024.clean.md") == "10-K"


def test_detect_filing_type_20f():
    assert detect_filing_type("SRC_003_20-F_FY2023.clean.md") == "20-F"


def test_detect_filing_type_annual():
    assert detect_filing_type("SRC_002_ANNUAL_REPORT_2025.txt") == "annual_report"


def test_detect_sections():
    text = "CONSOLIDATED BALANCE SHEET\nCONSOLIDATED STATEMENTS OF INCOME"
    sections = detect_sections(text)
    assert "balance_sheet" in sections
    assert "income_statement" in sections


def test_analyze_filing_full():
    text = (
        "(in thousands)\n"
        "For the Year Ended December 31, 2024\n"
        "Revenue $83,902\n"
        "CONSOLIDATED STATEMENTS OF OPERATIONS\n"
    )
    meta = analyze_filing("SRC_001_10-K_FY2024.clean.md", text)
    assert meta.filing_type == "10-K"
    assert meta.scale == "thousands"
    assert meta.scale_confidence == "high"
    assert meta.currency == "USD"
    assert "FY2024" in meta.periods_visible
    assert "income_statement" in meta.sections_found
