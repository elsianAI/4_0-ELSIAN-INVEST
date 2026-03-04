# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-04
> Actualizado por: Copilot (Project Director)

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Target Fase 1→2 | Fecha |
|---|---|---|---|
| Tickers FULL 100% (DEC-015) | **13** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, TEP, CROX, +KAR*) | ≥15 | 2026-03-04 |
| Tickers ANNUAL_ONLY 100% | 0 | — | 2026-03-04 |
| Tickers WIP | 0 | 0 | 2026-03-04 |
| Total campos validados | 3,010 (14×100%) | — | 2026-03-04 |
| Campos canónicos | 25 (22 originales + cfi, cff, delta_cash) | — | 2026-03-04 |
| Tests pasando | 1106 passed, 0 failed, 2 skipped | — | 2026-03-04 |
| Líneas de código (aprox.) | ~10,000 + ~5,000 tests | 2026-03-04 |

*KAR (49 campos, 3A): ASX annual-only — no quarterly filings disponibles en ASX para este ticker. Cuenta como FULL bajo DEC-015 excepción.

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 288 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| GCT | 252 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED (FULL: 6A+9Q) |
| IOSP | 338 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+17Q) |
| NEXN | 153 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED (FULL: 4A+6Q) |
| SONO | 311 | SEC (US) | 10-K HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| TEP | 80 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED (FULL: 6A+2H — BL-044 DONE) |
| TALO | 183 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+7Q) |
| NVDA | 336 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| KAR | 49 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED (DEC-015 excepción: no quarterly en ASX) |
| PR | 141 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 3A+6Q) |
| ACLS | 375 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+15Q) |
| INMD | 210 | SEC (US) | 20-F/6-K HTML (IFRS) | ✅ VALIDATED (FULL: 6A+6Q — BL-040 promoted) |
| CROX | 294 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL — BL-041 DONE) |

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
| IxbrlExtractor | ⚠️ Parser listo, Extractor pendiente | Parser iXBRL implementado (BL-004 DONE). Comando `elsian curate` operativo (BL-025 DONE). IxbrlExtractor para producción pendiente (WP-6). |
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
| Provenance Level 3 | ❌ Pendiente | source_map.json no implementado |
| CI GitHub Actions | ✅ Implementado | Workflow ci.yml en .github/workflows/. pytest en Python 3.11. WP-5 DONE |
| Sanity Checks post-extracción | ✅ Implementado | capex sign, revenue neg, gp>revenue, YoY >10x. BL-016 DONE |
| Autonomous Validator | ✅ Implementado | 9 quality gates intrínsecos (BS identity, CF identity, units 1000x, EV, margins, TTM, recency, completeness). BL-020 DONE |
| validate_expected.py | ✅ Implementado | 8 reglas + 2 sanity warnings. Pre-check en evaluate(). BL-017 DONE |
| Field Dependency Matrix | ✅ Publicado + Oleada 1 DONE | 26 campos analizados (8 critical, 12 required, 6 optional). 3 campos críticos añadidos: cfi, cff, delta_cash (BL-035 DONE). 7 faltan. |

## Tickers WIP

Ninguno. Todos los 14 tickers están al 100%.

## Bloqueantes actuales

No hay bloqueantes críticos activos. El pipeline es funcional end-to-end para los 14 tickers validados (13 FULL + KAR* excepción).

**Gaps pendientes (no bloqueantes):**
1. **IxbrlExtractor para producción pendiente** — Parser listo y curate funcional, falta integrar como Extractor en pipeline (WP-6, futuro).
2. **BL-035 Oleada 2 pendiente** — accounts_receivable, inventories, accounts_payable (required por producto, no critical).
3. **Faltan 2 tickers para llegar a 15 FULL (DEC-015):** SOM (LSE) y 0327 (HKEX). Ambos requieren fetchers nuevos.

## Hitos recientes

- ✅ **BL-022 + BL-024 + BL-007 (2026-03-05)** — Market data fetcher portado (830L, 62 tests), transcript finder portado (1085L, 58 tests), PdfTableExtractor creado (447L, 47 tests). +167 tests. CLI ampliado con `market` y `transcripts`.
- ✅ **BL-041 CROX 100% (2026-03-06)** — CROX (Crocs Inc.) arreglado de 98.98% a 100% (294/294). Fix en phase.py: severe_penalty -100→-300, regla canónica ingresos+income_statement:net_income, override activo para .txt, afinidad año-periodo para net_income. Sin regresiones: 14/14 PASS.
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
- **WP-6** — IxbrlExtractor en producción. **DIFERIDO.**

**Siguiente fase — Oleada 4 (DEC-016):**
- ✅ **BL-039 (ACLS)** — DONE. SEC semiconductor, iXBRL, FULL 375/375.
- ✅ **BL-040 (INMD)** — DONE. SEC 20-F/6-K, healthcare (IFRS), FULL 210/210.
- ✅ **BL-044 (TEP→FULL)** — DONE. Euronext semestrales, FULL 80/80.
- ✅ **BL-041 (CROX)** — DONE. SEC footwear, FULL 294/294.
- **BL-042 (SOM)** — LSE, nuevo mercado, requiere fetcher LSE. TODO.
- **BL-043 (0327)** — HKEX, nuevo mercado, requiere fetcher HKEX. TODO.

**Ruta a 15 FULL (DEC-015):**
- Actuales: **13 FULL** (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, TEP, CROX, KAR*)
- Pendientes: SOM (LSE, nuevo mercado), 0327 (HKEX, nuevo mercado)
- Proyección: 13 + 2 nuevos = **15 FULL** (exacto al target)

**WP-6** — IxbrlExtractor en producción (diferido).

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
