# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-02
> Actualizado por: Copilot (Project Director)

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Target Fase 1→2 | Fecha |
|---|---|---|---|
| Tickers FULL 100% (DEC-015) | 8 (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, +KAR*) | ≥15 | 2026-03-02 |
| Tickers ANNUAL_ONLY pendientes | 2 (NEXN — blocked BL-036, TEP — sin quarterly publicados) | Promover o documentar excepción | 2026-03-02 |
| Tickers WIP | 0 | 0 | 2026-03-02 |
| Total campos validados | 2,093 | — | 2026-03-02 |
| Tests pasando | 475 passed, 0 failed, 2 skipped | — | 2026-03-02 |
| Líneas de código (aprox.) | ~7,500 + ~2,200 tests | 2026-03-02 |

*KAR (49 campos, 3A): ASX annual-only — no quarterly filings disponibles en ASX para este ticker. Cuenta como FULL bajo DEC-015 excepción.

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 270 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| GCT | 252 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED (FULL: 6A+9Q) |
| IOSP | 338 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+17Q) |
| NEXN | 76 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED (ANNUAL_ONLY — blocked BL-036: 6-K exhibits) |
| SONO | 311 | SEC (US) | 10-K HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| TEP | 55 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED (ANNUAL_ONLY — sin quarterly publicados) |
| TALO | 183 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+7Q) |
| NVDA | 318 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| KAR | 49 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED (DEC-015 excepción: no quarterly en ASX) |
| PR | 141 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 3A+6Q) |

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
| PdfTableExtractor | ❌ Pendiente | pdfplumber ready, extractor no creado (BL-007) |
| Filing Preflight (idioma/estándar/moneda/unidades/restatement) | ✅ Implementado + Integrado | Portado de 3.0. EN/FR/ES/DE, IFRS/US-GAAP, 9 monedas, unidades por sección, restatement. BL-009 DONE. Integrado en ExtractPhase con units_by_section → ScaleCascade. BL-014/WP-4 DONE. |
| Deduplicación por contenido | ✅ Implementado | SHA-256 content hash portado. Integrado en AsxFetcher. BL-010 DONE |
| Exchange/Country awareness | ✅ Implementado | markets.py unificado: normalize_country/exchange, is_non_us, infer_regulator_code. BL-011 DONE |
| Filing Classification automática | ✅ Implementado | classify_filing_type() con 5 tipos. BL-012 DONE |
| IR Website Crawling | ✅ Implementado | ir_crawler.py portado completo (~600 líneas). Falta integrar en EuRegulatorsFetcher (BL-013) |
| Provenance Level 2 | ⚠️ Parcial | Modelo existe, campos no siempre poblados (BL-006) |
| Provenance Level 3 | ❌ Pendiente | source_map.json no implementado |
| CI GitHub Actions | ✅ Implementado | Workflow ci.yml en .github/workflows/. pytest en Python 3.11. WP-5 DONE |

## Bloqueantes actuales

No hay bloqueantes críticos activos. El pipeline es funcional end-to-end para los 10 tickers.

**Gaps pendientes (no bloqueantes):**
1. **IR Crawler no integrado en EuRegulatorsFetcher** — ir_crawler.py portado pero TEP sigue dependiendo de filings_sources manuales. BL-013.
2. **IxbrlExtractor para producción pendiente** — Parser listo y curate funcional, falta integrar como Extractor en pipeline (WP-6, futuro).

## Hitos recientes

- ✅ **BL-008 DONE** — AsxFetcher reescrito con escaneo 1-day backward. PDFs byte-idénticos. KAR autónomo.
- ✅ **BL-001 DONE** — KAR rehecho desde cero con AsxFetcher autónomo. 49 campos, 3 periodos, 100%.
- ✅ **BL-002 DONE** — NVDA completado y expandido. 318 campos (6A+12Q), 18 periodos, 100%. Scope corregido.
- ✅ **BL-027 DONE** — Scope Governance (WP-1). NVDA period_scope:FULL. Test de consistencia scope creado (9 tickers). 360 tests pasando.
- ✅ **BL-028 DONE** — SEC Hardening (WP-2). Cache lógico en sec_edgar.py. CaseConfig acepta `cik`. SecEdgarFetcher usa cik preconfigurado. 364 tests.
- ✅ **BL-004 DONE** — Parser iXBRL determinista (WP-3). 594 líneas, 45 concept mappings, 21/23 campos cubiertos. 63 tests nuevos.
- ✅ **BL-025 DONE** — Comando `elsian curate` (WP-3). TZOO: 100% field coverage, 93% value match. NVDA: 93% field coverage. KAR: skeleton OK.
- ✅ **WP-5 DONE** — CI GitHub Actions + verificación Python 3.11. Workflow ci.yml creado. Markers `slow`/`network` registrados.
- ✅ **BL-014/WP-4 DONE** — Preflight integrado en ExtractPhase. units_by_section → ScaleCascade por sección (IS/BS/CF). Provenance extendido con preflight_currency/standard/units_hint. 18 tests nuevos. 445 total.
- ✅ **BL-031 DONE** — Tests de integración para `elsian curate`. 18 tests: E2E TZOO (6), skeleton TEP (4), cobertura vs expected.json (2, guardrail ≥90%, medido 100%), sanity checks (6). 463 tests total.
- ✅ **BL-026 DONE** — FULL promotions: SONO 311/311 (6A+12Q), GCT 202/202 (6A+6Q), TALO 183/183 (5A+7Q). IOSP bloqueado por BL-038. 6 tickers FULL total (TZOO, NVDA, SONO, GCT, TALO, PR).
- ✅ **BL-033 DONE** — PR promovido de WIP a VALIDATED: 141/141 (100%, FULL scope, 3A+6Q). Fixes: shares_outstanding regex, total_debt reject patterns, eps_basic/net_income priority patterns, ascending_table_number override.
- ✅ **BL-038 DONE** — Table parser fix: parenthetical `( value | )` collapse, `$` currency prefix normalization, scale-note subheader tolerance. IOSP desbloquea 24+ Q periods. GCT Q1-Q3 2024 ahora disponibles. 473 tests, 0 regresiones.
- ✅ **BL-003 DONE** — Pipeline wiring completo. Todas las fases heredan PipelinePhase.
- ✅ **BL-009 DONE** — Filing Preflight portado de 3.0 (idioma, estándar, moneda, unidades, restatement).
- ✅ **BL-010 DONE** — Deduplicación por contenido SHA-256 portada e integrada.
- ✅ **BL-011 DONE** — Exchange/Country awareness unificado en markets.py.
- ✅ **BL-012 DONE** — Filing Classification automática portada.
- ✅ **Acquire layer completo** — SecEdgarFetcher, EuRegulatorsFetcher, AsxFetcher, ManualFetcher, IR Crawler, converters.
- ✅ **115+ tests nuevos** del port de acquire (277→346 total).

## Próximas prioridades

Ver BACKLOG.md para la cola completa. Plan de ejecución: `docs/project/PLAN_DEC010_WP1-WP6.md` (DEC-011).

**DEC-011 WPs completados (5/6):**
- ~~WP-1 (BL-027)~~ — DONE. Scope Governance.
- ~~WP-2 (BL-028)~~ — DONE. SEC Hardening.
- ~~WP-3 (BL-004, BL-025)~~ — DONE. iXBRL Parser + Curate.
- ~~WP-4 (BL-014)~~ — DONE. Preflight en ExtractPhase.
- ~~WP-5~~ — DONE. CI + Python 3.11.
- **WP-6** — IxbrlExtractor en producción. **DIFERIDO.**

**Siguiente fase:**
- **BL-036** — NEXN 6-K exhibit download → desbloquea NEXN FULL.
- **BL-005** — 5 tickers nuevos para llegar a 15 FULL (DEC-015).
- **WP-6** — IxbrlExtractor en producción (diferido).

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
