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

### BL-004 — Parser iXBRL determinístico (módulo reutilizable)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** BL-027 (governance limpio primero)
- **Descripción:** Construir `elsian/extract/ixbrl.py` — un parser determinístico que extrae datos financieros estructurados de ficheros iXBRL (los mismos .htm que ya descargamos de SEC/ESEF). El parser: (1) localiza tags `ix:nonFraction` / `ix:nonNumeric`, (2) extrae concepto, periodo, valor, unidad, escala (`decimals`), contexto, (3) mapea conceptos GAAP/IFRS a nuestros 23 campos canónicos vía `config/ixbrl_concept_map.json` (nuevo) + `field_aliases.json`, (4) normaliza escala y signos a nuestra convención (DEC-004). **Este módulo es reutilizable:** será consumido por `elsian curate` (BL-025) para generar expected.json, y en el futuro por `IxbrlExtractor(Extractor)` dentro del pipeline de producción. Un parser, dos consumidores (DEC-010). **Portado desde 3.0** `ixbrl_extractor.py` si existe, sino implementar con BeautifulSoup (ya es dependencia). **Plan detallado: WP-3 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Parser extrae correctamente todos los campos canónicos disponibles de al menos 2 tickers SEC (TZOO, NVDA). Tests unitarios con fixtures iXBRL reales. Output es una lista de FieldResult con provenance (concepto iXBRL, contexto, periodo). Sin dependencias nuevas (bs4 ya está).

### BL-025 — Comando `elsian curate` (generador de expected.json)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** BL-004 (parser iXBRL)
- **Descripción:** Crear comando `python3 -m elsian.cli curate {TICKER}` que genera `expected_draft.json` de forma automática. Para tickers con iXBRL (SEC, ESEF): usa el parser de BL-004 para extraer todos los campos canónicos de todos los periodos disponibles, filtrando solo campos con representación tabular en IS/BS/CF. Para tickers sin iXBRL (ASX, emergentes): genera un esqueleto vacío con los periodos detectados. El draft incluye metadata de origen (concepto iXBRL, filing fuente, escala original). El draft se depura después manualmente o con LLM para producir el expected.json final. **No forma parte del pipeline de producción** — es herramienta de desarrollo/QA. **Plan detallado: WP-3 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** `elsian curate TZOO` genera un expected_draft.json con ≥90% de los campos del expected.json actual. `elsian curate NVDA` genera draft con periodos anuales Y trimestrales. El draft pasa sanity checks automáticos (revenue>0, assets=liabilities+equity ±1%). Tests del comando.

### BL-026 — Promover tickers SEC a FULL vía curate
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-02, oleada 3)
- **Asignado a:** elsian-4
- **Depende de:** BL-025 (comando curate funcional)
- **Descripción:** Oleada 1 (SONO, GCT) + Oleada 2 (TALO) + Oleada 3 (IOSP, GCT Q1-Q3 2024) completadas. SONO→FULL 100% (311/311, 18p). GCT→FULL 100% (202/202→252/252, 15p). TALO→FULL 100% (183/183, 12p). IOSP→FULL 100% (95/95→338/338, 22p, 17 trimestres añadidos). PR promovido a FULL 100% (141/141). NVDA y TZOO ya estaban en FULL.
- **Criterio de aceptación:** ≥5 tickers en FULL al 100% (incluyendo TZOO y NVDA). Sin regresiones en tickers que no cambian de scope. ✅ Cumplido: 7 tickers en FULL (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP). Oleada 3 completada (IOSP desbloqueado por BL-038). 9/9 tickers PASS 100%.

### BL-027 — Scope Governance: coherencia case.json vs expected.json
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Corregir inconsistencias de scope detectadas en auditoría: (1) Añadir `period_scope: "FULL"` a NVDA case.json (tiene 18 periodos con Q pero scope implícito ANNUAL_ONLY). (2) Auditar todos los case.json: si expected.json tiene periodos Q*/H* → case.json debe tener period_scope FULL. (3) Corregir referencia a "23 campos canónicos" en docs → son 23. (4) Alinear test count en PROJECT_STATE con la realidad. (5) Crear test automático `tests/integration/test_scope_consistency.py` que verifique coherencia scope↔expected para todos los tickers validados. **Plan detallado: WP-1 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Todos los case.json coherentes con sus expected.json. Test de consistencia pasa. Docs alineados con realidad. Regresión verde.

### BL-028 — SEC Hardening: cache lógico + CIK preconfigurado
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** — (paralelo a WP-3)
- **Descripción:** (1) Cache en sec_edgar.py debe contar filings lógicos (stems únicos) no ficheros físicos. (2) Añadir campo `cik: str | None = None` a CaseConfig. (3) SecEdgarFetcher usa case.cik si existe, fallback a API si no. (4) Verificar que eliminación de Pass 2 exhibit_99 no pierde filings. **Plan detallado: WP-2 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Cache cuenta filings lógicos (test). CaseConfig acepta cik. NVDA usa CIK sin resolución API. Regresión verde.

### BL-029 — Corregir contrato Python: >=3.11 vs entorno local 3.9.6
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-06) — Verificado: codebase usa X|Y unions (3.10+), pyproject.toml >=3.11 es correcto. CI workflow creado.
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** pyproject.toml declara `requires-python = ">=3.11"` pero el entorno local actual es Python 3.9.6. Decidir: (a) bajar el requisito a >=3.9 si no usamos features de 3.10+, o (b) actualizar el entorno local a 3.11+. Verificar uso real de features post-3.9 (`match/case`, `X | Y` type unions, `tomllib`, etc.).
- **Criterio de aceptación:** El contrato en pyproject.toml coincide con el entorno mínimo real donde el pipeline funciona correctamente.

### BL-005 — Expandir a 15 tickers validados
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-025 (curate acelera la curación)
- **Descripción:** Objetivo Fase 1: 15-20 tickers validados. Con `elsian curate` disponible, añadir tickers es mucho más rápido para SEC/ESEF. Candidatos: large-cap US (AAPL, MSFT), sector financiero (JPM), micro-cap, Europa continental (SAP.DE, SAN.MC), Asia (Toyota). Cada uno valida un gap diferente en las reglas de extracción.
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
- **Estado:** DONE
- **Asignado a:** Claude (Copilot)
- **Depende de:** BL-009 (DONE)
- **Descripción:** `elsian/analyze/preflight.py` integrado en `ExtractPhase.extract()`. Preflight se ejecuta por filing (non-blocking). Units_by_section alimenta ScaleCascade via `_FIELD_SECTION_MAP`. Provenance incluye `preflight_currency`, `preflight_standard`, `preflight_units_hint`.
- **Completado:** 2026-03-02. 18 tests nuevos. 445 passed, 0 failed. 9/9 tickers al 100%.

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

### BL-030 — Test para Exhibit 99 fallback en SecEdgarFetcher
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** `_find_exhibit_99` en `sec_edgar.py` solo tiene Pass 1 (búsqueda en index.json). No hay test que cubra esta función ni validación de que funciona para 8-Ks con estructura irregular. WP-2 planificaba "validar eliminación de Pass 2" pero no se hizo. Añadir test unitario que verifique el comportamiento actual y un test de integración que confirme que earnings filings de TZOO se adquieren correctamente.
- **Criterio de aceptación:** ≥2 tests unitarios para `_find_exhibit_99`. Test de integración que valide que TZOO earnings filings se localizan vía index.json. Documentar si Pass 2 (HTML fallback) sería necesario para algún caso real.

### BL-031 — Tests de integración para el comando `elsian curate`
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-025 (DONE)
- **Descripción:** 18 tests de integración en `tests/integration/test_curate.py`. E2E TZOO (6 tests), skeleton TEP (4 tests), cobertura vs expected.json (2 tests, 100% real), sanity checks (6 tests). Fixtures scope=module con cleanup automático de expected_draft.json.
- **Criterio de aceptación:** ✓ 18 tests pasando. ✓ Cobertura TZOO 100% (102/102 campos). ✓ 463 total passed, 0 failed.

### BL-032 — Documentar o limpiar cases/PR
- **Prioridad:** BAJA
- **Estado:** DONE ✅ (2026-03-02) — DEC-013: PR trackeado como WIP.
- **Asignado a:** Director
- **Depende de:** —
- **Descripción:** El directorio `cases/PR/` (Permian Resources Corp, NYSE, CIK 0001658566, period_scope: FULL) fue creado durante WP-3. Decisión tomada en DEC-013: PR se trackea como WIP (88.65%, 125/141). case.json + expected.json añadidos al repo. Falta añadir a WIP_TICKERS en test_regression.py (BL-033).
- **Criterio de aceptación:** ✓ cases/PR documentado en PROJECT_STATE. ✓ DEC-013 registrada.

### BL-033 — Promover PR de WIP a VALIDATED (100%)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02) — PR al 100% (141/141, FULL scope). Commit ede5a4e.
- **Asignado a:** Claude (elsian-4)
- **Depende de:** DEC-013
- **Descripción:** PR (Permian Resources, NYSE) está al 88.65% (125/141). Problemas: (1) shares_outstanding no extraído en 9 periodos (FY2025-FY2023, Q3-Q1 2025, Q3-Q1 2024), (2) total_debt con desviación ~5-15% en 5 periodos, (3) net_income y eps_basic wrong en FY2023. El agente técnico debe: añadir PR a WIP_TICKERS en test_regression.py, diagnosticar los 3 problemas, iterar hasta 100%.
- **Criterio de aceptación:** ✓ PR al 100% (141/141). ✓ PR migrado de WIP_TICKERS a VALIDATED_TICKERS. ✓ Sin regresiones en los 9 tickers existentes (10/10 tickers a 100%).

### BL-038 — Pipeline bug: IS no extraído en 10-Q con formato de columna desalineado
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** Dos tickers (IOSP, GCT) no podían promoverse a FULL porque el pipeline fallaba al extraer IS desde 10-Q con formatos específicos: (1) IOSP: parenthetical `( value | )` generaba columnas extra. (2) GCT: `$` como celda separada desplazaba valores. (3) IOSP: scale-note cell bloqueaba detección de subheaders. Fix en dos commits: `_collapse_split_parentheticals()` + grouped year assignment + scale-note tolerance en `_is_subheader_row()`. IOSP ahora extrae 24+ periodos Q, GCT Q1-Q3 2024 ahora disponibles.
- **Criterio de aceptación:** ✅ Pipeline extrae IS para IOSP Q* (24+ periodos) y GCT Q1-Q3 2024 (18-20 campos). 10/10 tickers al 100%. 475 tests pass.

### BL-036 — SecEdgarFetcher: descargar Exhibit 99.1 de 6-K (NEXN quarterly)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03)
- **Asignado a:** Claude (Copilot)
- **Depende de:** —
- **Descripción:** El SecEdgarFetcher actual descarga `primary_doc` para 6-Ks, pero para foreign private issuers como NEXN (Israel/UK, 20-F/6-K), los datos financieros trimestrales están en el **Exhibit 99.1** adjunto al 6-K, no en el primary_doc (que es solo la portada del formulario, ~48 líneas). El fetcher ya tiene `_find_exhibit_99()` para 8-Ks pero no lo aplica a 6-Ks. Fix: extender la lógica de exhibit discovery a 6-Ks que contengan earnings results. Verificado: SRC_010_6-K_Q4-2025.txt referencia explícitamente "Exhibit 99.1" con financial statements completos (IS/BS/CF para three/nine months). Sin este fix, NEXN no puede promoverse a FULL.
- **Criterio de aceptación:** `acquire NEXN` descarga los .htm de Exhibit 99.1 de los 6-K con earnings results. Los .htm se convierten a .clean.md. `extract NEXN` produce periodos Q* con datos de IS/BS/CF. Tests unitarios para la nueva lógica de 6-K exhibit discovery. Sin regresiones en otros tickers SEC.

### BL-039 — Nuevo ticker ACLS (Axcelis Technologies, NASDAQ, SEC)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03) — ACLS FULL 100% (375/375, 21 periodos). Commits 79938bd + 3961d2b.
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** Axcelis Technologies como ticker SEC con iXBRL. NASDAQ, semiconductor (sector nuevo). Cobertura: 6 annual + 15 quarterly = 21 periodos, 375 campos. Cuatro fixes al pipeline: (1) ZWS stripping en html_tables.py, (2) "Twelve/Year Ended" period detection, (3) pro-forma column guard, (4) narrative suppression cuando .clean.md existe. Segundo commit: orphaned date fragment merging, income_tax IS/CF priority, section bonus fix.
- **Criterio de aceptación:** ✅ ACLS en VALIDATED_TICKERS al 100% FULL. 12/12 tickers al 100%. 487 tests pass. **Nota:** source_filing vacío en 223/375 campos quarterly — pendiente de corrección.

### BL-040 — Nuevo ticker INMD (InMode, NASDAQ, 20-F/6-K)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-036 DONE — puede usar solo 20-F annual si 6-K quarterly da problemas
- **Descripción:** Añadir InMode Ltd. (Israel) como foreign private issuer con 20-F/6-K. Sector healthcare (nuevo). iXBRL disponible. Patrón 6-K con Exhibit 99.1 (mismo que GCT/NEXN). Con BL-036 resuelto, promover a FULL con quarterly. Datos en `3_0-ELSIAN-INVEST/casos/INMD/`.
- **Criterio de aceptación:** INMD en VALIDATED_TICKERS al 100%. period_scope FULL con quarterly. eval --all sin regresiones.

### BL-041 — Nuevo ticker BOBS (Bob's Discount Furniture, NYSE, SEC)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Añadir BOBS como ticker SEC NYSE. **Test de robustez del fetcher SEC:** en el 3.0 solo se descargaron Form 4 (insider trading), lo que indica que el fetcher no identificó 10-K/10-Q correctamente. El pipeline 4.0 debe adquirirlos automáticamente con `elsian acquire BOBS`. Si no los descarga → diagnosticar y arreglar el bug en SecEdgarFetcher. Datos en `3_0-ELSIAN-INVEST/casos/BOBS/`.
- **Criterio de aceptación:** `acquire BOBS` descarga ≥3 annual + ≥6 quarterly filings automáticamente (no Form 4). BOBS en VALIDATED_TICKERS al 100% FULL. Si el fetcher tiene bug → bug corregido con test de regresión.

### BL-042 — Nuevo ticker SOM (Somero Enterprises, LSE, UK/FCA)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Primer ticker London Stock Exchange. Requiere: (1) Investigar si LSE/FCA tiene API de filings automatizable (RNS feed, FCA National Storage Mechanism). (2) Si la hay → construir `LseFetcher(Fetcher)`. (3) Si no → usar ManualFetcher. Filings son PDF annual reports con formato corporativo UK. Portar filings del 3.0 desde `3_0-ELSIAN-INVEST/casos/SOM/`. El fetcher LSE queda como infraestructura reutilizable.
- **Criterio de aceptación:** SOM en VALIDATED_TICKERS al 100%. Fetcher LSE (o ManualFetcher con justificación) funcional. period_scope: ANNUAL_ONLY inicialmente, evaluar si hay H1 para FULL.

### BL-043 — Nuevo ticker 0327 (PAX Global Technology, HKEX, Hong Kong)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Primer ticker Hong Kong Exchange. Requiere: (1) Investigar si HKEX tiene API de filings automatizable. (2) Si la hay → construir `HkexFetcher(Fetcher)`. (3) Si no → usar ManualFetcher. Filings son PDF annual reports en formato asiático. Portar filings del 3.0 desde `3_0-ELSIAN-INVEST/casos/0327/`. Sector industrials (nuevo).
- **Criterio de aceptación:** 0327 en VALIDATED_TICKERS al 100%. Fetcher HKEX (o ManualFetcher con justificación) funcional. period_scope: evaluar interim reports en HKEX (H1 obligatorio en HK → debería ser FULL).

### BL-044 — Promover TEP a FULL (investigar semestrales Euronext)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** TEP (Teleperformance, Euronext Paris) está en ANNUAL_ONLY con 55 campos y 100%. La EU Transparency Directive obliga a publicar reportes semestrales (H1). Investigar: (1) ¿Teleperformance publica H1 financial statements completos? (2) Si sí → descargar, curar con H1, cambiar period_scope a FULL. (3) Si no → documentar excepción bajo DEC-015.
- **Criterio de aceptación:** Si H1 existe → TEP al 100% con period_scope FULL. Si no → excepción DEC-015 documentada.

### BL-034 — Field Dependency Matrix: análisis de dependencias 3.0→4.0
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** —
- **Descripción:** Analizar estáticamente `scripts/runners/tp_validator.py` y `scripts/runners/tp_calculator.py` del 3.0 para generar una matriz objetiva de dependencias de campos. Para cada campo: clasificar como critical/required/optional según reglas objetivas: (1) critical = su ausencia provoca FAIL/SKIP en gates críticos del validator, (2) required = su ausencia degrada cálculos del calculator sin romper gates, (3) optional = solo afecta enriquecimiento no bloqueante. Publicar con evidencia por campo: archivo fuente, función, gate/métrica impactada, clasificación, justificación. **Análisis puro — no se toca código del 4.0.**
- **Criterio de aceptación:** Documento `docs/project/FIELD_DEPENDENCY_MATRIX.md` publicado. Snapshot máquina `docs/project/field_dependency_matrix.json` publicado. 100% de campos con evidencia rastreable al código fuente del 3.0. Revisión final por Elsian antes de pasar a Fase B.

### BL-035 — Expandir campos canónicos según Field Dependency Matrix
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Depende de:** BL-034 (matriz revisada) + BL-038 (DONE) + oleada 3 IOSP/NEXN (DONE)
- **Descripción:** Con la matriz de BL-034 en mano, expandir el extractor 4.0 y expected.json para cubrir campos faltantes priorizados como critical y luego required. **Oleada 1 (critical):** `cfi` (cash from investing), `cff` (cash from financing), `delta_cash` (variación neta de caja) — los 3 inputs del gate CASHFLOW_IDENTITY del validator. **Oleada 2 (required por producto):** `accounts_receivable`, `inventories`, `accounts_payable` — inputs de working capital en tp_calculator (no disparan gates del validator, pero son necesarios para completitud de producto). **Oleada 3:** resto de campos critical/required según matriz, solo si oleadas 1+2 están validadas. Pilotos: TZOO (primario) y NVDA (secundario). Usar `elsian curate` para generar drafts ampliados. Mantener formato expected.json v1 actual — solo se añaden más campos, sin nuevas claves estructurales. Toda priorización de campos sale de la matriz objetiva (BL-034), no de agrupaciones temáticas.
- **Criterio de aceptación:** Nuevos campos de oleada 1 extraídos y evaluados al 100% en TZOO y NVDA para periodos donde estén en expected.json. Sin regresiones en tickers validados. Cada campo nuevo en expected.json referencia filing fuente consistente con extracción. Tests unitarios por campo nuevo (caso positivo + caso negativo).

---

## Notas

- Las prioridades las establece el director según el estado del proyecto y el ROADMAP.
- Si un agente técnico descubre una tarea nueva durante su trabajo, la añade al final con prioridad MEDIA y estado TODO. El director la reordenará en la siguiente sesión.


