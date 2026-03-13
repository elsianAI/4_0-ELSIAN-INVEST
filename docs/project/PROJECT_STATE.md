# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-13
> Actualizado por: Codex (Tranche A Nivel 1 lifecycle contract; baseline persistence deferred until fresh full scout pass)
> Module 1 status: OPEN
> Semántica vigente del marker: `OPEN` mientras exista frontera operacional real en el subtree operativo de `OPPORTUNITIES.md`. `TEP` y `0327` pueden convivir con un cierre futuro solo como excepciones ticker-level reafirmadas; `TALO` no es compatible con `CLOSED` mientras siga siendo un gap factual abierto de autonomía/coverage.

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Target Fase 1→2 | Fecha |
|---|---|---|---|
| Tickers validados 100% | **17** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, CROX, TEP, SOM, 0327, KAR, ADTN, JBH) | — | 2026-03-11 |
| Tickers que cuentan para DEC-015 | **16** (14 FULL + 2 `ANNUAL_ONLY` justificados en ASX: KAR, JBH) | ≥15 | 2026-03-11 |
| Tickers FULL 100% | **14** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, CROX, TEP, ADTN, 0327) | — | 2026-03-09 |
| Tickers ANNUAL_ONLY justificado | **2** (KAR, JBH) | — | 2026-03-11 |
| Tickers ANNUAL_ONLY promocionable | **0** | — | 2026-03-11 |
| Tickers en frontera abierta | **1** (SOM) | — | 2026-03-11 |
| Tickers WIP | 0 | 0 | 2026-03-11 |
| Total campos validados | 4,652 | — | 2026-03-11 |
| Campos canónicos | 29 (26 previos + accounts_receivable, inventories, accounts_payable) | — | 2026-03-07 |
| Tests pasando | 1824 passed, 5 skipped, 1 warning en `python3 -m pytest -q` local | — | 2026-03-11 |
| Líneas de código (aprox.) | ~12,000 + ~6,500 tests | 2026-03-07 |

*Interpretación canónica vigente de `DEC-015`: cuentan hoy **16** tickers, exactamente **14 `FULL` + `KAR` + `JBH`**. `DEC-015` permite contar tickers `ANNUAL_ONLY` cuando se confirma que el mercado/regulador no publica quarterlies, y la lectura operativa actual formaliza de forma explícita que `KAR` y `JBH` entran bajo esa misma excepción documentada de ASX. `ADTN` cuenta como `FULL` tras el cierre targeted de `BL-081` (`8A+15Q`, 520/520), y `0327` queda validado como `FULL` con `3A+3H` bajo un path de acquire `hkex_manual` reproducible desde git. `BL-076` no alteró el hito previo de **15/15**; el cómputo factual actual de `DEC-015` asciende a **16** (`14 FULL + KAR + JBH`) y no coexiste aquí con una lectura alternativa. `SOM` no cuenta hoy para `DEC-015`: deja de describirse como "pendiente de promoción/cierre" y pasa a tratarse como la única **frontera abierta** actual, es decir, ticker validado `ANNUAL_ONLY` pero todavía no cerrado canónicamente ni como `ANNUAL_ONLY justificado` ni como promoción empaquetable.

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 348 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| GCT | 330 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED (FULL: 6A+9Q) |
| IOSP | 430 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+17Q) |
| NEXN | 177 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED (FULL: 4A+6Q) |
| SONO | 404 | SEC (US) | 10-K HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| TEP | 109 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED (FULL: 6A+2H) |
| TALO | 235 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+7Q) |
| NVDA | 422 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| KAR | 61 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED (DEC-015 excepción: no quarterly en ASX) |
| JBH | 36 | ASX (AU) | PDF (IFRS, AUD) | ✅ VALIDATED (DEC-015 excepción ASX: no quarterly) |
| PR | 185 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 3A+6Q) |
| ACLS | 486 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+15Q) |
| INMD | 234 | SEC (US) | 20-F/6-K HTML (IFRS) | ✅ VALIDATED (FULL: 6A+6Q — BL-040 promoted) |
| CROX | 326 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL — BL-041 DONE) |
| SOM | 203 | LSE/AIM (GB) | PDF (US-GAAP, USD) | ✅ VALIDATED (ANNUAL_ONLY: 16A, 203/203 — DEC-022 completado) |
| 0327 | 146 | HKEX (HK) | PDF/TXT manual HKEX (HKFRS, HKD) | ✅ VALIDATED (FULL: 3A+3H — BL-083 DONE, reproducible desde git) |
| ADTN | 520 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 8A+15Q — BL-081 DONE) |

## Programa de capacidad Module 1

### Clasificación factual por ticker

| Ticker | Mercado | Clasificación factual | Autonomía operativa ticker | Fase programa |
|---|---|---|---|---|
| TZOO | SEC (US) | FULL | autonomous | A |
| GCT | SEC (US) | FULL | autonomous | A |
| IOSP | SEC (US) | FULL | autonomous | A |
| NEXN | SEC (US) | FULL | autonomous | A |
| SONO | SEC (US) | FULL | autonomous | A |
| TEP | Euronext (FR) | FULL | documented exception | A |
| TALO | SEC (US) | FULL | gradual | A |
| NVDA | SEC (US) | FULL | autonomous | A |
| KAR | ASX (AU) | ANNUAL_ONLY justificado | autonomous | A |
| JBH | ASX (AU) | ANNUAL_ONLY justificado | autonomous | A |
| PR | SEC (US) | FULL | autonomous | A |
| ACLS | SEC (US) | FULL | autonomous | A |
| INMD | SEC (US) | FULL | autonomous | A |
| CROX | SEC (US) | FULL | autonomous | A |
| SOM | LSE/AIM (GB) | frontera abierta | gradual | C |
| 0327 | HKEX (HK) | FULL | documented exception | A |
| ADTN | SEC (US) | FULL | autonomous | A |

### Clasificación factual por mercado

| Mercado | Tickers actuales | Clasificación factual | Autonomía operativa mercado | Fase programa |
|---|---|---|---|---|
| SEC (US) | TZOO, GCT, IOSP, NEXN, SONO, TALO, NVDA, PR, ACLS, INMD, CROX, ADTN | Capacidad FULL operativa | autonomous | A |
| ASX (AU) | KAR, JBH | ANNUAL_ONLY justificado | autonomous | A |
| Euronext (FR) | TEP | Capacidad FULL en un ticker, sin autonomía de mercado amplia | gradual | A |
| LSE/AIM (GB) | SOM | frontera abierta | gradual | C |
| HKEX (HK) | 0327 | FULL en ticker validado, no generalizado como mercado | documented exception | C |

**Lectura del programa:**
- **Fase A** = capacidad cerrada hoy dentro del perímetro real de Module 1.
- **Fase B** = backlog vivo estrictamente BL-ready y serializable.
- **Fase C** = frontera abierta, hipótesis o excepciones aún no empaquetables como BL.

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
| Provenance Level 3 | ✅ Pilotado y revalidado en verde | `elsian/assemble/source_map.py` + CLI `elsian source-map`. El piloto histórico TZOO validó `SourceMap_v1` en verde y BL-080 recupera esa garantía para el artefacto actual: `python3 -m elsian source-map TZOO --output /tmp/tzoo_source_map_bl080_fixed.json` vuelve a `FULL` con 818/818 campos resueltos (100.0%). El hardening previo (`*.txt:table`, `case_dir` relativo, labels verticales, salida `FULL/PARTIAL/EMPTY`) sigue presente, y el closeout actual añade soporte explícito para punteros iXBRL derivados como `:bs_identity_bridge` sin cambiar winners de extracción ni merge/eval. |
| CI GitHub Actions | ✅ Implementado | Workflow ci.yml en .github/workflows/. pytest en Python 3.11. WP-5 DONE |
| Sanity Checks post-extracción | ✅ Implementado | capex sign, revenue neg, gp>revenue, YoY >10x. BL-016 DONE |
| Autonomous Validator | ✅ Implementado | 9 quality gates intrínsecos (BS identity, CF identity, units 1000x, EV, margins, TTM, recency, completeness). BL-020 DONE |
| validate_expected.py | ✅ Implementado | 8 reglas + 2 sanity warnings. Pre-check en evaluate(). BL-017 DONE |
| Field Dependency Matrix | ✅ Publicado + Oleadas 1/2 DONE | 26 campos analizados (8 critical, 12 required, 6 optional). 22 ya existen en 4.0; quedan 4 gaps no bloqueantes (`fx_effect_cash`, `other_cash_adjustments`, `market_cap`, `price`). |

## Manual overrides activos (DEC-024)

| Ticker | Overrides | % campos | Campos afectados | Estado DEC-024 |
|---|---|---|---|---|
| Ninguno | 0 | 0.0% | — | ✅ Sin overrides activos |

**Total:** 0 overrides / 4,652 campos = 0.00% global. TEP y SOM ya no tienen overrides activos tras BL-054 y BL-055.

**Estado "autónomo suficiente" (DEC-026):** ALCANZADO para extracción autónoma strict. Los 17 tickers validados pasan al 100% con 0 overrides activos. La adquisición sigue teniendo limitaciones conocidas y transparentes en algunos mercados sin API pública, pero la deuda de extracción manual ya está cerrada y SOM ya no depende de `filings_sources` hardcodeados.

## Tickers WIP

No hay tickers WIP actualmente. Los 17 tickers están al 100%.

## Bloqueantes actuales

No hay bloqueantes críticos de extractor/eval ni regresiones abiertas en Provenance Level 3. El pipeline es funcional end-to-end para los 17 tickers validados al 100%, `python3 -m pytest -q` queda documentado en verde local en `PROJECT_STATE`, `python3 -m elsian source-map TZOO --output /tmp/tzoo_source_map_bl080_fixed.json` mantiene `SourceMap_v1 FULL` con 818/818, y BL-069 deja además `python3 -m elsian diagnose --all --output /tmp/elsian-bl069-parent3` alineado con el path canónico de `eval` (`17/17 evaluated`, overall 100.0%, `wrong=0`, `missed=0`). BL-075 cerró la deuda de derivados deterministas en `expected.json`, BL-082 cerró el bloqueador shared-core de ADTN para restatements 2023-2024 y rutas de escala, BL-081 promovió ADTN a `FULL`, BL-083 consolidó `0327` como `FULL`, BL-005 añadió `JBH` como ticker validado de diversidad, BL-076 completó la retroportación de 7 campos adicionales con **4,652** campos validados y BL-085 cerró la única deuda residual de cobertura unitaria ligada a ese cierre. El cómputo factual actual de `DEC-015` es **16**: **14 FULL + KAR + JBH** por excepción ASX documentada. No queda backlog BL-ready vivo en este snapshot.

**Gaps y límites pendientes (no bloqueantes):**
1. **Residual field-dependency gaps** — `fx_effect_cash`, `other_cash_adjustments`, `market_cap` y `price` siguen fuera del set canónico. Son opcionales o de market data; no bloquean validación ni BL-058.
2. **TALO mantiene un gap factual de coverage/manifest** — los canonicals siguen recogiendo `coverage NEEDS_ACTION` o `filings_manifest` ausente para TALO. Se trata como limitación ticker-level del runtime actual, no como limitación general del mercado SEC.
3. **Adquisición no-SEC sigue siendo gradual por mercado** — `TEP` opera sobre `eu_manual` con `filings_sources` documentados; `SOM` resuelve un piloto LSE/AIM conservador, pero no canoniza todavía un programa de mercado amplio; `0327` es reproducible con `hkex_manual`, no con discovery general HKEX.
## Hitos recientes

- ✅ **BL-085 completado (2026-03-11)** — Cerrada la única deuda residual leve que seguía abierta tras BL-076: la cobertura unitaria específica del guard que descarta `inventories` espurios desde cash flow con named subsection en `clean.md`. El packet técnico final queda intencionalmente estrecho: solo cambia `tests/unit/test_extract_phase.py`, añade dos regresiones complementarias y no toca `elsian/extract/phase.py`. Validación factual: `python3 -m pytest -q tests/unit/test_extract_phase.py` → `70 passed`; `python3 -m elsian eval --all` → `17/17 PASS 100%`; `python3 -m pytest -q` → `1824 passed, 5 skipped, 1 warning`; auditoría independiente → ACCEPT FOR CLOSEOUT sin hallazgos materiales. Efecto operativo: desaparece el último riesgo residual explícito ligado al closeout de BL-076 y el backlog BL-ready queda vacío.

- ✅ **BL-069 completado (2026-03-11)** — El motor de diagnose queda cerrado end-to-end como superficie diagnóstica factual del pipeline actual. El paquete ya absorbido deja `elsian diagnose --all` con reportes JSON/MD, ranking de hotspots reutilizable, clustering adicional por `period_type`/`field_category` y `root_cause_hint`, y el audit-fix final que re-extrae on-the-fly para alinearse con `eval` y eliminar drift stale de artefactos persistidos. Validación de closeout: `python3 -m pytest tests/unit/test_diagnose.py tests/integration/test_diagnose_command.py -q` → `78 passed`; `python3 -m pytest tests/unit/ -q` → `1523 passed, 1 warning`; `python3 -m elsian eval --all` → `17/17 PASS 100%`; `python3 -m elsian diagnose --all --output /tmp/elsian-bl069-parent3` → `17/17 evaluated`, overall 100.0%, `wrong=0`, `missed=0`.

- ✅ **BL-076 completado (2026-03-09)** — Cerrado el packet final de retroportación de 7 campos a `expected.json` existentes con reconciliación shared-core y sin vender gaps pendientes como si siguieran abiertos. El paquete técnico final incluye el script nuevo `scripts/backfill_bl076_fields.py`, 20 tests unitarios en `tests/unit/test_backfill_bl076_fields.py`, retroportación filing-backed sobre 14 tickers (`0327`, `ACLS`, `CROX`, `GCT`, `IOSP`, `KAR`, `NEXN`, `NVDA`, `PR`, `SOM`, `SONO`, `TALO`, `TEP`, `TZOO`), fix mínimo en `elsian/extract/phase.py` para descartar `inventories` espurios desde cash flow con named subsection en `clean.md` sin romper rutas `txt`/table, y ajustes filing-backed finales en `CROX` quarterly `total_debt` y FY de `SONO` para alinear la verdad con los winners del pipeline respaldados por filing. Validación factual verificada: `python3 -m elsian eval --all` → PASS 16/16 (`0327 146/146`, `ACLS 486/486`, `ADTN 520/520`, `CROX 326/326`, `GCT 330/330`, `INMD 234/234`, `IOSP 430/430`, `KAR 61/61`, `NEXN 177/177`, `NVDA 422/422`, `PR 185/185`, `SOM 203/203`, `SONO 404/404`, `TALO 235/235`, `TEP 109/109`, `TZOO 348/348`); `python3 -m pytest -q` → `1417 passed, 5 skipped, 1 warning`; `python3 -m pytest -q tests/unit/test_backfill_bl076_fields.py` → `20 passed`; contratos post-fix PASS para `CROX`/`IOSP`/`SONO`. Efecto operativo: total campos validados sube a **4,616** y `DEC-015` no cambia: siguen contando **15** (`14 FULL + KAR`), con `SOM` como único `ANNUAL_ONLY` pendiente.

- ✅ **BL-083 completado (2026-03-09)** — `0327` cierra la promoción a `FULL` sobre soporte shared-core reusable para H1 compacto/bilingüe y deja de depender de artefactos sólo locales. `elsian/extract/detect.py` reconoce day-first half-years (`Six months ended 30 June 2025`) y `elsian/extract/html_tables.py` extrae bloques HKEX compactos desde TXT para income statement, balance sheet, cash flow, expenses-by-nature, receivables y per-share, además de resolver `shares_outstanding` en la variante `in issue`. `cases/0327/expected.json` canoniza `H1-2023`, `H1-2024` y `H1-2025` filing-backed, `cases/0327/case.json` pasa a `period_scope: FULL`, y el repo versiona el set mínimo `hkex_manual` `SRC_001`-`SRC_006` en TXT para que el green sea reproducible desde git. Validación: `python3 scripts/validate_contracts.py --schema case --path cases/0327/case.json` → PASS; `python3 scripts/validate_contracts.py --schema expected --path cases/0327/expected.json` → PASS; `python3 -m pytest -q tests/unit/test_detect.py tests/unit/test_html_tables.py tests/unit/test_extract_phase.py` → 110 passed; `python3 -m pytest -q tests/unit/test_hkex_fetcher.py tests/unit/test_cli_fetcher_routing.py` → 17 passed; `python3 -m elsian eval 0327` → PASS 100.0% (131/131); `python3 -m elsian eval --all` → PASS 16/16; `python3 -m pytest -q` → 1397 passed, 5 skipped, 1 warning; checkout limpio exportado desde git → `python3 -m elsian eval 0327` PASS 100.0% (131/131). Efecto operativo: `0327` pasa a `FULL` (`3A+3H`, 131/131) y `DEC-015` alcanza 15/15.

- ✅ **BL-081 completado (2026-03-08)** — ADTN se promueve de `ANNUAL_ONLY` a `FULL` sin cambiar la verdad anual ya canonizada. `cases/ADTN/case.json` pasa a `period_scope: FULL` y `cases/ADTN/expected.json` añade exactamente 15 trimestrales `Q*` con cobertura suficiente (`Q1-Q3 2021` y `Q1-Q3 2022-2025`), excluyendo `Q1-Q4 2019`, `Q1-Q4 2020`, `Q4-2021`, todos los `H1-*` y cualquier trimestral sparse. Para `Q1-Q3 2023` y `Q1-Q3 2024`, la verdad promoted conserva comparativos restated de filings posteriores cuando son explícitos y trazables. Validación: `python3 scripts/validate_contracts.py --schema case --path cases/ADTN/case.json` → PASS; `python3 scripts/validate_contracts.py --schema expected --path cases/ADTN/expected.json` → PASS; `python3 -m elsian eval ADTN` → PASS 100.0% (520/520); `python3 -m elsian eval --all` → PASS 16/16; `python3 -m pytest -q` → 1373 passed, 5 skipped, 1 warning. Efecto operativo: ADTN pasa a `FULL` y `DEC-015` sube a 14/15.
- ✅ **BL-082 completado (2026-03-08)** — Cerrado el bloqueador shared-core que seguía impidiendo la promoción trimestral de ADTN. `elsian/extract/phase.py` centraliza la afinidad de restatement para `total_equity` y la aplica simétricamente en iXBRL, table, narrative y `.txt` tables, mientras se preservan el fix de `depreciation_amortization` mixed-scale y la protección de `total_liabilities`. Validación: `python3 -m pytest -q tests/unit/test_extract_phase.py tests/unit/test_ixbrl_extractor.py tests/unit/test_merger.py` → 106 passed; `python3 -m elsian eval ACLS`/`ADTN`/`GCT`/`TZOO` → PASS 100%; `python3 -m elsian eval --all` → PASS 16/16; `python3 -m pytest -q` → 1373 passed, 5 skipped, 1 warning; repro `ADTN scratch FULL` → `score=100.0`, `wrong=0`, `missed=0`. Efecto operativo: `BL-081` deja de estar bloqueada y queda lista para una ola targeted de promoción a `FULL`.
- ✅ **BL-075 completado (2026-03-08)** — Cerrado el backfill determinista de campos derivados en `expected.json` sin mezclar la retroportación de BL-035/BL-058. El nuevo script `scripts/backfill_expected_derived.py` añade `ebitda = ebit + depreciation_amortization` y `fcf = cfo - abs(capex)` cuando existen ambos componentes, el derivado no está ya presente y no hay exclusión canonizada por `ticker+periodo+campo`. La ola toca 15 tickers (`0327`, `ACLS`, `ADTN`, `CROX`, `GCT`, `INMD`, `IOSP`, `NEXN`, `NVDA`, `PR`, `SOM`, `SONO`, `TALO`, `TEP`, `TZOO`) y deja `KAR` intacto. Para mantener la paridad, `elsian/evaluate/evaluator.py` y `elsian/curate_draft.py` ahora prefieren el valor derivado cuando el `expected.json` canoniza ese campo como `DERIVED`. En la misma ola se absorbió un fix mínimo previo de provenance para las dos filas `dividends_per_share` de SOM en el annual report FY2024, de modo que `pytest -q` vuelva a verde sin cambiar winner selection. Validación: baseline `python3 scripts/backfill_expected_derived.py --cases-dir cases --dry-run` → `ebitda eligible_missing_before=148`, `fcf eligible_missing_before=110`; apply → 15 `expected.json` modificados; rerun dry-run → `eligible_missing_before=0` para ambos campos; `python3 scripts/validate_contracts.py --schema expected --path <15 touched expected.json>` → PASS; `python3 -m elsian eval --all` → PASS 16/16 (`0327 62/62`, `ACLS 399/399`, `ADTN 209/209`, `CROX 314/314`, `GCT 267/267`, `INMD 234/234`, `IOSP 366/366`, `KAR 49/49`, `NEXN 169/169`, `NVDA 374/374`, `PR 153/153`, `SOM 197/197`, `SONO 335/335`, `TALO 199/199`, `TEP 90/90`, `TZOO 312/312`); `python3 -m pytest -q` → 1359 passed, 5 skipped, 1 warning.
- ✅ **BL-080 completado (2026-03-08)** — Recuperada la regresión acotada de Provenance Level 3 en TZOO sin reabrir extractor/eval de Módulo 1. `elsian/assemble/source_map.py` vuelve a resolver punteros `:ixbrl:` con sufijos derivados como `:bs_identity_bridge` contra el fact base de iXBRL, y `tests/unit/test_source_map.py` añade la regresión específica. Validación: `python3 -m pytest -q tests/unit/test_source_map.py tests/integration/test_source_map.py` → 14 passed; `python3 -m elsian source-map TZOO --output <tmp>` → `SourceMap_v1 FULL` (818/818); `python3 -m elsian eval TZOO` → PASS 100.0% (300/300); `python3 -m pytest -q` → 1349 passed, 6 skipped, 1 warning.

- ✅ **BL-079 completado (2026-03-08)** — Cerrado el drift extractor amplio de ADTN con una corrección shared-core en extractor/merge, no con parche local por ticker. ADTN queda en PASS 100.0% (193/193) contra su verdad filing-backed anual; GCT y TZOO siguen en PASS 100%; los controles extra NEXN, NVDA, TEP, TALO, SONO e INMD también quedan verdes, y `eval --all` vuelve a pasar 16/16. En gobernanza, `BL-079` y `BL-074` quedan archivadas y `PROJECT_STATE` se reconcilia con ADTN como `ANNUAL_ONLY` validado pero todavía fuera del contador `DEC-015`.

- ✅ **BL-057 completado (2026-03-07)** — Cerrado el piloto conservador de auto-discovery LSE/AIM para SOM. `EuRegulatorsFetcher` ya deduplica variantes `/media` vs `/~/media`, backfillea `filings/` parciales cuando `filings_expected_count` queda corto, poda documentos no financieros y limita LSE/AIM a un set núcleo anual/interim/regulatory. `ir_crawler` además conserva PDFs de presentación directos y usa basename context para CTA genéricos tipo `Read more`, evitando misclasificaciones por contexto vecino. Un caso temporal de SOM sin `filings_sources` descarga `annual-report-2024`, `somero-2024-final-results-presentation` y `somero-2025-interim-investor-presentation`, manteniendo `eval SOM` en PASS 100.0% (179/179).

- ✅ **BL-047 completado (2026-03-07)** — Endurecimiento reusable del extractor HTML en dos patrones compartidos. `elsian/extract/html_tables.py` ahora descarta tablas comparativas suplementarias con columnas explícitas de `Change`, y además preserva el contexto `Six/Nine Months Ended` cuando el markdown split deja la fecha del periodo anterior como header suelto. Eso evita period mappings ambiguos en notas como `Interest income` y corrige el ruido YTD de cash flow (`capex`, `cfo`, `depreciation_amortization`) sin tocar truth ni degradar winner selection. Validación shared-core: `python3 -m pytest -q tests/unit/test_html_tables.py tests/unit/test_extract_phase.py` → 65 passed; `python3 -m elsian eval NVDA` → PASS 100.0% (354/354, `extra` 545 → 503); `python3 -m elsian eval --all` → 15/15 PASS; `pytest -q` → 1303 passed, 5 skipped.

- ✅ **BL-053 completado (2026-03-07)** — Provenance Level 3 queda pilotado sin reabrir el pipeline de extracción. Nuevo builder `elsian/assemble/source_map.py` + CLI `elsian source-map` generan `SourceMap_v1` desde `extraction_result.json` y resuelven targets trazables sobre `.htm`, `.clean.md` y `.txt`. Piloto TZOO validado con 851/851 campos resueltos. El hardening posterior añade resolución `*.txt:table`, soporte de `case_dir` relativo, labels verticales más robustos y UX CLI `FULL/PARTIAL/EMPTY` con preflight explícito de `extraction_result.json`. Validación targeted actualizada: `tests/unit/test_source_map.py` + `tests/integration/test_source_map.py` → 13 passed; `ruff` limpio; `python3 -m elsian eval TZOO` → PASS 100.0% (300/300); demo `python3 -m elsian source-map TZOO --output <tmp>` → 851/851 resueltos.

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

La ola governance-only del 2026-03-11 deja **sin** backlog vivo ejecutable. `BL-085` era el único packet BL-ready, pequeño y serial, y queda ya absorbido con closeout canónico.

El resto del programa queda repartido así:
- **Fase A** — capacidad cerrada actual: 16 tickers en capacidad operativa cerrada dentro de Module 1; esa cifra mezcla capacidad `FULL` y excepciones ticker-level ya cerradas, no equivale a 5 mercados cerrados de forma generalizada.
- **Fase B** — backlog vivo: vacío en este snapshot.
- **Fase C** — frontera abierta, watchlist de excepciones y expansión de capacidad: `SOM`, la generalización de mercado en LSE/AIM/HKEX/Euronext, el gap factual de coverage/manifest de `TALO` y la watchlist de excepciones ticker-level viven ahora en el subtree operativo estructurado de `docs/project/OPPORTUNITIES.md` hasta que aparezca evidencia nueva suficiente para empaquetarlos como BL o reafirmarlos como excepción estable.

El contrato `parallel-ready` sigue vigente por `BL-072` y `DEC-029`, pero no cambia el criterio de esta fase: cualquier nueva ola técnica que reaparezca desde evidencia factual deberá volver a empaquetarse de forma **serial** y de blast radius mínimo.

Ver BACKLOG.md para la cola completa. Plan de ejecución: `docs/project/PLAN_DEC010_WP1-WP6.md` (DEC-011).

**DEC-011 WPs completados (5/6):**
- ~~WP-1 (BL-027)~~ — DONE. Scope Governance.
- ~~WP-2 (BL-028)~~ — DONE. SEC Hardening.
- ~~WP-3 (BL-004, BL-025)~~ — DONE. iXBRL Parser + Curate.
- ~~WP-4 (BL-014)~~ — DONE. Preflight en ExtractPhase.
- ~~WP-5~~ — DONE. CI + Python 3.11.
- **WP-6** — IxbrlExtractor en producción. **DONE** (BL-048).

**Histórico — Oleada 4 (DEC-016, snapshot archivado; no describe el estado operativo vigente):**
- ✅ **BL-039 (ACLS)** — DONE. SEC semiconductor, iXBRL, FULL 375/375.
- ✅ **BL-040 (INMD)** — DONE. SEC 20-F/6-K, healthcare (IFRS), FULL 210/210.
- ✅ **BL-044 (TEP→FULL)** — DONE. Euronext semestrales, FULL 80/80. Regresión por BL-042 corregida en BL-046.
- ✅ **BL-041 (CROX)** — DONE. SEC footwear, FULL 294/294.
- ✅ **BL-042 (SOM)** — DONE (DEC-022). 16 periodos, 179/179, 100%. Regresión TEP corregida.
- ✅ **BL-049 (Truth Pack)** — DONE. TruthPackAssembler funcional. 45 tests.
- ✅ **BL-051 (Auto-discovery)** — DONE. elsian discover funcional. 38 tests.
- ✅ **BL-043 (0327)** — DONE. HKEX, primer ticker asiático. 3A, 59/59, 100%.

Ese bloque conserva el cierre factual de aquella oleada, pero queda supersedido por la taxonomía viva de este documento. En particular, la línea histórica de `BL-042 (SOM)` no debe leerse como estado operativo actual de `SOM` ni como cierre vigente del frente LSE/AIM.

**Lectura canónica vigente de DEC-015:**
- Cuentan hoy: **16** (14 FULL + KAR + JBH por excepción ASX documentada)
- No cuenta hoy: **SOM**, mientras siga clasificado como **frontera abierta** en LSE/AIM.
- `ADTN` y `0327` ya no quedan fuera del cómputo: `BL-081` promueve ADTN a `FULL` con 15 trimestrales filing-backed y `BL-083` promueve `0327` a `FULL` con 3 semestrales HKEX extractor-backed.
- `JBH` sí cuenta hoy dentro del cómputo operativo de `DEC-015` bajo la misma excepción ASX ya aplicada a `KAR`; esta es la única lectura vigente en los canonicals actuales.
- **DEC-015 target operativo alcanzado y superado factualmente** sin convertir `SOM` en excepción implícita ni cerrar su tratamiento documental antes de tiempo.

**WP-6** — IxbrlExtractor en producción. **DONE** (BL-048).

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
