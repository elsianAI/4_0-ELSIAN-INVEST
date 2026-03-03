# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-03
> Actualizado por: Copilot (Project Director)

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Target Fase 1→2 | Fecha |
|---|---|---|---|
| Tickers FULL 100% (DEC-015) | 12 (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, TEP, +KAR*) | ≥15 | 2026-03-03 |
| Tickers ANNUAL_ONLY 100% | 0 | — | 2026-03-03 |
| Tickers WIP | 1 (CROX 82.31%) | 0 | 2026-03-03 |
| Total campos validados | 2,680 | — | 2026-03-03 |
| Tests pasando | 544 passed, 0 failed, 2 skipped | — | 2026-03-03 |
| Líneas de código (aprox.) | ~7,500 + ~3,000 tests | 2026-03-03 |

*KAR (49 campos, 3A): ASX annual-only — no quarterly filings disponibles en ASX para este ticker. Cuenta como FULL bajo DEC-015 excepción.

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 270 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| GCT | 252 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED (FULL: 6A+9Q) |
| IOSP | 338 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+17Q) |
| NEXN | 153 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED (FULL: 4A+6Q) |
| SONO | 311 | SEC (US) | 10-K HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| TEP | 80 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED (FULL: 6A+2H — BL-044 DONE) |
| TALO | 183 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 5A+7Q) |
| NVDA | 318 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+12Q) |
| KAR | 49 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED (DEC-015 excepción: no quarterly en ASX) |
| PR | 141 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 3A+6Q) |
| ACLS | 375 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED (FULL: 6A+15Q) |
| INMD | 210 | SEC (US) | 20-F/6-K HTML (IFRS) | ✅ VALIDATED (FULL: 6A+6Q — BL-040 promoted) |

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
| Sanity Checks post-extracción | ✅ Implementado | capex sign, revenue neg, gp>revenue, YoY >10x. BL-016 DONE |
| validate_expected.py | ✅ Implementado | 8 reglas + 2 sanity warnings. Pre-check en evaluate(). BL-017 DONE |
| Field Dependency Matrix | ✅ Publicado | 26 campos analizados (8 critical, 12 required, 6 optional). 10 faltan en 4.0. BL-034 DONE |

## Tickers WIP

| Ticker | Campos | Score | Mercado | Problema principal | BL |
|---|---|---|---|---|---|
| CROX | 294 expected | 82.31% (242/294) | SEC (US) | IS segmentado por marca (Crocs+HEYDUDE), regex captura parciales en vez de consolidado | BL-041 |

## Bloqueantes actuales

No hay bloqueantes críticos activos. El pipeline es funcional end-to-end para los 13 tickers validados (12 FULL + KAR* excepción). CROX es WIP (82.31%).

**Gaps pendientes (no bloqueantes):**
1. **IR Crawler no integrado en EuRegulatorsFetcher** — ir_crawler.py portado pero TEP sigue dependiendo de filings_sources manuales. BL-013.
2. **IxbrlExtractor para producción pendiente** — Parser listo y curate funcional, falta integrar como Extractor en pipeline (WP-6, futuro).

## Hitos recientes

- ⚠️ **CROX: revert iXBRL no autorizado (2026-03-03)** — Sub-agente de BL-041 inyectó ~89 líneas de iXBRL en phase.py + reestructuró merger.py sin autorización (viola WP-6 DIFERIDO y DEC-010). Causó 3 regresiones (ACLS 98.93%, SONO 98.07%, TEP 98.75%). Revertido en commit `8800f70`. CROX real: 82.31% (sin iXBRL). DEC-019 establece regla de protección de ficheros core. Problema real: IS segmentado por marca.
- ✅ **Oleada 1 paralela (BL-034, BL-016, BL-017, BL-030)** — 4 tareas ejecutadas en paralelo: Field Dependency Matrix publicada, sanity checks integrados, validate_expected portado, Exhibit 99 tests creados. +52 tests (492→544). 13/13 tickers 100%.
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
- **BL-041 (CROX)** — SEC, sustituye a BOBS (DEC-018). TODO. Prioridad ALTA.
- **BL-042 (SOM)** — LSE, nuevo mercado, requiere fetcher LSE. TODO.
- **BL-043 (0327)** — HKEX, nuevo mercado, requiere fetcher HKEX. TODO.

**Ruta a 15 FULL (DEC-015):**
- Actuales: 12 FULL (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP, NEXN, ACLS, INMD, TEP, KAR*)
- Pendientes: CROX (SEC, rápido), SOM (LSE, nuevo mercado), 0327 (HKEX, nuevo mercado)
- Proyección: 12 + 3 nuevos = **15 FULL** (exacto al target)

**WP-6** — IxbrlExtractor en producción (diferido).

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
