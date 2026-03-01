# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-02
> Actualizado por: Copilot

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Fecha |
|---|---|---|
| Tickers validados (100%) | 9 | 2026-03-02 |
| Tickers WIP | 0 | 2026-03-02 |
| Total campos validados | 892 (9 tickers @100%) | 2026-03-02 |
| Tests pasando | 342 passed, 0 failed, 2 skipped | 2026-03-02 |
| Líneas de código (aprox.) | ~5,800 + ~1,200 tests | 2026-03-02 |

## Tickers validados

| Ticker | Campos | Mercado | Formato | Estado |
|---|---|---|---|---|
| TZOO | 270 | SEC (US) | 10-K/10-Q HTML | ✅ VALIDATED |
| GCT | 108 | SEC (US) | 20-F→10-K HTML | ✅ VALIDATED |
| IOSP | 95 | SEC (US) | 10-K HTML | ✅ VALIDATED |
| NEXN | 76 | SEC (US) | 20-F/6-K HTML | ✅ VALIDATED |
| SONO | 116 | SEC (US) | 10-K HTML | ✅ VALIDATED |
| TEP | 55 | Euronext (FR) | PDF (IFRS, EUR) | ✅ VALIDATED |
| TALO | 85 | SEC (US) | 10-K HTML | ✅ VALIDATED |
| NVDA | 38 | SEC (US) | 10-K HTML | ✅ VALIDATED |
| KAR | 49 | ASX (AU) | PDF (IFRS, USD) | ✅ VALIDATED |

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
| IxbrlExtractor | ❌ Pendiente | Existe en 3.0, hay que portar (BL-004) |
| PdfTableExtractor | ❌ Pendiente | pdfplumber ready, extractor no creado (BL-007) |
| Filing Preflight (idioma/estándar/moneda/unidades/restatement) | ❌ Pendiente | Existe en 3.0 (320 líneas). 4.0 detect.py es parcial (BL-009) |
| Deduplicación por contenido | ❌ Pendiente | Content hash del 3.0 no portado (BL-010) |
| Exchange/Country awareness | ⚠️ Parcial | Cada fetcher tiene su lógica, no unificado (BL-011) |
| Filing Classification automática | ❌ Pendiente | El 3.0 clasifica ANNUAL/INTERIM/REGULATORY (BL-012) |
| IR Website Crawling | ❌ Pendiente (Baja prioridad) | ~600 líneas en 3.0. Solo necesario para mercados sin API |
| Provenance Level 2 | ⚠️ Parcial | Modelo existe, campos no siempre poblados (BL-006) |
| Provenance Level 3 | ❌ Pendiente | source_map.json no implementado |

## Bloqueantes actuales

1. **AsxFetcher usa endpoint genérico** — escanea TODOS los anuncios de ASX en ventanas de 14 días (~78 requests). ASX tiene endpoint por compañía que lo resuelve en 1-3 requests. Debe reescribirse antes de rehacer KAR.
2. **KAR eliminado** — caso borrado completamente. Se recreará desde cero una vez AsxFetcher funcione correctamente.
3. **NVDA en fase cero** — solo tiene case.json. Sin filings, sin expected.json.

## Hitos recientes

- ✅ **BL-003 completado** — Todas las fases (Acquire, Extract, Evaluate) heredan de PipelinePhase con run(context). Pipeline orquesta correctamente. +6 tests.
- ✅ **Acquire layer portado** — SecEdgarFetcher, EuRegulatorsFetcher, converters HTML→MD y PDF→text.

## Próximas prioridades

Ver BACKLOG.md para la cola completa. Las 3 más urgentes:

1. Reescribir AsxFetcher con endpoint por compañía (BL-008, prerrequisito de KAR)
2. Rehacer KAR desde cero con AsxFetcher funcional (BL-001)
3. Completar NVDA: acquire + curación + eval (BL-002)
4. Portar IxbrlExtractor desde 3.0 (BL-004, ya desbloqueado)

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
