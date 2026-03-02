# ELSIAN-INVEST 4.0 — Estado del Proyecto

> Última actualización: 2026-03-05
> Actualizado por: Copilot (Project Director)

---

## Fase actual: FASE 1 — Consolidar Layer 1

Ver ROADMAP.md para descripción completa de fases.

## Métricas clave

| Métrica | Valor | Fecha |
|---|---|---|
| Tickers validados (100%) | 9 | 2026-03-05 |
| Tickers WIP | 0 | 2026-03-05 |
| Total campos validados | 892 (9 tickers @100%) | 2026-03-05 |
| Tests pasando | 346 passed, 0 failed, 2 skipped | 2026-03-05 |
| Líneas de código (aprox.) | ~6,700 + ~1,500 tests | 2026-03-05 |

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
| Filing Preflight (idioma/estándar/moneda/unidades/restatement) | ✅ Implementado | Portado de 3.0. EN/FR/ES/DE, IFRS/US-GAAP, 9 monedas, unidades por sección, restatement. BL-009 DONE. Falta integrar en ExtractPhase (BL-014) |
| Deduplicación por contenido | ✅ Implementado | SHA-256 content hash portado. Integrado en AsxFetcher. BL-010 DONE |
| Exchange/Country awareness | ✅ Implementado | markets.py unificado: normalize_country/exchange, is_non_us, infer_regulator_code. BL-011 DONE |
| Filing Classification automática | ✅ Implementado | classify_filing_type() con 5 tipos. BL-012 DONE |
| IR Website Crawling | ✅ Implementado | ir_crawler.py portado completo (~600 líneas). Falta integrar en EuRegulatorsFetcher (BL-013) |
| Provenance Level 2 | ⚠️ Parcial | Modelo existe, campos no siempre poblados (BL-006) |
| Provenance Level 3 | ❌ Pendiente | source_map.json no implementado |

## Bloqueantes actuales

No hay bloqueantes críticos activos. El pipeline es funcional end-to-end para los 9 tickers.

**Gaps pendientes (no bloqueantes):**
1. **Preflight no integrado en ExtractPhase** — preflight.py funciona standalone pero sus resultados (currency, units_by_section) no alimentan ScaleCascade durante la extracción. BL-014.
2. **IR Crawler no integrado en EuRegulatorsFetcher** — ir_crawler.py portado pero TEP sigue dependiendo de filings_sources manuales. BL-013.
3. **IxbrlExtractor pendiente** — fuente primaria para SEC según DEC-005. BL-004.

## Hitos recientes

- ✅ **BL-008 DONE** — AsxFetcher reescrito con escaneo 1-day backward. PDFs byte-idénticos. KAR autónomo.
- ✅ **BL-001 DONE** — KAR rehecho desde cero con AsxFetcher autónomo. 49 campos, 3 periodos, 100%.
- ✅ **BL-002 DONE** — NVDA completado. 38 campos, 2 periodos, 100%.
- ✅ **BL-003 DONE** — Pipeline wiring completo. Todas las fases heredan PipelinePhase.
- ✅ **BL-009 DONE** — Filing Preflight portado de 3.0 (idioma, estándar, moneda, unidades, restatement).
- ✅ **BL-010 DONE** — Deduplicación por contenido SHA-256 portada e integrada.
- ✅ **BL-011 DONE** — Exchange/Country awareness unificado en markets.py.
- ✅ **BL-012 DONE** — Filing Classification automática portada.
- ✅ **Acquire layer completo** — SecEdgarFetcher, EuRegulatorsFetcher, AsxFetcher, ManualFetcher, IR Crawler, converters.
- ✅ **115+ tests nuevos** del port de acquire (277→346 total).

## Próximas prioridades

Ver BACKLOG.md para la cola completa. Las 3 más urgentes:

1. **BL-004** — Portar IxbrlExtractor desde 3.0. Fuente primaria SEC según DEC-005.
2. **BL-005** — Expandir a 15 tickers validados. 9/15 conseguidos.
3. **BL-014** — Integrar Preflight en ExtractPhase para que units_by_section alimente ScaleCascade.

---

## Protocolo de actualización

**Quién actualiza este fichero:** El agente director, después de revisar CHANGELOG.md y el estado del código.

**Cuándo se actualiza:**
- Al inicio de cada sesión del director (leer → evaluar → actualizar si hay cambios)
- Después de que un agente técnico reporte progreso significativo

**Qué NO va aquí:** Decisiones estratégicas (van en DECISIONS.md), tareas pendientes (van en BACKLOG.md), cambios técnicos (van en CHANGELOG.md).
