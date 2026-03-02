# Plan de Ejecución DEC-010: iXBRL + Governance + Hardening

> **Fecha:** 2026-03-02
> **Origen:** Revisión Devil's Advocate (Codex) + validación Claude
> **Para:** Agente técnico (elsian-4) vía Project Director
> **Decisión base:** DEC-010 (estrategia iXBRL: un parser, dos mundos)
> **Estado actual:** 351 tests passing, 2 skipped, 9 tickers validated (todos 100%)

---

## Orden de ejecución

| Orden | WP | Título | Backlog | Depende de |
|-------|----|--------|---------|------------|
| 1 | WP-1 | Scope Governance | BL-027 | Nada |
| 2 | WP-3 | Parser iXBRL + Curate | BL-004, BL-025 | WP-1 |
| 3 | WP-4 | Preflight en Pipeline | BL-014 | WP-3 |
| ∥ | WP-2 | SEC Hardening | BL-028 | Nada (paralelo) |
| ∥ | WP-5 | CI y Paralelización | — | Nada (paralelo) |
| 4 | WP-6 | IxbrlExtractor Producción | — | WP-3 maduro + WP-4 |

**Regla:** Cada WP del camino crítico se cierra con regresión verde (351+ tests, 0 failed) antes de empezar el siguiente. WP-2 y WP-5 son paralelos e independientes.

---

## WP-1 — Scope Governance

### Contexto
Hay inconsistencias entre lo que dicen los ficheros de documentación y el estado real del código. Específicamente: NVDA tiene 18 periodos en expected.json (6A + 12Q) pero no tiene `period_scope: "FULL"` en case.json, `field_aliases.json` tiene 25 claves (23 datos + 2 metadata) pero los docs dicen 22, y PROJECT_STATE.md dice 346 tests cuando la realidad es 351. Estas incoherencias erosionan la confianza en la documentación como fuente de verdad.

### Qué hacer

1. **Corregir NVDA case.json**: Añadir `"period_scope": "FULL"` al fichero `cases/NVDA/case.json`. NVDA ya tiene 18 periodos (6 anuales + 12 trimestrales) en expected.json — el scope real es FULL pero no estaba documentado.

2. **Auditar todos los case.json vs expected.json**: Para cada ticker en `tests/integration/test_regression.py` → `VALIDATED_TICKERS`, verificar que:
   - Si expected.json contiene periodos Q* o H* → case.json debe tener `"period_scope": "FULL"`
   - Si expected.json solo tiene periodos FY* → case.json debe tener `"period_scope": "ANNUAL_ONLY"` (o sin campo, que es el default)
   - Corregir cualquier incoherencia encontrada.

3. **Verificar referencia a campos canónicos**: Confirmar que todos los ficheros dicen 23 campos canónicos (25 claves totales incluyendo _version y _description). Ya corregido en limpieza documental pre-DEC-011. Ficheros verificados:
   - `docs/project/DECISIONS.md` (DEC-010 — corregido a 23)
   - `docs/project/BACKLOG.md` (BL-004 ya decía 23, BL-027 corregido a 23)
   - `.github/agents/elsian-4.agent.md` (verificar si menciona el número)

4. **Verificar test count en PROJECT_STATE.md**: Ejecutar `python3 -m pytest --tb=no -q` y actualizar la métrica "Tests pasando" con el número real. A fecha de hoy debería ser 351 passed, 2 skipped.

5. **Añadir test de consistencia scope**: Crear un test en `tests/integration/` que para cada ticker en VALIDATED_TICKERS verifique que `period_scope` en case.json es coherente con los periodos presentes en expected.json. Esto evita futuras regresiones de documentación.

### Qué NO hacer
- No cambiar la lógica del evaluador. El evaluador ya funciona correctamente evaluando todo lo que hay en expected.json.
- No cambiar expected.json de ningún ticker. Solo se corrigen los metadatos (case.json, docs).

### Criterio de aceptación
- Todos los case.json son coherentes con sus expected.json en cuanto a period_scope.
- El número de campos canónicos está correctamente documentado en todos los ficheros.
- PROJECT_STATE.md refleja el test count real.
- Existe un test automatizado que previene incoherencias scope↔expected.
- Regresión verde: todos los tests existentes siguen pasando.

### Referencia
- `cases/NVDA/case.json` — falta period_scope
- `cases/TZOO/case.json` — referencia correcta (ya tiene period_scope: "FULL")
- `config/field_aliases.json` — 25 claves reales
- `tests/integration/test_regression.py` — VALIDATED_TICKERS
- `elsian/models/case.py` línea 22 — default "ANNUAL_ONLY"

---

## WP-2 — SEC Hardening

### Contexto
Codex implementó retry con backoff en sec_edgar.py (BL-008), pero quedan correcciones residuales: el cache de sec_edgar cuenta ficheros físicos en vez de filings lógicos (el fix de BL-008 solo se aplicó a asx.py), y CaseConfig no tiene campo `cik` aunque case.json de NVDA ya lo incluye. Además, se eliminó el Pass 2 de exhibit_99 (HTML index parsing) y el CIK preloaded — ambos cambios sin documentar que deben validarse.

### Qué hacer

1. **Cache lógico en sec_edgar.py**: Aplicar el mismo patrón de conteo por stems que se implementó en asx.py (BL-008). En la función de cache de `elsian/acquire/sec_edgar.py`, contar filings lógicos (stems únicos sin extensión) en vez de ficheros físicos. Un filing con `SRC_001_annual_FY2025.pdf` + `SRC_001_annual_FY2025.txt` es 1 filing, no 2.
   - Referencia: `elsian/acquire/asx.py` líneas 388-401 (patrón ya implementado).

2. **Añadir campo `cik` a CaseConfig**: En `elsian/models/case.py`, añadir `cik: str | None = None` al dataclass CaseConfig. Actualizar `from_json()` para leer `data.get("cik")`. Esto formaliza lo que NVDA ya tiene en su case.json.

3. **SecEdgarFetcher usa CaseConfig.cik**: Si `case.cik` está presente, usarlo directamente para las llamadas a EDGAR sin hacer resolución por API. Si es None, resolver vía API como ahora. Esto es una optimización que reduce 1 request HTTP por acquire y evita fallos por throttling de EDGAR.

4. **Validar eliminación de Pass 2 exhibit_99**: Codex eliminó `_find_exhibit_99` Pass 2 (parsing de HTML index). Ejecutar acquire para TZOO y verificar que todos los earnings releases (exhibit_99) se siguen encontrando solo con Pass 1 (index.json). Si algún filing se pierde, restaurar Pass 2.

5. **Documentar cambios de Codex en CHANGELOG.md**: Añadir entrada documentando los 3 cambios no planificados que hizo Codex en sec_edgar.py:
   - Retry con backoff (3 intentos, 5s/10s)
   - Eliminación de Pass 2 exhibit_99
   - Eliminación de CIK preloaded

### Qué NO hacer
- No reimplementar el retry logic — ya está hecho y funciona.
- No restaurar Pass 2 exhibit_99 a menos que se demuestre que se pierden filings.
- No tocar asx.py — el cache lógico ya está implementado ahí.

### Criterio de aceptación
- `elsian acquire TZOO` descarga el mismo número de filings que antes (verificar contra el estado actual).
- Cache de sec_edgar cuenta filings lógicos (test: directorio con .pdf + .txt del mismo filing → cuenta 1).
- CaseConfig acepta `cik` opcional. NVDA usa su CIK sin resolución API.
- CHANGELOG.md actualizado con los cambios de Codex.
- Regresión verde.

### Referencia
- `elsian/acquire/sec_edgar.py` — fichero principal a modificar
- `elsian/acquire/asx.py` líneas 388-401 — patrón de cache lógico
- `elsian/models/case.py` — añadir campo cik
- `cases/NVDA/case.json` — ya tiene `"cik": "1045810"`
- `tests/unit/test_asx.py` test `test_cache_counts_logical_filings` — patrón de test

---

## WP-3 — Parser iXBRL + Comando Curate

### Contexto
Este es el corazón de DEC-010. El cuello de botella para escalar ELSIAN es la curación manual de expected.json: hoy requiere que un LLM lea el filing HTML completo, identifique tablas financieras, y extraiga valores — un proceso lento, caro y propenso a errores. Los filings SEC (y ESEF europeos) contienen datos iXBRL incrustados: cada número financiero está etiquetado con su concepto GAAP/IFRS, periodo, unidad y escala. Un parser que extraiga estos tags genera un expected_draft.json en segundos, no horas.

**IMPORTANTE:** Este WP construye el parser iXBRL y el comando curate como **herramienta de desarrollo/QA**. NO se integra en el pipeline de producción (eso es WP-6). El pipeline de extracción HTML/PDF sigue siendo el motor principal y debe funcionar sin iXBRL.

### Qué hacer

1. **Crear `elsian/extract/ixbrl.py`** — Parser iXBRL determinístico:
   - Parsear ficheros .htm con BeautifulSoup (ya es dependencia).
   - Localizar todos los tags `ix:nonFraction` (numéricos) e `ix:nonNumeric` (texto).
   - Para cada tag extraer: concepto (ej: `us-gaap:Revenue`), valor, periodo (contextRef → fecha), unidad, escala (atributo `decimals` o `scale`), signo (`sign` attribute).
   - Mapear conceptos GAAP/IFRS a los 23 campos canónicos de `config/field_aliases.json` (25 claves totales incluyendo _version y _description). Crear tabla de mapeo `config/ixbrl_concept_map.json` (ej: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` → `revenue`). Alimentar con los conceptos que aparecen en TZOO y NVDA.
   - Normalizar escala y signos según DEC-004 (as-presented).
   - Output: lista de diccionarios `{field, period, value, concept, context_ref, unit, source_filing}`.
   - El parser debe ser **puro** (sin side effects, sin I/O excepto lectura del fichero).

2. **Tests del parser con fixtures reales**:
   - Copiar fragmentos reales de iXBRL de TZOO y NVDA 10-K como fixtures en `tests/fixtures/ixbrl/`.
   - Tests unitarios: verificar que el parser extrae correctamente revenue, net_income, total_assets, etc.
   - Test de cobertura: comparar output del parser con expected.json existente — debería cubrir ≥90% de los campos.

3. **Crear comando `elsian curate`** en `elsian/cli.py`:
   - Nuevo subcomando: `python3 -m elsian.cli curate {TICKER}`.
   - Para tickers con ficheros .htm en `filings/`: ejecutar parser iXBRL sobre cada filing, agregar resultados por periodo, generar `expected_draft.json` en el directorio del caso.
   - El draft incluye metadata: `{"_source": "ixbrl", "_concept": "us-gaap:Revenue", "_filing": "SRC_001_annual_FY2025.htm"}` por cada valor.
   - Sanity checks automáticos sobre el draft:
     - revenue > 0
     - total_assets ≈ total_liabilities + total_equity (±1%)
     - no hay valores duplicados para el mismo campo+periodo
   - Para tickers sin .htm (ASX, PDF-only): generar esqueleto vacío con periodos detectados desde los nombres de fichero. Mensaje informativo: "No iXBRL files found. Generated skeleton with detected periods."

4. **Tests del comando curate**:
   - Test: `elsian curate TZOO` genera draft con ≥90% de los campos del expected.json actual.
   - Test: `elsian curate NVDA` genera draft con periodos anuales Y trimestrales.
   - Test: `elsian curate KAR` genera esqueleto vacío (KAR es ASX, sin iXBRL).
   - Test: sanity checks detectan un draft incoherente (total_assets ≠ liabilities + equity).

### Qué NO hacer
- **NO integrar en ExtractPhase.** El parser iXBRL en este WP es herramienta de curación, no de producción. No toca el pipeline `extract` → `evaluate`.
- **NO crear IxbrlExtractor(Extractor).** Eso es WP-6 (futuro).
- **NO usar LLM en el parser.** Todo determinístico. La depuración LLM del draft es un paso humano posterior, no automatizado en este WP.
- **NO intentar mapear TODOS los conceptos GAAP/IFRS. ** Empezar con los que aparecen en TZOO y NVDA. El concept_map crecerá orgánicamente con cada ticker nuevo.

### Criterio de aceptación
- `elsian/extract/ixbrl.py` existe con tests unitarios que pasan.
- `config/ixbrl_concept_map.json` existe con mapeos para ≥20 conceptos GAAP comunes.
- `elsian curate TZOO` genera un expected_draft.json que cubre ≥90% de los campos del expected.json actual de TZOO.
- `elsian curate NVDA` genera draft con periodos anuales Y trimestrales.
- `elsian curate KAR` genera esqueleto sin errores.
- Sanity checks detectan inconsistencias básicas.
- **El pipeline de extracción (extract/evaluate) no ha sido tocado.** Regresión verde.

### Referencia
- `config/field_aliases.json` — 23 campos canónicos de datos
- `cases/TZOO/filings/` — filings .htm con iXBRL incrustado
- `cases/NVDA/filings/` — filings .htm con iXBRL incrustado
- `elsian/cli.py` — añadir subcomando curate
- `elsian/extract/` — directorio destino del parser
- DEC-010 en `docs/project/DECISIONS.md` — estrategia iXBRL completa
- DEC-004 — convención de signos (as-presented)
- Si existe en 3.0: `deterministic/src/extract/ixbrl_extractor.py` o similar — **portar antes que reimplementar** (DEC-009)

---

## WP-4 — Integrar Preflight en Pipeline de Extracción

### Contexto
`elsian/analyze/preflight.py` está portado del 3.0 (BL-009 DONE) y funciona standalone, pero sus resultados (moneda detectada, unidades por sección, estándar contable) no alimentan el pipeline de extracción. Esto significa que ScaleCascade no sabe qué unidades usa cada sección del filing, lo que puede causar errores de escala especialmente en tickers con mixed units (millones en una tabla, miles en otra).

Con WP-3 completado, el parser iXBRL proporcionará metadata adicional (escala por concepto) que puede servir como cross-validation del preflight.

### Qué hacer

1. **Ejecutar preflight automáticamente en ExtractPhase**: Antes de la extracción de cada filing, ejecutar `preflight.analyze()` y almacenar los resultados en el contexto de extracción.

2. **Alimentar ScaleCascade con `units_by_section`**: El preflight detecta unidades por sección (ej: "Income Statement: millions", "Balance Sheet: thousands"). Pasar esta información a ScaleCascade para que use la escala correcta por sección en vez de una única escala global.

3. **Añadir metadata de preflight al extraction_result.json**: Cada FieldResult debe incluir los metadatos de preflight del filing fuente: `{currency, accounting_standard, language, units_hint}`.

4. **Tests de integración**: Verificar que TEP (IFRS, EUR, FR) y KAR (IFRS, USD) se benefician del preflight — especialmente la detección de unidades por sección.

### Qué NO hacer
- No reimplementar preflight — ya funciona (BL-009).
- No hacer que el preflight sea bloqueante — si falla, el pipeline debe continuar con defaults (como ahora).

### Criterio de aceptación
- Cada filing pasa por preflight antes de la extracción.
- ScaleCascade usa `units_by_section` cuando está disponible.
- extraction_result.json incluye metadata de preflight.
- TEP y KAR siguen al 100%.
- Regresión verde.

### Referencia
- `elsian/analyze/preflight.py` — módulo a integrar
- `elsian/extract/phase.py` — punto de integración
- `elsian/normalize/scale.py` — ScaleCascade
- BL-014 en `docs/project/BACKLOG.md`

---

## WP-5 — CI y Paralelización

### Contexto
Con WP-1 a WP-4 completados, el proyecto tendrá significativamente más tests y tickers. La suite de regresión actual ejecuta tickers secuencialmente. Además, no hay CI automatizado — todo depende de que el agente ejecute `pytest` manualmente.

### Qué hacer

1. **Paralelizar tests de regresión**: Los 9+ tickers en test_regression.py son independientes entre sí. Usar `pytest-xdist` o paralelización nativa para ejecutarlos en paralelo.

2. **Crear GitHub Actions workflow** (si no existe): CI básico que ejecute `pytest` en cada push/PR. Debe fallar si cualquier test falla.

3. **Añadir smoke test rápido**: Un subset de tests (~30 segundos) que se pueda ejecutar como pre-commit hook o quick validation. Excluir tests de integración lentos (acquire, que hace HTTP).

4. **Verificar que pyproject.toml requiere Python correcto**: Actualmente dice Python 3.11 pero el entorno puede estar ejecutando 3.10. Verificar y alinear.

### Qué NO hacer
- No complicar el CI con Docker o entornos complejos. Un workflow simple que ejecute pytest es suficiente.
- No hacer tests de acquire en CI (requieren acceso a SEC/ASX y son lentos).

### Criterio de aceptación
- Tests de regresión ejecutan en paralelo (≥2x speedup).
- CI workflow existe y funciona.
- Python version requirement es consistente entre pyproject.toml y el entorno de ejecución.
- Regresión verde.

### Referencia
- `tests/integration/test_regression.py` — tests a paralelizar
- `pyproject.toml` — version de Python
- `.github/workflows/` — directorio para CI

---

## WP-6 — IxbrlExtractor en Pipeline de Producción (FUTURO)

### Contexto
Una vez que el parser iXBRL (WP-3) está maduro y probado en curación, el paso natural es integrarlo como extractor de producción dentro del pipeline Layer 1. Esto convierte iXBRL en una fuente más (la más fiable donde exista) que complementa HTML/PDF. Cross-validation iXBRL vs HTML aumenta la confianza.

**Este WP no se ejecuta inmediatamente.** Se ejecuta cuando WP-3 haya curado ≥5 tickers y el parser esté estabilizado.

### Qué hacer

1. **Crear `IxbrlExtractor(Extractor)`** en `elsian/extract/ixbrl_extractor.py`:
   - Hereda de Extractor ABC.
   - Usa el parser de `elsian/extract/ixbrl.py` (WP-3) como motor interno.
   - Output: lista de FieldResult con Provenance completa (concepto iXBRL, contextRef, filing fuente).
   - Se registra en ExtractPhase junto a los extractores HTML/PDF existentes.

2. **Implementar cross-validation**: Cuando un campo se extrae tanto por iXBRL como por HTML, comparar valores. Si coinciden → confianza alta. Si difieren → flag para revisión (no bloquear).

3. **Prioridad de extracción**: iXBRL > HTML tables > PDF tables > narrative. El pipeline intenta la fuente más fiable primero.

4. **Tests**: Verificar que TZOO con IxbrlExtractor produce los mismos resultados que el extractor HTML actual. No debe haber regresiones.

### Qué NO hacer
- No hacer de iXBRL la única fuente — siempre debe haber fallback a HTML/PDF.
- No ejecutar este WP hasta que WP-3 haya madurado.

### Criterio de aceptación
- IxbrlExtractor produce FieldResults con provenance completa.
- TZOO 100% con IxbrlExtractor como fuente primaria.
- Cross-validation funciona y detecta discrepancias.
- HTML/PDF extractors siguen funcionando como fallback.
- Regresión verde.

### Referencia
- `elsian/extract/ixbrl.py` — parser (WP-3)
- `elsian/extract/base.py` — Extractor ABC
- `elsian/extract/phase.py` — registro de extractores
- DEC-010 — "producción (futuro)" = este WP

---

## Resumen de impacto en BACKLOG

| WP | Tareas BACKLOG que cierra | Tareas nuevas que crea |
|----|--------------------------|----------------------|
| WP-1 | — (governance, no estaba en backlog) | Test de consistencia scope |
| WP-2 | BL-008 residual (cache sec_edgar) | — |
| WP-3 | BL-004, BL-025 | BL-026 se desbloquea |
| WP-4 | BL-014 | — |
| WP-5 | — (CI, no estaba en backlog) | — |
| WP-6 | — (futuro) | — |

## Criterio global de éxito

Al completar WP-1 a WP-5:
- Documentación coherente con la realidad del código.
- `elsian curate {TICKER}` genera expected_draft.json en segundos para tickers SEC.
- Preflight alimenta la extracción automáticamente.
- CI previene regresiones.
- El camino queda abierto para WP-6 (iXBRL producción) y BL-026 (promover tickers a FULL).
