"""Extended tests for AliasResolver — rejection, priority, additive, fuzzy."""

from elsian.normalize.aliases import AliasResolver


def test_reject_eps_as_net_income():
    """EPS-like labels should NOT resolve to net_income."""
    resolver = AliasResolver()
    assert resolver.resolve("Net income per share") is None
    assert resolver.resolve("Net income (loss) per diluted share") is None


def test_liabilities_and_equity_is_total_assets():
    """'Total liabilities and stockholders equity' = total_assets (A = L + E)."""
    resolver = AliasResolver()
    assert resolver.resolve("Total liabilities and stockholders equity") == "total_assets"


def test_reject_cash_restricted():
    resolver = AliasResolver()
    assert resolver.resolve("Restricted cash") is None


def test_is_additive_sga():
    resolver = AliasResolver()
    assert resolver.is_additive("sga") is True


def test_is_additive_ingresos_false():
    resolver = AliasResolver()
    assert resolver.is_additive("ingresos") is False


def test_label_priority():
    resolver = AliasResolver()
    # exact match: "^operating income"  for ebit
    p1 = resolver.label_priority("ebit", "Operating income")
    p2 = resolver.label_priority("ebit", "Some other income from operations")
    assert p1 > p2


def test_get_multiplier():
    resolver = AliasResolver()
    # Most fields have null multiplier
    assert resolver.get_multiplier("ingresos") is None


def test_fuzzy_matching():
    """Multi-word aliases should match as substrings."""
    resolver = AliasResolver()
    # "total assets" is an alias — should match even with prefix
    result = resolver.resolve("total assets")
    assert result == "total_assets"


def test_reject_income_tax_deferred():
    resolver = AliasResolver()
    assert resolver.resolve("Deferred income tax") is None
    assert resolver.resolve("Income tax expense") == "income_tax"
