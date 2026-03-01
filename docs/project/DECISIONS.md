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
- **Estado:** Pendiente de implementación (Fase 1.3 del roadmap).

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
