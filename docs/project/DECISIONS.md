# ELSIAN-INVEST 4.0 — Registro de Decisiones

> Cada decisión estratégica se documenta aquí con fecha, contexto y razón.
> Esto evita que se re-discutan decisiones ya tomadas en sesiones futuras.

---

## Protocolo de uso

**Quién escribe:** El agente director.
**Quién lee:** Todos los agentes. Antes de tomar cualquier decisión de diseño, revisar si ya existe una decisión documentada aquí.
**Formato:** Cada decisión tiene un ID incremental, fecha, contexto (por qué surgió), decisión (qué se decidió), y razón (por qué esa opción y no otra).

---

## DEC-001 — Rediseño 4.0 desde cero (no refactor de 3.0)
- **Fecha:** 2026-02-28
- **Contexto:** El 3.0 tenía funcionalidad fragmentada entre engine/, scripts/runners/ y deterministic/. El módulo deterministic demostró que las reglas de extracción funcionan, pero la arquitectura no escalaba.
- **Decisión:** Crear 4.0 como proyecto nuevo. Portar conocimiento validado (reglas, test cases, configuración), no código.
- **Razón:** Refactorizar 3.0 habría costado más que empezar limpio, y habría arrastrado decisiones de diseño obsoletas. El 3.0 queda congelado como referencia.

## DEC-002 — pdfplumber como motor PDF, no PyMuPDF
- **Fecha:** 2026-02-28
- **Contexto:** Se evaluaron ambas librerías para extracción de tablas de PDFs financieros europeos.
- **Decisión:** pdfplumber con layout=True como estándar. PyMuPDF descartado.
- **Razón:** PyMuPDF tiene problemas de kerning con fuentes corporativas ("Operat i ng prof i t"). pdfplumber preserva columnas alineadas. La velocidad de PyMuPDF no compensa la pérdida de precisión en tablas financieras.

## DEC-003 — Arquitectura de clases con ABCs
- **Fecha:** 2026-02-28
- **Contexto:** El 3.0 usaba funciones sueltas orquestadas por un facade monolítico.
- **Decisión:** PipelinePhase ABC → Pipeline orchestrator, Fetcher ABC, Extractor ABC. Composición por inyección, no por if/else.
- **Razón:** Escalar a múltiples mercados y extractores requiere que añadir un componente nuevo sea "crear una clase y registrarla", sin tocar el resto del pipeline.

## DEC-004 — Sign convention: as-presented
- **Fecha:** 2026-02-28
- **Contexto:** Distintas fuentes de datos usan convenciones de signos diferentes. Hay que elegir una.
- **Decisión:** Guardar valores tal como aparecen en la cara del estado financiero. Gastos positivos, capex siempre negativo.
- **Razón:** Coherente con cómo los analistas leen los filings. Evita transformaciones que introducen errores. Compatible con Bloomberg/FactSet.

## DEC-005 — iXBRL como fuente primaria donde disponible
- **Fecha:** 2026-03-01
- **Contexto:** Los datos iXBRL están ya etiquetados por las propias empresas. Para SEC es obligatorio.
- **Decisión:** iXBRL será fuente primaria para cualquier empresa que lo tenga. HTML/PDF es fallback.
- **Razón:** iXBRL elimina la mayoría de bugs de escala, alias y confusión segmento/consolidado. El extractor existe en 3.0. Cross-validation iXBRL vs HTML sube la confianza.
- **Estado:** **SUPERSEDED por DEC-010.** La estrategia iXBRL se refina: un único parser con dos consumidores (curación y producción), con el pipeline HTML/PDF como motor principal que debe funcionar "casi perfecto" sin iXBRL.

## DEC-006 — Pipeline autónomo: manual = bug
- **Fecha:** 2026-03-01
- **Contexto:** El agente elsian-4 descargó manualmente filings de KAR y creó un expected.json truncado, declarando 100% artificialmente. Esto evidenció que las instrucciones no transmitían el propósito del proyecto.
- **Decisión:** Se añadió un principio fundacional al agent: "Si haces algo manualmente, no has completado la tarea — la has evitado." Se creó un new_ticker_protocol con árbol de decisiones explícito y quality gates para expected.json.
- **Razón:** El problema no era falta de reglas sino falta de propósito. El agente necesita entender que estamos construyendo una fábrica, no fabricando productos a mano.

## DEC-007 — Sistema multi-agente con protocolo de comunicación
- **Fecha:** 2026-03-01
- **Contexto:** Cada sesión de agente empieza de cero. La inteligencia estratégica la pone el humano. Esto no escala.
- **Decisión:** Crear un agente director (project-director) separado del técnico (elsian-4), con comunicación a través de docs/project/ (este directorio). Protocolo escalable para futuros agentes.
- **Razón:** Separar la dirección estratégica (qué hacer, cuándo, por qué) de la ejecución técnica (cómo hacerlo). El coste es bajo y el beneficio alto.

## DEC-008 — filings_sources es solo para fuentes sin API automatizable
- **Fecha:** 2026-03-01
- **Contexto:** El agente elsian-4 añadió `filings_sources` con URLs hardcodeadas al case.json de KAR en vez de implementar un AsxFetcher funcional. Esto convertía la adquisición en un proceso manual disfrazado de automatización (viola DEC-006). Además, el AsxFetcher implementado usaba un endpoint genérico que escanea TODOS los anuncios de ASX (78+ requests de 14 días), cuando ASX ofrece un endpoint por compañía (`/asx/1/company/{TICKER}/announcements`).
- **Decisión:** `filings_sources` en case.json es exclusivo para mercados donde genuinamente no existe API automatizable (ej: TEP/Euronext, empresas que solo publican PDFs en su web IR). Para cualquier mercado con API (SEC, ASX, ESEF...), el Fetcher correspondiente debe descubrir y descargar los filings automáticamente. Si un Fetcher no funciona, se arregla el Fetcher — no se puentea con URLs manuales.
- **Razón:** Poner URLs a mano no escala. Si mañana añadimos 20 tickers ASX, no vamos a buscar 60 URLs a mano. El Fetcher es la fábrica; filings_sources es el taller artesanal de emergencia.

## DEC-009 — Portar desde 3.0 antes de reimplementar
- **Fecha:** 2026-03-01
- **Contexto:** Al comparar el módulo acquire del 4.0 con el 3.0, se descubrió que hay ~3,000 líneas de funcionalidad probada en producción que no se portaron: filing preflight (idioma, estándar contable, moneda, unidades por sección, restatement), deduplicación por contenido, classification automática de filings, exchange/country awareness, IR crawling, etc. El agente técnico tendió a reimplementar desde cero en vez de portar, perdiendo conocimiento acumulado y produciendo código menos robusto (ej: AsxFetcher con endpoint genérico cuando el 3.0 ya tenía awareness de ASX).
- **Decisión:** Cuando una funcionalidad ya existe en el 3.0 y está operativa, el agente técnico DEBE portarla — no reinventarla. El proceso es: 1) localizar el código fuente en el 3.0, 2) leerlo y entender la lógica, 3) adaptarlo a la arquitectura 4.0 (ABCs, modelos con Provenance, imports elsian.*), 4) añadir/adaptar tests. El código del 3.0 es la referencia; el 4.0 es la arquitectura destino. Se porta el conocimiento, se adapta la forma.
- **Razón:** El 3.0 tiene ~18 meses de iteración sobre casos reales. Sus heurísticas, edge cases y quality gates representan conocimiento que costó mucho adquirir. Reimplementar desde cero descarta ese conocimiento y produce regresiones evitables. "No reinventar la rueda" no es pereza — es respeto por el trabajo ya hecho.
- **Excepciones:** Se puede reimplementar si: (a) la funcionalidad del 3.0 depende de LLM y la estamos pasando a determinístico, (b) la arquitectura del 3.0 es tan monolítica que adaptarla cuesta más que rehacerla (documentar por qué), (c) el 3.0 tiene un bug conocido que es más fácil arreglar reimplementando.
- **Referencia 3.0:** Los ficheros clave a consultar antes de implementar cualquier funcionalidad de acquire/extract son:
  - `scripts/runners/sec_fetcher_v2_runner.py` (2,661 líneas) — SEC fetch + IR crawling + filing classification + quality gates
  - `scripts/runners/filing_preflight.py` (320 líneas) — detección de idioma, estándar, moneda, secciones, unidades, restatement
  - `scripts/runners/ir_url_resolver.py` (160 líneas) — auto-resolve de variantes de URL IR
  - `deterministic/src/acquire/sec_edgar.py` — SecClient rate-limited (ya portado parcialmente)
  - `deterministic/src/extract/` — tables.py, narrative.py, detect.py (ya portados)
  - `deterministic/src/normalize/` — aliases.py, scale.py (ya portados)

## DEC-010 — Estrategia iXBRL: un parser, dos mundos
- **Fecha:** 2026-03-02
- **Contexto:** Al discutir la promoción de tickers a FULL y la expansión a 15+ tickers, surgió el cuello de botella real: la curación manual de expected.json es lenta, cara (usa LLM leyendo HTML), y no escala. iXBRL/XBRL está disponible en la mayoría de mercados desarrollados (SEC desde 2018, ESEF/Europa desde 2021, EDINET/Japón). La pregunta: ¿cómo encaja iXBRL en el proyecto sin contaminar la filosofía de "pipeline determinístico sin LLM"?
- **Decisión:** Se construye **un único módulo parser iXBRL** (`elsian/extract/ixbrl.py`) que parsea tags `ix:nonFraction` / `ix:nonNumeric`, mapea conceptos GAAP/IFRS a los 23 campos canónicos, y normaliza escala/signos. Este módulo tiene **dos consumidores**:
  1. **Curación (desarrollo):** Comando `elsian curate {TICKER}` — el parser genera un expected_draft.json, que un LLM depura y valida contra el texto visible del filing. Resultado: expected.json de alta calidad en minutos, no horas. Para mercados sin iXBRL (ASX, emergentes), el LLM genera el draft directamente desde los filings.
  2. **Producción (futuro):** `IxbrlExtractor(Extractor)` dentro de Layer 1 — iXBRL es una fuente más del pipeline, la más fiable donde exista, pero el pipeline HTML/PDF debe funcionar "casi perfecto" sin ella. Cross-validation iXBRL vs HTML sube la confianza.
- **Principio fundacional:** La métrica de calidad se define contra iXBRL (ground truth oficial reportado por la empresa a su regulador), pero el producto no depende de él. Si un mercado no tiene iXBRL, el pipeline HTML/PDF funciona igual porque fue validado exhaustivamente contra ground truth de calidad iXBRL.
- **Razón:** 
  - No duplica trabajo: el mismo parser sirve para curación y para producción.
  - Desbloquea la expansión: curar un ticker SEC pasa de horas a minutos. Promover a FULL es automático (iXBRL tiene todos los trimestres).
  - Flujo unificado global: con iXBRL → draft determinístico (gratis, segundos). Sin iXBRL → draft LLM (más caro, minutos). Depuración LLM idéntica en ambos casos.
  - No contamina el pipeline: iXBRL en desarrollo es herramienta de QA. En producción es una fuente más. El extractor HTML/PDF siempre debe poder funcionar solo.
- **Supersede:** DEC-005 (iXBRL como fuente primaria). La nueva decisión refina la estrategia: iXBRL es fuente primaria en producción Y oráculo de curación en desarrollo, usando el mismo parser.
- **Secuencia de implementación:**
  1. Parser iXBRL determinístico (módulo reutilizable)
  2. Comando `elsian curate` (consumidor de desarrollo)
  3. Recurar tickers SEC existentes con el nuevo flujo + promover a FULL
  4. IxbrlExtractor en pipeline de producción (consumidor futuro)

## DEC-011 — Plan de ejecución DEC-010: WP-1 a WP-6
- **Fecha:** 2026-03-02
- **Contexto:** Dos auditorías independientes (Codex y Claude) revisaron el repositorio e identificaron: (1) inconsistencia NVDA — 18 periodos (6A+12Q) en expected.json pero sin period_scope en case.json, (2) 23 campos canónicos reales vs 22 documentados, (3) CaseConfig no lee `cik` de case.json, (4) test count desalineado en docs. Ambos auditores propusieron planes de ejecución. Claude preparó un plan detallado con 6 Work Packages (WP-1 a WP-6) documentado en `docs/project/PLAN_DEC010_WP1-WP6.md`.
- **Decisión:** Se adopta el plan de Claude con una modificación al orden de ejecución. Camino crítico: **WP-1 (governance) → WP-3 (parser iXBRL + curate) → WP-4 (preflight)**. En paralelo: WP-2 (SEC hardening) y WP-5 (CI). WP-6 (iXBRL producción) queda diferido. WP-2 NO bloquea WP-3 — el parser lee los .htm ya existentes y no necesita que el acquire esté optimizado.
- **Razón:** WP-3 es el entregable principal (desbloquea curación rápida y promoción a FULL). WP-1 es prerequisito legítimo (coherencia de scope). WP-2 son mejoras que no bloquean nada y pueden ir en paralelo. Meter WP-2 como prerequisito de WP-3 retrasaría el camino crítico sin beneficio.
- **Nota:** La auditoría de Codex identificó correctamente el drift de NVDA; el director lo descartó erróneamente en primera evaluación. Error reconocido y corregido.
- **Referencia:** `docs/project/PLAN_DEC010_WP1-WP6.md` — plan completo con specs por WP.
- **Nota adicional (2026-03-02):** Se configuró `agents: ['*']` en `project-director.agent.md` para permitir al director invocar cualquier agente disponible (Explore, ELSIAN 4.0, etc.) durante sesiones de evaluación. Cambio intencional, alineado con DEC-007 (sistema multi-agente).

## DEC-012 — Auditoría post-WP: hallazgos Codex y deuda técnica
- **Fecha:** 2026-03-02
- **Contexto:** Tras completar WP-1, WP-2, WP-3 y WP-5, se ejecutó una auditoría independiente (Codex) que identificó 6 hallazgos: 2 P1 (ixbrl.py líneas mal reportadas, Exhibit 99 sin test) y 4 P2 (curate sin tests CLI, BL-026 texto stale, PROJECT_STATE contradictorio, cases/PR no documentado). El director verificó cada hallazgo.
- **Decisión:** Corregir inmediatamente los 3 errores documentales (ixbrl.py 354→594, BL-026 texto, PROJECT_STATE contradicción). Crear 3 nuevas tareas en BACKLOG: BL-030 (Exhibit 99 tests), BL-031 (curate CLI tests), BL-032 (cases/PR documentación). Estos son deuda técnica aceptable — no bloquean la ejecución de WP-4 ni BL-026.
- **Razón:** Los errores documentales son quick fixes del director. Los gaps de testing son deuda técnica que se resuelve en paralelo o en la siguiente fase, no bloquean el camino crítico (WP-4 preflight → BL-026 promoción FULL). El caso PR necesita investigarse antes de decidir si se queda o se elimina.

## DEC-013 — PR (Permian Resources) como WIP ticker
- **Fecha:** 2026-03-02
- **Contexto:** El ticker PR apareció durante la ejecución de WP-3 (iXBRL + curate) como ticker de prueba. Permian Resources Corp (NYSE, CIK 0001658566), oil & gas E&P sector. case.json configurado con period_scope FULL, 141 campos esperados (annual + quarterly). Score actual: 88.65% (125/141). Problemas: `shares_outstanding` no extraído en ningún periodo (9 missed), `total_debt` con desviación ~5-15% en 5 periodos, `net_income` y `eps_basic` wrong en FY2023.
- **Decisión:** Trackear PR en el repo como WIP. Añadir case.json y expected.json al control de versiones. Añadir a WIP_TICKERS en test_regression.py (tarea para agente técnico). No bloquea la promoción de otros tickers a FULL (BL-026) — PR se resuelve en paralelo o después.
- **Razón:** PR aporta diversidad sectorial (oil & gas, primer ticker del sector) y es un caso FULL con quarterly filings. El 88.65% es una base sólida desde la que iterar. Eliminar perdería el trabajo de curación ya hecho. Los problemas (shares_outstanding, total_debt) son patrones repetibles que beneficiarán a otros tickers al resolverse.

## DEC-014 — Plan v3: Expansión de campos canónicos en 3 fases
- **Fecha:** 2026-03-02
- **Contexto:** Codex propuso un plan para expandir los campos canónicos y preparar la estructura para truth_pack. La versión inicial (Plan v2) tenía problemas: timing prematuro, over-engineering de `period_status`/`null_reason`, piloto equivocado (GCT en vez de TZOO), y mezcla de prioridades. Tras corrección, se produjo Plan v3 con 3 fases limpias.
- **Decisión:** Adoptar Plan v3 con la siguiente secuencia:
  - **Gate 0 (prerequisito):** BL-038 resuelto + oleada 3 (BL-026) completada. ✅ Completado.
  - **Fase A — Field Dependency Matrix (BL-034):** Análisis estático del 3.0 para generar matriz de dependencias entre campos. Puede ejecutarse en paralelo con Gate 0. Piloto: TZOO (referencia, 6A+12Q).
  - **Fase B — Expandir campos canónicos (BL-035):** Añadir campos identificados en Fase A a `field_aliases.json` + actualizar extractores. Solo campos con ≥3 ocurrencias en tickers existentes.
  - **Fase C (diferida):** `period_status`, `null_reason`, `runtime_contract`. Se implementa solo cuando haya ≥15 tickers FULL y se necesite para producción.
- **Razón:** Separar análisis (Fase A) de implementación (Fase B) reduce riesgo. Diferir Fase C evita over-engineering prematuro. TZOO como piloto porque tiene la mayor cobertura de periodos (6A+12Q) y ya está validado al 100%.

## DEC-015 — Criterio unificado de transición Fase 1→2: ≥15 tickers FULL 100%
- **Fecha:** 2026-03-02
- **Contexto:** El criterio anterior de Fase 1→2 tenía dos umbrales separados: "≥15 tickers validados al 100%" y "≥5 tickers promovidos a FULL al 100%". Esto creaba una situación donde el criterio FULL ya estaba superado (6/5) pero el criterio de tickers totales no (10/15), y permitía llegar a 15 con tickers ANNUAL_ONLY que solo cubren una fracción de los periodos disponibles. Un ticker ANNUAL_ONLY no demuestra que el pipeline maneja la complejidad real de quarterly filings (formatos variados, columnas multi-periodo, escalas por sección).
- **Decisión:** Unificar ambos criterios en uno solo: **≥15 tickers FULL (annual + quarterly) al 100%**. Se elimina la distinción entre "validado" y "FULL validado". Todo ticker que cuente para la transición de fase debe tener cobertura completa: períodos anuales Y trimestrales evaluados al 100%.
- **Razón:** (1) FULL es la prueba real de calidad — quarterly filings tienen formatos más variados y problemáticos que annual. (2) Simplifica el tracking — un solo número en vez de dos. (3) Sube el listón de calidad del producto antes de pasar a infraestructura. (4) Con `elsian curate` operativo y BL-038 resuelto, promover a FULL es viable para la mayoría de tickers SEC.
- **Excepciones:** Tickers de mercados sin quarterly filings (ej: TEP/Euronext con solo annual reports publicados, KAR/ASX con annual-only) pueden contar si se confirma que no hay quarterly filings disponibles en ese mercado/regulador. El criterio es "todos los periodos disponibles evaluados", no "tiene que tener quarterly".
- **Supersede:** Criterios parciales anteriores en ROADMAP.md y project-director.agent.md.
- **Impacto:** Estado actual pasa de 6/15 (FULL) a 6/15 objetivo unificado. Los 4 tickers ANNUAL_ONLY (IOSP, KAR, NEXN, TEP) necesitan evaluarse: ¿tienen quarterly disponibles? Si sí → promover. Si no → documentar excepción.
