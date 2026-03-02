# ELSIAN-INVEST 4.0 — Hoja de Ruta Estratégica

> Del laboratorio al producto comercial. Marzo 2026.

---

## 1. Dónde estamos

ELSIAN-INVEST 4.0 ha completado su fase de bootstrap y ha logrado algo que no debíamos dar por sentado: un pipeline funcional end-to-end que descarga filings, extrae datos financieros y los evalúa contra ground truth curado, todo sin intervención humana y sin una sola llamada a LLM.

### Lo construido

| Componente | Estado | Líneas |
|---|---|---:|
| **Acquire (Layer 0)** | SecEdgarFetcher + EuRegulatorsFetcher + ManualFetcher + converters (HTML→MD, PDF→text) | ~730 |
| **Extract (Layer 1)** | HTML tables + narrative + vertical BS + detect + phase orchestrator | ~3,020 |
| **Normalize** | AliasResolver (295), ScaleCascade, SignConvention, AuditLog | ~540 |
| **Merge + Evaluate** | Multi-filing merger + evaluator + dashboard | ~440 |
| **Modelos + CLI** | Dataclasses con Provenance, CLI argparse (acquire/extract/eval/run/dashboard) | ~800 |
| **Tests** | 150 tests: unit + integration + regresión parametrizada | ~1,200 |
| **TOTAL** | Pipeline completo acquire → extract → eval | **~6,730** |

*7 tickers validados al 100%: GCT (108), IOSP (95), NEXN (76), SONO (116), TALO (85), TEP (55), TZOO (270) = 805 campos.*

### Lo que falta por decidir

El bootstrap está hecho. Ahora viene la pregunta estratégica: ¿en qué orden construimos el resto? La respuesta no es obvia porque hay dependencias cruzadas entre los módulos y porque no todo tiene el mismo valor comercial.

Hay una tensión fundamental entre dos direcciones:

- **Profundizar en calidad (vertical):** más tickers, iXBRL como fuente primaria, provenance nivel 3, refinar reglas de extracción. Esto hace que el producto sea más fiable pero no más amplio.
- **Ampliar capacidades (horizontal):** extracción cualitativa (Capa 2), LLM fallback (Capa 3), análisis (Capa 4). Esto hace el producto más completo pero sobre una base más estrecha.

**Recomendación:** la base cuantitativa debe ser irrefutable antes de añadir capas de inteligencia encima. Un sistema de análisis brillante construido sobre datos poco fiables no vale nada. La secuencia correcta es profundidad primero, amplitud después.

---

## 2. Líneas maestras del proyecto

Estas son las cinco directrices estratégicas que deben guiar todas las decisiones técnicas:

### Línea 1: La provenance es el producto

No estamos construyendo "un extractor de datos financieros más". Estamos construyendo la primera base de datos financiera global donde cada número tiene un enlace verificable a su fuente original. Eso es lo que nos diferencia de Bloomberg, Capital IQ y FactSet. Cualquier decisión técnica que debilite la trazabilidad es una decisión equivocada.

Implicación práctica: nunca extraer un valor sin coordenadas. Nunca añadir un extractor nuevo que no propague provenance. El source_map.json que vincula el clean.md con el documento original no es un "nice to have", es parte del producto.

### Línea 2: Zero-LLM en la capa cuantitativa

La Capa 1 (extracción de datos numéricos) debe funcionar sin ninguna llamada a LLM. Esto no es una limitación, es una ventaja competitiva. Los clientes institucionales (fondos, auditoras, reguladores) desconfían de datos generados por IA. Un pipeline 100% determinístico y reproducible es certificable, auditable y vendible a estos clientes.

El LLM tiene su lugar (Capas 2 y 3), pero siempre como complemento, nunca como fuente primaria de datos cuantitativos.

### Línea 3: Cobertura global por composición

Cada mercado nuevo (Europa, Japón, Australia) se añade como un Fetcher y/o Extractor nuevo, sin tocar el código existente. La arquitectura de clases con ABCs ya lo permite. La configuración por case.json (source_hint, currency, fiscal_year_end_month) hace que el pipeline se adapte sin if/else.

Esto significa que escalar de 8 a 80 tickers no requiere reescribir nada, solo añadir casos y afinar reglas.

### Línea 4: Las Capas 0+1 son un producto independiente

Las capas de descarga y extracción determinística deben poder venderse por separado, sin necesitar las capas de análisis. Esto significa: API limpia, documentación, rate limiting, autenticación. El visor de filings (Línea de producto 2) solo necesita estas dos capas para funcionar.

### Línea 5: Cada ticker mejora el sistema entero

Cada caso nuevo genera reglas de extracción validadas contra ground truth curado. Esas reglas se acumulan en field_aliases.json, selection_rules.json y en el propio código de los extractores. Un competidor que empiece de cero tiene que recorrer el mismo camino. Es un moat de datos propietario que crece con el uso.

---

## 3. Fases del proyecto

### Fase 1 — Consolidar Layer 1 (ahora → próximas 4-6 semanas)

> *Objetivo: que la extracción determinística sea tan fiable que pueda venderse como producto.*

Esta es la fase en la que estamos. El pipeline funciona, pero hay deuda técnica y gaps importantes:

#### 1.1 Completar la arquitectura Pipeline

ExtractPhase tiene 914 líneas con su propio método `extract()` pero no implementa `PipelinePhase.run(context)`. Las ABCs existen pero no están wired. Esto debe corregirse ahora porque cada módulo nuevo que añadamos después será más difícil de integrar.

- **Wire ExtractPhase, AcquirePhase y EvaluatePhase** a `PipelinePhase.run(context)`
- **`cmd_run`** debe usar `Pipeline([AcquirePhase(), ExtractPhase(), EvaluatePhase()]).run(context)`
- **Mantener compatibilidad** — los comandos individuales siguen funcionando

#### 1.2 Expandir a ≥15 tickers FULL 100% (DEC-015)

10 tickers no son suficientes para validar que el sistema es robusto. El criterio unificado (DEC-015) exige ≥15 tickers en FULL scope (annual + quarterly) al 100%. Necesitamos cobertura de:

| Gap actual | Tickers candidatos | Qué valida |
|---|---|---|
| Large-cap US | AAPL, MSFT, JNJ | Filings complejos, segmentos, escalas mixtas |
| Sector financiero | JPM, GS | Balance sheets atípicos, estados financieros específicos |
| Micro-cap | 2-3 tickers <$100M | Filings simples, baja calidad de formato |
| Europa continental | SAP.DE, SAN.MC | IFRS, EUR, idiomas no ingleses |
| Asia | 7203.T (Toyota) | EDINET, JPY, año fiscal marzo |

Cada ticker nuevo fortalece las reglas para todos los demás. A partir de 15-20 casos, la tasa de "sorpresas" al añadir un ticker nuevo debería bajar drásticamente.

#### 1.3 iXBRL como fuente primaria

Este es el cambio más importante de la Fase 1. iXBRL es datos estructurados ya etiquetados por las propias empresas: tags GAAP/IFRS con periodo, escala y contexto explícitos. Para cualquier empresa SEC, los datos iXBRL son más fiables que parsear tablas HTML.

- **Portar** `ixbrl_extractor.py` desde 3.0 y envolver en `IxbrlExtractor(Extractor)`
- **Prioridad:** donde exista iXBRL, es fuente primaria. HTML/PDF es fallback
- **Cross-validation:** si iXBRL y HTML dan el mismo número → confianza máxima. Si difieren → flag
- **Provenance nativa:** iXBRL ya incluye concepto, periodo, contexto → Level 2 gratis

iXBRL elimina de raíz la mayoría de bugs de escala, alias y confusión segmento/consolidado que hoy resolvemos con reglas manuales.

#### 1.4 Provenance Level 2 completa

Actualmente la Provenance tiene `source_filing` y `source_location` (coordenadas tipo `tblX:rowY:colZ`). Falta poblar los campos que ya están definidos en el modelo pero no se usan: `table_title`, `row_label`, `col_label`, `raw_text`. El modelo ya está preparado — solo falta llenar los campos desde los extractores.

---

### Fase 2 — Infraestructura de datos (semanas 6-10)

> *Objetivo: pasar de "script que extrae datos" a "plataforma que sirve datos".*

Una vez que Layer 1 sea sólida con 15-20 tickers, necesitamos la infraestructura para convertirla en producto:

#### 2.1 Base de datos y API

- **Almacenamiento:** Los extraction_result.json deben migrar a una base de datos (PostgreSQL o SQLite para empezar). Cada campo es una fila con su provenance completa.
- **API REST:** Endpoints básicos: `GET /api/v1/{ticker}/financials`, `GET /api/v1/{ticker}/field/{field_name}/provenance`. FastAPI como framework.
- **Versionado:** Cada extracción se versiona. Si re-ejecutamos el pipeline con reglas mejoradas, el resultado anterior se mantiene como histórico.

#### 2.2 Scheduler de actualización

SEC publica filings nuevos cada día. El pipeline debe poder ejecutarse periódicamente para detectar nuevos filings y re-extraer. Esto convierte el producto de "snapshot puntual" a "datos siempre actualizados".

#### 2.3 Provenance Level 3 — Link al documento original

El converter (HTML → markdown) debe generar un `source_map.json` que vincule cada tabla/fila/columna del clean.md con su posición en el HTML original. Esto permite el "click to source": el usuario ve un número, hace clic, y llega a la celda exacta del filing original en SEC EDGAR.

Para PDF, pdfplumber ya proporciona bounding boxes por elemento. TATR (Table Transformer) daría coordenadas aún más precisas cuando se implemente.

---

### Fase 3 — Extracción cualitativa, Capa 2 (semanas 10-16)

> *Objetivo: extraer señales de texto no estructurado que hoy no procesamos.*

Los 10-K y 10-Q que ya descargamos contienen información cualitativa extremadamente valiosa en secciones como MD&A (Management Discussion & Analysis) y Risk Factors. Hoy la ignoramos completamente.

#### Qué extraer

- **Cambios en risk factors:** ¿qué riesgos aparecieron nuevos? ¿cuáles desaparecieron?
- **Tono del MD&A:** ¿el management es más optimista o pesimista que el trimestre anterior?
- **Guidance cuantitativa:** "We expect revenue in the range of $X to $Y"
- **Cambios contables:** nuevas políticas, restatements, reclasificaciones
- **Litigios:** demandas nuevas, resoluciones, provisiones

#### Cómo hacerlo

Esta capa SÍ usa LLM, pero con trazabilidad al párrafo exacto del filing. La arquitectura sería:

1. **Segmentar** el filing en secciones (MD&A, Risk Factors, etc.)
2. **Analizar** cada sección con LLM usando prompts específicos
3. **Vincular** cada hallazgo al párrafo fuente (provenance cualitativa)
4. **Comparar** entre periodos para detectar cambios significativos

Esto se convierte en una nueva familia de clases: `QualitativeExtractor`, `SectionSegmenter`, `ChangeDetector`, etc. Todas implementando la misma interfaz de provenance.

---

### Fase 4 — LLM Fallback + Análisis, Capas 3-4 (semanas 16-24)

> *Objetivo: completar el sistema de inversión con inteligencia analítica.*

#### Capa 3 — LLM como fallback cuantitativo

Cuando Layer 1 no puede extraer un campo (confianza baja, tabla no reconocida, PDF corrupto), un LLM revisa el filing y lo completa. Pero siempre marcado como "LLM-assisted" en la provenance, nunca como dato determinístico. El usuario sabe exactamente qué datos son 100% verificables y cuáles tienen asistencia IA.

#### Capa 4 — Análisis y decisión

Aquí entran los módulos de análisis del 3.0 (TruthPack, CATALYST, BULL, RED_TEAM, ARBITRO), adaptados para consumir la nueva capa de datos con provenance. Esta capa es la que convierte datos en conclusiones accionables.

La Capa 4 es donde está el valor premium de ELSIAN, pero solo funciona si las capas inferiores son sólidas. Por eso va última.

---

### Fase 5 — Producto comercial (semanas 24+)

> *Objetivo: poner ELSIAN en manos de usuarios reales.*

- **API pública** con autenticación, rate limiting, documentación OpenAPI
- **Visor de filings web** — interfaz donde cada número es clicable y lleva al filing original
- **Dashboard de análisis** — TruthPack, comparativas, alertas
- **Modelo de negocio** — freemium (datos básicos gratis) + premium (provenance completa + análisis)

---

## 4. Decisiones críticas pendientes

Hay varias decisiones que debemos tomar pronto porque afectan a todo lo demás:

### 4.1 ¿Cuándo añadir iXBRL?

**Recomendación: ahora, en Fase 1.** iXBRL no es un "nice to have", es un cambio de paradigma. Para empresas SEC, iXBRL convierte la extracción de "adivinar dónde están los números en una tabla" a "leer datos ya etiquetados". La precisión sube drásticamente y las reglas de alias/escala se simplifican. Además, el extractor ya existe en 3.0 — solo hay que portarlo.

### 4.2 ¿Base de datos o ficheros?

Hoy los resultados son JSON en disco. Esto funciona para 8 tickers pero no escala a 200. Sin embargo, migrar a PostgreSQL ahora añadiría complejidad prematura. **Recomendación:** mantener JSON durante la Fase 1, migrar a SQLite/PostgreSQL al inicio de la Fase 2. El modelo ExtractionResult ya tiene `to_dict()` — la serialización está resuelta.

### 4.3 ¿Qué LLM para Capa 2?

Claude para extracción cualitativa sería la elección natural (ventana de contexto grande, bueno con documentos largos). Pero también podríamos usar modelos open-source para reducir costes en producción. Esta decisión puede esperar a la Fase 3.

### 4.4 ¿Monorepo o repos separados?

4.0 ya es un proyecto independiente de 3.0, lo cual es correcto. La pregunta es si el visor web, la API, y el scheduler deben vivir en el mismo repo o separarse. **Recomendación:** monorepo durante las Fases 1-3 (simplicidad, refactoring fácil), evaluar separar cuando haya equipo.

---

## 5. Resumen ejecutivo

ELSIAN-INVEST 4.0 está en un punto de inflexión. El laboratorio ha terminado — tenemos un pipeline funcional con 805 campos al 100% en 7 tickers. Ahora empieza la construcción del producto.

| Fase | Foco | Entregable | Plazo |
|:---:|---|---|:---:|
| **1** | Consolidar Layer 1: arquitectura, iXBRL, ≥15 tickers FULL 100% (DEC-015) | Extracción irrefutable | 4-6 sem |
| **2** | Infraestructura: BD, API, scheduler, provenance L3 | Plataforma de datos | 6-10 sem |
| **3** | Capa 2: extracción cualitativa con LLM | Señales de texto | 10-16 sem |
| **4** | Capas 3-4: LLM fallback + análisis | Sistema completo | 16-24 sem |
| **5** | Producto comercial: API, visor web, dashboard | Producto vendible | 24+ sem |

Lo más importante ahora no es ir rápido, sino ir bien. Cada ticker que añadamos con 100% refuerza las reglas para todos los demás. Cada campo con provenance completa acerca el "click to source" que nos diferencia del mercado. La paciencia en Layer 1 es lo que hará que las capas superiores funcionen.

**La pregunta no es si ELSIAN puede competir con Bloomberg. La pregunta es cuántos tickers necesitamos para demostrarlo. Y la respuesta empieza en la Fase 1.**
