"""Tests for configuration loader."""

from elsian.config import load_field_aliases, load_selection_rules


def test_load_field_aliases(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "ingresos" in aliases
    assert "net_income" in aliases
    assert len(aliases) >= 22


def test_load_selection_rules(config_dir):
    rules = load_selection_rules(config_dir)
    assert "filing_priority_by_period" in rules
    assert "source_type_priority" in rules
