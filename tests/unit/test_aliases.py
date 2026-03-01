"""Tests for AliasResolver."""

from elsian.normalize.aliases import AliasResolver


def test_resolve_exact_english():
    resolver = AliasResolver()
    assert resolver.resolve("Revenue") == "ingresos"
    assert resolver.resolve("net income") == "net_income"
    assert resolver.resolve("Total Assets") == "total_assets"


def test_resolve_unknown():
    resolver = AliasResolver()
    assert resolver.resolve("something random") is None


def test_resolve_canonical_name():
    resolver = AliasResolver()
    assert resolver.resolve("ingresos") == "ingresos"
    assert resolver.resolve("ebit") == "ebit"


def test_canonical_names_count():
    resolver = AliasResolver()
    assert len(resolver.get_all_canonical_names()) >= 22
