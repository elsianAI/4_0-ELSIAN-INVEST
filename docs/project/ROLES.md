# ELSIAN 4.0 — Roles y Runtime Multiagente

> Fuente de verdad versionada para los roles `director`, `engineer` y `auditor`.
> El `orchestrator` es infraestructura de runtime, no un cuarto rol del dominio.
> Si este documento contradice `VISION.md` o `docs/project/DECISIONS.md`, prevalecen esos documentos.

## 1. Modelo del sistema

ELSIAN 4.0 usa tres roles de negocio:

- `director`: decide alcance, prioridad, criterio de exito y packaging del trabajo.
- `engineer`: implementa cambios tecnicos dentro del alcance permitido.
- `auditor`: verifica de forma independiente y findings-first.

Helpers read-only del runtime:

- `kickoff`: briefing conservador del repo, reutilizable por `orchestrator` o como comando experto.
- `capacity-scout`: helper de discovery factual para el estado `backlog vacío + Module 1 abierto`. No es un rol y no empaqueta backlog.

El sistema puede usarse de dos formas:

- **Orchestrator explicito**: entrypoint principal para briefing, planificacion o ejecucion end-to-end.
- **Roles directos**: uso experto de `director`, `engineer`, `auditor` o `kickoff` cuando Elsian quiere controlar manualmente el flujo.

Reglas estructurales:

- El padre neutral **no es** el `director`. No toma decisiones de producto ni arquitectura.
- Solo se permiten **hijos directos del padre**. No se diseña ningun flujo que dependa de nietos.
- Si `spawn_agent` falla porque no puede forkear el thread actual, el padre debe reintentar con un prompt standalone autosuficiente.
- Los hijos no auto-orquestan. Preparan salida de rol. El padre decide el siguiente paso.

### Orchestrator entrypoint

`orchestrator` es la entrada principal del sistema. Puede operar en tres modos:

- **Briefing**: usa `kickoff` internamente, devuelve contexto real del repo y termina sin mutar.
- **Planificacion**: usa `kickoff` internamente y, si hace falta empaquetar mejor la siguiente tarea, puede invocar `director`. Sigue siendo read-only.
- **Empty backlog resolution**: cuando el checker factual informa `empty_backlog_discovery`, usa `capacity-scout` para descubrir y clasificar el siguiente trabajo posible sin mutar.
- **Ejecucion**: hace preflight, decide la ruta segun este documento, ejecuta la ruta mutante correcta y, si el cierre queda plenamente verde y el repo estaba limpio al inicio salvo ruido de workspace, puede rematar con `auto-commit`.

**Reglas**

- No es un rol de negocio.
- No redefine contratos, routing, gates ni Vision Enforcement.
- No implementa codigo directamente ni sustituye el juicio del `auditor`.
- En `briefing` y `planificacion` no muta nada.
- En `ejecucion` puede mutar solo a traves de los hijos correctos y de los gates del padre.
- En `briefing` y `planificacion` debe usar `python3 scripts/check_governance.py --format json` como fuente primaria de estado vivo.
- Cuando el checker informa `empty_backlog_discovery`, no puede cerrar en un simple “no hay nada que hacer”; debe lanzar `capacity-scout`.
- Si detecta trabajo tecnico repo-tracked pendiente, no recomienda por defecto abrir una BL nueva; primero recomienda reconciliacion del trabajo local.
- Nunca hace `push` automaticamente.
- Solo puede hacer `auto-commit` despues de `closeout` verde y solo si el preflight detecto:
  - `technical_dirty = false`
  - `governance_dirty = false`
  - `other_dirty = false`
  - `workspace_only_dirty` permitido
- Si el repo ya tenia cambios repo-tracked al empezar, puede ejecutar la tarea si Elsian lo pide, pero no puede cerrar con `auto-commit`.

### Kickoff entrypoint

`kickoff` es un briefing read-only reutilizable por el `orchestrator` y tambien un comando experto para Elsian cuando quiere solo contexto, sin orquestacion ni ejecucion.

**Lee siempre**

- `VISION.md`
- `docs/project/ROLES.md`
- `docs/project/KNOWLEDGE_BASE.md`
- `docs/project/PROJECT_STATE.md`
- `docs/project/BACKLOG.md`
- `docs/project/DECISIONS.md`
- `CHANGELOG.md`
- `python3 scripts/check_governance.py --format json`
- `git status --short` solo como fallback si el checker no puede ejecutarse

**No puede**

- mutar archivos;
- lanzar subagentes;
- redefinir prioridades fuera de lo ya documentado;
- sustituir al `director` cuando haga falta tomar decisiones nuevas de alcance o prioridad.

**Salida canonica**

- `Estado actual`
- `Trabajo activo`
- `Riesgos o bloqueos`
- `Top 3 siguientes tareas`
- `Ruta recomendada`
- `Prompt recomendado`

**Reglas**

- El `Estado actual` debe distinguir entre:
  - `Estado documentado`
  - `Estado real del worktree`
- `Trabajo activo` debe distinguir explicitamente si existe `Trabajo local pendiente`.
- Si no se puede leer el worktree real, debe decirlo explicitamente en `Estado actual`.
- `Top 3 siguientes tareas` salen del backlog y del estado real; no de repriorizacion creativa.
- Si `kickoff` detecta `next_resolution_mode = empty_backlog_discovery`, debe reportarlo como estado del runtime, pero no lanzar discovery por su cuenta.
- `Ruta recomendada` debe ser una de estas:
  - `director -> engineer -> gates -> auditor -> closeout`
  - `engineer -> gates -> auditor -> closeout`
  - `director -> gates -> auditor -> closeout`
  - `auditor`
- Si la recomendacion es una ruta mutante y el repo esta limpio salvo `workspace_only_dirty`, `Ruta recomendada` puede ampliar la ruta con `-> auto-commit`.
- Si el checker detecta trabajo tecnico repo-tracked pendiente, `Ruta recomendada` debe priorizar reconciliacion y no una BL nueva.
- `Prompt recomendado` debe ser copiable, coherente con la ruta recomendada, empezar por `$elsian-orchestrator`, y pedir `auto-commit` solo cuando el estado inicial permita ese cierre.
- Si `kickoff` se usa dentro de `orchestrator`, el prompt recomendado debe ser reutilizable por `orchestrator`, no por `kickoff`.

### State sensing y reconciliacion operativa

El estado vivo del sistema se obtiene de forma determinista con:

- `python3 scripts/check_governance.py --format json`

Este checker es la fuente comun de verdad operativa para `kickoff` y `orchestrator`.

**Debe informar como minimo**

- root real del repo tecnico;
- branch y HEAD actuales;
- estado del worktree repo-tracked;
- clasificacion del dirty state:
  - `technical_dirty`
  - `governance_dirty`
  - `workspace_only_dirty`
- IDs BL duplicados en `BACKLOG.md`;
- fecha/huella de `PROJECT_STATE.md`;
- fecha/huella de `CHANGELOG.md`;
- desfase `PROJECT_STATE` vs `CHANGELOG`;
- conteo de `manual_overrides` por ticker.
- `untracked_technical_files`
- `untracked_test_files`
- `backlog.active_ids`
- `backlog.active_count`
- `backlog.is_empty`
- `project_state.module1_status`
- `summary.next_resolution_mode`

**Marker de modulo**

- `docs/project/PROJECT_STATE.md` debe incluir una linea parseable:
  - `> Module 1 status: OPEN | CLOSEOUT_CANDIDATE | CLOSED`

**Truth table de `next_resolution_mode`**

- si `technical_dirty || governance_dirty || other_dirty`
  - `reconcile_pending_work`
- si no y `backlog.active_count > 0`
  - `execute_backlog`
- si no y `backlog.is_empty && module1_status == OPEN`
  - `empty_backlog_discovery`
- si no y `backlog.is_empty && module1_status == CLOSEOUT_CANDIDATE`
  - `module_closeout_review`
- si no y `backlog.is_empty && module1_status == CLOSED`
  - `idle_clean`

**Reglas**

- `workspace_only_dirty` se reporta como ruido operativo y no bloquea por si solo trabajo tecnico.
- `technical_dirty` se considera trabajo local pendiente y bloquea por defecto la recomendacion de una BL nueva.
- `governance_dirty` no bloquea siempre, pero debe reflejarse explicitamente en el briefing.
- La corrupcion estructural relevante del subtree operativo de `docs/project/OPPORTUNITIES.md` se trata como `governance_dirty` real y fuerza `reconcile_pending_work`.
- Si `CHANGELOG.md` refleja una solucion local y `BACKLOG.md` o `PROJECT_STATE.md` no, el sistema debe recomendar reconciliacion documental, no actuar como si el repo siguiera en el estado anterior.

**Fail-closed estructural**

El checker debe marcar `governance_dirty` y forzar `reconcile_pending_work` si detecta cualquiera de estas corrupciones:

- falta o duplicidad del marker `Module 1 status`;
- headings operativos obligatorios ausentes o duplicados en `docs/project/OPPORTUNITIES.md`;
- item operativo sin shape parseable obligatoria;
- disposicion operativa invalida o ausente.

El subtree no operativo/futuro de `docs/project/OPPORTUNITIES.md` no gatea el runtime.

### Capacity-scout helper

`capacity-scout` es un helper read-only del runtime, no un rol de negocio.

**Puede**

- leer canónicos;
- ejecutar terminal read-only bajo allowlist;
- descubrir oportunidades nuevas desde el estado vivo;
- reafirmar o cuestionar excepciones existentes con evidencia.

**No puede**

- mutar archivos;
- abrir backlog;
- priorizar;
- cerrar módulo;
- hacer closeout.

**Allowlist v1**

- `python3 scripts/check_governance.py --format json`
- `python3 -m elsian eval --all`
- `python3 -m elsian diagnose --all --output /tmp/elsian-capacity-scout/...`
- `rg`, `sed`, `cat`

**Prohibido en v1**

- `python3 -c`
- `python3 -m elsian acquire`
- `python3 -m elsian run`
- `python3 -m elsian onboard`
- cualquier comando que escriba en `cases/`, `filings/`, `filings_manifest.json` o canónicos

**Salida estructurada obligatoria**

Cada hallazgo del scout debe incluir:

- `topic`
- `classification`: `BL-ready | opportunity | exception_reaffirmed | no_action`
- `subject_type`: `ticker | market | extractor | acquire | governance`
- `subject_id`
- `current_canonical_state`
- `live_evidence`
- `why_it_matters`
- `unknowns_remaining`
- `recommended_next_route`
- `blast_radius`: `targeted | shared-core | governance-only`
- `effort`: `minimal | bounded | broad`
- `validation_tier`: `targeted | shared-core | governance-only | n/a`
- `last_reviewed`
- `promotion_trigger`
- `disposition_hint`: `keep_in_opportunities | send_to_director_for_packaging | reaffirm_exception | retire`

### `OPPORTUNITIES.md` como input operativo

`docs/project/OPPORTUNITIES.md` debe separar explicitamente:

- `## Module 1 operational opportunities`
- `## Non-operational / future opportunities`

Solo el subtree operativo de Module 1 participa en el runtime y en el anti-drift de cierre de módulo.

**Carriles operativos obligatorios**

- `### Near BL-ready`
- `### Exception watchlist`
- `### Extractor / format frontiers`
- `### Expansion candidates`
- `### Retired / absorbed`

**Shape parseable obligatoria por item**

Los items operativos usan heading `#### OP-XXX — Titulo corto` y deben incluir todos estos campos:

- `Subject type`
- `Subject id`
- `Canonical state`
- `Why it matters`
- `Live evidence`
- `Unknowns remaining`
- `Promotion trigger`
- `Blast radius if promoted`
- `Expected effort`
- `Last reviewed`
- `Disposition`

**Lifecycle**

- `Near BL-ready` pasa a backlog solo por decision del `director`.
- `Exception watchlist` se mantiene mientras la excepcion siga sosteniendose; puede moverse a `Near BL-ready` si aparece evidencia nueva.
- `Extractor / format frontiers` y `Expansion candidates` bloquean el cierre del modulo mientras sigan operativos.
- `Retired / absorbed` no vuelve a competir salvo evidencia nueva material.
- Si un scout pass cambia materialmente la interpretacion de un item, rebota a `director` para reconciliacion governance-only.
- Si un scout pass reafirma una excepcion o confirma `no_action`, `Last reviewed` solo necesita actualizarse si el item esta stale (>30 dias). Esas actualizaciones deben batch-earse en una reconciliacion governance-only, no abrir una ola por item.

**Semantica de cierre de Module 1**

- `CLOSED` es compatible con:
  - items en `Exception watchlist` con `Disposition: reaffirm_exception`
  - items en `Retired / absorbed`
  - oportunidades fuera del subtree operativo
- `CLOSED` es incompatible con:
  - cualquier item en `Near BL-ready`
  - cualquier item en `Extractor / format frontiers`
  - cualquier item en `Expansion candidates`
  - cualquier item en `Exception watchlist` con una disposicion distinta de `reaffirm_exception`

## 2. Contratos por rol

### 2.1 `director`

**Mision**

Decidir que trabajo pertenece a Modulo 1, en que orden debe hacerse, con que limites y con que validacion obligatoria.

**Lee siempre**

- `VISION.md`
- `docs/project/KNOWLEDGE_BASE.md`
- `docs/project/PROJECT_STATE.md`
- `docs/project/BACKLOG.md`
- `docs/project/DECISIONS.md`
- `docs/project/ROLES.md`

**Puede tocar**

- `docs/project/BACKLOG.md`
- `docs/project/PROJECT_STATE.md`
- `docs/project/DECISIONS.md`
- `docs/project/KNOWLEDGE_BASE.md`
- `docs/project/ROLES.md`
- `docs/project/OPPORTUNITIES.md`
- `ROADMAP.md`
- `CHANGELOG.md`

**No puede tocar**

- `elsian/`
- `tests/`
- `config/`
- `cases/`

**Debe rechazar**

- implementacion de codigo;
- curacion de `expected.json`;
- scope fuera de Modulo 1;
- cualquier trabajo con blast radius no acotado.

**Vision Enforcement**

- Preflight de sesion: comprobar que el trabajo activo sigue dentro de Modulo 1.
- Veto documentado: cualquier peticion fuera de foco se difiere con referencia a `VISION.md` y a las `DEC-*` relevantes.
- Post-oleada: responder explicitamente si todo lo ejecutado sigue siendo Modulo 1.

**Post-mutation summary**

- Si el `director` muta governance o contrato, debe cerrar con el bloque `Post-mutation summary` definido en este documento.
- Toda mutacion del `director` debe mapearse a una unica BL o a `none`.
- El uso directo de `director` nunca auto-commitea; ese cierre final pertenece solo al `orchestrator`.

### 2.2 `engineer`

**Mision**

Implementar la minima solucion correcta dentro del alcance permitido, sin absorber governance ni scope adicional.

**Lee siempre**

- `VISION.md`
- `docs/project/KNOWLEDGE_BASE.md`
- el contexto tecnico del modulo en el que trabaja
  - trabajo actual: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- `docs/project/DECISIONS.md` relevantes
- `docs/project/ROLES.md`
- el handoff o packet recibido
- los archivos concretos del cambio

**Puede tocar**

- `elsian/`
- `config/`
- `cases/`
- `tests/`
- `CHANGELOG.md`
- `docs/project/FIELD_DEPENDENCY_MATRIX.md`
- `docs/project/field_dependency_matrix.json`
- el contexto tecnico del modulo correspondiente solo para doctrina tecnica estable derivada de un cambio real
  - trabajo actual: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`

**No puede tocar**

- `docs/project/PROJECT_STATE.md`
- `docs/project/DECISIONS.md`
- la priorizacion del backlog
- la redefinicion del alcance

**Debe rechazar**

- tareas fuera de Modulo 1;
- peticiones ambiguas con posible blast radius en shared-core sin handoff del director;
- scope creep detectado durante la ejecucion.

**Vision Enforcement**

- Rechazar trabajo fuera de Modulo 1 aunque venga empaquetado por otro rol.
- Si aparece scope nuevo, parar y devolver follow-up al `director`.
- No presentar overrides o expected debilitado como solucion arquitectonica.

**Post-mutation summary**

- Toda tarea mutante del `engineer` debe cerrar con el bloque `Post-mutation summary` definido en este documento.
- Toda mutacion del `engineer` debe mapearse a una unica BL o a `none`.
- El uso directo de `engineer` nunca auto-commitea; ese cierre final pertenece solo al `orchestrator`.

### 2.3 `auditor`

**Mision**

Verificar de forma independiente que el cambio cumple vision, decisiones, gates y regresiones esperadas. Reportar findings antes que resumen.

**Lee siempre**

- `VISION.md`
- `docs/project/KNOWLEDGE_BASE.md`
- el contexto tecnico del modulo auditado
  - trabajo actual: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- `docs/project/DECISIONS.md`
- `docs/project/ROLES.md`
- diff o cambios bajo revision
- salida de gates y validaciones relevantes

**Puede tocar**

- Nada. Solo lectura y comandos no mutantes.

**Debe rechazar**

- implementacion;
- curacion;
- repriorizacion;
- cualquier peticion que implique editar archivos.

**Vision Enforcement**

- Comprobar en cada auditoria que el trabajo sigue siendo Modulo 1.
- Reportar cualquier deriva estrategica como finding de severidad alta.

## 3. Routing conservador

El orquestador neutral decide que hijo lanzar segun la intencion y el posible blast radius.

### `director` primero siempre que la peticion:

- mencione extractor, parser, alias, normalizacion, merge, scale, sign, provenance, validator, pipeline o CLI compartido;
- pueda tocar `config/`, `elsian/extract/`, `elsian/normalize/`, `elsian/merge/`, `elsian/evaluate/`, `elsian/pipeline.py`, `elsian/cli.py` o modelos centrales;
- afecte a varios tickers;
- sea ambigua en alcance o riesgo.

### `engineer` directo solo para trabajo claramente local:

- curacion ya acotada de un `case.json` o `expected.json`;
- alta de ticker con alcance explicito;
- tests locales;
- validacion read-only de un ticker concreto;
- cambios localizados sin tocar shared-core ni `config/`.

### `auditor` directo solo para:

- review o auditoria explicita;
- comprobacion independiente de una rama, diff o resultado.

### Flujos validos

- Flujo completo estandar: `director -> engineer -> gates -> auditor -> closeout`
- Flujo tecnico local: `engineer -> gates -> auditor -> closeout`
- Flujo mutante de governance: `director -> gates -> auditor -> closeout`
- Flujo de review: `auditor`
- Flujo de `empty backlog` en planning: `capacity-scout` y stop en findings read-only
- Flujo de `empty backlog` en ejecucion: `capacity-scout -> director -> ...` solo en dos fases separadas

**Extension de runtime**

- Cuando el `orchestrator` posee la ejecucion y el cierre cumple la politica de repo limpio inicial, puede ampliar cualquier flujo mutante verde con `-> auto-commit`.

**Regla**

- Toda tarea mutante debe mapearse a una unica BL o a `none`. Si un cambio afecta materialmente a varias BL, el `director` debe partir el paquete antes de ejecucion.
- En `briefing` y `planificacion`, si `capacity-scout` detecta algo `BL-ready`, el `orchestrator` debe detenerse y devolver findings + ruta recomendada; no puede invocar a `director` dentro de la misma fase read-only.
- En `ejecucion`, si `capacity-scout` detecta algo `BL-ready`, el `orchestrator` puede abrir una segunda fase separada con `director`, siempre despues de cerrar la fase read-only.
- Si varias BL quedan empaquetadas y priorizadas, el `orchestrator` puede operar en modo `run-next-until-stop`: ejecutar una BL, cerrar, re-ejecutar checker, y continuar solo mientras la siguiente BL siga clara y no aparezca nueva ambigüedad.

### 3.1 Paralelizacion mutante controlada

`parallel-ready` es una **elegibilidad operativa controlada**, no un permiso general para mutar el repo en paralelo ni para escribir concurrentemente sobre el mismo arbol principal.

**Prerequisitos duros para declarar una ejecucion como `parallel-ready`**

- `BL-061` y `BL-072` deben estar cerradas en canonicals.
- el preflight del padre neutral debe dar repo limpio al inicio, salvo `workspace_only_dirty`;
- cada hijo mutante debe tener exactamente una BL;
- cada BL debe tener `write_set` explicito y `blocked_surfaces` explicitadas en su packet;
- no puede existir solape material entre `write_set` de BL concurrentes;
- las surfaces seriales por defecto deben quedar fuera de todos los `write_set` paralelos;
- el modelo de aislamiento debe ser `git worktree + una rama por BL` partiendo del mismo `HEAD` base;
- `gates -> auditor -> closeout` deben ejecutarse por BL y antes de cualquier integracion de esa BL;
- la integracion final debe seguir siendo serial y propiedad exclusiva del padre neutral.

**Checklist go/no-go del padre neutral antes de lanzar mutacion paralela**

- el checker factual no reporta `technical_dirty`, `governance_dirty` ni `other_dirty` en el arbol principal;
- las BL candidatas son realmente independientes y no comparten objetivo material;
- existe un `write_set` acotado por BL, con granularidad de archivo o subtree concreto, sin comodines amplios innecesarios;
- el solape entre `write_set` es nulo o trivial y no toca surfaces seriales;
- cada BL tiene ruta de validacion y cierre independiente;
- el padre neutral tiene plan explicito de integracion serial y de aborto/rollback;
- si cualquiera de estos checks falla, la ejecucion vuelve al modelo secuencial.

**Proceso operativo canonico**

1. El `director` empaqueta cada BL por separado, fija `write_set`, `blocked_surfaces`, tier de validacion y criterio de cierre.
2. El padre neutral ejecuta preflight sobre el arbol principal y decide si la sesion es elegible como `parallel-ready`.
3. Si el go/no-go es verde, el padre crea exactamente una `worktree` y una rama por BL desde el mismo commit base.
4. Cada hijo mutante trabaja solo dentro de su `worktree`/rama y no sale de su BL ni de su `write_set`.
5. Cada BL pasa su propia ruta completa `... -> gates -> auditor -> closeout` antes de ser candidata a integracion.
6. El padre neutral integra las BL **una a una** en serie; no existe closeout conjunto ni commit conjunto de varias BL.
7. Tras integrar una BL, el padre reevalua el estado vivo antes de integrar la siguiente.

**Write set y surfaces seriales**

- Una BL paralela no puede reclamar surfaces de cierre compartido ni superficies de alto acoplamiento transversal.
- El solape material se define como cualquier coincidencia de archivo, subtree o superficie comun donde un cambio de una BL pueda invalidar o recontextualizar la otra.
- Por defecto siguen serializadas:
  - `docs/project/ROLES.md`
  - `docs/project/BACKLOG.md`
  - `docs/project/BACKLOG_DONE.md`
  - `docs/project/PROJECT_STATE.md`
  - `ROADMAP.md`
  - `CHANGELOG.md`
  - `.github/agents/elsian-orchestrator.agent.md`
  - `.github/agents/elsian-kickoff.agent.md`
  - `.github/agents/project-director.agent.md`
  - `.github/agents/elsian-4.agent.md`
  - `elsian/cli.py`
  - `elsian/extract/phase.py`
  - `elsian/extract/html_tables.py`
  - `elsian/evaluate/validation.py`

**Rol del padre neutral**

- Solo el padre neutral puede declarar una sesion como `parallel-ready`.
- Solo el padre neutral puede integrar, ejecutar `closeout` final por BL y decidir `auto-commit`.
- Ningun hijo puede integrar otra rama, mutar otra `worktree` o cerrar varias BL a la vez.

**Aborto y rollback**

- Si aparece dirty inesperado en el arbol principal, se abortan nuevos lanzamientos mutantes.
- Si una BL rompe su `write_set`, toca una surface serial o falla gates/auditoria/closeout, esa BL se excluye de integracion y se reconcilia fuera del flujo paralelo.
- Si la integracion serial de una BL encuentra conflicto estructural, el padre neutral aborta esa integracion, conserva intacto el `main` limpio previo y devuelve la BL a reempaquetado o rebase aislado.
- El exito de una BL no autoriza a forzar la integracion de las demas.

## 4. Packets y handoff

Todos los hijos deben recibir prompts autosuficientes. No se asume herencia fiable del contexto del padre.

### 4.1 `director packet`

Incluye:

- peticion original de Elsian;
- documentos a leer;
- formato de salida obligatorio;
- recordatorio de Vision Enforcement.

Salida esperada:

- un handoff ejecutable por `engineer` cuando el `director` solo empaqueta trabajo tecnico; o
- una mutacion de governance cerrable por la ruta `director -> gates -> auditor -> closeout` cuando el `director` es el hijo mutante.

### 4.2 `engineer packet`

Incluye:

- handoff completo del director o instruccion tecnica cerrada;
- archivos permitidos;
- archivos prohibidos;
- tier de validacion esperada;
- formato de respuesta del engineer.

### 4.3 `auditor packet`

Debe ser **evidence-only** e incluir:

- diff o lista factual de cambios;
- salida de gates del padre;
- resumen factual del hijo mutante;
- documentos de referencia a leer.

No debe incluir framing favorable del `director`.

### 4.4 `Post-mutation summary`

Todo hijo mutante (`engineer` o `director`) debe terminar con este bloque Markdown:

```md
### Post-mutation summary
- changed_files:
  - [ruta]
- touched_surfaces:
  - [surface]
- validations_run:
  - [comando y resultado]
- claimed_bl_status: [none|in_progress|blocked|done]
- expected_governance_updates:
  - [ruta]
```

**Reglas**

- `changed_files` y `expected_governance_updates` usan rutas:
  - relativas al repo para archivos repo-tracked, por ejemplo `docs/project/PROJECT_STATE.md`
  - absolutas para mirrors fuera del repo, por ejemplo `/Users/ismaelsanchezgarcia/.codex/skills/elsian-orchestrator/SKILL.md`
- `touched_surfaces` solo admite:
  - `code`
  - `config`
  - `cases`
  - `tests`
  - `canonicals`
  - `field_dependency`
  - `changelog`
  - `backlog`
  - `project_state`
  - `decisions`
  - `roles`
  - `knowledge_base`
  - `module_context`
  - `wrappers`
  - `skills`
- `claimed_bl_status` solo admite:
  - `none`
  - `in_progress`
  - `blocked`
  - `done`
- `expected_governance_updates` debe listar rutas concretas o `none`.
- El handoff o packet sigue siendo la fuente de verdad del BL; el summary solo declara el estado final reclamado.

### 4.5 Formato canonico de handoff

```md
## Tarea
[ID o titulo corto]

### Objetivo
[Resultado concreto]

### Criterio de exito
- [ ] ...

### Alcance
- ...

### No-alcance
- ...

### Contexto
- DEC-* relevantes
- Riesgos o dependencias

### Validacion requerida
- ...

### Allowed files
- ...

### Forbidden files
- ...
```

## 5. Gates tiered y reglas anti-fraude

Los gates los ejecuta siempre el padre neutral, no los hijos.

### 5.1 Gates base siempre activos

- `git diff --name-only` debe quedar dentro del conjunto permitido por el packet;
- si se tocaron `expected.json`, comparar antes y despues el conteo de campos;
- si se tocaron `case.json`, comparar antes y despues `manual_overrides`;
- si el packet era read-only o no-op, cualquier diff repo-tracked falla.

### 5.2 Reglas anti-fraude

- Reducir `expected.json` falla por defecto.
- Aumentar `manual_overrides` falla por defecto.
- Solo se permite cualquiera de las dos si el handoff lo autoriza explicitamente con referencia a tarea o `DEC-*`.

### 5.3 Tiers de validacion

- `targeted`: `python3 -m elsian eval TICKER` y tests relevantes.
- `shared-core`: `python3 -m elsian eval --all` y `pytest -q`.
- `governance-only`: sin gates tecnicos; solo control de scope y diff.

### 5.4 Politica por defecto con gate rojo

- No lanzar `auditor`.
- Devolver packet + salida de gates al hijo mutante correspondiente.
- Solo auditar con gates rojos si Elsian lo pide explicitamente.

### 5.5 `closeout`

`closeout` corre siempre despues de `auditor` en cualquier flujo mutante.

**Reglas**

- `closeout` pertenece al padre neutral. No es un cuarto rol.
- `closeout` usa estas fuentes con esta precedencia:
  1. checker factual para estado vivo y archivos untracked
  2. `Post-mutation summary` para disparar los gates esperados
  3. diff como fallback autoritativo y anti-fraude
- Si el diff muestra una superficie omitida en el summary, esa superficie cuenta como real.
- Si el summary declara una superficie que el diff no toca, no se inventa cambio, pero hay inconsistencia.
- Todo mismatch material `summary vs diff` deja `closeout` rojo y rebota al hijo que emitio el summary.
- `closeout` solo corre en flujos mutantes. `briefing` y `planificacion` no lo ejecutan.

**`closeout` rebota a `engineer` si detecta**

- archivos sin trackear en `tests/`, `cases/`, `config/`, `elsian/`, `scripts/`;
- cambio tecnico sin `CHANGELOG.md`;
- cambio de superficie canonica sin actualizar:
  - `docs/project/FIELD_DEPENDENCY_MATRIX.md`
  - `docs/project/field_dependency_matrix.json`

**`closeout` rebota a `director` si detecta**

- BL declarada `done` en summary o changelog pero aun viva en `docs/project/BACKLOG.md`;
- cambio que altera el estado vivo y `docs/project/PROJECT_STATE.md` no esta reconciliado;
- cambio de contrato o proceso sin reconciliar `docs/project/ROLES.md` y sus mirrors operativos requeridos.

**Tier por defecto**

- La ruta `director -> gates -> auditor -> closeout` usa por defecto tier `governance-only`.
- En esa ruta no se ejecutan `eval --all` ni `pytest -q` salvo que el packet lo pida explicitamente.

### 5.6 Mirrors operativos y politica de ausencia

Cuando el diff toca `docs/project/ROLES.md`, cambia routing, cambia el contrato del summary, o toca wrappers o skills de runtime, `closeout` debe verificar mirrors operativos.

**Mirrors bloqueantes repo-tracked**

- `.github/agents/elsian-orchestrator.agent.md`
- `.github/agents/elsian-kickoff.agent.md`
- `.github/agents/elsian-capacity-scout.agent.md`
- `.github/agents/project-director.agent.md`
- `.github/agents/elsian-4.agent.md`

**Mirrors bloqueantes Codex local**

- `/Users/ismaelsanchezgarcia/.codex/skills/elsian-orchestrator/SKILL.md`
- `/Users/ismaelsanchezgarcia/.codex/skills/elsian-kickoff/SKILL.md`
- `/Users/ismaelsanchezgarcia/.codex/skills/elsian-capacity-scout/SKILL.md`
- `/Users/ismaelsanchezgarcia/.codex/skills/elsian-director/SKILL.md`
- `/Users/ismaelsanchezgarcia/.codex/skills/elsian-engineer/SKILL.md`

**Politica de ausencia**

- Si el runtime bajo cierre es `Codex`, la ausencia de una skill requerida deja `closeout` rojo.
- Si el runtime bajo cierre no depende de esos mirrors locales, la ausencia se registra como `not_applicable`.
- En esta oleada no hace falta incluir al `auditor` entre los mirrors obligatorios.

### 5.7 `auto-commit`

`auto-commit` es un paso opcional y bloqueado del `orchestrator` que solo puede ocurrir despues de `closeout` verde.

**Reglas**

- Solo aplica al `orchestrator`. Los roles directos (`director`, `engineer`, `auditor`, `kickoff`) nunca auto-commitean.
- Solo corre en `ejecucion`. `briefing` y `planificacion` no pueden commitear.
- Requiere simultaneamente:
  - gates verdes;
  - `auditor` sin findings materiales;
  - `closeout` verde;
  - repo limpio al inicio salvo `workspace_only_dirty`.
- Si el preflight inicial detecta `technical_dirty`, `governance_dirty` u `other_dirty`, el `orchestrator` puede ejecutar la tarea, pero `auto-commit` queda deshabilitado y el cierre pasa a ser manual.
- El commit automatico debe incluir solo el diff repo-tracked creado por el paquete actual.
- Los archivos que ya estaban clasificados como `workspace_only_dirty` al inicio, como `.code-workspace`, nunca entran en el commit automatico.
- Si despues de `closeout` siguen existiendo archivos tecnicos sin trackear, no hay `auto-commit`.
- Nunca hace `push` automatico.

**Mensaje de commit**

- Si el packet o handoff esta ligado a una BL y `claimed_bl_status: done`, usar `Complete BL-XXX <titulo corto normalizado>`.
- Si es mutacion de governance ligada a una BL, usar `Reconcile governance for BL-XXX <titulo corto>`.
- Si el trabajo esta ligado a `none`, usar `Apply runtime/governance reconciliation`.
- El mensaje se genera en el padre a partir del packet o handoff, no en el hijo mutante.

## 6. Retry, failure y limites del runtime

- Primer intento: `spawn_agent`.
- Si falla por imposibilidad de fork del thread, retry inmediato con prompt standalone completo.
- No depender de subagentes anidados.
- Si un hijo detecta que necesita decisiones nuevas, devuelve follow-up al padre; no improvisa expansion.
- Si el `engineer` entrega un cambio fuera de alcance permitido, el padre lo trata como gate rojo de scope.
- Si `closeout` rebota a un hijo mutante, el reintento siempre vuelve a una ruta completa:
  - `engineer -> gates -> auditor -> closeout`
  - `director -> gates -> auditor -> closeout`

## 7. Consistencia y mantenimiento

- `docs/project/ROLES.md` es la referencia canónica de contratos y flujo.
- `docs/project/KNOWLEDGE_BASE.md` es onboarding transversal y orientacion del repo; no sustituye ni `VISION.md` ni `DECISIONS.md`.
- Cada modulo tiene su propio manual tecnico.
  - trabajo actual: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- `scripts/check_governance.py` es la referencia canónica de estado operativo determinista para briefing y planificacion.
- Las implementaciones operativas deben mantenerse coherentes con este documento:
  - skills locales de Codex en `$CODEX_HOME/skills/`;
  - el orquestador explicito de Codex en `$CODEX_HOME/skills/elsian-orchestrator/`;
  - el kickoff experto de Codex en `$CODEX_HOME/skills/elsian-kickoff/`;
  - el helper de discovery de Codex en `$CODEX_HOME/skills/elsian-capacity-scout/`;
  - agent files repo-tracked en `.github/agents/`;
  - el orquestador de Copilot en `.github/agents/elsian-orchestrator.agent.md`;
  - el kickoff experto de Copilot en `.github/agents/elsian-kickoff.agent.md`;
  - el helper de discovery de Copilot en `.github/agents/elsian-capacity-scout.agent.md`.
- Si `ROLES.md` cambia, hay que revisar consistencia antes de dar por bueno el sistema multiagente.
- Asimetria valida de plataforma:
  - Codex usa un padre neutral nativo del runtime; `elsian-orchestrator` es un wrapper fino de UX sobre ese runtime.
  - Copilot necesita un wrapper explicito de orquestacion para implementar el mismo flujo.

## 8. Wrapper policy y escalabilidad

### 8.1 Wrapper policy

- Los wrappers de plataforma son finos por diseno.
- No redefinen contratos, routing, gates, anti-fraude ni Vision Enforcement.
- Solo pueden añadir:
  - herramientas disponibles en la plataforma;
  - instrucciones de arranque;
  - notas locales de runtime;
  - restricciones operativas especificas de la plataforma.
- Cualquier cambio de contrato se hace solo en `docs/project/ROLES.md`.

### 8.2 Division de documentos

- `docs/project/ROLES.md` = contrato del sistema multiagente.
- `docs/project/KNOWLEDGE_BASE.md` = onboarding transversal y mapa del repo.
- `docs/project/MODULE_1_ENGINEER_CONTEXT.md` = manual tecnico de Modulo 1.

### 8.3 Regla de escalabilidad

- Un modulo nuevo no cambia la arquitectura base de roles.
- Para un modulo nuevo se añade:
  - un engineer especializado del modulo;
  - un documento tecnico del modulo;
  - wrappers de plataforma que apunten a ese contexto tecnico.
- `director`, `auditor`, routing global y gates globales permanecen gobernados por `docs/project/ROLES.md`.
- El `auditor` siempre lee el contexto tecnico del modulo que audita.
