# ELSIAN-INVEST 4.0 — Backlog Activo

> Cola de trabajo ejecutable. Este fichero contiene solo tareas vivas (`TODO`, `IN_PROGRESS`, `BLOCKED`).
> El histórico de tareas completadas vive en `docs/project/BACKLOG_DONE.md`.

---

## Protocolo de uso

**Quién escribe:** el agente director (prioriza, añade, reordena y cierra).
**Quién lee:** `orchestrator`, `kickoff` y agentes técnicos para conocer la cola viva.
**Estados válidos aquí:** `TODO`, `IN_PROGRESS`, `BLOCKED`.

**Formato por tarea:**

```md
### BL-XXX — Título corto
- **Prioridad:** CRÍTICA | ALTA | MEDIA | BAJA
- **Estado:** TODO | IN_PROGRESS (agente) | BLOCKED (razón)
- **Asignado a:** rol o agente
- **Módulo:** Module 1 | Governance
- **Validation tier:** targeted | shared-core | governance-only
- **Depende de:** BL-XXX (si aplica)
- **Referencias:** DEC-XXX (si aplica)
- **Descripción:** Qué hay que hacer y por qué
- **Criterio de aceptación:** Cómo sabemos que está terminado
```

---

## Tareas activas

### BL-059 — T01 — Contratos y esquemas versionados
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** —
- **Referencias:** T01, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Crear la capa de contratos versionados para los artefactos principales del sistema (`case.json`, `expected.json`, manifests, extraction results, truth pack y source map) y validar que prompts y tooling usen el set canónico real actual sin drift.
- **Criterio de aceptación:** Existen esquemas versionados y una validación centralizada que cubre los artefactos activos; los casos reales validan contra contrato y desaparecen referencias obsoletas al set canónico o a rutas legacy.

### BL-061 — T03 — Task manifests y core protegido
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-059
- **Referencias:** T03, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Añadir manifests de tarea ejecutables y extender la protección del core para que el runtime pueda verificar scope, superficies protegidas, validación requerida y documentos a reconciliar sin depender solo del prompt.
- **Criterio de aceptación:** Existe al menos un manifest real, el checker detecta cambios fuera de scope y el sistema puede ejecutar paquetes con contrato técnico explícito.

### BL-062 — T04 — Service layer y registry de fetchers
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-059, BL-060, BL-061
- **Referencias:** T04, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Reabrir las fronteras internas del sistema con una service layer clara y un registry centralizado de fetchers, dejando la CLI como adaptador fino.
- **Criterio de aceptación:** El routing de fetchers vive en un único punto, la lógica principal sale de la CLI y la nueva capa queda cubierta por tests unitarios e integración.

### BL-063 — T05 — Descomposición real del pipeline
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-062
- **Referencias:** T05, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Separar el pipeline en fases reales con severidades explícitas y persistencia de artefactos diagnósticos cuando el fallo no sea fatal.
- **Criterio de aceptación:** La arquitectura documentada y la real convergen en fases explícitas, con cobertura de fallos fatales y no fatales y sin degradar la ejecución actual.

### BL-064 — T06 — Modelo unificado de readiness
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-063
- **Referencias:** T06, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Introducir un readiness compuesto que complemente el score histórico con cobertura real, validator, provenance y penalización de extras.
- **Criterio de aceptación:** `elsian eval` expone readiness compuesto junto al score legado y permite ordenar tickers por preparación operativa real.

### BL-065 — T07 — Policies y rule packs (scope filtrado restante)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-063
- **Referencias:** T07-parcial, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Externalizar thresholds y quirks pendientes a policies y rule packs reutilizables por mercado/formato, tomando BL-047 como patrón y sin reabrir lo ya absorbido por fixes previos.
- **Criterio de aceptación:** Reglas operativas salen del core donde hoy siguen embebidas y al menos un fix pasa a resolverse por config/rule pack sin tocar lógica central.

### BL-066 — T08 — Hardening de adquisición (scope filtrado restante)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-062
- **Referencias:** T08-parcial, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Endurecer el path de adquisición que ya existe con límites y trazabilidad operativa reales: User-Agent configurable, rate limit duro, caching TTL, retries/backoff y manifests con metadatos de fiabilidad.
- **Criterio de aceptación:** Los fetchers dejan rastro de confianza/caché/retries, no usan placeholders inseguros y degradan de forma controlada ante terceros inestables.

### BL-067 — T09 — Factoría de onboarding
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-062, BL-066
- **Referencias:** T09, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Industrializar el onboarding con un único entrypoint que recorra discover, acquire, convert, preflight, draft y reporte de gaps, reduciendo el trabajo manual repetitivo.
- **Criterio de aceptación:** Existe un flujo único de onboarding que funciona al menos para un ticker SEC y uno no-SEC y deja un reporte claro de estado, gaps y siguiente paso.

### BL-068 — T11 — Logging estructurado y métricas por run
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-063
- **Referencias:** T11, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Añadir logging estructurado y artefactos de métricas por run para observar tiempos, ratios y cobertura sin parsear texto libre.
- **Criterio de aceptación:** Cada ejecución deja métricas agregables por run con contexto suficiente para diagnóstico y comparación.

### BL-069 — T12 — Motor de diagnose
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-068
- **Referencias:** T12, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Construir un motor de diagnose que agrupe fallos y gaps por patrón técnico para abrir trabajo de mejora con menos inspección manual.
- **Criterio de aceptación:** El sistema genera un informe de hotspots reutilizable para decidir próximas BL sin revisar ticker por ticker a mano.

### BL-070 — T14 — Separación fixtures vs artefactos runtime
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-062
- **Referencias:** T14, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Separar fixtures versionadas de artefactos runtime y permitir workspaces externos sin ensuciar el repo con outputs generados.
- **Criterio de aceptación:** El runtime puede ejecutarse en workspace externo y el repo deja de depender de artefactos generados para funcionar o testear.

### BL-071 — T15 — Scaffolding y plantillas
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-069, BL-070
- **Referencias:** T15, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Añadir scaffolding y plantillas para tareas, casos y reportes, reduciendo pasos manuales y forzando metadatos mínimos de aceptación, riesgos y validación.
- **Criterio de aceptación:** Crear una nueva tarea o un nuevo caso requiere menos pasos manuales y las plantillas obligan a declarar validación y criterio de cierre.

### BL-072 — Habilitación de paralelismo: criterio `parallel-ready` y proceso operativo
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Governance
- **Validation tier:** governance-only
- **Depende de:** —
- **Referencias:** BL-061, docs/project/KNOWLEDGE_BASE.md
- **Descripción:** Definir el modelo oficial de paralelización mutante para ELSIAN y dejar explícito cuándo el sistema puede considerarse `parallel-ready`. La tarea debe fijar un único proceso operativo, preferentemente con `git worktree + una rama por BL`, incluyendo preflight, criterios go/no-go, surfaces seriales, reglas de write set, rol del padre neutral, integración serial, closeout por BL y criterios de aborto/rollback.
- **Criterio de aceptación:** Existe una definición explícita de `parallel-ready`. Existe un checklist go/no-go antes de lanzar trabajo mutante en paralelo. Queda fijado el proceso end-to-end de creación de worktree/rama, ejecución por agente, validación, auditoría, closeout, integración y commit. Quedan definidas las surfaces que nunca se paralelizan. Queda explícito que la implementación mutante en paralelo sigue deshabilitada mientras no se cumplan al menos los prerrequisitos definidos en esta BL, incluyendo `BL-061`.

### BL-073 — Piloto controlado de paralelización multiagente
- **Prioridad:** MEDIA
- **Estado:** BLOCKED (espera `BL-072` y `BL-061`)
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-072, BL-061
- **Referencias:** BL-059, BL-060, docs/project/KNOWLEDGE_BASE.md
- **Descripción:** Ejecutar un primer piloto real de paralelización mutante con dos BL independientes y write sets disjuntos, usando exclusivamente el proceso definido en `BL-072`. El piloto debe demostrar aislamiento por `git worktree` y rama, integración serial en el padre, cierre independiente por BL y aborto limpio si aparece solape material.
- **Criterio de aceptación:** Se ejecuta un piloto con dos BL válidas y una BL por worktree/rama. Ningún agente sale de su write set. Cada BL pasa `gates -> auditor -> closeout` por separado. La integración se hace en serie y genera un commit por BL. Si aparece conflicto estructural, el piloto aborta sin contaminar `main`. Queda una decisión explícita de mantener, ajustar o descartar el modelo antes de extenderlo a más trabajo.

### BL-084 — Implementar fallback no duplicativo de `finance lease obligation` hacia `total_debt`
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** —
- **Referencias:** DEC-028
- **Descripción:** Implementar en shared-core la policy canónica de `DEC-028`: cuando no exista una señal explícita mejor de `total debt` o `long-term debt`, el sistema podrá sintetizar `total_debt` a partir de `Current portion of finance lease obligation` + `Long-term finance lease obligation` como fallback debt-like. La implementación debe preservar precedencia estricta y no duplicación: si el filing ya expone una línea agregada de deuda totalizada, esa línea gana y los componentes lease/debt no se suman encima. Quedan fuera de alcance semántico `operating lease liabilities`, `lease expense` y `principal payments on finance lease obligation`. Esta BL no reabre BL-076 ni toca truth local; es una ola shared-core nueva para extracción/normalización/ensamblado consistente de `total_debt`.
- **Write set previsto:** `elsian/extract/vertical.py`, `elsian/extract/phase.py`, `config/field_aliases.json`, `config/ixbrl_concept_map.json`, `elsian/assemble/source_map.py`, `tests/unit/test_extract_phase.py`
- **Tests mínimos:** caso tipo ACLS con `current portion of finance lease obligation` + `long-term finance lease obligation` que produzca `total_debt` por fallback cuando no exista línea agregada mejor; negativos explícitos para `operating lease liabilities`, `lease expense` y `principal payments on finance lease obligation`; precedencia cuando exista `total debt` o `long-term debt` explícito; prueba de no duplicación cuando coexistan línea agregada y componentes subyacentes.
- **Validación prevista:** `pytest` targeted sobre `tests/unit/test_extract_phase.py` y cualquier suite unitaria nueva tocada por la ola; smoke de extractor/eval sobre un caso SEC representativo tipo ACLS y, si el cambio toca ensamblado/provenance de `total_debt`, una comprobación targeted del artefacto afectado. No vender cierre global ni reopen de paquetes previos sin evidencia nueva.
- **Criterio de aceptación:** La extracción de `total_debt` incorpora `finance lease obligation` solo como fallback debt-like conforme a `DEC-028`, sin contaminarse con operating lease ni movimientos de cash flow, sin duplicar deuda ya totalizada y con cobertura de tests suficiente para blindar precedencia y no-duplicación.

### BL-077 — Investigar inconsistencias de campos derivados
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Depende de:** BL-075, BL-076
- **Referencias:** DEC-027
- **Descripción:** Investigar caso por caso las inconsistencias de campos derivados detectadas en la auditoría. ACLS: `ebitda` reportado vs `ebit + D&A` difiere hasta 47%. NEXN: `gross_profit` diverge de `ingresos - cost_of_revenue` hasta 18.8%. SONO: `gross_profit` diverge 23.7% en Q3-2023. SOM: `delta_cash` diverge 398% en FY2023. TZOO: `delta_cash` diverge 27–30% en múltiples FY. Para cada caso, determinar si (a) el `expected.json` tiene un valor incorrecto que debe corregirse, (b) la fórmula simplificada no aplica y debe documentarse, o (c) falta o está mal capturado un campo componente.
- **Criterio de aceptación:** Cada `DERIVED_INCONSISTENT` queda clasificado como (a), (b) o (c). Los casos (a) quedan corregidos. Los casos (b) y (c) quedan documentados. Se genera un mini-informe en `docs/reports/DERIVED_INCONSISTENCIES_RESOLUTION.md`.

### BL-005 — Expandir cobertura de tickers (diversidad de mercados/formatos)
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-067
- **Referencias:** DEC-015, T09, docs/project/PLAN_IMPLEMENTACION_FILTRADO.md
- **Descripción:** Añadir tickers nuevos no por volumen, sino por diversidad real de mercados, reguladores, sectores y formatos. Debe ejecutarse solo cuando las prioridades técnicas inmediatas estén suficientemente cerradas y cada ticker nuevo cubra un gap concreto que hoy no está representado. Nota de subordinación: la ejecución efectiva de BL-005 queda subordinada a BL-067 (T09 — Factoría de onboarding).
- **Criterio de aceptación:** Cada ticker nuevo validado cubre un gap documentado de diversidad y no introduce regresiones en el conjunto existente.

---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
