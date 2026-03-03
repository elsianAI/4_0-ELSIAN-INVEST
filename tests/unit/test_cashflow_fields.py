"""Tests for BL-035: cfi, cff, delta_cash canonical fields."""

import json
from pathlib import Path

from elsian.normalize.aliases import AliasResolver
from elsian.config import load_field_aliases


# ---------------------------------------------------------------------------
# 1. field_aliases.json contains the 3 new fields
# ---------------------------------------------------------------------------

def test_field_aliases_has_cfi(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "cfi" in aliases, "cfi missing from field_aliases.json"
    assert len(aliases["cfi"]["aliases"]) >= 10


def test_field_aliases_has_cff(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "cff" in aliases, "cff missing from field_aliases.json"
    assert len(aliases["cff"]["aliases"]) >= 10


def test_field_aliases_has_delta_cash(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "delta_cash" in aliases, "delta_cash missing from field_aliases.json"
    assert len(aliases["delta_cash"]["aliases"]) >= 10


def test_canonical_names_count_includes_new_fields():
    resolver = AliasResolver()
    names = resolver.get_all_canonical_names()
    assert len(names) >= 25, f"Expected >=25 canonical names, got {len(names)}"
    assert "cfi" in names
    assert "cff" in names
    assert "delta_cash" in names


# ---------------------------------------------------------------------------
# 2. AliasResolver maps common CF labels to canonical names
# ---------------------------------------------------------------------------

class TestAliasResolverCashflow:
    """Test that common Cash Flow Statement labels resolve correctly."""

    def setup_method(self):
        self.resolver = AliasResolver()

    # cfi aliases
    def test_resolve_cfi_net_cash_used_investing(self):
        assert self.resolver.resolve("Net cash used in investing activities") == "cfi"

    def test_resolve_cfi_net_cash_provided_investing(self):
        assert self.resolver.resolve("Net cash provided by investing activities") == "cfi"

    def test_resolve_cfi_net_cash_provided_used_investing(self):
        assert self.resolver.resolve("Net cash provided by (used in) investing activities") == "cfi"

    def test_resolve_cfi_cash_flows_from_investing(self):
        assert self.resolver.resolve("Cash flows from investing activities") == "cfi"

    # cff aliases
    def test_resolve_cff_net_cash_used_financing(self):
        assert self.resolver.resolve("Net cash used in financing activities") == "cff"

    def test_resolve_cff_net_cash_provided_financing(self):
        assert self.resolver.resolve("Net cash provided by financing activities") == "cff"

    def test_resolve_cff_net_cash_provided_used_financing(self):
        assert self.resolver.resolve("Net cash provided by (used in) financing activities") == "cff"

    def test_resolve_cff_cash_flows_from_financing(self):
        assert self.resolver.resolve("Cash flows from financing activities") == "cff"

    # delta_cash aliases
    def test_resolve_delta_cash_net_increase_decrease(self):
        assert self.resolver.resolve("Net increase (decrease) in cash, cash equivalents and restricted cash") == "delta_cash"

    def test_resolve_delta_cash_change_in_cash(self):
        assert self.resolver.resolve("Change in cash and cash equivalents") == "delta_cash"

    def test_resolve_delta_cash_net_decrease(self):
        assert self.resolver.resolve("Net decrease in cash, cash equivalents and restricted cash") == "delta_cash"

    def test_resolve_delta_cash_net_increase(self):
        assert self.resolver.resolve("Net increase in cash, cash equivalents and restricted cash") == "delta_cash"

    def test_resolve_delta_cash_net_change(self):
        assert self.resolver.resolve("Net change in cash and cash equivalents") == "delta_cash"


# ---------------------------------------------------------------------------
# 3. iXBRL concept map has entries for the 3 new fields
# ---------------------------------------------------------------------------

def test_ixbrl_concept_map_has_new_fields():
    config_dir = Path(__file__).resolve().parents[2] / "config"
    ixbrl_path = config_dir / "ixbrl_concept_map.json"
    data = json.loads(ixbrl_path.read_text())
    mapping = data["mapping"]

    # cfi
    assert mapping.get("us-gaap:NetCashProvidedByUsedInInvestingActivities") == "cfi"
    assert mapping.get("ifrs-full:CashFlowsFromUsedInInvestingActivities") == "cfi"

    # cff
    assert mapping.get("us-gaap:NetCashProvidedByUsedInFinancingActivities") == "cff"
    assert mapping.get("ifrs-full:CashFlowsFromUsedInFinancingActivities") == "cff"

    # delta_cash
    assert mapping.get("us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect") == "delta_cash"
    assert mapping.get("us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease") == "delta_cash"


# ---------------------------------------------------------------------------
# 4. No confusion between cfo-family aliases
# ---------------------------------------------------------------------------

class TestNoCrossContamination:
    """Ensure cfo/cfi/cff/delta_cash aliases don't cross-resolve."""

    def setup_method(self):
        self.resolver = AliasResolver()

    def test_cfo_stays_cfo(self):
        assert self.resolver.resolve("Net cash provided by operating activities") == "cfo"

    def test_cfi_not_cfo(self):
        assert self.resolver.resolve("Net cash used in investing activities") != "cfo"

    def test_cff_not_cfo(self):
        assert self.resolver.resolve("Net cash used in financing activities") != "cfo"

    def test_delta_cash_not_cfo(self):
        assert self.resolver.resolve("Net increase (decrease) in cash") != "cfo"

    def test_investing_not_financing(self):
        assert self.resolver.resolve("Net cash used in investing activities") != "cff"

    def test_financing_not_investing(self):
        assert self.resolver.resolve("Net cash used in financing activities") != "cfi"
