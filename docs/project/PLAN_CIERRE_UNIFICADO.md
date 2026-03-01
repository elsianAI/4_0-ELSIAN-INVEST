# Plan de Cierre Unificado 4.0 — Paridad 3.0 + Gaps Estratégicos

> **Autores:** Codex (iteraciones 40-42, IR crawler parity) + Claude (inventario exhaustivo 3.0→4.0)
> **Fecha:** 2026-03-01 (rev.1 — corregido tras review de Codex)
> **Objetivo:** Cerrar TODOS los gaps detectados entre 3.0 y 4.0, organizados en fases ejecutables.

---

## Contexto

Se han hecho dos análisis independientes:

1. **Codex** detectó gaps operativos concretos en el IR crawler (fallback de fecha HTML, tie-break por fecha en empates de score) y propone sacar KAR temporalmente de la regresión.

2. **Claude** hizo un inventario exhaustivo del 3.0 completo (~48,700 líneas, 158 ficheros Python) comparándolo con el 4.0 (~10,940 líneas, 73 ficheros). Identificó gaps en Layer 1 que no están ni portados ni en el backlog, más todo el engine/ de Layer 2+ como referencia futura.

Este plan unifica ambos análisis en un roadmap ejecutable.

---

## FASE A — Paridad IR + Regresión (Plan Codex, inmediato)

> Prioridad: **CRÍTICA**. Esto desbloquea la suite de tests.

### A1. IR Crawler Parity Patch (Iteración 40 de Codex)

**Archivo:** `elsian/acquire/ir_crawler.py`

**Estado verificado:** `_extract_date_from_html_document()` existe (línea 191) pero es dead code — nunca se invoca desde `extract_filing_candidates()` ni `_extract_embedded_pdf_candidates()`. Los sort (líneas 852 y 879) solo usan `selection_score`, sin tie-break por fecha.

**Cambios:**
- En `extract_filing_candidates()`:
  - Calcular `page_date, page_date_source = _extract_date_from_html_document(html, base_url)` una sola vez.
  - Mantener prioridad actual: `_resolve_local_candidate_date()` manda.
  - Si `date_guess` es `None` y `page_date` existe → fallback:
    - `fecha_publicacion = page_date`
    - `fecha_source = f"page_{page_date_source}"`
    - `fecha_publicacion_estimated = True`
- En `_extract_embedded_pdf_candidates()`:
  - Añadir mismo fallback por `page_date` cuando no haya fecha contextual.
- **Tie-break por fecha** — Restaurar paridad 3.0 para empates de score:
  - Actualmente: `key=lambda x: float(x.get("selection_score", 0.0))`
  - Cambiar a: `key=lambda x: (float(x.get("selection_score", 0.0)), x.get("fecha_publicacion", ""))`
  - Aplica tanto en `extract_filing_candidates()` (línea ~853) como en `select_fallback_candidates()` (línea ~879).
- No cambiar `_prefer_new_candidate()` salvo ajustes mínimos de compatibilidad.

**Tests nuevos** (en `tests/unit/test_ir_crawler.py`):
1. `test_fallback_page_date_when_candidate_has_no_date` — Link sin fecha en anchor/row/url + HTML con meta date → `fecha_publicacion` poblada con prefijo `page_*`.
2. `test_do_not_override_context_date_with_page_date` — Link con fecha contextual válida + HTML con meta date distinta → se conserva la contextual.
3. `test_tie_break_by_fecha_when_score_equal` — Dos candidatos con mismo `selection_score` → primero el más reciente.

### A2. Regresión: KAR temporalmente fuera de validated (Iteración 41 de Codex)

**Archivo:** `tests/integration/test_regression.py`

**Estado actual:**
```python
VALIDATED_TICKERS = ["TZOO", "GCT", "IOSP", "NEXN", "SONO", "TEP", "TALO", "KAR"]
WIP_TICKERS: list[str] = []
```

**Cambio:**
```python
VALIDATED_TICKERS = ["TZOO", "GCT", "IOSP", "NEXN", "SONO", "TEP", "TALO"]

# Tickers with known issues pending recertification
PENDING_RECERT_TICKERS = ["KAR"]

# Tickers still being curated (expected to fail, not blocking)
WIP_TICKERS: list[str] = []
```

- Añadir test parametrizado para `PENDING_RECERT_TICKERS` marcado con `pytest.mark.skip(reason="KAR recertification pending — BL-001 + BL-008")`.
- KAR aparece como SKIPPED en la salida, no desaparece.

**Documentación:**
- BACKLOG.md: ya tiene BL-001 y BL-008 que cubren la recertificación.
- CHANGELOG.md: registrar la exclusión temporal y razón.

### A3. Verificación (Iteración 42 de Codex)

```bash
python3 -m pytest -q
python3 -m pytest tests/unit/test_ir_crawler.py -q
python3 -m pytest tests/integration/test_regression.py -q
```

**Criterios:**
- 0 FAIL.
- KAR aparece como SKIPPED con motivo explícito.
- Resto de regresión (7 tickers) al 100%.
- Candidatos sin fecha contextual salen con `fecha_source` de tipo `page_*`.

---

## FASE B — Gaps Layer 1 no contemplados (Hallazgos Claude, alta prioridad)

> Prioridad: **ALTA**. Funcionalidad determinística (0 LLM) que debería existir en 4.0 pero no está portada ni en el backlog.

### B1. Calculadora de métricas derivadas — `tp_calculator.py` (806 líneas en 3.0)

**¿Qué es?** Aritmética financiera pura:
- TTM (Trailing Twelve Months) = suma de últimos 4 trimestres OR FY0 fallback
- FCF = CFO − CapEx
- EV = market_cap + total_debt − cash
- Working Capital = (AR + INV) − (AP + accruals)
- Márgenes: bruto, operativo, neto, FCF
- Retornos: ROIC, ROE, ROA
- Múltiplos: EV/EBIT, EV/FCF, P/FCF, FCF_yield
- Net Debt = Debt − Cash
- Per-share: EPS, FCF/share, BV/share

**¿Existe en 4.0?** NO. No hay nada equivalente.

**Acción:** Portar como `elsian/calculate/derived.py`. Es código determinístico puro, no depende de LLM.

**Referencia 3.0:** `scripts/runners/tp_calculator.py`

### B2. Sanity checks del normalizer — `tp_normalizer.py` (808 líneas en 3.0)

**¿Qué es?** Validaciones post-extracción:
- CapEx siempre positivo (convención)
- Revenue > 0
- Gross profit ≤ revenue
- No saltos YoY >10x sin razón
- 11 formatos de value wrappers: `{"value": X}` → `X`
- Aplanamiento de estructuras anidadas: `metricas.X` → top-level
- Normalización de 6 nesting patterns

**¿Existe en 4.0?** PARCIALMENTE. `normalize/aliases.py`, `normalize/scale.py` y `normalize/signs.py` cubren alias y escala, pero NO las sanity checks ni el value unwrapping.

**Acción:** Portar las sanity checks como `elsian/normalize/sanity.py` e integrar en el pipeline post-extracción.

**Referencia 3.0:** `scripts/runners/tp_normalizer.py`

### B3. Validación de expected.json — `validate_expected.py` (108 líneas en 3.0)

**¿Qué es?** Valida estructura y calidad de expected.json antes de usarlo en evaluación:
- Formato correcto (periodos, campos, valores)
- Quality gates (mínimo de campos por periodo)
- Coherencia interna

**¿Existe en 4.0?** NO. El evaluator.py asume que expected.json es correcto.

**Acción:** Portar como `elsian/evaluate/validate_expected.py`. Integrarlo en `evaluate()` como pre-check.

**Referencia 3.0:** `deterministic/src/validate_expected.py`

### B4. Quality gates para clean.md — `clean_md_quality.py` (240 líneas en 3.0)

**¿Qué es?** Validación semántica de los .clean.md generados:
- ¿Tiene tablas reales con datos numéricos?
- ¿No es un stub/placeholder?
- ¿Cumple mínimos por sección financiera?

**¿Existe en 4.0?** PARCIALMENTE. `html_to_markdown.py` ya incluye:
- `_is_clean_md_useful()` (línea 216): valida ≥1 sección con contenido real + ≥10 datos numéricos
- Filtros de ≥2 rows numéricos por tabla (líneas 188, 208)
- `convert()` retorna string vacío si el quality gate falla (línea 304)

**¿Qué falta vs 3.0?** El `clean_md_quality.py` del 3.0 (240 líneas) tiene validaciones MÁS granulares:
- Mínimos por sección individual (no solo global)
- Detección de stubs/placeholders más sofisticada
- Métricas de calidad exportables (no solo pass/fail)
- Posibilidad de dry-run para diagnóstico

**Acción:** Evaluar qué validaciones adicionales del 3.0 aportan valor real y portarlas como extensión de `_is_clean_md_useful()` o como módulo separado `convert/md_quality.py`. No reimplementar lo que ya existe.

**Referencia 3.0:** `scripts/runners/clean_md_quality.py`

### ~~B5. Extracción financiera de HTML con presupuestos por sección~~ — **YA PORTADO**

**Diagnóstico original erróneo.** Tras revisión de código, `convert/html_to_markdown.py` (306 líneas) YA TIENE:
- `SECTION_PATTERNS` con regex multiidioma EN/FR/ES/DE para balance, income, cash flow, equity (líneas 18-64)
- `SECTION_BUDGETS` con presupuestos por sección: 80K (balance/income/cashflow), 40K (equity) (líneas 66-71)
- `HARD_CAP = 220_000` (línea 73)
- Quality gate `_is_clean_md_useful()` que valida ≥1 sección y ≥10 datos numéricos (líneas 216-227)
- Validación de ≥2 rows numéricos por tabla (líneas 188-193)

**Acción:** NINGUNA. Ya existe paridad con `clean_md_extractor.py` del 3.0. Lo único pendiente de evaluar es si `clean_md_pipeline.py` (257 líneas del 3.0, que unifica HTML→clean.md + PDF→TXT→clean.md) aporta algo que no cubra el pipeline actual — pero esto es menor y no bloquea.

### B6. Validación de Truth Pack — `tp_validator.py` (790 líneas en 3.0)

**¿Qué es?** Quality gates post-extracción + post-cálculo:
- Campos requeridos presentes (ingresos, net_income, etc.)
- Cobertura de periodos (suficientes anuales + trimestrales)
- Sanity checks: revenue > 0, márgenes razonables, no cambios extremos YoY
- Consistencia de escala
- Alineación de moneda

**¿Existe en 4.0?** PARCIALMENTE. `evaluate/evaluator.py` (104 líneas) compara contra expected.json pero NO tiene las validaciones intrínsecas (sin expected.json de referencia).

**Acción:** Portar como `elsian/evaluate/validation.py` — validación autónoma que no depende de expected.json.

**Referencia 3.0:** `scripts/runners/tp_validator.py`

---

## FASE C — Componentes operativos (prioridad media)

> No bloquean Layer 1, pero mejoran la robustez operativa.

### C1. Sources Compiler — `sources_compiler_runner.py` (865 líneas en 3.0)

**¿Qué es?** El puente Stage 1→2: compila fuentes de 3 fetchers en un SourcesPack unificado.
- Merge de fuentes de SEC, market data, transcripts
- Dedup por URL (keep best quality score)
- Dedup por content_hash
- Renombrado a IDs canónicos (SRC_001, SRC_002, ...)
- Selección de mejor representación: .clean.md > .txt > .htm > .pdf
- Análisis de cobertura documental

**¿Existe en 4.0?** NO directamente. AcquirePhase orquesta fetchers pero no tiene la compilación/dedup/renombrado.

**Acción:** Evaluar si la arquitectura de 4.0 (AcquirePhase → per-fetcher results) necesita un compilador explícito o si el merge se hace diferente. Documentar decisión.

### C2. Prefetch Coverage Audit — `prefetch_coverage_audit.py` (370 líneas en 3.0)

**¿Qué es?** Audita si cada ticker tiene suficientes filings por categoría:
- Domestic US: SEC ≥20, transcripts ≥6, market data ≥1
- FPI/ADR: SEC ≥10, annual ≥1, periodic ≥1, transcripts ≥4
- NonUS: local ≥1, transcripts ≥4

**¿Existe en 4.0?** NO.

**Acción:** Portar como `elsian/evaluate/coverage_audit.py`. Útil para BL-005 (expandir a 15 tickers).

### C3. Market Data Fetcher — `market_data_v1_runner.py` (704 líneas en 3.0)

**¿Qué es?** Obtiene precio, market cap, shares outstanding de Yahoo Finance / AlphaVantage / IR pages.

**¿Existe en 4.0?** NO. Necesario para la calculadora de métricas derivadas (B1) — los múltiplos EV/EBIT, P/FCF necesitan market cap.

**Acción:** Portar como `elsian/acquire/market_data.py` implementando Fetcher ABC.

### C4. Transcript Finder — `transcript_finder_v2_runner.py` (1,434 líneas en 3.0)

**¿Qué es?** Busca y descarga transcripts de earnings calls (Fintool, IR pages, Seeking Alpha).

**¿Existe en 4.0?** NO.

**Acción:** Portar como `elsian/acquire/transcripts.py` implementando Fetcher ABC. Es input para las fases LLM futuras (catalyst detection, bull case, etc.).

---

## FASE D — Engine / LLM Layers (referencia para Phase 2+)

> **NO ejecutar ahora.** Documentado para que cuando lleguemos a Layer 2+ sepamos exactamente qué hay.

### D1. Engine Core (~7,400 líneas)
- `engine/engine.py` (2,245) — Orquestador principal
- `engine/router.py` (2,340) — Ejecución DAG: SOURCES → TRUTH_PACK → IMPLIED → CATALYST → FORENSIC → BULL → RED_TEAM → ARBITRO
- `engine/dispatcher.py` (2,822) — Dispatch multi-modelo con retry y escalation

### D2. LLM Backends (~1,150 líneas)
- `engine/backends/claude.py` (386) — Actualizar a claude-opus-4.6
- `engine/backends/codex.py` (281) — Actualizar a gpt-5
- `engine/backends/gemini.py` (242) — Actualizar versiones
- `engine/backends/copilot.py` (242) — Evaluar disponibilidad

### D3. Prompt & Quality (~2,600 líneas)
- `engine/prompt_builder.py` (681) — Construcción de prompts por paso
- `engine/quality_voting.py` (611) — Consenso multi-modelo
- `engine/review_compiler.py` (629) — Compilación de reviews
- `engine/model_quality_stats.py` (468) — Telemetría por modelo
- `engine/error_tracker.py` (449) — Tracking de errores

### D4. State & Config (~2,300 líneas)
- `engine/config.py` (730) — Configuración completa
- `engine/state.py` (562) — Persistencia _estado.json
- `engine/model_defaults.py` (357) — Defaults por modelo
- `engine/model_plan.py` (410) — Plan de selección
- `engine/validator.py` (311) — Validación de schemas LLM

### D5. LLM Prompts
- `_instrucciones/activas/` — Todos los prompts de análisis (catalyst, forensic, bull, red_team, implied, scanner, etc.)

### D6. Truth Pack Post-Processing (~2,700 líneas)
- `scripts/runners/tp_extractor_merger.py` (916) — Fusión multi-filing
- `scripts/runners/tp_normalizer.py` (808) — Normalización completa (parcialmente en B2)
- `scripts/runners/tp_calculator.py` (806) — Cálculos derivados (parcialmente en B1)
- `scripts/runners/deterministic_extractor.py` (528) — Wrapper de extracción

### D7. QA & Operations (~3,300 líneas)
- `scripts/case_quality_audit.py` (687) — Auditoría por caso
- `scripts/regression_check.py` (480) — Regresión
- `scripts/estado_resumen.py` (1,126) — Dashboard de estado
- `scripts/r1_canary_validation.py` (560) — Canary testing
- `scripts/phase2_ab_truthpack.py` (718) — A/B testing
- `scripts/qa/` — Recovery utilities (~750 líneas)

---

## Resumen de gaps: Estado actual vs Completo

| Componente | 3.0 LOC | 4.0 LOC | Estado | Fase |
|---|---:|---:|---|---|
| **Acquire (SEC, EU, ASX, IR)** | ~3,200 | ~2,550 | ✅ PORTADO | — |
| **Extract (tables, narrative, vertical)** | ~2,100 | ~3,060 | ✅ PORTADO | — |
| **Normalize (aliases, scale, audit)** | ~525 | ~550 | ✅ PORTADO | — |
| **Preflight** | ~320 | ~330 | ✅ PORTADO | — |
| **Dedup + Classify** | ~250* | ~245 | ✅ PORTADO | — |
| **Merge + Evaluate** | ~340 | ~385 | ✅ PORTADO | — |
| **IR Crawler date fallback** | — | — | 🔴 GAP | A1 |
| **Regresión KAR** | — | — | 🔴 GAP | A2 |
| **Calculadora derivadas** | ~806 | 0 | 🔴 GAP | B1 |
| **Sanity checks** | ~808* | 0 | 🔴 GAP | B2 |
| **validate_expected** | ~108 | 0 | 🔴 GAP | B3 |
| **clean.md quality** | ~240 | ~parcial | 🟡 PARCIAL (básico existe, faltan validaciones granulares) | B4 |
| **Financial sections extraction** | ~560 | ~306 | ✅ PORTADO (SECTION_PATTERNS, BUDGETS, HARD_CAP, quality gate) | ~~B5~~ |
| **Truth Pack validator** | ~790 | ~parcial | 🟡 PARCIAL | B6 |
| **Sources compiler** | ~865 | 0 | 🟡 GAP | C1 |
| **Coverage audit** | ~370 | 0 | 🟡 GAP | C2 |
| **Market data fetcher** | ~704 | 0 | 🟡 GAP | C3 |
| **Transcript finder** | ~1,434 | 0 | 🟡 GAP | C4 |
| **Engine (LLM orchestration)** | ~15,000 | 0 | ⬜ FUTURO | D |
| **QA scripts** | ~3,300 | 0 | ⬜ FUTURO | D7 |
| **LLM prompts** | ~múltiple | 0 | ⬜ FUTURO | D5 |

*LOC estimados de las funciones relevantes dentro de ficheros más grandes.

---

## Orden de ejecución recomendado

```
FASE A (inmediato, desbloquea suite)
  A1 → A2 → A3: IR patch + KAR skip + verify
  ↓
FASE B+C intercaladas (Layer 1 + operacional)
  B3 → B2 → B4 → B6          (validate_expected → sanity → md_quality → tp_validator)
  ↓
  C3 → B1                     (market data → calculator — B1 necesita C3 para múltiplos)
  ↓
  C2 → C1 → C4                (coverage audit → sources compiler → transcripts)
  ↓
FASE D (Layer 2+, futuro)
  D1-D7 según ROADMAP
```

**Nota:** B5 se elimina de la secuencia de ejecución (ver sección B5 — ya portado).

---

## Decisiones implícitas en este plan

1. **DEC-009 aplica a TODO:** Cada componente de B y C se porta desde el 3.0, no se reimplementa.
2. **Layer 1 primero:** No tocamos engine/ hasta que Layer 1 esté sólido.
3. **KAR se recupera vía BL-008 + BL-001**, no como parte de este plan.
4. **B1 (calculator) se ejecuta DESPUÉS de C3 (market data)** — los cálculos puros (FCF, márgenes, returns) no dependen de market data, pero los múltiplos (EV/EBIT, P/FCF) sí necesitan market cap. Por eso C3 se intercala antes de B1 en la secuencia.

---

## Backlog items a crear (nuevos, no existentes)

| ID propuesto | Título | Prioridad | Fase |
|---|---|---|---|
| BL-015 | Portar calculadora de métricas derivadas (tp_calculator.py) | ALTA | B1 |
| BL-016 | Portar sanity checks del normalizer (tp_normalizer.py) | ALTA | B2 |
| BL-017 | Portar validate_expected.py | ALTA | B3 |
| BL-018 | Extender quality gates de clean.md (validaciones granulares de clean_md_quality.py) | MEDIA | B4 |
| ~~BL-019~~ | ~~Portar extracción financiera con presupuestos por sección~~ — **YA EXISTE** en html_to_markdown.py | — | ~~B5~~ |
| BL-020 | Portar Truth Pack validator autónomo (tp_validator.py) | MEDIA | B6 |
| BL-021 | Portar coverage audit (prefetch_coverage_audit.py) | MEDIA | C2 |
| BL-022 | Portar market data fetcher (market_data_v1_runner.py) | MEDIA | C3 |
| BL-023 | Portar sources compiler (sources_compiler_runner.py) | MEDIA | C1 |
| BL-024 | Portar transcript finder (transcript_finder_v2_runner.py) | MEDIA | C4 |

---

## Acciones pendientes sobre este plan

1. **BL-items formalizados en BACKLOG.md** — Los IDs BL-015 a BL-024 (sin BL-019) ya están creados en el BACKLOG para ejecución por agentes técnicos.
2. **Fase A es responsabilidad de Codex** — Las iteraciones 40-42 se ejecutan directamente.
3. **Fases B y C las asigna el director** — Cada item se puede ejecutar independientemente.

## Asunciones

- No se toca `cases/KAR/expected.json` en Fase A — la recertificación es BL-001.
- No se cambia scoring heurístico fuera del tie-break por fecha (Fase A).
- Se prioriza paridad con 3.0 donde ya existe comportamiento probado.
- Fase A termina cuando la suite queda verde con KAR explícitamente pendiente.
- Fases B y C son incrementales — cada item se puede ejecutar independientemente.
- Fase D no tiene fecha — depende de que Layer 1 esté consolidado.
