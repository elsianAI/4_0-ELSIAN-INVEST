# ELSIAN-INVEST 4.0 — Visión Operativa

> Este documento es la **referencia canónica** de qué es ELSIAN 4.0, por qué existe, y qué estamos construyendo. Todo agente que trabaje en este proyecto debe leer este documento antes de hacer cualquier otra cosa. ROADMAP.md describe la visión a largo plazo. Este documento describe la realidad operativa.

---

## Origen: por qué existe el 4.0

El 3.0 fue un laboratorio. Contenía tres bloques que no se comunicaban bien entre sí: un engine de orquestación LLM (~14,600 líneas), scripts/runners sueltos (~11,600 líneas), y un módulo deterministic (~3,800 líneas) que nació para resolver el problema fundamental — que ningún ticker del 3.0 tenía los datos financieros correctamente extraídos.

El 3.0 cumplió su propósito: descubrimos qué fuentes de datos existen, cómo se estructuran los filings de cada regulador, qué reglas de extracción funcionan, cómo evaluar calidad, cómo manejar restatements y colisiones entre filings. Todo ese conocimiento se porta al 4.0, pero no el código tal cual.

La decisión de crear el 4.0 no fue "mejorar el 3.0". Fue reemplazarlo completamente con un sistema modular, construido desde cero con arquitectura de clases Python. El 3.0 está congelado. Es una referencia de lectura, no una base de código activa.

La documentación fundacional de esta decisión está en `3_0-ELSIAN-INVEST/deterministic/mejoras/IDEAS.md`, Idea #11.

---

## Qué es ELSIAN 4.0

Un sistema de inversión modular construido desde cero con Python. Cada módulo es independiente, tiene su propia responsabilidad, sus propios tests, y puede funcionar de forma autónoma. Los módulos se componen entre sí, pero no dependen unos de otros para existir.

### Principios de diseño

1. **Módulos independientes.** Cada módulo del sistema tiene una responsabilidad clara, un CLI propio, y tests autónomos. Un módulo no requiere que otro esté terminado para funcionar.

2. **Arquitectura de clases desde el día uno.** Cada componente es una clase Python con interfaz tipada (ABCs, `run(context) → result`). No hay funciones sueltas, no hay facades monolíticos, no hay orquestación por if/else. El sistema se configura por composición e inyección de dependencias. Añadir un nuevo fetcher, extractor o regulador = crear una clase nueva y registrarla. El pipeline no cambia.

3. **Código reutilizable y escalable.** Las clases son genéricas por diseño. Un `SecEdgarFetcher` y un `AsxFetcher` comparten la misma interfaz `Fetcher`. Un `HtmlTableExtractor` y un `PdfTableExtractor` comparten la misma interfaz `Extractor`. Esto permite que cada mercado, formato o regulador nuevo se añada sin tocar el código existente.

4. **Zero-LLM en extracción cuantitativa.** La capa de datos financieros es 100% determinista: regex, tablas, normalización por reglas, evaluación por gates. Reproducible, auditable, sin coste por ejecución. Los LLM vendrán en módulos futuros y separados — nunca dentro del pipeline de extracción cuantitativa.

5. **Testing como ciudadano de primera.** Cada ticker validado al 100% es un test de regresión permanente. `eval --all` debe pasar al 100% ante cualquier cambio. Cualquier commit que rompa un ticker es un bug, no un trade-off aceptable. CI/CD integrado con GitHub Actions.

6. **Provenance como principio fundacional.** Cada dato extraído debe ser trazable hasta su origen exacto: fichero fuente, tabla, fila, columna, texto original de la celda. Sin provenance, el dato no tiene valor. Esto no es un "nice to have" — es el core del producto.

7. **Configuración sobre código.** Aliases de campos, reglas de selección, prioridades de filing, pesos de sección — todo vive en ficheros JSON de configuración con override por caso o mercado. Cambiar una regla no requiere tocar código Python.

---

## El Módulo 1: Pipeline de Extracción Financiera

Es el primer módulo, el más importante, y **el foco actual y único del proyecto**.

### Qué hace

Dado un ticker de cualquier mercado del mundo, el Módulo 1:

1. **Descarga** automáticamente sus filings financieros del regulador correspondiente (SEC, Euronext, ASX, LSE, HKEX...)
2. **Convierte** los documentos a formatos procesables (HTML→Markdown, PDF→texto)
3. **Extrae** todos los datos cuantitativos de los estados financieros (Income Statement, Balance Sheet, Cash Flow)
4. **Normaliza** los datos: resuelve aliases multilingüe (EN/FR/ES/DE), aplica cascada de escala, enforce signos, ejecuta sanity checks
5. **Fusiona** datos de múltiples filings con resolución de colisiones por prioridad de tipo de filing
6. **Valida** el resultado con 9 quality gates autónomos (BS identity, CF identity, units sanity, margins, TTM, recency, completeness...)
7. **Evalúa** contra expected.json curado para medir precisión

Todo sin intervención humana. Todo sin LLM. Todo con provenance completa.

### Arquitectura del pipeline

```
Acquire → Convert → Extract → Normalize → Merge → Evaluate
```

**Acquire** — Fetchers por regulador. Cada mercado nuevo = una clase `Fetcher` nueva. Hoy: SecEdgarFetcher (US), EuRegulatorsFetcher (Euronext/ESEF con IR crawler integrado), AsxFetcher (Australia), ManualFetcher (fallback). Además: MarketDataFetcher (precios, shares outstanding), TranscriptFinder (earnings calls), SourcesCompiler (merge multi-fetcher con dedup por hash).

**Convert** — Transformación de formatos. HTML→Markdown (con detección de secciones IS/BS/CF/Notes/MD&A), PDF→texto (pdfplumber), quality gates sobre el clean.md resultante.

**Extract** — El músculo del sistema. HtmlTableExtractor (regex + estructura de tablas, multilingüe, multi-formato), PdfTableExtractor (pdfplumber structured tables), NarrativeExtractor (patrones de texto en MD&A y notas), VerticalBSExtractor (balance sheets no tabulares), e `IxbrlExtractor` para filings SEC con iXBRL disponible. El parser iXBRL ya no es solo una herramienta de curación: forma parte del pipeline productivo para el alcance actual, mientras HTML/PDF siguen cubriendo el resto de formatos y gaps.

**Normalize** — AliasResolver (150+ aliases multilingüe por campo canónico), ScaleCascade (5 niveles de inferencia de escala), SignEnforcement (capex siempre negativo, revenue siempre positivo), SanityChecks (4 reglas post-extracción no bloqueantes), AuditLog (trazabilidad de cada decisión).

**Merge** — Fusión multi-filing. Prioridad: 10-K/20-F > 10-Q/6-K > 8-K/earnings. Resolución de colisiones por tipo de filing y confianza. Deduplicación por (campo, periodo).

**Evaluate** — Autonomous Validator con 9 quality gates intrínsecos (no necesitan expected.json). CoverageAudit (clasificación de issuer, thresholds por clase). ValidateExpected (8 errores estructurales + 2 sanity warnings). Evaluator (comparación contra ground truth). Dashboard.

### Componentes de soporte

- **Calculadora de métricas derivadas (714L):** TTM (cascade 4Q → semestral → FY0), Q4 sintético, FCF, EV, márgenes (gross/op/net/FCF), retornos (ROIC/ROE/ROA), múltiplos (EV/EBIT, EV/FCF, P/FCF), net debt, per-share. Null propagation.
- **Filing Preflight (319L):** Detección determinista de idioma, estándar contable, moneda, secciones financieras, unidades por sección, restatement, año fiscal. <1ms por filing.
- **Provenance Level 2:** Cada dato trazable a tabla_index, tabla_title, row_label, col_label, row, col, raw_text, extraction_method. 100% de completitud en todos los extractores.

### Estado actual (marzo 2026)

La foto viva del proyecto se mantiene en `docs/project/PROJECT_STATE.md`. Este documento no replica métricas operativas ni contadores cambiantes para evitar deriva documental.

- El Módulo 1 sigue siendo el foco actual y único del proyecto.
- El pipeline ya opera sobre múltiples mercados, reguladores y formatos con suite de regresión activa.
- La CLI y los artefactos de soporte del pipeline están en producción y evolucionan dentro del perímetro del Módulo 1.
- Cualquier cifra oficial de cobertura, tests, overrides o tickers validados debe leerse en `docs/project/PROJECT_STATE.md`.

---

## Cuándo está "terminado" el Módulo 1

El Módulo 1 no tiene una fecha de entrega — tiene criterios de madurez. No hay prisa por pasar a ninguna fase siguiente. El objetivo es que el pipeline sea irrefutable.

**Criterios de madurez (orientativos, no exhaustivos):**

- Cobertura de tickers amplia y diversa: múltiples mercados, reguladores, formatos, idiomas, estándares contables
- Todos los campos canónicos necesarios para el cálculo completo de métricas derivadas
- Pipeline end-to-end completamente autónomo (de ticker a datos validados sin intervención)
- Provenance completa (nivel 2 consolidado, nivel 3 deseable)
- Suite de regresión verde y robusta ante cualquier cambio
- Código limpio, modular, documentado, con tests unitarios e integración
- Capacidad demostrada de añadir un ticker nuevo en horas, no días

**Lo que queda por hacer dentro del Módulo 1:**

- Añadir más tickers para cubrir gaps (nuevos mercados, nuevos formatos, edge cases)
- Expandir campos canónicos (working capital: accounts_receivable, inventories, accounts_payable)
- Mejorar extractores donde hay gaps conocidos (interest_income, capex en ciertos formatos)
- Eliminar manual_overrides activos o documentar excepciones permanentes con justificación técnica
- Provenance Level 3 (mapeo clean.md → documento original para "click to source")

---

## Módulos futuros

Estos módulos se construirán cuando el Módulo 1 esté maduro y Elsian lo decida. No se trabaja en ellos ahora. No se planifican activamente. Están listados aquí para dar contexto de hacia dónde va el sistema, no como tareas pendientes.

- **Módulo 2 — Extracción cualitativa (LLM-assisted):** MD&A, risk factors, guidance, cambios entre periodos. Requiere LLM con trazabilidad al párrafo exacto del filing. Los datos ya están descargados — solo falta procesarlos.
- **Módulo 3 — LLM fallback cuantitativo:** Completar datos que la capa determinista no pudo extraer o tiene confianza baja. El ground truth curado del Módulo 1 sirve para validar que el fallback es correcto.
- **Módulo 4 — Análisis y decisión:** consumo de los outputs cuantitativos del Módulo 1 (incluyendo truth packs ya ensamblados), métricas derivadas de decisión, IMPLIED expectations, CATALYST detection, BULL/RED_TEAM analysis, ARBITRO final decision.
- **Infraestructura de producto:** API REST, base de datos (PostgreSQL), visor web con "click to source", scheduler de actualización. Se construirá cuando haya algo que servir.

---

## La regla de oro

**No se trabaja en ningún módulo futuro, ni en infraestructura de producto, ni en API, ni en visor web, ni en análisis, hasta que el Pipeline de Extracción Financiera (Módulo 1) funcione de forma irrefutable.** Cualquier desvío hacia fases comerciales, capas de LLM, o funcionalidad de análisis sin que el módulo de extracción esté completo y maduro es una pérdida de foco y una repetición del error que ya cometimos.

El Módulo 1 es la base sobre la que se construye todo lo demás. Si la base no es sólida, nada de lo que se construya encima tendrá valor.

---

## Documentos de referencia

| Documento | Qué es | Dónde está |
|---|---|---|
| IDEAS.md | Documento fundacional — las 15 ideas que originaron el 4.0 | `3_0-ELSIAN-INVEST/deterministic/mejoras/IDEAS.md` |
| ROADMAP.md | Visión a largo plazo (aspiracional, no operativo) | Raíz del repo 4.0 |
| ROLES.md | Contratos operativos de director / engineer / auditor | `docs/project/ROLES.md` |
| PROJECT_STATE.md | Estado actual del proyecto con métricas reales | `docs/project/PROJECT_STATE.md` |
| BACKLOG.md | Cola de tareas priorizadas | `docs/project/BACKLOG.md` |
| DECISIONS.md | Registro de decisiones estratégicas | `docs/project/DECISIONS.md` |
