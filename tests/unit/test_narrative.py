"""Tests for narrative extraction ported from 3.0."""

from elsian.extract.narrative import extract_from_narrative, NarrativeField


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
