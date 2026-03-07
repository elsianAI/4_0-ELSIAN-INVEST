# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-07
> Actualizado por: Codex (BL-057 closeout)

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Target Fase 1→2 | Fecha |
|---|---|---|---|
| Tickers validados 100% | **15** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, CROX, TEP, SOM, 0327, KAR) | — | 2026-03-07 |
| Tickers que cuentan para DEC-015 | **13** (12 FULL + KAR por excepción documentada) | ≥15 | 2026-03-07 |
| Tickers FULL 100% | **12** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, CROX, TEP) | — | 2026-03-07 |
| Tickers ANNUAL_ONLY 100% pendientes de promoción/cierre | 2 (SOM, 0327) | — | 2026-03-07 |
| Tickers WIP | 0 | 0 | 2026-03-05 |
| Total campos validados | 3,278 | — | 2026-03-07 |
| Campos canónicos | 29 (26 previos + accounts_receivable, inventories, accounts_payable) | — | 2026-03-07 |
| Tests pasando | 1285 passed, 5 skipped (último sweep completo) + BL-053 targeted 6 passed | — | 2026-03-07 |
| Líneas de código (aprox.) | ~12,000 + ~6,500 tests | 2026-03-07 |

*`DEC-015` permite contar tickers `ANNUAL_ONLY` cuando se confirma que el mercado/regulador no publica quarterlies. `KAR` ya entra en esa excepción documentada (ASX). `SOM` y `0327` siguen en `ANNUAL_ONLY`, pero no cuentan todavía hacia el umbral de transición porque su tratamiento operativo no está cerrado como excepción equivalente a `FULL`.

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 300 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| GCT | 252 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED (FULL: 6A+9Q) |
| IOSP | 338 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+17Q) |
| NEXN | 153 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED (FULL: 4A+6Q) |
| SONO | 311 | SEC (US) | 10-K HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| TEP | 80 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED (FULL: 6A+2H) |
| TALO | 183 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+7Q) |
| NVDA | 354 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| KAR | 49 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED (DEC-015 excepción: no quarterly en ASX) |
| PR | 141 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 3A+6Q) |
| ACLS | 375 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+15Q) |
| INMD | 210 | SEC (US) | 20-F/6-K HTML (IFRS) | ✅ VALIDATED (FULL: 6A+6Q — BL-040 promoted) |
| CROX | 294 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL — BL-041 DONE) |
| SOM | 179 | LSE/AIM (GB) | PDF (US-GAAP, USD) | ✅ VALIDATED (ANNUAL_ONLY: 16A, 179/179 — DEC-022 completado) |
| 0327 | 59 | HKEX (HK) | PDF (HKFRS, HKD) | ✅ VALIDATED (ANNUAL_ONLY: 3A — BL-043 DONE, primer ticker asiático) |

## Nuevos componentes (Oleada 2 cierre Módulo 1)

| Componente | Estado | Notas |
|---|---|---|
| Truth Pack assembler | ✅ Implementado | elsian/assemble/truth_pack.py (296L). TruthPack_v1 schema. CLI `elsian assemble`. 45 tests. BL-049 DONE. BL-056 DONE (truth_pack.json en .gitignore). |
| Auto-discovery de ticker | ✅ Implementado | elsian/discover/discover.py. SEC (EDGAR) + non-US (Yahoo Finance). CLI `elsian discover`. 38 tests. BL-051 DONE |
| IxbrlExtractor producción | ✅ Implementado | elsian/extract/ixbrl_extractor.py. iXBRL como extractor primario para SEC. extraction_method=ixbrl. 45 tests. BL-048 DONE. |
| `elsian run` pipeline | ✅ Implementado | Convert→Extract→Evaluate→Assemble. --with-acquire, --skip-assemble, --force, --all. 13 tests. BL-050 DONE. |

## Componentes implementados

| Componente | Estado | Notas |
|---|---|---|
| Pipeline + PipelinePhase ABC | ✅ Implementado | pipeline.py, context.py |
| AcquirePhase | ✅ Implementado | SecEdgarFetcher, EuRegulatorsFetcher, ManualFetcher |
| Converters (HTML→MD, PDF→text) | ✅ Implementado | html_to_markdown.py, pdf_to_text.py |
| ExtractPhase (wired a PipelinePhase) | ✅ Implementado | run(context) delegando a extract(). BL-003 completado. |
| NormalizePhase | ✅ Implementado | Alias, Scale, Sign, Audit |
| MergePhase | ✅ Implementado | Multi-filing merger |
| EvaluatePhase | ✅ Implementado | evaluator.py + dashboard |
| IxbrlExtractor | ✅ Implementado | Parser iXBRL (BL-004) + IxbrlExtractor producción (BL-048). extraction_method=ixbrl. Dominant-scale normalization. Calendar quarter fix para fiscal year no-calendar. |
| PdfTableExtractor | ✅ Implementado | elsian/extract/pdf_tables.py (pdfplumber structured tables). BL-007 DONE |
| Filing Preflight (idioma/estándar/moneda/unidades/restatement) | ✅ Implementado + Integrado | Portado de 3.0. EN/FR/ES/DE, IFRS/US-GAAP, 9 monedas, unidades por sección, restatement. BL-009 DONE. Integrado en ExtractPhase con units_by_section → ScaleCascade. BL-014/WP-4 DONE. |
| Deduplicación por contenido | ✅ Implementado | SHA-256 content hash portado. Integrado en AsxFetcher. BL-010 DONE |
| Exchange/Country awareness | ✅ Implementado | markets.py unificado: normalize_country/exchange, is_non_us, infer_regulator_code. BL-011 DONE |
| Filing Classification automática | ✅ Implementado | classify_filing_type() con 5 tipos. BL-012 DONE |
| Calculadora métricas derivadas | ✅ Implementado | TTM, FCF, EV, márgenes, retornos, múltiplos, per-share. BL-015 DONE |
| Prefetch coverage audit | ✅ Implementado | Issuer class, thresholds, reporte. CLI `elsian coverage`. BL-021 DONE |
| Sources compiler | ✅ Implementado | Merge multi-fetcher, dedup, SourcesPack_v1. CLI `elsian compile`. BL-023 DONE |
| IR Website Crawling | ✅ Implementado + Integrado | ir_crawler.py portado completo (~600 líneas). Integrado en EuRegulatorsFetcher como fallback automático (BL-013 DONE). |
| Provenance Level 2 | ✅ Completo | BL-006 DONE. Todos los extractores emiten L2 completo (table_title, row_label, col_label, raw_text, row, col, table_index, extraction_method). 100% completitud. |
| Provenance Level 3 | 🟡 Pilotado | `elsian/assemble/source_map.py` + CLI `elsian source-map`. Piloto TZOO validado con `SourceMap_v1`: 851/851 campos resueltos (`html_ixbrl`, `clean_md_table`, `text_label`). El piloto acepta anchors equivalentes en `.clean.md`/`.txt` manteniendo la ruta al filing original; el builder además confina `source_filing` al caso. Queda pendiente convertirlo en soporte general de producto/UI. |
| CI GitHub Actions | ✅ Implementado | Workflow ci.yml en .github/workflows/. pytest en Python 3.11. WP-5 DONE |
| Sanity Checks post-extracción | ✅ Implementado | capex sign, revenue neg, gp>revenue, YoY >10x. BL-016 DONE |
| Autonomous Validator | ✅ Implementado | 9 quality gates intrínsecos (BS identity, CF identity, units 1000x, EV, margins, TTM, recency, completeness). BL-020 DONE |
| validate_expected.py | ✅ Implementado | 8 reglas + 2 sanity warnings. Pre-check en evaluate(). BL-017 DONE |
| Field Dependency Matrix | ✅ Publicado + Oleadas 1/2 DONE | 26 campos analizados (8 critical, 12 required, 6 optional). 22 ya existen en 4.0; quedan 4 gaps no bloqueantes (`fx_effect_cash`, `other_cash_adjustments`, `market_cap`, `price`). |

## Manual overrides activos (DEC-024)

| Ticker | Overrides | % campos | Campos afectados | Estado DEC-024 |
|---|---|---|---|---|
| Ninguno | 0 | 0.0% | — | ✅ Sin overrides activos |

**Total:** 0 overrides / 3,278 campos = 0.00% global. TEP y SOM ya no tienen overrides activos tras BL-054 y BL-055.

**Estado "autónomo suficiente" (DEC-026):** ALCANZADO para extracción autónoma strict. Los 15 tickers validados pasan al 100% con 0 overrides activos. La adquisición sigue teniendo limitaciones conocidas y transparentes en algunos mercados sin API pública, pero la deuda de extracción manual ya está cerrada y SOM ya no depende de `filings_sources` hardcodeados.

## Tickers WIP

No hay tickers WIP actualmente. Los 15 tickers están al 100%.

## Bloqueantes actuales

No hay bloqueantes críticos. El pipeline es funcional end-to-end para los 15 tickers validados al 100%, pero el tracking operativo de `DEC-015` sigue en **13/15**: **12 FULL + KAR por excepción documentada**. La deuda actual ya no es de overrides ni de calidad base, sino de cómo promover o cerrar el tratamiento de `SOM` y `0327` sin mezclar excepciones implícitas.

**Gaps pendientes (no bloqueantes):**
1. **Residual field-dependency gaps** — `fx_effect_cash`, `other_cash_adjustments`, `market_cap` y `price` siguen fuera del set canónico. Son opcionales o de market data; no bloquean validación ni BL-058.
2. **TALO y TEP sin filings_manifest.json** — adquisición manual (ManualFetcher / EuRegulatorsFetcher). Coverage audit retorna NEEDS_ACTION. Limitación conocida, no bug.
3. **Adquisición no-SEC aún gradual** — TALO y TEP mantienen rutas de acquire con limitaciones conocidas (coverage `NEEDS_ACTION` o manifest ausente). SOM ya resuelve su piloto LSE/AIM por auto-discovery conservador, pero la autonomía completa de acquire fuera de mercados con API pública sigue siendo gradual.

## Hitos recientes

- ✅ **BL-057 completado (2026-03-07)** — Cerrado el piloto conservador de auto-discovery LSE/AIM para SOM. `EuRegulatorsFetcher` ya deduplica variantes `/media` vs `/~/media`, poda documentos no financieros y limita LSE/AIM a un set núcleo anual/interim/regulatory. Un caso temporal de SOM sin `filings_sources` descarga 3 documentos y mantiene `eval SOM` en PASS 100.0% (179/179).

- ✅ **BL-047 completado (2026-03-07)** — Endurecimiento reusable del extractor HTML en dos patrones compartidos. `elsian/extract/html_tables.py` ahora descarta tablas comparativas suplementarias con columnas explícitas de `Change`, y además preserva el contexto `Six/Nine Months Ended` cuando el markdown split deja la fecha del periodo anterior como header suelto. Eso evita period mappings ambiguos en notas como `Interest income` y corrige el ruido YTD de cash flow (`capex`, `cfo`, `depreciation_amortization`) sin tocar truth ni degradar winner selection. Validación shared-core: `python3 -m pytest -q tests/unit/test_html_tables.py tests/unit/test_extract_phase.py` → 65 passed; `python3 -m elsian eval NVDA` → PASS 100.0% (354/354, `extra` 545 → 503); `python3 -m elsian eval --all` → 15/15 PASS; `pytest -q` → 1303 passed, 5 skipped.

- ✅ **BL-053 completado (2026-03-07)** — Provenance Level 3 queda pilotado sin reabrir el pipeline de extracción. Nuevo builder `elsian/assemble/source_map.py` + CLI `elsian source-map` generan `SourceMap_v1` desde `extraction_result.json` y resuelven targets trazables sobre `.htm`, `.clean.md` y `.txt`. Piloto TZOO validado con 851/851 campos resueltos. Validación targeted: `tests/unit/test_source_map.py` + `tests/integration/test_source_map.py` → 6 passed; `ruff` limpio; `python3 -m elsian eval TZOO` → PASS 100.0% (300/300); demo `python3 -m elsian source-map TZOO --output <tmp>` → 851/851 resueltos.

- ✅ **BL-058 completado (2026-03-07)** — Oleada 2 de working capital cerrada. `accounts_receivable`, `inventories` y `accounts_payable` entran en el set canónico compartido y quedan pilotados en TZOO y NVDA. TZOO sube a 300/300 y NVDA a 354/354; `eval --all` vuelve a pasar 15/15 al 100% y `pytest -q` queda en 1285 passed, 5 skipped. La governance derivada (`BACKLOG`, `PROJECT_STATE`, `FIELD_DEPENDENCY_*`, `ROADMAP`, `MODULE_1_ENGINEER_CONTEXT`) queda reconciliada con 29 campos canónicos y 3,278 campos validados.

- ✅ **BL-055 completado (2026-03-06)** — SOM eliminó sus 2 manual_overrides de DPS mediante extracción determinista desde `FINANCIAL HIGHLIGHTS 2024` en el annual report FY2024. SOM se mantiene en 100% (179/179) con 0 overrides. eval SOM PASS 100.0%, eval --all 15/15 PASS 100%, pytest -q 1267 passed, 5 skipped.

- ✅ **BL-054 completado (2026-03-06)** — TEP eliminó sus 6 manual_overrides mediante rutas deterministas estrechas en narrative extraction. TEP se mantiene en 100% (80/80) con 0 overrides. eval TEP PASS 100.0%, eval --all 15/15 PASS 100%, pytest -q 1258 passed, 5 skipped.

- ✅ **Oleada 2 cierre Módulo 1 (2026-03-05)** — 4 tareas completadas + hotfix:
  - **BL-048 IxbrlExtractor producción:** iXBRL como extractor primario SEC. Dominant-scale normalization. 45 tests. Regresiones SONO/ACLS corregidas en hotfix posterior.
  - **BL-050 `elsian run` pipeline:** Convert→Extract→Evaluate→Assemble. --with-acquire, --all. 13 tests.
  - **BL-043 0327 HKEX completado:** PAX Global Technology. 3 periodos (FY2022-FY2024), 59/59 100%. D&A additive, EBITDA segment, DPS narrative. Primer ticker asiático.
  - **BL-056 truth_pack .gitignore:** Limpieza de 3 ficheros del tracking.
  - **Hotfix regresiones:** TEP/SOM/ACLS restaurados a 100% (aliases scoped, rescaled iXBRL quality). SONO curado (calendar vs fiscal quarter labels).
- 15/15 PASS 100%, 1258 tests (5 skipped), 3,248 campos validados.
- ✅ **Oleada 1 cierre Módulo 1 (2026-03-04)** — 3 tareas en paralelo completadas:
  - **BL-042 SOM completado:** 16 periodos (FY2009-FY2024), 179/179 100%. DEC-022 resuelto. Regresión TEP corregida en mismo commit.
  - **BL-049 Truth Pack assembler verificado:** TruthPackAssembler (296L, 45 tests). CLI `elsian assemble`. TZOO piloto: 51 periodos, 792 campos, quality PASS.
  - **BL-051 Auto-discovery creado:** elsian/discover/ (38 tests). CLI `elsian discover`. AAPL (SEC) y TEP.PA (Euronext) verificados.
- 14/14 PASS 100%, 1193 tests, 3,189 campos validados.
- ✅ **BL-022 + BL-024 + BL-007 (2026-03-05)** — Market data fetcher portado (830L, 62 tests), transcript finder portado (1085L, 58 tests), PdfTableExtractor creado (447L, 47 tests). +167 tests. CLI ampliado con `market` y `transcripts`.
- ✅ **BL-041 CROX 100% (2026-03-04)** — CROX (Crocs Inc.) arreglado de 98.98% a 100% (294/294). Fix en phase.py: severe_penalty -100→-300, regla canónica ingresos+income_statement:net_income, override activo para .txt, afinidad año-periodo para net_income. Sin regresiones: 14/14 PASS.
- ⚠️ **CROX mejoró 82.31% → 98.98% (2026-03-05)** — Scope creep de sub-agente BL-007 (DEC-020). Solo phase.py modificado. 3 wrong restantes resueltos en BL-041.
- ✅ **Oleada paralela BL-035/BL-006/BL-018/BL-013 (2026-03-04)** — 4 tareas ejecutadas en paralelo: (1) BL-035: cfi/cff/delta_cash añadidos como campos canónicos 23-25, pilotados en TZOO (+18) y NVDA (+18), +24 tests. (2) BL-006: Provenance L2 completo en todos los extractores (0%→100%), +17 tests, CROX mejoró 82%→95% como efecto colateral. (3) BL-018: Quality gates clean.md portados de 3.0, +24 tests. (4) BL-013: IR Crawler integrado en EuRegulatorsFetcher como fallback, +15 tests. Total: +80 tests (544→627). 2,716 campos validados.
- ✅ **TEP → FULL** — Promovido a FULL (80/80, 6A+2H). Semestrales H1 curados desde Euronext interim filing.
- ✅ **INMD → FULL** — Promovido de ANNUAL_ONLY (108) a FULL (210/210, 6A+6Q).
- ✅ **BL-045 DONE** — Limpieza post-auditoría: KAR/TEP period_scope explícito, ficheros basura eliminados, .gitignore actualizado, pyproject.toml corregido.
- ✅ **BL-039 DONE** — ACLS (Axcelis Technologies): SEC semiconductor, iXBRL, FULL 375/375.
- ✅ **BL-040 DONE** — INMD (InMode): SEC 20-F/6-K, healthcare (IFRS), FULL 210/210.
- ✅ **BL-036 DONE** — NEXN promovido a FULL: 153/153 (4A+6Q). 6-K Exhibit 99.1 download.
- ✅ **BL-038 DONE** — Table parser fix: parenthetical collapse, currency prefix normalization.

## Próximas prioridades

Ver BACKLOG.md para la cola completa. Plan de ejecución: `docs/project/PLAN_DEC010_WP1-WP6.md` (DEC-011).

**DEC-011 WPs completados (5/6):**
- ~~WP-1 (BL-027)~~ — DONE. Scope Governance.
- ~~WP-2 (BL-028)~~ — DONE. SEC Hardening.
- ~~WP-3 (BL-004, BL-025)~~ — DONE. iXBRL Parser + Curate.
- ~~WP-4 (BL-014)~~ — DONE. Preflight en ExtractPhase.
- ~~WP-5~~ — DONE. CI + Python 3.11.
- **WP-6** — IxbrlExtractor en producción. **DONE** (BL-048).

**Siguiente fase — Oleada 4 (DEC-016):**
- ✅ **BL-039 (ACLS)** — DONE. SEC semiconductor, iXBRL, FULL 375/375.
- ✅ **BL-040 (INMD)** — DONE. SEC 20-F/6-K, healthcare (IFRS), FULL 210/210.
- ✅ **BL-044 (TEP→FULL)** — DONE. Euronext semestrales, FULL 80/80. Regresión por BL-042 corregida en BL-046.
- ✅ **BL-041 (CROX)** — DONE. SEC footwear, FULL 294/294.
- ✅ **BL-042 (SOM)** — DONE (DEC-022). 16 periodos, 179/179, 100%. Regresión TEP corregida.
- ✅ **BL-049 (Truth Pack)** — DONE. TruthPackAssembler funcional. 45 tests.
- ✅ **BL-051 (Auto-discovery)** — DONE. elsian discover funcional. 38 tests.
- ✅ **BL-043 (0327)** — DONE. HKEX, primer ticker asiático. 3A, 59/59, 100%.

**Tracking operativo de DEC-015:**
- Cuentan hoy: **13/15** (12 FULL + KAR por excepción documentada)
- ANNUAL_ONLY pendientes: **2** (SOM, 0327)
- **DEC-015 target aún no se declara alcanzado** mientras no exista promoción adicional o cierre explícito para `SOM` y `0327`.

**WP-6** — IxbrlExtractor en producción. **DONE** (BL-048).

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
