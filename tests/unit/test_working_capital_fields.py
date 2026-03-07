"""Tests for BL-058: working capital canonical fields."""

import json
from pathlib import Path

from elsian.config import load_field_aliases
from elsian.extract.phase import _period_affinity, _section_bonus
from elsian.normalize.aliases import AliasResolver


def test_field_aliases_has_accounts_receivable(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "accounts_receivable" in aliases
    assert len(aliases["accounts_receivable"]["aliases"]) >= 7


def test_field_aliases_has_inventories(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "inventories" in aliases
    assert len(aliases["inventories"]["aliases"]) >= 3


def test_field_aliases_has_accounts_payable(config_dir):
    aliases = load_field_aliases(config_dir)
    assert "accounts_payable" in aliases
    assert len(aliases["accounts_payable"]["aliases"]) >= 2


def test_canonical_names_count_includes_working_capital_fields():
    resolver = AliasResolver()
    names = resolver.get_all_canonical_names()
    assert len(names) == 29, f"Expected 29 canonical names, got {len(names)}"
    assert "accounts_receivable" in names
    assert "inventories" in names
    assert "accounts_payable" in names


class TestAliasResolverWorkingCapital:
    def setup_method(self):
        self.resolver = AliasResolver()

    def test_resolve_accounts_receivable_net(self):
        assert self.resolver.resolve("Accounts receivable, net") == "accounts_receivable"

    def test_resolve_accounts_receivable_allowance(self):
        label = "Accounts receivable, less allowance for doubtful accounts"
        assert self.resolver.resolve(label) == "accounts_receivable"

    def test_resolve_trade_receivables(self):
        assert self.resolver.resolve("Trade receivables") == "accounts_receivable"

    def test_resolve_inventories(self):
        assert self.resolver.resolve("Inventories") == "inventories"

    def test_resolve_inventory_net(self):
        assert self.resolver.resolve("Inventory, net") == "inventories"

    def test_resolve_accounts_payable(self):
        assert self.resolver.resolve("Accounts payable") == "accounts_payable"

    def test_resolve_trade_payables(self):
        assert self.resolver.resolve("Trade payables") == "accounts_payable"


def test_ixbrl_concept_map_has_working_capital_fields():
    config_dir = Path(__file__).resolve().parents[2] / "config"
    ixbrl_path = config_dir / "ixbrl_concept_map.json"
    data = json.loads(ixbrl_path.read_text())
    mapping = data["mapping"]
    preferred = data["preferred_concepts"]

    assert mapping.get("us-gaap:AccountsReceivableNetCurrent") == "accounts_receivable"
    assert mapping.get("us-gaap:InventoryNet") == "inventories"
    assert mapping.get("us-gaap:AccountsPayableCurrent") == "accounts_payable"

    assert preferred.get("accounts_receivable") == ["us-gaap:AccountsReceivableNetCurrent"]
    assert preferred.get("inventories") == ["us-gaap:InventoryNet"]
    assert preferred.get("accounts_payable") == ["us-gaap:AccountsPayableCurrent"]


class TestNoCrossContamination:
    def setup_method(self):
        self.resolver = AliasResolver()

    def test_receivables_not_payables(self):
        assert self.resolver.resolve("Accounts receivable, net") != "accounts_payable"

    def test_inventory_not_receivables(self):
        assert self.resolver.resolve("Inventories") != "accounts_receivable"

    def test_payables_not_inventory(self):
        assert self.resolver.resolve("Accounts payable") != "inventories"


def test_section_bonus_penalizes_working_capital_net_income_tables():
    source_location = "SRC_001_10-K_FY2026.clean.md:table:income_statement:net_income:tbl9:row13:col3"
    assert _section_bonus(source_location, canonical="accounts_payable") < 0
    assert _section_bonus(source_location, canonical="inventories") < 0
    assert _section_bonus(source_location, canonical="accounts_receivable") < 0


def test_period_affinity_prefers_primary_filing_for_working_capital_fields():
    assert _period_affinity("FY2021", "SRC_006_10-K_FY2021.clean.md", "accounts_payable") == 0
    assert _period_affinity("FY2021", "SRC_005_10-K_FY2022.clean.md", "accounts_payable") == 1
