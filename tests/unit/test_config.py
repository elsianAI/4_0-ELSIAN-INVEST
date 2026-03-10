"""Tests for configuration loader."""

from elsian.config import load_field_aliases, load_selection_rules, load_extraction_rules, resolve_extraction_pack


def test_load_field_aliases(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "ingresos" in aliases
    assert "net_income" in aliases
    assert len(aliases) >= 22


def test_load_selection_rules(config_dir):
    rules = load_selection_rules(config_dir)
    assert "filing_priority_by_period" in rules
    assert "source_type_priority" in rules


def test_load_extraction_rules(config_dir):
    rules = load_extraction_rules(config_dir)
    assert "base" in rules
    assert "packs" in rules
    assert "_pack_routing" in rules
    assert "context_bonus" in rules["base"]
    assert "html" in rules["base"]


def test_resolve_extraction_pack_base_only():
    """Unknown pack name → result equals base."""
    rules = {
        "base": {"context_bonus": {"hard_penalty": -300}},
        "packs": {},
    }
    resolved = resolve_extraction_pack(rules, "nonexistent")
    assert resolved == {"context_bonus": {"hard_penalty": -300}}


def test_pack_overrides_base_auxiliary_markers(config_dir):
    """sec_html pack must drop profit_and_loss_transfer_agreement vs base."""
    rules = load_extraction_rules(config_dir)
    base = rules["base"]["context_bonus"]["auxiliary_note_markers"]
    resolved = resolve_extraction_pack(rules, "sec_html")
    sec_markers = resolved["context_bonus"]["auxiliary_note_markers"]
    assert "profit_and_loss_transfer_agreement" in base
    assert "profit_and_loss_transfer_agreement" not in sec_markers


def test_precedence_base_pack_case_overrides():
    """Case config_overrides wins over pack wins over base."""
    rules = {
        "base": {"context_bonus": {"hard_penalty": -300, "primary_label_bonus": 100}},
        "packs": {"mypack": {"context_bonus": {"hard_penalty": -200}}},
    }
    case_overrides = {"context_bonus": {"hard_penalty": -50}}
    resolved = resolve_extraction_pack(rules, "mypack", case_overrides)
    assert resolved["context_bonus"]["hard_penalty"] == -50
    assert resolved["context_bonus"]["primary_label_bonus"] == 100
