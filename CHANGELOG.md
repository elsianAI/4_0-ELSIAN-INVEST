# Changelog

## 2026-03-04

### [Acquire/Preflight] Complete gaps in IR Crawler (Block E) and Preflight (Block B)
- **What:** Ported missing functions from 3.0 to bring Block E and Block B to 100%:
  - **IR Crawler** (`elsian/acquire/ir_crawler.py`):
    - `parse_date_loose()`: Flexible date parser (ISO, compact, text dates)
    - `parse_year_hint()`: Fiscal year keyword extraction from text
    - `_resolve_local_candidate_date()`: Date resolution from anchor/row/URL context
    - `_extract_date_from_html_document()`: Date from HTML meta tags, <time>, title, URL
    - `_local_event_registration_penalty()`: Soft-penalize webcast/registration links
    - `_clean_embedded_pdf_url()`: Clean escaped PDF URLs from JSON/HTML
    - `_extract_embedded_title()`: Title extraction from context around PDF URLs
    - `_extract_embedded_pdf_candidates()`: ~120-line embedded PDF extractor with regex, scoring, dedup
    - `_prefer_new_candidate()`: Score-based dedup with date-aware protection
    - Updated `extract_filing_candidates()`: now resolves dates per candidate, applies event penalty,
      merges embedded PDF candidates, uses `_prefer_new_candidate()` for dedup
  - **Preflight** (`elsian/analyze/preflight.py`):
    - Added `confidence_by_signal: dict[str, str]` field to `PreflightResult`
    - Populated during `preflight()` with keys: `lang:*`, `standard:*`, `currency:*`, `fiscal_year`, `restatement`
    - Added `to_prompt_block()` method (ported from 3.0 `format_prompt_block()`)
    - Updated `to_dict()` to include `confidence_by_signal`
- **Ported from:** sec_fetcher_v2_runner.py (lines 358-410, 500-522, 743-972), filing_preflight.py (lines 268-319)
- **Tests:** 344 passed, 1 skipped, 0 failed (+67 new tests)
- **Regression:** 8/8 tickers at 100%

### [Acquire] Full audit and port of acquire module from 3.0
- **What:** Ported 6 blocks of acquire infrastructure from 3.0 `sec_fetcher_v2_runner.py`,
  `filing_preflight.py`, and `ir_url_resolver.py`:
  - **Block A** `elsian/markets.py`: Exchange/country awareness — `NON_US_EXCHANGES`,
    `NON_US_COUNTRIES`, `LOCAL_FILING_KEYWORDS_*`, `normalize_country()`,
    `normalize_exchange()`, `is_non_us()`, `infer_regulator_code()`. (25 tests)
  - **Block B** `elsian/analyze/preflight.py`: Filing pre-flight metadata extractor —
    language (en/fr/es/de), accounting standard (IFRS/US-GAAP/FR-GAAP), currency (9),
    sections (6), units per section, restatement signals, fiscal year. (26 tests)
  - **Block C** `elsian/acquire/dedup.py`: Content-based deduplication via SHA-256 —
    `normalize_text_for_hash()`, `content_hash()`, `is_duplicate()`, `dedup_texts()`. (17 tests)
  - **Block D** `elsian/acquire/classify.py`: Filing classification and quality —
    `classify_filing_type()` (ANNUAL_REPORT/INTERIM/REGULATORY/IR_NEWS/OTHER),
    `financial_signal_hits()`, `classify_annual_extractability()`. (15 tests)
  - **Block E** `elsian/acquire/ir_crawler.py`: IR website crawling toolkit —
    `build_ir_url_candidates()`, `resolve_ir_base_url()`, `derive_ir_roots()`,
    `build_ir_pages()`, `discover_ir_subpages()`, `extract_filing_candidates()`,
    `select_fallback_candidates()`. (32 tests)
  - **Block F** `elsian/acquire/asx.py`: Integrated content dedup via `content_hash()`
    in AsxFetcher download loop to skip duplicate PDFs.
- **Ported from:** sec_fetcher_v2_runner.py (2660 lines), filing_preflight.py (319 lines),
  ir_url_resolver.py (145 lines)
- **Tests:** 277 passed, 1 skipped, 0 failed (+115 new tests)
- **Regression:** 8/8 tickers at 100%

## 2026-03-03

### [Ticker] KAR — 8th ticker, Australian ASX, IFRS, PDF-based

### [Architecture] Wire phases to PipelinePhase ABC
- **What:** Made all three core phases inherit `PipelinePhase` with `run(context) -> PhaseResult`:
  - `elsian/acquire/phase.py`: NEW — `AcquirePhase(PipelinePhase)` wraps fetcher routing
  - `elsian/evaluate/phase.py`: NEW — `EvaluatePhase(PipelinePhase)` wraps evaluator
  - `elsian/extract/phase.py`: `ExtractPhase` now inherits `PipelinePhase`, adds `run()` that
    delegates to `extract()` and stores result in `context.result`
  - `elsian/cli.py`: `cmd_run` uses `Pipeline([ExtractPhase(), EvaluatePhase()])` orchestrator
  - `tests/unit/test_phases.py`: NEW — 6 tests for phase inheritance, run() contract, pipeline chain
- **Tests:** 157 passed, 0 failed (+6 new phase tests)
- **Regression:** ALL 8/8 at 100% (833/833)
- **What:** Created KAR (Karoon Energy Ltd) as 8th regression ticker.
  Australian ASX company, IFRS, PDF annual reports, USD presentation currency.
  - `cases/KAR/case.json`: eu_manual source_hint, 3 PDF annual report sources
  - `cases/KAR/expected.json`: 2 periods (FY2025, FY2024), 14 fields each = 28 total
  - Fixed `elsian/extract/html_tables.py` section header regex:
    added `PROFIT AND LOSS` (IFRS income statement), `FINANCIAL SUMMARY/HIGHLIGHTS`,
    fixed `CASH[-\s]+FLOWS` for multi-space PDF text
  - Added ~15 IFRS/British aliases to `config/field_aliases.json`:
    "profit for financial year" (net_income), "depreciation and amortisation"
    (British spelling), "net cash flows from operating activities" (cfo),
    "basic/diluted earnings per ordinary share" (eps), "borrowings" (total_debt)
  - KAR added to VALIDATED_TICKERS in regression suite
- **Tests:** 151 passed, 0 failed
- **Regression:** ALL 8/8 at 100% (833/833): GCT(108) IOSP(95) KAR(28) NEXN(76) SONO(116) TALO(85) TEP(55) TZOO(270)

## 2026-03-02

### [Acquire] Port acquisition layer — SecEdgarFetcher, EuRegulatorsFetcher, convert modules
- **What:** Ported complete acquisition infrastructure from 3.0:
  - `elsian/convert/html_to_markdown.py`: Full HTML→Markdown converter with
    section detection (IS, BS, CF, Equity), table extraction, quality gate.
    Ported from 3.0 `deterministic/src/acquire/html_to_markdown.py`.
  - `elsian/convert/pdf_to_text.py`: pdfplumber (layout=True) + pypdf fallback.
    Ported from 3.0 `deterministic/src/acquire/pdf_to_text.py`.
  - `elsian/acquire/sec_edgar.py`: SecEdgarFetcher — CIK resolution, filing
    collection (annual/quarterly/earnings), Exhibit 99 discovery, download with
    HTML/PDF conversion. Rate-limited SecClient. Ported from 3.0
    `deterministic/src/acquire/sec_edgar.py`.
  - `elsian/acquire/eu_regulators.py`: EuRegulatorsFetcher — HTTP download from
    filings_sources in case.json, raw filings import fallback. Ported from 3.0
    `deterministic/src/acquire/eu_regulators.py`.
  - `elsian/models/result.py`: Added AcquisitionResult model.
  - `elsian/cli.py`: Added `acquire` CLI command with auto-routing by source_hint.
- **Ported from:** 3.0 sec_edgar.py (469 lines), eu_regulators.py (314 lines),
  html_to_markdown.py (295 lines), pdf_to_text.py (96 lines)
- **Tests:** 150 passed, 0 failed (+45 new tests)
- **Regression:** ALL 7/7 at 100% (805/805)

### [Sync] Port 3.0 TALO+TEP improvements — 7/7 at 100% (805/805)
- **What:** Synced all extraction improvements from 3.0 (794914e→bf9ef15):
  - `config/field_aliases.json`: 3 DD&A aliases (depletion variants, dd&a)
  - `elsian/normalize/aliases.py`: global reject patterns (section titles
    misinterpreted as data), capex "included in accounts payable" reject,
    `_is_rejected` checks global patterns first
  - `elsian/extract/html_tables.py`: numeric-anchor calibration for sparse
    headers, "per common/ordinary share" heading normalization, plural
    regex for section headers (STATEMENTS?, SHEETS?), Schedule I exclusion
    zone, TOC F-page skip, split-line section header detection
  - `elsian/extract/vertical.py`: NEW module — vertical-format balance
    sheet extraction from EDGAR .txt (221 lines, key BS totals + debt synthesis)
  - `elsian/extract/phase.py`: vertical BS integration (+20 bonus),
    _section_bonus canonical-aware (total_equity IS penalty),
    negative total_debt IS rejection, _STRONGLY_DEPRIORITIZED expanded
    (Schedule I patterns), manual_overrides support from case.json
  - `cases/TEP/`: updated expected.json (48→55 fields: +FY2022, FY2021,
    FY2019), case.json with manual_overrides and filings_sources, 28 new filings
- **Ported from:** 3.0 commits 794914e→bf9ef15 (6 files, 774 insertions)
- **Tests:** 105 passed, 0 failed
- **Regression:** ALL 7/7 at 100% (805/805): GCT(108) IOSP(95) NEXN(76) SONO(116) TALO(85) TEP(55) TZOO(270)

## 2026-03-01

### [Bootstrap] Project scaffold and core modules (Steps 1-7)
- **What:** Created ELSIAN 4.0 from scratch with full project structure,
  data models (with Provenance), configuration (field_aliases.json,
  selection_rules.json ported from 3.0), base ABCs (Fetcher, Extractor,
  PipelinePhase), Pipeline orchestrator, PipelineContext, normalize module
  (AliasResolver, ScaleCascade, SignConvention, AuditLog), evaluate module
  (evaluator + dashboard), CLI (eval, dashboard), and comprehensive unit tests.
- **Ported from:** 3.0 deterministic/src/schemas.py, deterministic/config/,
  deterministic/src/evaluate.py, deterministic/src/normalize/aliases.py
- **Tests:** Initial suite covering models, aliases, scale, signs, evaluator,
  config, and pipeline orchestrator.

### [Extraction] Port battle-tested extraction engine from 3.0 (Step 8)
- **What:** Ported the complete deterministic extraction engine from 3.0:
  html_tables.py (1098 lines, markdown + space-aligned table extraction),
  narrative.py (303 lines, regex patterns), detect.py (378 lines, filing
  metadata detection), full AliasResolver (278 lines, with rejection patterns,
  priority, additive fields, fuzzy matching), merger.py (204 lines, multi-filing
  merge with priority). Created ExtractPhase (708 lines) — the core orchestrator
  that ties together detection, table extraction, narrative extraction, alias
  resolution, scale cascade, collision resolution with sort keys, additive fields,
  sign convention, and post-processing (total_liabilities recovery, EPS duplication).
  Updated audit.py and scale.py with 3.0-compatible APIs (infer_scale_cascade,
  validate_scale_sanity). Wired CLI with extract and run commands.
- **Ported from:** deterministic/src/extract/tables.py, narrative.py, detect.py,
  deterministic/src/normalize/aliases.py, deterministic/src/merge.py,
  deterministic/src/pipeline.py (extract method), deterministic/src/normalize/scale.py
- **Adapted for 4.0:** FieldResult wraps source info in Provenance dataclass
  (3.0 has flat source_filing/source_location). All imports updated to elsian.*.
  FilingMetadata model extended. AuditLog API aligned.
- **Tests:** 105 passed (82 unit + 16 extract phase + 7 regression)
- **Regression:** TZOO 100%, GCT 100%, IOSP 100%, NEXN 100%, SONO 100%, TEP 100%
  (TALO 42.4% — pre-existing curation issue, same as 3.0's 48.2%)
