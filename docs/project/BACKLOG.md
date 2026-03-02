# ELSIAN-INVEST 4.0 — Backlog Priorizado

> Cola de trabajo ordenada por prioridad. El agente técnico toma tareas de arriba a abajo.
> El agente director reordena según el estado del proyecto.

---

## Protocolo de uso

**Quién escribe:** El agente director (prioriza, añade, reordena, cierra).
**Quién lee:** Los agentes técnicos. Al iniciar sesión, leer las primeras 3-5 tareas para saber qué hacer.
**Quién actualiza estado:** El agente técnico marca IN_PROGRESS al empezar y DONE al terminar. El director limpia periódicamente las tareas DONE.

**Estados posibles:**
- `TODO` — Pendiente, nadie la ha empezado
- `IN_PROGRESS` — Un agente la está ejecutando (indicar cuál)
- `BLOCKED` — No se puede avanzar, indicar por qué
- `DONE` — Completada, pendiente de que el director la revise y archive

**Formato por tarea:**
```
### BL-XXX — Título corto
- **Prioridad:** CRÍTICA | ALTA | MEDIA | BAJA
- **Estado:** TODO | IN_PROGRESS (agente) | BLOCKED (razón) | DONE
- **Asignado a:** elsian-4 | director | sin asignar
- **Depende de:** BL-XXX (si aplica)
- **Descripción:** Qué hay que hacer y por qué
- **Criterio de aceptación:** Cómo sabemos que está terminado
```

---

## Tareas activas

### BL-008 — Reescribir AsxFetcher con endpoint por compañía
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** El AsxFetcher actual usa el endpoint genérico `/asx/1/announcement/list` que devuelve TODOS los anuncios de TODAS las empresas del ASX, y filtra por ticker en Python. Esto requiere ~78 requests HTTP en ventanas de 14 días para cubrir 3 años (DEC-008). **Hallazgo:** El endpoint por compañía (`asx.api.markitdigital.com`) tiene un hard cap de 5 items sin paginación — inutilizable. El endpoint genérico no soporta filtro por compañía ni paginación. Solución implementada: ventanas de 1 día con escaneo hacia atrás desde los meses de reporting esperados. Descarga ≥3 annual reports en 3-6 requests. Filings descargados son byte-idénticos a los manuales.
- **Criterio de aceptación:** ✓ `acquire KAR` descarga ≥3 annual reports automáticamente. ✓ No usa filings_sources. ✓ Tests existentes siguen pasando (339/339). ✓ PDFs son byte-idénticos a los descargados manualmente. **Nota:** Velocidad ~30-90s (API inherentemente lenta, no <30s como se esperaba — el endpoint por compañía no existe).

### BL-001 — Rehacer KAR desde cero
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-008 (AsxFetcher funcional) — DONE
- **Descripción:** KAR rehecho desde cero con AsxFetcher autónomo. case.json (source_hint=asx, currency=USD, fiscal_year_end_month=12), filings adquiridos automáticamente vía ASX API (6 PDFs + 6 TXTs), expected.json curado manualmente (49 campos, 3 periodos FY2023-FY2025, ≥15 campos/periodo cubriendo IS+BS+CF). Score: 100% (49/49).
- **Criterio de aceptación:** ✓ KAR en VALIDATED_TICKERS con 100%. ✓ filings/ tiene PDFs + .txt generados por acquire. ✓ expected.json tiene ≥15 campos por periodo. ✓ Regresión 10/10 al 100%.

### BL-002 — Nuevo ticker NVDA
- **Prioridad:** ALTA
- **Estado:** DONE ✅
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Añadir NVIDIA como ticker SEC large-cap. **Completado:** case.json ✅, acquire ✅ (28 filings descargados). expected.json ✅ (2 anni, 19 campos/período = 38 total cubriendo IS+BS+CF). **Extraction:** 100% — 38/38 matched.
- **Criterio de aceptación:** ✓ NVDA 100% (38/38). ✓ expected.json con 19 campos por período. ✓ filings/ con 28 archivos (6 annual, 12 quarterly, 10 earnings). ✓ Regresión 7/7 @ 100% (sin cambios en otros tickers). ✓ NVDA añadido a VALIDATED_TICKERS.

### BL-003 — Wire ExtractPhase a PipelinePhase.run(context)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03) — ver sección "Tareas completadas"
- **Asignado a:** elsian-4
- **Depende de:** —
- **Resultado:** Implementado. Todas las fases heredan PipelinePhase con run(context). Pipeline orquesta correctamente. cmd_run usa Pipeline([ExtractPhase(), EvaluatePhase()]). +6 tests nuevos. 346 tests pasando.

### BL-004 — Portar IxbrlExtractor desde 3.0
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** — (BL-003 ya completado)
- **Descripción:** Portar ixbrl_extractor.py de 3.0 y envolver en IxbrlExtractor(Extractor). iXBRL es fuente primaria donde exista (SEC). Cross-validation con HTML. Provenance nativa (concepto, periodo, contexto).
- **Criterio de aceptación:** IxbrlExtractor pasa tests unitarios. Al menos 1 ticker SEC extraído vía iXBRL con score ≥ resultado HTML. Sin regresiones.

### BL-005 — Expandir a 15 tickers validados
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-001, BL-002 (los primeros nuevos tickers)
- **Descripción:** Objetivo Fase 1: 15-20 tickers validados. Candidatos: large-cap US (AAPL, MSFT), sector financiero (JPM), micro-cap, Europa continental (SAP.DE, SAN.MC), Asia (Toyota). Cada uno valida un gap diferente en las reglas de extracción.
- **Criterio de aceptación:** ≥15 tickers en VALIDATED_TICKERS. Cada ticker cubre un gap diferente (documentado en regression_suite).

### BL-006 — Provenance Level 2 completa en todos los extractores
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** El modelo Provenance tiene campos table_title, row_label, col_label, raw_text pero no siempre se pueblan. Auditar cada extractor y asegurar que todos propagan coordenadas completas.
- **Criterio de aceptación:** Cada FieldResult en extraction_result.json tiene provenance con al menos source_filing + table_index + row + col + raw_text.

### BL-007 — Crear PdfTableExtractor
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** pdfplumber está integrado para conversión pero no hay un Extractor(ABC) dedicado a tablas PDF. Necesario para tickers como TEP y KAR que dependen de PDF.
- **Criterio de aceptación:** PdfTableExtractor(Extractor) con tests. TEP sigue al 100% usando el nuevo extractor.

### BL-009 — Portar Filing Preflight desde 3.0
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar `3_0-ELSIAN-INVEST/scripts/runners/filing_preflight.py` (320 líneas) al 4.0. Este módulo detecta idioma, estándar contable (IFRS/US-GAAP), moneda, secciones financieras, unidades por sección, restatement, y año fiscal — todo determinístico, <1ms por filing. El 4.0 tiene `detect.py` con funcionalidad parcial pero le falta: detección de restatement, unidades por sección (crítico para escala), multiidioma (fr, es, de), y confianza por señal. **Portar, no reimplementar (DEC-009).** Leer el código fuente del 3.0 primero, adaptar a la arquitectura 4.0.
- **Criterio de aceptación:** Preflight corre sobre todos los filings existentes. Detecta correctamente idioma, estándar, moneda, y unidades por sección para TZOO (US-GAAP, USD), TEP (IFRS, EUR, FR), y KAR (IFRS, USD). Tests unitarios con fixtures de cada tipo. Sin regresiones.
- **Referencia 3.0:** `scripts/runners/filing_preflight.py`

### BL-010 — Deduplicación de filings por contenido
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar la lógica de content hash del 3.0 (`_content_hash`, `_normalize_text_for_hash` en `sec_fetcher_v2_runner.py` líneas ~411-418). El pipeline puede procesar múltiples representaciones del mismo filing (.htm, .txt, .clean.md) como si fueran documentos distintos, generando colisiones en merge. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Dos filings con el mismo contenido textual se detectan como duplicados. Se procesan una sola vez. TZOO (28 filings, muchos con versiones .htm/.txt) no tiene colisiones por duplicación.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` funciones `_content_hash`, `_normalize_text_for_hash`

### BL-011 — Exchange/Country awareness unificada
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar del 3.0 las funciones `normalize_exchange()`, `normalize_country()`, `is_non_us()`, `infer_regulator_code()` (líneas ~297-358 de `sec_fetcher_v2_runner.py`) y las constantes `NON_US_EXCHANGES`, `NON_US_COUNTRIES`, `LOCAL_FILING_KEYWORDS_BY_EXCHANGE`. Unificar en `elsian/config/markets.py`. Usado por AcquirePhase para routing y por futuros fetchers. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Module con funciones puras + tests. AcquirePhase usa el módulo para routing en vez de string matching en `_get_fetcher()`.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` líneas 50-170 (constantes) y 297-358 (funciones)

### BL-012 — Filing Classification automática
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar `_classify_local_filing_type()` del 3.0 (líneas ~686-742 de `sec_fetcher_v2_runner.py`). Clasifica filings en ANNUAL_REPORT / INTERIM_REPORT / REGULATORY_FILING / IR_NEWS basándose en keywords del título, URL y snippet. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Función que recibe (title, url, snippet) → filing_type. Tests con ejemplos de SEC, ASX y EU. Integrado en los fetchers que no tienen clasificación propia.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` función `_classify_local_filing_type`

---

## Tareas completadas

### BL-003 — Wire ExtractPhase a PipelinePhase.run(context)
- **Prioridad:** ALTA
- **Estado:** DONE ✅
- **Completado:** 2026-03-03
- **Asignado a:** elsian-4
- **Resultado:** Todas las fases (Acquire, Extract, Evaluate) heredan PipelinePhase con run(context). Pipeline orquesta correctamente. cmd_run usa Pipeline([ExtractPhase(), EvaluatePhase()]). +6 tests nuevos. 157 tests pasando.

---

## Tareas descubiertas durante el port del módulo acquire (2026-03-04)

### BL-013 — Integrar IR Crawler en EuRegulatorsFetcher
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-012 (DONE)
- **Descripción:** `elsian/acquire/ir_crawler.py` está portado con todas las funciones de crawling (build_ir_pages, discover_ir_subpages, extract_filing_candidates, select_fallback_candidates, resolve_ir_base_url). Falta integrarlo en EuRegulatorsFetcher como fallback automático cuando `filings_sources` no está definido en case.json. El fetcher debería: 1) intentar `web_ir` → resolve_ir_base_url, 2) crawlear páginas IR, 3) extraer candidatos, 4) seleccionar y descargar. Esto eliminaría la dependencia de URLs manuales para tickers EU.
- **Criterio de aceptación:** `python3 -m elsian.cli acquire TEP` funciona sin `filings_sources` en case.json (usando solo web_ir). Tests de integración.

### BL-014 — Integrar preflight en el pipeline de extracción
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-009 (DONE)
- **Descripción:** `elsian/analyze/preflight.py` está portado pero no se ejecuta automáticamente. Debe integrarse en ExtractPhase para que cada filing pase por preflight antes de la extracción. Los resultados de preflight (currency, standard, units_by_section) deben alimentar ScaleCascade y AliasResolver.
- **Criterio de aceptación:** Cada filing en extraction_result.json incluye metadata de preflight. ScaleCascade usa units_by_section del preflight. Sin regresiones.

### BL-015 — Portar calculadora de métricas derivadas (tp_calculator.py)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-022
- **Descripción:** Portar `scripts/runners/tp_calculator.py` (3.0) a `elsian/calculate/derived.py`. Debe cubrir TTM, FCF, EV, working capital, márgenes, retornos, net debt y per-share. Mantener enfoque determinístico y paridad funcional.
- **Criterio de aceptación:** Módulo con tests unitarios; cálculo correcto sobre fixtures de TZOO/GCT; sin regresiones.

### BL-016 — Portar sanity checks del normalizer (tp_normalizer.py)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Portar sanity checks y value-unwrapping de `scripts/runners/tp_normalizer.py` a `elsian/normalize/sanity.py` e integrarlo post-extracción. Incluye reglas de coherencia (revenue>0, gross<=revenue, saltos extremos YoY, wrappers `{\"value\": X}`).
- **Criterio de aceptación:** Sanity checks activos en pipeline, con tests de aceptación y sin regresiones.

### BL-017 — Portar validate_expected.py
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Portar `deterministic/src/validate_expected.py` (3.0) a `elsian/evaluate/validate_expected.py` e integrarlo en `evaluate()` como pre-check estructural y de calidad.
- **Criterio de aceptación:** `evaluate()` falla con mensaje claro ante expected inválido; tests unitarios para casos válidos e inválidos.

### BL-018 — Extender quality gates de clean.md (gap parcial)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** `elsian/convert/html_to_markdown.py` ya implementa quality gate básico (`_is_clean_md_useful`) y mínimos numéricos por tabla. Portar solo las validaciones granulares faltantes de `scripts/runners/clean_md_quality.py` (métricas por sección, detección avanzada de stubs, diagnóstico exportable).
- **Criterio de aceptación:** Quality report granular por clean.md y gates reforzados sin degradar conversión actual.

### BL-020 — Portar validator autónomo de Truth Pack (tp_validator.py)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-015, BL-016
- **Descripción:** Portar validaciones autónomas de `scripts/runners/tp_validator.py` a `elsian/evaluate/validation.py` para checks intrínsecos (sin expected.json): identidad BS/CF, sanity de márgenes/escala/consistencia.
- **Criterio de aceptación:** Validator ejecutable sobre extraction/calc outputs con score de calidad y tests.

### BL-021 — Portar prefetch coverage audit
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Portar `scripts/runners/prefetch_coverage_audit.py` a `elsian/evaluate/coverage_audit.py` para medir cobertura por ticker/mercado antes de extracción.
- **Criterio de aceptación:** Reporte de coverage por caso con thresholds por tipo de mercado y tests.

### BL-022 — Portar market data fetcher (market_data_v1_runner.py)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Portar `scripts/runners/market_data_v1_runner.py` a `elsian/acquire/market_data.py` (Fetcher ABC). Necesario para múltiplos de valoración en BL-015.
- **Criterio de aceptación:** Fetcher de market cap/shares/precio con tests y contrato de salida estable.

### BL-023 — Portar sources compiler
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-022, BL-024
- **Descripción:** Portar `scripts/runners/sources_compiler_runner.py` para consolidar fuentes multi-fetcher (dedup URL/hash, prioridad de representación, IDs canónicos `SRC_*`).
- **Criterio de aceptación:** SourcesPack compilado de forma determinística con tests de dedup/prioridad.

### BL-024 — Portar transcript finder
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Portar `scripts/runners/transcript_finder_v2_runner.py` a `elsian/acquire/transcripts.py` (Fetcher ABC) para captura de earnings transcripts.
- **Criterio de aceptación:** Fetcher funcional con tests y outputs integrables en acquire pipeline.

> Nota: **BL-019 no se crea** porque la extracción financiera por secciones y presupuestos ya está portada en `elsian/convert/html_to_markdown.py`.

---

## Nuevas tareas (descubiertas en BL-002 NVDA)

### BL-010 — Mejorar HTML table extractor: interest_income + capex
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** NVDA extraction mostró 3 gaps:
  1. **interest_income** (×3 periodos): Campos no extraídos. Field no tiene patrón en narrative.py o nombre alternativo en field_aliases.json. Revisar filings para confirmar que el campo existe en tablas/narrativa. Si existe, añadir patrón de extracción.
  2. **capex** (×3 periodos): No extraído. Probable: Cash Flow Statement no parseado completamente. CapEx es uno de los campos críticos. Verificar source_filing y row en el 10-K.
  3. **total_debt** (off by 11.8%): Extracted 7,469 vs expected 8,468 (FY2026). Probable row selection error (short-term debt vs total debt). Audit table structure en balance sheet.
- **Criterio de aceptación:** interest_income y capex se extraen en ≥1 ticker. NVDA score sube a ≥90%. No hay regresión en otros tickers.

---

## Notas

- Las prioridades las establece el director según el estado del proyecto y el ROADMAP.
- Si un agente técnico descubre una tarea nueva durante su trabajo, la añade al final con prioridad MEDIA y estado TODO. El director la reordenará en la siguiente sesión.
- Las dependencias son orientativas. Si un agente puede resolver una tarea sin que su dependencia esté completada, puede hacerlo.
