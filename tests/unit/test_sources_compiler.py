"""Tests for elsian.acquire.sources_compiler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elsian.acquire.sources_compiler import (
    _build_empresa,
    _dedup_by_content_hash,
    _dedup_by_url_accession,
    _parse_filing_stem,
    _prefer_candidate,
    _source_from_market_data,
    _sources_from_filings_dir,
    _sources_from_transcripts,
    build_cobertura,
    compile_sources,
    infer_category,
    normalize_type,
    save_sources_pack,
    source_key,
)


# ─────────────────────────────────────────────────────────────────────────────
# TestNormalizeType
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeType:
    def test_uppercase_passthrough(self) -> None:
        assert normalize_type("10-K") == "10-K"

    def test_lowercase_input(self) -> None:
        assert normalize_type("10-k") == "10-K"

    def test_strips_whitespace(self) -> None:
        assert normalize_type("  20-F ") == "20-F"

    def test_none_returns_other(self) -> None:
        assert normalize_type(None) == "OTHER"

    def test_int_returns_other(self) -> None:
        assert normalize_type(42) == "OTHER"  # type: ignore[arg-type]

    def test_empty_string_returns_other(self) -> None:
        assert normalize_type("") == "OTHER"

    def test_blank_whitespace_returns_other(self) -> None:
        assert normalize_type("   ") == "OTHER"


# ─────────────────────────────────────────────────────────────────────────────
# TestInferCategory
# ─────────────────────────────────────────────────────────────────────────────


class TestInferCategory:
    def test_annual_filing_regulatorio(self) -> None:
        assert infer_category("10-K") == "REGULATORIO"

    def test_quarterly_regulatorio(self) -> None:
        assert infer_category("10-Q") == "REGULATORIO"

    def test_foreign_annual_regulatorio(self) -> None:
        assert infer_category("20-F") == "REGULATORIO"

    def test_six_k_regulatorio(self) -> None:
        assert infer_category("6-K") == "REGULATORIO"

    def test_eight_k_regulatorio(self) -> None:
        assert infer_category("8-K") == "REGULATORIO"

    def test_earnings_transcript_transcripcion(self) -> None:
        assert infer_category("EARNINGS_TRANSCRIPT") == "TRANSCRIPCION"

    def test_transcript_keyword_in_type(self) -> None:
        assert infer_category("CALL_TRANSCRIPT") == "TRANSCRIPCION"

    def test_investor_presentation_ir(self) -> None:
        assert infer_category("INVESTOR_PRESENTATION") == "IR"

    def test_press_release_ir(self) -> None:
        assert infer_category("PRESS_RELEASE") == "IR"

    def test_market_data_mercado(self) -> None:
        assert infer_category("MARKET_DATA") == "MERCADO"

    def test_unknown_type_otra(self) -> None:
        assert infer_category("UNKNOWN_XYZ") == "OTRA"

    def test_lowercase_normalized(self) -> None:
        assert infer_category("market_data") == "MERCADO"


# ─────────────────────────────────────────────────────────────────────────────
# TestSourceKey
# ─────────────────────────────────────────────────────────────────────────────


class TestSourceKey:
    def test_url_normalized(self) -> None:
        src = {"url": "  HTTPS://EXAMPLE.COM/FILING.HTM  ", "accession_number": None}
        url_key, acc_key = source_key(src)
        assert url_key == "https://example.com/filing.htm"
        assert acc_key == ""

    def test_accession_normalized(self) -> None:
        src = {"url": "", "accession_number": "0001193125-24-012345"}
        url_key, acc_key = source_key(src)
        assert url_key == ""
        assert acc_key == "0001193125-24-012345"

    def test_missing_fields_empty_strings(self) -> None:
        url_key, acc_key = source_key({})
        assert url_key == ""
        assert acc_key == ""

    def test_non_string_url_returns_empty(self) -> None:
        url_key, _ = source_key({"url": 42})
        assert url_key == ""


# ─────────────────────────────────────────────────────────────────────────────
# TestParseFilingStem
# ─────────────────────────────────────────────────────────────────────────────


class TestParseFilingStem:
    def test_annual_10k(self) -> None:
        result = _parse_filing_stem("SRC_001_10-K_FY2024")
        assert result == ("SRC_001", "10-K", "FY2024")

    def test_quarterly_10q(self) -> None:
        result = _parse_filing_stem("SRC_007_10-Q_Q3-2025")
        assert result == ("SRC_007", "10-Q", "Q3-2025")

    def test_earnings_8k(self) -> None:
        result = _parse_filing_stem("SRC_013_8-K_Q1-2025")
        assert result == ("SRC_013", "8-K", "Q1-2025")

    def test_foreign_20f(self) -> None:
        result = _parse_filing_stem("SRC_002_20-F_FY2023")
        assert result == ("SRC_002", "20-F", "FY2023")

    def test_no_match_returns_none(self) -> None:
        assert _parse_filing_stem("random_name.txt") is None
        assert _parse_filing_stem("NOTASRC_001_10-K_FY2024") is None

    def test_lowercase_src_normalized(self) -> None:
        result = _parse_filing_stem("src_001_10-k_fy2024")
        assert result is not None
        assert result[0] == "SRC_001"
        assert result[1] == "10-K"


# ─────────────────────────────────────────────────────────────────────────────
# TestDeduplicateByUrl
# ─────────────────────────────────────────────────────────────────────────────


class TestDeduplicateByUrl:
    def _make_src(
        self,
        src_id: str,
        tipo: str = "10-K",
        url: str = "",
        local_path: str | None = None,
        accession: str | None = None,
    ) -> dict:
        return {
            "source_id": src_id,
            "tipo": tipo,
            "url": url,
            "local_path": local_path,
            "accession_number": accession,
        }

    def test_no_duplication(self) -> None:
        sources = [
            self._make_src("SRC_001", url="https://a.com"),
            self._make_src("SRC_002", url="https://b.com"),
        ]
        result, dropped = _dedup_by_url_accession(sources)
        assert dropped == 0
        assert len(result) == 2

    def test_url_dedup_drops_lower_priority(self) -> None:
        # SRC_001 (IR) and SRC_002 (10-K) share the same URL.
        # 10-K has higher priority → 10-K should win.
        sources = [
            self._make_src("SRC_001", tipo="INVESTOR_PRESENTATION", url="https://same.com"),
            self._make_src("SRC_002", tipo="10-K", url="https://same.com"),
        ]
        result, dropped = _dedup_by_url_accession(sources)
        assert dropped == 1
        assert len(result) == 1
        assert result[0]["source_id"] == "SRC_002"

    def test_url_dedup_keeps_existing_if_better(self) -> None:
        sources = [
            self._make_src("SRC_001", tipo="10-K", url="https://same.com"),
            self._make_src("SRC_002", tipo="INVESTOR_PRESENTATION", url="https://same.com"),
        ]
        result, dropped = _dedup_by_url_accession(sources)
        assert dropped == 1
        assert result[0]["source_id"] == "SRC_001"

    def test_accession_dedup(self) -> None:
        acc = "0001193125-24-012345"
        sources = [
            self._make_src("SRC_001", accession=acc),
            self._make_src("SRC_002", accession=acc),
        ]
        result, dropped = _dedup_by_url_accession(sources)
        assert dropped == 1
        assert len(result) == 1

    def test_empty_url_not_deduped(self) -> None:
        # Two sources with empty URL should not be deduped by URL
        sources = [
            self._make_src("SRC_001", url=""),
            self._make_src("SRC_002", url=""),
        ]
        result, dropped = _dedup_by_url_accession(sources)
        assert dropped == 0
        assert len(result) == 2


# ─────────────────────────────────────────────────────────────────────────────
# TestDeduplicateByContentHash
# ─────────────────────────────────────────────────────────────────────────────


class TestDeduplicateByContentHash:
    def _make_src(self, src_id: str, tipo: str = "10-K", chash: str | None = None) -> dict:
        return {"source_id": src_id, "tipo": tipo, "content_hash": chash}

    def test_no_hash_no_dedup(self) -> None:
        sources = [self._make_src("SRC_001"), self._make_src("SRC_002")]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 0
        assert len(result) == 2

    def test_short_hash_not_deduped(self) -> None:
        sources = [
            self._make_src("SRC_001", chash="abc123"),  # < 16 chars
            self._make_src("SRC_002", chash="abc123"),
        ]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 0
        assert len(result) == 2

    def test_same_hash_drops_lower_priority(self) -> None:
        h = "a" * 64  # valid SHA-256 length
        sources = [
            self._make_src("SRC_001", tipo="INVESTOR_PRESENTATION", chash=h),
            self._make_src("SRC_002", tipo="10-K", chash=h),
        ]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 1
        assert len(result) == 1
        assert result[0]["source_id"] == "SRC_002"  # 10-K has higher priority

    def test_different_hashes_kept(self) -> None:
        sources = [
            self._make_src("SRC_001", chash="a" * 64),
            self._make_src("SRC_002", chash="b" * 64),
        ]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 0
        assert len(result) == 2

    def test_hash_case_insensitive(self) -> None:
        h_lower = "abcdef" * 10 + "1234"
        h_upper = h_lower.upper()
        sources = [
            self._make_src("SRC_001", tipo="10-K", chash=h_lower),
            self._make_src("SRC_002", tipo="10-Q", chash=h_upper),
        ]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestBuildCobertura
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildCobertura:
    def _make_src(self, src_id: str, tipo: str) -> dict:
        return {"source_id": src_id, "tipo": tipo}

    def test_annual_found(self) -> None:
        sources = [self._make_src("SRC_001", "10-K")]
        cob = build_cobertura(sources)
        assert cob["informe_anual"]["encontrado"] is True
        assert cob["informe_anual"]["source_id"] == "SRC_001"

    def test_annual_not_found(self) -> None:
        cob = build_cobertura([self._make_src("SRC_001", "10-Q")])
        assert cob["informe_anual"]["encontrado"] is False
        assert cob["informe_anual"]["source_id"] is None

    def test_quarterly_found(self) -> None:
        sources = [self._make_src("SRC_002", "10-Q")]
        cob = build_cobertura(sources)
        assert cob["informe_trimestral"]["encontrado"] is True

    def test_market_data_found(self) -> None:
        sources = [self._make_src("SRC_MKT", "MARKET_DATA")]
        cob = build_cobertura(sources)
        assert cob["fuente_precio_y_acciones"]["encontrado"] is True

    def test_transcript_found(self) -> None:
        sources = [self._make_src("TR_001", "EARNINGS_TRANSCRIPT")]
        cob = build_cobertura(sources)
        assert cob["transcripcion_resultados_mas_reciente"]["encontrado"] is True

    def test_empty_sources_all_false(self) -> None:
        cob = build_cobertura([])
        for v in cob.values():
            assert v["encontrado"] is False

    def test_20f_counts_as_annual(self) -> None:
        sources = [self._make_src("SRC_001", "20-F")]
        cob = build_cobertura(sources)
        assert cob["informe_anual"]["encontrado"] is True

    def test_8k_counts_as_earnings(self) -> None:
        sources = [self._make_src("SRC_005", "8-K")]
        cob = build_cobertura(sources)
        assert cob["earnings_release_mas_reciente"]["encontrado"] is True


# ─────────────────────────────────────────────────────────────────────────────
# TestSourceFromMarketData
# ─────────────────────────────────────────────────────────────────────────────


class TestSourceFromMarketData:
    def test_empty_dict_returns_none(self) -> None:
        assert _source_from_market_data({}, "2025-01-01") is None

    def test_valid_market_data(self) -> None:
        md = {
            "ticker": "TZOO",
            "price": 12.34,
            "currency": "USD",
            "exchange": "NASDAQ",
            "sector": "Technology",
            "industry": "Software",
            "fetched_at": "2025-03-04T10:00:00Z",
        }
        src = _source_from_market_data(md, "2025-03-04")
        assert src is not None
        assert src["tipo"] == "MARKET_DATA"
        assert src["categoria"] == "MERCADO"
        assert src["source_id"] == "SRC_MKT"
        assert src["market_snapshot"]["price"] == 12.34
        assert src["fecha_publicacion"] == "2025-03-04"

    def test_fetched_at_truncated_to_date(self) -> None:
        md = {"ticker": "X", "fetched_at": "2026-01-15T09:30:00Z"}
        src = _source_from_market_data(md, "2026-01-15")
        assert src["fecha_publicacion"] == "2026-01-15"


# ─────────────────────────────────────────────────────────────────────────────
# TestSourcesFromTranscripts
# ─────────────────────────────────────────────────────────────────────────────


class TestSourcesFromTranscripts:
    def test_empty_data_returns_empty(self) -> None:
        result = _sources_from_transcripts({}, "2025-01-01")
        assert result == []

    def test_no_sources_key(self) -> None:
        result = _sources_from_transcripts({"ticker": "TZOO"}, "2025-01-01")
        assert result == []

    def test_single_transcript(self) -> None:
        data = {
            "ticker": "TZOO",
            "sources": [
                {
                    "source_id": "TR_001",
                    "tipo": "EARNINGS_TRANSCRIPT",
                    "period": "Q1-2025",
                    "url": "https://fintool.com/tr/001",
                    "title": "TZOO Q1 2025 Earnings",
                    "date": "2025-05-01",
                    "local_path": None,
                    "content_hash": None,
                }
            ],
        }
        result = _sources_from_transcripts(data, "2025-05-01")
        assert len(result) == 1
        src = result[0]
        assert src["source_id"] == "TR_001"
        assert src["tipo"] == "EARNINGS_TRANSCRIPT"
        assert src["categoria"] == "TRANSCRIPCION"
        assert src["url"] == "https://fintool.com/tr/001"

    def test_skips_non_dict_items(self) -> None:
        data = {"sources": ["invalid", None, {"source_id": "TR_001", "tipo": "TRANSCRIPT"}]}
        result = _sources_from_transcripts(data, "2025-01-01")
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestSourcesFromFilingsDir
# ─────────────────────────────────────────────────────────────────────────────


class TestSourcesFromFilingsDir:
    def test_no_filings_dir(self, tmp_path: Path) -> None:
        result = _sources_from_filings_dir(tmp_path, {}, "2025-01-01")
        assert result == []

    def test_basic_filings_parsed(self, tmp_path: Path) -> None:
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # Create minimal filing files (no .clean.md quality requirement for .txt)
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Revenue 1000\n" * 200)
        (filings_dir / "SRC_002_10-Q_Q1-2024.txt").write_text("Revenue 250\n" * 200)
        result = _sources_from_filings_dir(tmp_path, {}, "2025-01-01")
        assert len(result) == 2
        ids = {s["source_id"] for s in result}
        assert "SRC_001" in ids
        assert "SRC_002" in ids

    def test_multiple_extensions_collapsed(self, tmp_path: Path) -> None:
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        # Same filing in .htm and .txt
        (filings_dir / "SRC_001_10-K_FY2024.htm").write_text("<html/>")
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Revenue 1000\n" * 100)
        result = _sources_from_filings_dir(tmp_path, {}, "2025-01-01")
        # Should collapse to ONE source for SRC_001
        assert len(result) == 1
        assert result[0]["source_id"] == "SRC_001"

    def test_unrecognized_files_ignored(self, tmp_path: Path) -> None:
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "README.txt").write_text("not a filing")
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Revenue\n" * 50)
        result = _sources_from_filings_dir(tmp_path, {}, "2025-01-01")
        assert len(result) == 1

    def test_tipo_inferred_from_filename(self, tmp_path: Path) -> None:
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Rev\n")
        result = _sources_from_filings_dir(tmp_path, {}, "2025-01-01")
        assert result[0]["tipo"] == "10-K"
        assert result[0]["categoria"] == "REGULATORIO"


# ─────────────────────────────────────────────────────────────────────────────
# TestBuildEmpresa
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildEmpresa:
    def test_market_data_takes_precedence(self) -> None:
        manifest = {"source": "sec_edgar", "cik": "0001234567"}
        md = {
            "company_name": "Travelzoo Inc.",
            "exchange": "NASDAQ",
            "country": "US",
            "sector": "Travel",
            "industry": "Internet",
            "currency": "USD",
        }
        empresa = _build_empresa("TZOO", manifest, md, {})
        assert empresa["nombre"] == "Travelzoo Inc."
        assert empresa["bolsa"] == "NASDAQ"
        assert empresa["sector"] == "Travel"
        assert empresa["currency"] == "USD"
        assert empresa["cik"] == "0001234567"

    def test_fallback_when_no_market_data(self) -> None:
        empresa = _build_empresa("TZOO", {}, {}, {})
        assert empresa["ticker"] == "TZOO"
        assert empresa["nombre"] == "TZOO"
        assert empresa["currency"] == "USD"

    def test_ticker_uppercased(self) -> None:
        empresa = _build_empresa("tzoo", {}, {}, {})
        assert empresa["ticker"] == "TZOO"


# ─────────────────────────────────────────────────────────────────────────────
# TestPreferCandidate
# ─────────────────────────────────────────────────────────────────────────────


class TestPreferCandidate:
    def _s(self, tipo: str, local: bool = False, src_id: str = "SRC_099") -> dict:
        return {"tipo": tipo, "local_path": "/f" if local else None, "source_id": src_id}

    def test_higher_priority_wins(self) -> None:
        existing = self._s("INVESTOR_PRESENTATION")
        candidate = self._s("10-K")
        assert _prefer_candidate(existing, candidate) is True

    def test_lower_priority_loses(self) -> None:
        existing = self._s("10-K")
        candidate = self._s("INVESTOR_PRESENTATION")
        assert _prefer_candidate(existing, candidate) is False

    def test_local_path_wins_tie(self) -> None:
        existing = self._s("10-K", local=False)
        candidate = self._s("10-K", local=True)
        assert _prefer_candidate(existing, candidate) is True

    def test_smaller_src_id_wins_all_equal(self) -> None:
        existing = self._s("10-K", local=True, src_id="SRC_002")
        candidate = self._s("10-K", local=True, src_id="SRC_001")
        assert _prefer_candidate(existing, candidate) is True


# ─────────────────────────────────────────────────────────────────────────────
# TestCompileSources — integration with mock case dir
# ─────────────────────────────────────────────────────────────────────────────


class TestCompileSources:
    def _setup_case(self, tmp_path: Path) -> Path:
        """Create a minimal but complete mock case directory."""
        # filings
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Revenue 1000\n" * 50)
        (filings_dir / "SRC_002_10-Q_Q1-2024.txt").write_text("Revenue 250\n" * 50)
        (filings_dir / "SRC_003_8-K_Q1-2024.txt").write_text("Earnings release\n" * 50)

        # manifest
        manifest = {
            "ticker": "MOCK",
            "source": "sec_edgar",
            "cik": "0001234567",
            "filings_downloaded": 3,
        }
        (tmp_path / "filings_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        # market data
        md = {"ticker": "MOCK", "price": 10.0, "currency": "USD", "sector": "Tech"}
        (tmp_path / "_market_data.json").write_text(json.dumps(md), encoding="utf-8")

        # transcripts
        tr = {
            "ticker": "MOCK",
            "sources": [
                {
                    "source_id": "TR_001",
                    "tipo": "EARNINGS_TRANSCRIPT",
                    "period": "Q1-2024",
                    "url": "https://fintool.com/tr/001",
                    "title": "MOCK Q1 2024 Earnings Call",
                    "date": "2024-05-01",
                    "local_path": None,
                    "content_hash": None,
                }
            ],
        }
        (tmp_path / "_transcripts.json").write_text(json.dumps(tr), encoding="utf-8")
        return tmp_path

    def test_compile_returns_correct_schema(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        pack = compile_sources("MOCK", case_dir)
        assert pack["version_esquema"] == "SourcesPack_v1"
        assert pack["ticker"] == "MOCK"
        assert "empresa" in pack
        assert "cobertura_documental" in pack
        assert "fuentes" in pack
        assert "_meta" in pack

    def test_filing_count_includes_all_types(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        pack = compile_sources("MOCK", case_dir)
        meta = pack["_meta"]["fuentes_consolidadas"]
        # 3 filing sources + 1 transcript + 1 market data = 5 total input
        assert meta["filing_sources"] == 3
        assert meta["transcript_sources"] == 1
        assert meta["market_data_sources"] == 1
        assert meta["total_input"] == 5

    def test_cobertura_annual_found(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        pack = compile_sources("MOCK", case_dir)
        assert pack["cobertura_documental"]["informe_anual"]["encontrado"] is True

    def test_cobertura_transcript_found(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        pack = compile_sources("MOCK", case_dir)
        assert pack["cobertura_documental"]["transcripcion_resultados_mas_reciente"]["encontrado"] is True

    def test_market_data_source_included(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        pack = compile_sources("MOCK", case_dir)
        tipos = {s["tipo"] for s in pack["fuentes"]}
        assert "MARKET_DATA" in tipos

    def test_invalid_case_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            compile_sources("MOCK", tmp_path / "nonexistent")

    def test_url_dedup_transcript_vs_filing(self, tmp_path: Path) -> None:
        """If a transcript URL matches a filing URL, dedup removes the duplicate."""
        filings_dir = tmp_path / "filings"
        filings_dir.mkdir()
        shared_url = "https://sec.gov/filing/001.htm"
        (filings_dir / "SRC_001_10-K_FY2024.txt").write_text("Revenue 1000\n" * 50)

        manifest = {"ticker": "DUP", "source": "sec_edgar"}
        (tmp_path / "filings_manifest.json").write_text(json.dumps(manifest))

        tr = {
            "ticker": "DUP",
            "sources": [
                {
                    "source_id": "TR_001",
                    "tipo": "EARNINGS_TRANSCRIPT",
                    "period": None,
                    "url": shared_url,
                    "title": "Earnings",
                    "date": None,
                    "local_path": None,
                    "content_hash": None,
                }
            ],
        }
        (tmp_path / "_transcripts.json").write_text(json.dumps(tr))

        # Also add the URL to the filing source by patching via a compile round
        # Instead: just test that sources with matching URLs are deduped
        from elsian.acquire.sources_compiler import _dedup_by_url_accession

        s1 = {"source_id": "SRC_001", "tipo": "10-K", "url": shared_url, "accession_number": None, "local_path": "/f"}
        s2 = {"source_id": "TR_001", "tipo": "EARNINGS_TRANSCRIPT", "url": shared_url, "accession_number": None, "local_path": None}
        result, dropped = _dedup_by_url_accession([s1, s2])
        assert dropped == 1
        assert len(result) == 1
        # 10-K has higher priority so it should survive
        assert result[0]["source_id"] == "SRC_001"

    def test_save_sources_pack_writes_file(self, tmp_path: Path) -> None:
        case_dir = self._setup_case(tmp_path)
        out_path = save_sources_pack("MOCK", case_dir)
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["version_esquema"] == "SourcesPack_v1"
        assert data["ticker"] == "MOCK"

    def test_no_fetcher_outputs_still_runs(self, tmp_path: Path) -> None:
        """compile_sources works even when no fetcher outputs exist."""
        (tmp_path / "filings").mkdir()
        pack = compile_sources("EMPTY", tmp_path)
        assert pack["version_esquema"] == "SourcesPack_v1"
        assert pack["fuentes"] == []
        meta = pack["_meta"]["fuentes_consolidadas"]
        assert meta["total_final"] == 0

    def test_content_hash_dedup_eliminates_duplicate(self, tmp_path: Path) -> None:
        """Two sources with identical content hashes: only one survives."""
        h = "a" * 64
        from elsian.acquire.sources_compiler import _dedup_by_content_hash

        sources = [
            {"source_id": "SRC_001", "tipo": "10-K", "content_hash": h, "local_path": "/f"},
            {"source_id": "SRC_002", "tipo": "10-Q", "content_hash": h, "local_path": None},
        ]
        result, dropped = _dedup_by_content_hash(sources)
        assert dropped == 1
        assert len(result) == 1
        # 10-K beats 10-Q
        assert result[0]["source_id"] == "SRC_001"
