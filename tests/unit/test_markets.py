"""Tests for elsian.markets — exchange/country awareness utilities."""

from elsian.markets import (
    LOCAL_FILING_KEYWORDS_BY_EXCHANGE,
    LOCAL_FILING_KEYWORDS_COMMON,
    NON_US_COUNTRIES,
    NON_US_EXCHANGES,
    infer_regulator_code,
    is_non_us,
    normalize_country,
    normalize_exchange,
)


class TestNormalizeCountry:
    def test_none_returns_none(self):
        assert normalize_country(None) is None

    def test_empty_returns_none(self):
        assert normalize_country("") is None
        assert normalize_country("   ") is None

    def test_usa_variants(self):
        assert normalize_country("USA") == "US"
        assert normalize_country("United States") == "US"
        assert normalize_country("UNITED STATES OF AMERICA") == "US"

    def test_standard_aliases(self):
        assert normalize_country("Australia") == "AU"
        assert normalize_country("ISRAEL") == "IL"
        assert normalize_country("France") == "FR"
        assert normalize_country("canada") == "CA"
        assert normalize_country("United Kingdom") == "GB"
        assert normalize_country("Hong Kong") == "HK"

    def test_already_iso_code(self):
        assert normalize_country("US") == "US"
        assert normalize_country("AU") == "AU"
        assert normalize_country("fr") == "FR"

    def test_unknown_passthrough(self):
        assert normalize_country("ZZ") == "ZZ"


class TestNormalizeExchange:
    def test_none_returns_none(self):
        assert normalize_exchange(None) is None

    def test_empty_returns_none(self):
        assert normalize_exchange("") is None

    def test_uppercase(self):
        assert normalize_exchange("nyse") == "NYSE"
        assert normalize_exchange("Asx") == "ASX"

    def test_otc_detection(self):
        assert normalize_exchange("OTC Markets") == "OTC"
        assert normalize_exchange("otcbb") == "OTC"


class TestIsNonUs:
    def test_us_company(self):
        assert is_non_us(exchange="NYSE", country="US", cik="0001234") is False

    def test_non_us_country(self):
        assert is_non_us(country="AU") is True
        assert is_non_us(country="FR") is True

    def test_non_us_exchange(self):
        assert is_non_us(exchange="ASX") is True
        assert is_non_us(exchange="LSE") is True
        assert is_non_us(exchange="EPA") is True

    def test_no_cik_no_us_country(self):
        assert is_non_us(cik=None, country=None) is True

    def test_no_cik_with_us_country(self):
        assert is_non_us(cik=None, country="US") is False


class TestInferRegulatorCode:
    def test_hkex(self):
        assert infer_regulator_code("SEHK", "HK") == "HKEX"
        assert infer_regulator_code("HKEX") == "HKEX"
        assert infer_regulator_code(country="HK") == "HKEX"

    def test_rns(self):
        assert infer_regulator_code("LSE") == "RNS"
        assert infer_regulator_code("AIM", "GB") == "RNS"
        assert infer_regulator_code(country="UK") == "RNS"

    def test_asx(self):
        assert infer_regulator_code("ASX") == "ASX"
        assert infer_regulator_code(country="AU") == "ASX"

    def test_euronext(self):
        assert infer_regulator_code("EPA") == "EURONEXT"
        assert infer_regulator_code(country="FR") == "EURONEXT"

    def test_sedar(self):
        assert infer_regulator_code("TSX") == "SEDAR+"
        assert infer_regulator_code(country="CA") == "SEDAR+"

    def test_fallback(self):
        assert infer_regulator_code("NYSE", "US") == "LOCAL_IR"
        assert infer_regulator_code() == "LOCAL_IR"


class TestConstants:
    def test_non_us_exchanges_not_empty(self):
        assert len(NON_US_EXCHANGES) >= 6

    def test_non_us_countries_not_empty(self):
        assert len(NON_US_COUNTRIES) >= 8

    def test_keywords_common_not_empty(self):
        assert len(LOCAL_FILING_KEYWORDS_COMMON) >= 8

    def test_keywords_by_exchange_keys(self):
        assert "ASX" in LOCAL_FILING_KEYWORDS_BY_EXCHANGE
        assert "SEHK" in LOCAL_FILING_KEYWORDS_BY_EXCHANGE
        assert "LSE" in LOCAL_FILING_KEYWORDS_BY_EXCHANGE
        assert "EPA" in LOCAL_FILING_KEYWORDS_BY_EXCHANGE
