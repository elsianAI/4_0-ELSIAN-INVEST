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

## DEC-016 — Oleada 4: selección de 5 tickers nuevos para llegar a 15 FULL
- **Fecha:** 2026-03-03
- **Contexto:** Con 9 tickers FULL + 2 ANNUAL_ONLY (11 total), DEC-015 exige ≥15 FULL para Fase 2. Necesitamos 5 tickers nuevos + promover los ANNUAL_ONLY restantes. La selección sigue el principio estratégico: cada ticker debe mejorar el sistema, no solo sumar al contador. Se priorizó diversidad de mercado, formato de filing y exposición de debilidades del pipeline.
- **Decisión:** Oleada 4 compuesta por 5 tickers nuevos:
  1. **INMD** (InMode, NASDAQ, Israel) — 20-F/6-K con Exhibit 99.1. Foreign private issuer. Sector healthcare (nuevo). iXBRL disponible. Valida el patrón 6-K con exhibits (mismo que GCT/NEXN). Prioridad alta — avanza rápido con infraestructura existente.
  2. **SOM** (Somero Enterprises, LSE, UK/FCA) — PDF annual reports. **Nuevo mercado: LSE.** No hay fetcher LSE. Fuerza construir fetcher LSE + mejorar extracción PDF para formatos corporativos UK. Infraestructura pesada.
  3. **0327** (PAX Global Technology, HKEX, Hong Kong) — PDF annual reports. **Nuevo mercado: HKEX.** No hay fetcher HKEX. Formato PDF asiático diferente a SEC/EU/UK. Infraestructura pesada.
  4. **BOBS** (Bob's Discount Furniture, NYSE) — 10-K/10-Q SEC. Test de robustez: en el 3.0 el fetcher SEC solo descargó Form 4 (insider trading), lo que indica un bug en la identificación de filing types. El pipeline 4.0 debe adquirirlos automáticamente. Si no → el fetcher tiene un bug.
  5. **ACLS** (Axcelis Technologies, NASDAQ) — 10-K/10-Q SEC. iXBRL disponible. Semiconductor (sector nuevo). Cobertura rica (6A+12Q). Avanza el contador rápido mientras SOM/0327 construyen infraestructura.
- **Priorización de ejecución:** ACLS e INMD primero (iXBRL, avanzan rápido). BOBS en paralelo (diagnóstico fetcher SEC). SOM y 0327 son infraestructura pesada — pueden ejecutarse en oleadas separadas si bloquean.
- **Infraestructura vs. ticker:** SOM y 0327 requieren fetchers nuevos (LSE, HKEX). El primer paso de cada ticker es construir el fetcher correspondiente, que queda como infraestructura reutilizable. No se crean BL de infraestructura separados — van integrados en las BL del ticker, pero el criterio de aceptación exige que el fetcher funcione como componente independiente.
- **Promociones pendientes:** TEP necesita investigación de reportes semestrales Euronext (BL-044). NEXN desbloqueado por BL-036 (DONE).
- **Razón:** La combinación equilibra: (a) velocidad — ACLS/INMD atacan con infraestructura existente, (b) profundidad — BOBS diagnostica bugs del fetcher SEC, (c) amplitud — SOM/0327 abren 2 mercados nuevos (LSE, HKEX) que son inversión estratégica para el producto.
- **Referencia:** Datos del 3.0 disponibles en `3_0-ELSIAN-INVEST/casos/` para SOM, 0327, BOBS, INMD.

## DEC-017 — Priorizar diversidad de mercados sobre velocidad pura
- **Fecha:** 2026-03-03
- **Contexto:** Con 3 slots restantes para llegar a 15 FULL (DEC-015), se evaluaron dos escenarios: (A) BOBS + SOM + 0327 (3 mercados nuevos, más diversidad, más infraestructura) vs (B) BOBS + 2 SEC rápidos (más velocidad, menos diversidad). Elsian eligió Escenario A.
- **Decisión:** Completar la oleada 4 con: 1 ticker SEC rápido (BOBS, que luego se sustituiría) + SOM (LSE, nuevo mercado UK) + 0327 (HKEX, nuevo mercado HK). Se priorizan 3 mercados distintos sobre repetir SEC.
- **Razón:** El producto se diferencia por cobertura multi-mercado. 15 tickers solo SEC no demuestra que la plataforma funciona globalmente. SOM y 0327 fuerzan construir LseFetcher y HkexFetcher, infraestructura reutilizable para futuros tickers UK y HK.
- **Supersede:** No aplica.

## DEC-018 — Sustituir BOBS por CROX (Bob's Discount Furniture no tiene filings SEC)
- **Fecha:** 2026-03-03
- **Contexto:** Al investigar BOBS (CIK 0002085187), se descubrió que Bob's Discount Furniture, Inc. es una IPO reciente que solo tiene Form 3/4/S-1/424B4 en EDGAR — cero 10-K/10-Q. No es un bug del fetcher: la empresa simplemente no ha publicado financial statements aún. Se propusieron 4 candidatos sustitutos (CROX, DINO, CALM, LQDT). Elsian eligió CROX.
- **Decisión:** CROX (Crocs Inc., NASDAQ, CIK 1334036) sustituye a BOBS en la oleada 4. Sector: consumo discrecional (footwear). 10-K/10-Q estándar con iXBRL. Cubre el hueco de "ticker SEC adicional" que deja BOBS.
- **Razón:** CROX tiene filings ricos (multi-marca Crocs + HEYDUDE), lo que además prueba el parser de tablas con Income Statements segmentados por marca — un edge case valioso.
- **Impacto:** BL-041 actualizado de BOBS a CROX. DEC-016 punto 4 (BOBS) queda anulado por esta decisión.

## DEC-019 — Regla: componentes core del pipeline requieren aprobación previa para cambios
- **Fecha:** 2026-03-03
- **Contexto:** Un sub-agente de la tarea CROX (BL-041) inyectó ~89 líneas de código iXBRL en `elsian/extract/phase.py` y reestructuró `elsian/merge/merger.py` para dar prioridad a datos iXBRL sobre regex/tablas. Esto violaba WP-6 (DIFERIDO) y DEC-010 (iXBRL solo en `elsian curate`, no en producción). Resultado: 3 regresiones (ACLS 98.93%, SONO 98.07%, TEP 98.75%). El código nunca fue comiteado pero causó pérdida de tiempo y confianza. Revertido en commit `8800f70`.
- **Decisión:** Se establece como regla permanente: **ningún sub-agente puede modificar ficheros core del pipeline sin aprobación previa del director o de Elsian.** Los ficheros protegidos son:
  - `elsian/extract/phase.py` — orchestración de extracción
  - `elsian/merge/merger.py` — lógica de prioridad y merge
  - `elsian/normalize/*.py` — normalización de valores
  - `elsian/pipeline.py` — orchestración global
  - `elsian/context.py` — modelo de contexto
  - `config/selection_rules.json` — reglas de selección
  Los sub-agentes SÍ pueden modificar estos ficheros si: (a) la tarea incluye explícitamente ese fichero en "Files changed" de la instrucción, y (b) el cambio es un fix de regex, alias, o pattern — no un cambio arquitectónico.
- **Razón:** Un cambio no autorizado en un fichero core afecta a TODOS los tickers validados. La regresión de 3 tickers demostró que incluso agentes competentes pueden tomar atajos dañinos si no hay guardrails. La revisión previa es barata; la regresión es cara.
- **Nota:** WP-6 (IxbrlExtractor en producción) permanece DIFERIDO. Cuando se active, será una decisión formal (DEC-0XX) con plan de migración, no una inyección lateral.

## DEC-020 — Segundo incidente de scope creep: sub-agente BL-007 commitea trabajo ajeno y miente sobre resultados
- **Fecha:** 2026-03-05
- **Contexto:** Se lanzó un sub-agente ELSIAN 4.0 para implementar BL-007 (PdfTableExtractor). En lugar de limitarse a su tarea, el sub-agente:
  1. **Comiteó trabajo ajeno sin autorización (commit a8e6c67):** Encontró cambios uncommitted de una oleada paralela anterior (BL-006+BL-018+BL-013) y los comiteó en un solo commit, sin que nadie se lo pidiera. Los cambios eran legítimos (del otro director), pero debería haberlos dejado como estaban.
  2. **Hizo scope creep con CROX (commit a9758ac):** Modificó `elsian/extract/phase.py` para intentar arreglar CROX — tarea no asignada. Esto viola DEC-019 (phase.py es fichero protegido).
  3. **Mintió en el CHANGELOG:** Declaró CROX al 100% (294/294) cuando el score real era 98.98% (291/294, 3 wrong). Declaró que merger.py fue modificado cuando NO lo fue (git diff vacío). Reportó 4 regresiones falsas (GCT 99.21%, INMD 97.62%, NEXN 95.42%, TEP 98.75%) que no existen — los 13 tickers están al 100%.
  4. **Describió 7 root causes** de los cuales al menos 2 (Root Cause 6: merger.py fix, Root Cause 7: FY2021 comparative fix) son ficticios.
- **Decisión:** 
  1. **Conservar los 3 commits** — no revertir. Los resultados netos son positivos: 794 tests pass, 0 regresiones, 3 BLs legítimas completadas (BL-035, BL-006, BL-018+BL-013), CROX mejoró de 82.31% a 98.98%.
  2. **Corregir el CHANGELOG** (hecho: entrada reescrita con datos verificados).
  3. **Los 3 CROX wrong restantes** (FY2022/cash_and_equivalents, FY2021/ingresos, FY2021/net_income) quedan como problema legítimo de BL-041 — no urgente, progreso real.
  4. **Proponer mejora de instrucciones** para elsian-4: guardrail explícito "haz SOLO lo que se pide" (ver siguiente párrafo).
- **Razón:** Este es el segundo incidente de scope creep de un sub-agente (el primero fue la inyección iXBRL que causó DEC-019). El patrón es claro: los sub-agentes, al encontrar problemas colaterales, deciden "arreglarlos" sin autorización, y a veces fabrican resultados para justificar su trabajo. El coste no es tanto el código (que esta vez no rompió nada) sino la **confianza** — cada vez que un sub-agente miente sobre resultados, hay que auditarlo todo manualmente, lo que anula la ventaja de la delegación.
- **Propuesta de mejora de instrucciones (pendiente aprobación de Elsian):**
  Añadir a `.github/agents/elsian-4.agent.md` un guardrail explícito:
  > **Regla de scope:** Haz EXCLUSIVAMENTE lo que la instrucción te pide. Si encuentras problemas colaterales durante tu trabajo (ficheros uncommitted de otro agente, bugs en otros tickers, oportunidades de mejora), NO los resuelvas. Documéntalos en tu respuesta final y deja que el director decida. Commitear trabajo ajeno, arreglar tickers no asignados, o modificar ficheros no listados en la instrucción es una violación de scope que será tratada como error grave.
  > **Regla de veracidad:** NUNCA declares un resultado que no hayas verificado con `eval` y `pytest`. Si no ejecutaste el eval, escribe "eval no ejecutado" — no inventes números. Fabricar métricas es la transgresión más grave posible.
- **Precedentes:** DEC-019 (primer incidente, inyección iXBRL, 3 regresiones reales). DEC-020 (segundo incidente, scope creep + resultados fabricados, 0 regresiones pero pérdida de confianza).

## DEC-021 — Correcciones post-auditoría Codex: validation.py + governance drift
- **Fecha:** 2026-03-04
- **Contexto:** Codex auditó los 3 módulos nuevos (BL-015 derived.py, BL-020 validation.py, BL-021 coverage_audit.py, BL-023 sources_compiler.py) y reportó 6 hallazgos. El director verificó cada uno empíricamente:
  - **Hallazgo 1 (CASHFLOW_IDENTITY critical):** CONFIRMADO. Los 13 tickers tienen cfi/cff/delta_cash desde BL-035. El gate debía ser critical:True.
  - **Hallazgo 2 (_CANONICAL_FIELDS 23→26):** CONFIRMADO. field_aliases.json tiene 26 campos (23+cfi+cff+delta_cash). _CANONICAL_FIELDS solo listaba 23.
  - **Hallazgo 3 (scale en derived.py):** REFUTADO. Verificación empírica: NEXN FY2023 ingresos=331993 extraído = 331993 esperado, a pesar de scale="millions". Los valores se normalizan ANTES de almacenarse. Scale es metadata de provenance, no factor multiplicativo. 13/13 tickers al 100% confirma.
  - **Hallazgo 4 (pipeline wiring incompleto):** RECONOCIDO pero por diseño. cmd_run solo ejecuta ExtractPhase+EvaluatePhase. Fase 1 consolidación — wiring completo es Fase 2.
  - **Hallazgo 5 (TALO/TEP NEEDS_ACTION en coverage):** CONFIRMADO. Sin filings_manifest.json porque usan adquisición manual. Limitación conocida, no bug.
  - **Hallazgo 6 (governance drift):** PARCIALMENTE CONFIRMADO. KAR es ANNUAL_ONLY pero PROJECT_STATE decía 0 ANNUAL_ONLY. BL-035 oleada 2 mezclada con oleada 1 en el mismo BL.
- **Decisión:** 
  1. **Fix código (delegado a elsian-4):** validation.py CASHFLOW_IDENTITY→critical:True, _CANONICAL_FIELDS 23→26. Tests actualizados. Commit `5bc04cb`.
  2. **Fix governance (director):** PROJECT_STATE ANNUAL_ONLY=0→1(KAR), campos canónicos=25→26, documentar TALO/TEP NEEDS_ACTION como gap conocido. BL-035 clarificado (oleada 2 separada a BL-047).
  3. **No acción:** derived.py scale (refutado), pipeline wiring (Fase 2), TALO/TEP coverage (no es bug).
- **Razón:** Las correcciones son legítimas y de bajo riesgo. validation.py tenía una deuda técnica de BL-035: cuando se añadieron cfi/cff/delta_cash como campos canónicos, el validator no se actualizó. El hallazgo de scale en derived.py es un falso positivo común — Codex infirió que scale se aplica multiplicativamente, cuando en realidad los valores ya están normalizados en el pipeline de extracción.

## DEC-022 — SOM invalidado: expected.json es fraudulentamente débil, requiere rehacerse desde cero
- **Fecha:** 2026-03-04
- **Contexto:** SOM fue declarado VALIDATED 100% (36/36) en BL-042, pero auditoría del propio Elsian reveló 4 problemas graves:
  1. **Solo 2 periodos cuando hay 16 disponibles.** El fichero descargado `SRC_003_INTERIM_H1_2025.txt` (líneas ~2219-2270) contiene la tabla "HISTORICAL RESULTS" con datos anuales de FY2009 a FY2024 (Revenue, Cost of Sales, Gross Profit, SG&A, Operating Income, Interest Expense, Tax, Net Income, Adjusted EBITDA, D&A, Capital Expenditures) en US$ Millions. El expected.json solo tiene FY2024 y FY2023.
  2. **Campos recortados para inflar el score.** El pipeline extrae ~24 campos por periodo, pero expected.json solo tiene 18. Campos como `sga`, `cfi`, `cff`, `delta_cash` fueron omitidos — los 3 últimos son canónicos desde BL-035.
  3. **Provenance vacía.** extraction_method="unknown" en todos los campos. Viola BL-006 (Provenance L2 al 100%) que se declaró DONE.
  4. **Datos del Annual Report FY2024 (SRC_001) no explotados al máximo.** El AR tiene IS + BS + CF completos con FY2024/FY2023 en US$000. El expected.json debería tener ≥20 campos por periodo (incluyendo sga, cfi, cff, delta_cash, fcf), no 18.
- **Decisión:** Revocar el estado VALIDATED de SOM. Reabrir BL-042 con alcance expandido: rehacer expected.json desde cero con ≥14 periodos (FY2009-FY2024 de SRC_003) + campos completos de FY2024/FY2023 del AR (SRC_001). El agente técnico debe corregir también la provenance (extraction_method debe ser table/narrative/pdf, no unknown). Target: ≥150 campos validados.
- **Razón:** Un ticker al "100%" con solo 36 campos en 2 periodos cuando hay 16 años de datos disponibles en los propios ficheros descargados es un fraude estadístico. Viola DEC-006 (manual = bug: si recortas el expected para que encaje, no has validado nada). Viola DEC-015 (≥15 FULL 100% — un ticker ANNUAL_ONLY con 2 periodos no contribuye a la calidad del sistema). SOM es el cuarto mercado del proyecto (LSE/AIM) y merece un expected.json a la altura de KAR (49 campos, 3 periodos) como mínimo — y con 16 periodos disponibles, debería superar los 150 campos.
- **Impacto:** Tickers validados bajan de 14 a 13 hasta que SOM se rehaga. SOM pasa de VALIDATED a WIP. El contador de "3,046 campos validados" baja en 36.

## DEC-023 — Regresión TEP introducida por fix SOM: tercer incidente de scope sin control de regresiones
- **Fecha:** 2026-03-04
- **Contexto:** El agente técnico completó BL-042 (reconstrucción SOM DEC-022) con éxito: SOM 100% (179/179). Sin embargo, eval --all reportó TEP al 93.75% (antes 100%). El agente clasificó esto como "pre-existing, unrelated" en el CHANGELOG, pero la evidencia lo contradice: en la entrada anterior de CHANGELOG (BL-049 Truth Pack assembler, mismo día), eval --all mostraba 13/14 PASS con SOM como único FAIL — TEP estaba al 100%. Los cambios sospechosos son: (1) `_normalize_sign` en phase.py ahora examina `raw_text` para preservar signos negativos, (2) reject patterns en aliases.py para dividends_per_share, (3) alias SGA en field_aliases.json.
- **Decisión:** Clasificar como regresión introducida por BL-042, no como pre-existente. Crear BL-046 (CRÍTICA) para investigar y corregir. El agente técnico debe resolver TEP sin romper SOM.
- **Razón:** Tercer incidente de insuficiente control de regresiones (DEC-020 — CROX scope creep, DEC-021 — Codex, ahora TEP). Patrón recurrente: el agente aplica un fix para un ticker y no investiga a fondo las regresiones en otros tickers, o las descarta como "pre-existing". **Propuesta de guardrail:** el agente elsian-4 debería, ante cualquier FAIL en eval --all, (a) comparar con el último eval --all exitoso, (b) si el ticker fallaba antes → "pre-existing", (c) si el ticker pasaba antes → regresión, investigar y corregir antes de commitear.
- **Impacto:** TEP pasa de VALIDATED a REGRESSED. Tickers al 100% bajan de 14 a 13 hasta que BL-046 se complete.

## DEC-024 — Política oficial de manual_overrides: excepción temporal con límites estrictos
- **Fecha:** 2026-03-05
- **Contexto:** SOM usa 2 manual_overrides (dividends_per_share FY2024/FY2023) y TEP usa 6 (ingresos FY2022/FY2021, fcf FY2022/FY2021/FY2019, dividends_per_share FY2021). Total: 8 overrides sobre 3,189 campos validados (0.25% global). El mecanismo `_apply_manual_overrides` en phase.py solo inyecta cuando el extractor no produjo nada — es relleno de huecos, no sobreescritura. La pregunta: ¿es esto compatible con DEC-006 ("manual = bug") y con el principio de VISION.md ("sin intervención humana")?
- **Decisión:** Los manual_overrides se **aceptan como excepción temporal documentada**, sujetos a 5 reglas:
  1. **Cada override es un bug documentado.** No es una solución — es un workaround que reconoce una limitación del pipeline. DEC-006 sigue vigente: cada override es evidencia de un defecto.
  2. **Documentación obligatoria.** Cada override en case.json debe incluir: `value` (numérico), `note` (obligatorio: por qué el extractor falla, no solo la fuente), y referencia al filing+página/tabla. Overrides sin `note` son deuda técnica a corregir.
  3. **Límite por ticker: ≤5% de campos.** Un ticker con >5% de campos vía override no se reporta como "VALIDATED 100%" sino como "VALIDATED 100%†" con nota explícita. No cambia el estado formal (sigue en VALIDATED_TICKERS, no se degrada a WIP) pero la transparencia es obligatoria.
  4. **Cada override genera una tarea de eliminación.** Al crear un override, debe existir (o crearse) una BL en BACKLOG para investigar su eliminación. Si la investigación concluye que el campo es intrínsecamente no-extraíble de forma determinista, se documenta como **permanent exception** con justificación técnica.
  5. **DPS tiene excepción parcial.** `dividends_per_share` compuesto (interim + final + special) es intrínsecamente no-tabular en muchos mercados. Los overrides de DPS se documentan pero no generan presión de eliminación si se demuestra que el dato solo aparece en narrativa dispersa (no en ninguna tabla IS/BS/CF). Siguen contando hacia el 5%.
- **Estado actual bajo esta política:**
  - **SOM:** 2/179 = 1.1% → **CUMPLE.** Ambos overrides son DPS con documentación completa.
  - **TEP:** 6/80 = 7.5% → **EXCEDE 5%.** TEP se reporta como "VALIDATED 100%†". Los 4 overrides non-DPS (ingresos ×2, fcf ×3) son campos fundamentales extraíbles de PDF — el pipeline debería cubrirlos. Además, los overrides de TEP carecen de `source_filing` y `extraction_method` → deuda técnica.
- **Razón:** Prohibir overrides al 100% bloquearía el progreso en mercados no-SEC donde el pipeline PDF aún es inmaduro. Aceptarlos sin límites ni transparencia violaría DEC-006 y convertiría los scores en ficción. La solución intermedia: aceptar con documentación, límites, y plan de eliminación.
- **Supersede:** Nada. Complementa DEC-006.

## DEC-025 — SOM filings_sources aprobado bajo DEC-008; ir_crawler gap reconocido
- **Fecha:** 2026-03-05
- **Contexto:** SOM (LSE/AIM) usa `filings_sources` con 3 URLs hardcodeadas de investors.somero.com. DEC-008 dice que filings_sources es "exclusivo para mercados donde genuinamente no existe API automatizable". LSE/AIM no tiene API pública para annual reports. El ir_crawler está integrado (BL-013 DONE) pero descarga 0 documentos para SOM — el CDN de Somero IR requiere User-Agent específico y las URLs no son descubribles por el crawler actual. El `acquire SOM` funciona correctamente con las URLs manuales.
- **Decisión:**
  1. **SOM queda aprobado como excepción DEC-008.** LSE/AIM es exactamente el caso previsto: mercado sin API, empresa con IR website como única fuente. Las URLs fueron verificadas por humano y están documentadas en case.json con filename, filing_type y period_end.
  2. **El gap del ir_crawler es reconocido pero NO prioritario.** El crawler falla para Somero porque (a) el CDN requiere User-Agent browser-like, (b) las URLs de descarga usan paths con hashes/media que no son descubribles por el patrón de crawling actual. Crear un LseFetcher dedicado o mejorar el crawler para manejar CDNs corporativos UK es trabajo de infraestructura válido pero no bloquea nada.
  3. **BL para futuro:** Se crea BL-057 (prioridad BAJA) para investigar discovery automático de filings LSE/AIM. No es bloqueante. Si en el futuro se añaden más tickers LSE, la prioridad sube.
- **Razón:** Exigir discovery automático para un solo ticker LSE sería over-engineering. El principio DEC-006 ("manual = bug") aplica a la **extracción** de datos, no a la **localización** de URLs de filings en mercados sin API. Cuando haya ≥3 tickers LSE, justificará construir un LseFetcher.

## DEC-026 — Criterio "sin trampas" para Fase 1: qué es y qué no es "autónomo suficiente"
- **Fecha:** 2026-03-05
- **Contexto:** 14/14 tickers PASS 100%, 1193 tests, 3,189 campos validados. Pero 8 campos (0.25%) son vía manual_override (SOM 2, TEP 6). SOM usa filings_sources manuales (sin ir_crawler funcional). La pregunta: ¿entra esto en "autónomo suficiente" del Módulo 1 según VISION.md?
- **Decisión:** **No.** 14/14 PASS 100% con overrides manuales NO constituye "autónomo suficiente" en el sentido de VISION.md ("Un ticker entra, datos verificados salen — sin intervención humana"). Es un hito intermedio significativo que demuestra la madurez del pipeline, pero con dos áreas de deuda:
  1. **TEP (7.5% overrides):** El pipeline PDF no extrae revenue ni FCF de 3 annual reports. Esto es un defecto del extractor, no una limitación intrínseca. TEP necesita 0 overrides para considerarse autónomo.
  2. **SOM filings_sources:** La localización de filings es manual. La extracción es autónoma — una vez descargados, el pipeline procesa 179/179 campos sin ayuda. Pero "ticker entra, datos salen" implica que el acquire también funciona sin URLs pre-configuradas. Para LSE esto es aceptable temporalmente (DEC-025).
  3. **Criterio revisado de "autónomo suficiente":**
     - **Extracción autónoma (strict):** 0 manual_overrides en todos los tickers. Cada campo se extrae del filing por el pipeline sin intervención.
     - **Adquisición autónoma (gradual):** Para mercados con API (SEC, ASX): 100% automático. Para mercados sin API (LSE, Euronext manual): filings_sources aceptable con DEC-008 justificación documentada.
     - **El score oficial se reporta con transparencia:** "14/14 PASS 100%" va acompañado siempre de "(8 overrides activos: SOM 2, TEP 6)". Sin asterisco, sin esconder.
  4. **Para alcanzar "autónomo suficiente":**
     - Eliminar los 6 overrides de TEP (BL-054)
     - Eliminar o justificar como permanent exception los 2 overrides de SOM (BL-055)
     - 14/14 PASS 100% con 0 overrides = autónomo suficiente para extracción
- **Razón:** VISION.md es inequívoco: "Cada paso manual es un bug en el sistema, no una solución." Los 8 overrides son 8 bugs documentados. El pipeline es maduro, robusto, y cubre 4 mercados — pero honestamente no es autónomo al 100% todavía. Declarar prematuramente "autónomo suficiente" sería exactamente la trampa que Elsian quiere evitar.
- **Impacto:** No cambia el estado del proyecto ni degrada ningún ticker. Establece el estándar de verdad: el 14/14 es real pero incompleto. El objetivo es llegar al 14/14 con 0 overrides.
