# Changelog

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
