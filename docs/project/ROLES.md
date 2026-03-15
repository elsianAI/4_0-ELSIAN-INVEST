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
- En `planificacion`, si el checker informa `empty_backlog_discovery`, `kickoff` es obligatorio pero no terminal: el parent debe ejecutar `kickoff` y despues `capacity-scout` antes de cerrar la fase read-only.
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

### Runtime surfaces y ciclo de vida

**Superficies duras**

- `docs/project/BACKLOG.md` sigue siendo la unica cola ejecutable y ahora debe persistir `Work kind` por BL.
- `docs/project/PROJECT_STATE.md` puede persistir `Discovery Baseline`, pero no crea cola ejecutable ni cola paralela.
- `docs/project/OPPORTUNITIES.md` sigue siendo la superficie persistida de frontera, excepciones y `Near BL-ready` todavia no empaquetadas.

**Packet status**

- `3ffc88e` deja cerrada y estabilizada la Tranche A del Nivel 1.
- Lo que sigue es **Packet B — Investigacion y expansion como trabajo de primer nivel**.
- Packet B mantiene las garantias de Tranche A, pero reescribe de forma coordinada el contrato de `capacity-scout`, `director`, `orchestrator`, `BACKLOG.md` y `OPPORTUNITIES.md`.

**Ciclo de vida en 4 niveles**

- **Nivel 1** — implementado completo en esta tranche:
  - `capacity-scout` `state-vivo-first`
  - `full scout pass` con criterio de terminacion y fallback cerrados
  - batch packaging governance-only del `director`
  - reconciliacion governance-only cuando haya `missing/stale`
  - `baseline-only governance wave`
  - ejecucion serial `run-next-until-stop`
  - Packet B amplifica este nivel con investigacion packageable, expansion curada y `work_kind` persistido en backlog
- **Nivel 2** — contrato futuro, no gateado en runtime:
  - usa el mismo modelo de cola unica y una futura semantica de promocion/reapertura de modulo basada en evidencia acumulada, nunca en una segunda cola.
- **Nivel 3** — contrato futuro, no gateado en runtime:
  - extiende el mismo ciclo a handoffs inter-modulo sin romper la regla de `BACKLOG.md` como unica cola ejecutable.
- **Nivel 4** — contrato futuro, no gateado en runtime:
  - eleva el mismo contrato a coordinacion de programa/release, sin permitir colas ejecutables paralelas fuera de `BACKLOG.md`.

**Invariantes**

- Una ola governance-only de batch packaging puede crear varias BLs en un solo ciclo.
- Una `baseline-only governance wave` puede mutar solo canonicals de governance para persistir baseline.
- Una ola governance-only de curacion de expansion puede mutar solo canonicals para proponer o descartar candidatos ticker-level.
- Una ola governance-only de normalizacion de oportunidades puede mutar solo `docs/project/OPPORTUNITIES.md` para volver investigables items ya abiertos.
- Todas esas carve-outs deben cerrar con `claimed_bl_status: none`.
- Fuera de esas carve-outs, cada ejecucion mutante posterior sigue mapeandose a una sola BL.

### Capacity-scout helper

`capacity-scout` es un helper read-only del runtime, no un rol de negocio. En Nivel 1 opera `state-vivo-first`: primero contrasta el estado vivo y los artefactos reales; despues usa canonicals como contexto de reconciliacion, nunca como sustituto del estado vivo.

**Puede**

- leer canónicos;
- ejecutar terminal read-only bajo allowlist;
- descubrir oportunidades nuevas desde el estado vivo;
- reafirmar o cuestionar excepciones existentes con evidencia;
- calcular firmas deterministas para `Discovery Baseline`.

**No puede**

- mutar archivos;
- abrir backlog;
- priorizar;
- cerrar módulo;
- hacer closeout.

**Inputs primarios**

- `python3 scripts/check_governance.py --format json`
- `python3 -m elsian eval --all --output-json /tmp/elsian-capacity-scout/eval_report.json`
- `python3 -m elsian diagnose --all --output /tmp/elsian-capacity-scout/...`
- `python3 scripts/build_scout_context.py --eval-json /tmp/elsian-capacity-scout/eval_report.json --diagnose-json /tmp/elsian-capacity-scout/diagnose/diagnose_report.json --cases-root cases --opportunities-md docs/project/OPPORTUNITIES.md --output-json /tmp/elsian-capacity-scout/scout_context.json`
- `cases/*/case.json`
- `cases/*/filings_manifest.json` cuando exista
- inspeccion read-only de `cases/*/filings/` cuando haga falta

**Inputs secundarios**

- `docs/project/PROJECT_STATE.md`
- `docs/project/OPPORTUNITIES.md`
- `docs/project/DECISIONS.md`
- `VISION.md`

**Allowlist v1**

- `python3 scripts/check_governance.py --format json`
- `python3 -m elsian eval --all --output-json /tmp/elsian-capacity-scout/eval_report.json`
- `python3 -m elsian diagnose --all --output /tmp/elsian-capacity-scout/...`
- `python3 scripts/build_scout_context.py --eval-json /tmp/elsian-capacity-scout/eval_report.json --diagnose-json /tmp/elsian-capacity-scout/diagnose/diagnose_report.json --cases-root cases --opportunities-md docs/project/OPPORTUNITIES.md --output-json /tmp/elsian-capacity-scout/scout_context.json`
- `rg`
- `sed`
- `cat`

**Prohibido en v1**

- `python3 -c`
- `python3 -m elsian acquire`
- `python3 -m elsian run`
- `python3 -m elsian onboard`
- cualquier comando que escriba en `cases/`, `filings/`, `filings_manifest.json` o canónicos

**Salida top-level obligatoria**

La salida del scout debe ser un objeto con exactamente tres bloques:

- `pass_summary`
- `findings`
- `reconciliation_summary`

**`pass_summary`**

Campos obligatorios:

- `all_cases_reviewed`
- `all_manifests_reviewed`
- `manifest_missing_cases`
- `all_operational_items_reviewed`
- `eval_run`
- `diagnose_run`
- `partial_pass`
- `partial_reasons`
- `evaluated_tickers`
- `reviewed_opportunity_ids`
- `bl_ready_count`
- `investigation_bl_ready_count`
- `expansion_candidate_count`
- `packageable_count`
- `missing_count`
- `stale_count`

`eval_run` y `diagnose_run` deben tener exactamente:

- `status: ok | timeout | error | unusable_artifact`
- `artifact_path`
- `signature`
- `notes`

Regla de nullability:

- si `status = ok`:
  - `artifact_path` es ruta absoluta
  - `signature` es SHA-256
  - `notes` es string, puede ser vacio
- si `status = timeout | error | unusable_artifact`:
  - `artifact_path: null`
  - `signature: null`
  - `notes` es string no vacio

**Helper repo-tracked de contexto**

El scout debe ejecutar:

- `python3 scripts/build_scout_context.py --eval-json /tmp/elsian-capacity-scout/eval_report.json --diagnose-json /tmp/elsian-capacity-scout/diagnose/diagnose_report.json --cases-root cases --opportunities-md docs/project/OPPORTUNITIES.md --output-json /tmp/elsian-capacity-scout/scout_context.json`

Y debe usar `scout_context.json` como fuente primaria para:

- `eval_run`
- `diagnose_run`
- `partial_pass`
- `partial_reasons`
- `case_review.manifest_missing_tickers`
- firmas de baseline

Regla de mapeo:

- `case_review.manifest_missing_tickers` del helper se copia en `pass_summary.manifest_missing_cases`;
- el helper no clasifica semanticamente los casos sin manifest; solo reporta que tickers carecen de manifest;
- la clasificacion semantica (`manifest_expected_absent`, `manifest_missing_gap`, `manifest_not_needed_for_current_finding`) sigue siendo responsabilidad del scout con apoyo de `OPPORTUNITIES.md`, `PROJECT_STATE.md` y `DECISIONS.md`.

**`findings`**

Lista de objetos con exactamente:

- `topic: string`
- `classification: BL-ready | investigation_BL_ready | expansion_candidate | opportunity | exception_reaffirmed | no_action | closeout_evidence_insufficient`
- `subject_type: ticker | market | extractor | acquire | governance`
- `subject_id: string`
- `current_canonical_state: string`
- `live_evidence: string[]`
- `why_it_matters: string`
- `unknowns_remaining: string[]`
- `recommended_next_route: string`
- `blast_radius: targeted | shared-core | governance-only`
- `effort: minimal | bounded | broad`
- `validation_tier: targeted | shared-core | governance-only | n/a`
- `last_reviewed: string | null`
- `promotion_trigger: string | null`
- `disposition_hint: keep_in_opportunities | send_to_director_for_packaging | reaffirm_exception | retire`
- `evidence_basis: runtime_direct | runtime_plus_canonical`
- `opportunities_alignment: matched | missing | stale | not_applicable`
- `unchanged_since_last_pass: boolean`

**`reconciliation_summary`**

Objeto con listas:

- `missing_in_opportunities`
- `stale_in_opportunities`
- `still_valid_in_opportunities`
- `retire_candidates`

Shapes exactas:

- `missing_in_opportunities`:
  - `subject_type`
  - `subject_id`
  - `topic`
  - `suggested_lane`
  - `why_it_matters`
- `stale_in_opportunities`:
  - `opportunity_id`
  - `subject_id`
  - `staleness_reason`
  - `recommended_disposition`
- `still_valid_in_opportunities`:
  - `opportunity_id`
  - `subject_id`
  - `unchanged_since_last_pass`
- `retire_candidates`:
  - `opportunity_id`
  - `subject_id`
  - `retire_reason`

**`full scout pass`**

El pass no termina hasta que:

- revisa todos los `case.json`;
- revisa todos los `filings_manifest.json` existentes;
- clasifica todos los casos sin manifest;
- ejecuta `eval --all --output-json ...`;
- ejecuta `diagnose --all --output ...`;
- contrasta todos los items del subtree operativo de `OPPORTUNITIES.md`.

Casos sin manifest como `0327`, `TALO` o `TEP` cuentan como revisados solo si se clasifican como:

- `manifest_expected_absent`
- `manifest_missing_gap`
- `manifest_not_needed_for_current_finding`

Si no pueden clasificarse razonablemente, el scout debe marcar `partial_pass = true`.

**Regla de `partial_pass`**

- `eval_run`, `diagnose_run`, `partial_pass` y `partial_reasons` deben salir del helper repo-tracked, no de inferencia LLM;
- `timeout`, `error` o `unusable_artifact` en `eval` o `diagnose` fuerzan `partial_pass = true`.
- un caso sin manifest no clasificado razonablemente fuerza `partial_pass = true`.
- `partial_reasons` debe explicar cada degradacion.
- un pass parcial no puede disparar packaging tecnico; solo planning o reconciliacion governance-only.

**Packet B — investigacion y expansion packageable**

- `packageable_count` se define exactamente como:
  - `bl_ready_count + investigation_bl_ready_count + expansion_candidate_count`
- `investigation_BL_ready` y `expansion_candidate` son trabajo packageable de primer nivel, no anotaciones cosmeticas.
- La expansion proactiva nunca desplaza investigaciones abiertas del modulo; solo usa slots sobrantes del presupuesto de batch.
- La shape de `findings` y `reconciliation_summary` no cambia; Packet B solo amplia la enum de clasificacion y los contadores de `pass_summary`.

**Semantica discovery para `eval --all --output-json`**

- si `eval --all --output-json ...` termina con `exit 1` solo porque hay tickers `FAIL`, pero el JSON existe y es parseable/completo:
  - `eval_run.status = ok`
  - `artifact_path` apunta al JSON absoluto
  - `signature` usa el JSON, no stdout
  - `notes` puede registrar que hubo FAILs de contenido
- solo cuentan como `timeout | error | unusable_artifact`:
  - timeout
  - crash real
  - JSON ausente
  - JSON corrupto o no usable

**Semantica de firmas**

- `last_eval_signature`:
  - se calcula desde `eval_report.json`
  - usa `sha256` de la lista `reports` normalizada y ordenada por `ticker`
  - no usa stdout
- `last_diagnose_signature`:
  - se calcula desde `diagnose_report.json`
  - incluye solo `summary`, `root_cause_summary`, `by_period_type`, `by_field_category` y `hotspots` con allowlist exacta:
    - `rank`
    - `field`
    - `field_category`
    - `gap_type`
    - `occurrences`
    - `affected_tickers`
    - `evidence`
    - `root_cause_hint`
  - ignora `schema_version`, `generated_at` y `cases_dir`
- `last_cases_signature`:
  - por ticker incluye el contenido logico de `case.json`
  - si existe `filings_manifest.json`, incluye su contenido logico normalizado
  - si no existe manifest, usa inventario estable de `filings/` con `relative_path`, `size` y `sha256(bytes)`
- `last_operational_opportunities_signature`:
  - es el `sha256` del subtree operativo de `docs/project/OPPORTUNITIES.md`

**Persistencia de baseline**

- el scout calcula firmas siempre;
- el `director` persiste baseline;
- solo un `full scout pass` no parcial puede actualizar `## Discovery Baseline`;
- una pasada parcial nunca sobrescribe baseline.

**Regla mecanica de `investigation_BL_ready`**

Un item solo puede clasificarse como `investigation_BL_ready` si, y solo si:

- esta en el subtree operativo de `docs/project/OPPORTUNITIES.md`;
- esta en `Near BL-ready`, `Exception watchlist` o `Extractor / format frontiers`;
- su `Disposition` actual es `keep` o `reaffirm_exception`;
- `Unknowns remaining` ya esta normalizado como un unico experimento ejecutable y falsable;
- el experimento recae sobre un ticker concreto, o mercado + ticker concreto;
- la BL de investigacion cabe en un unico packet `targeted`;
- el resultado terminal de esa BL solo puede ser:
  - `promoted`
  - `exception_reaffirmed`
  - `technical_followup_opened`
  - `discarded_with_evidence`

Regla clave:

- el filtro usa el blast radius de la investigacion, no el del resultado potencial;
- por eso un item puede salir como `investigation_BL_ready` aunque su `Blast radius if promoted` en `OPPORTUNITIES.md` sea `shared-core`, siempre que la investigacion en si sea ticker-level y `targeted`;
- la elegibilidad depende del estado actual de `Unknowns remaining`, no de si una wave historica "ya ocurrio";
- si la investigacion descubre necesidad reusable o `shared-core`, el resultado correcto es `technical_followup_opened`, no ampliar el packet actual.

**Regla mecanica de `expansion_candidate`**

Un item solo puede clasificarse como `expansion_candidate` si, y solo si:

- esta en `Expansion candidates`;
- representa un ticker concreto, no un mercado abstracto;
- no existe ya en `cases/`;
- no existe ya como BL activa en `docs/project/BACKLOG.md`;
- el mercado ya esta dentro del alcance operativo actual o de sus fronteras vigentes;
- el trabajo cabe en una sola BL `targeted`;
- sigue la doctrina de onboarding de `docs/project/MODULE_1_ENGINEER_CONTEXT.md`.

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
- `Near BL-ready`, `Exception watchlist` y `Extractor / format frontiers` pueden producir `investigation_BL_ready` solo si `Unknowns remaining` ya esta normalizado como experimento unico, ejecutable y falsable.
- `Exception watchlist` se mantiene mientras la excepcion siga sosteniendose; puede moverse a `Near BL-ready` si aparece evidencia nueva.
- `Expansion candidates` solo puede producir `expansion_candidate` cuando existe ticker concreto; los mercados abstractos no son packageables por si mismos.
- `Extractor / format frontiers` y `Expansion candidates` bloquean el cierre del modulo mientras sigan operativos.
- `Retired / absorbed` no vuelve a competir salvo evidencia nueva material.
- Si un scout pass cambia materialmente la interpretacion de un item, rebota a `director` para reconciliacion governance-only.
- Si un scout pass reafirma una excepcion o confirma `no_action`, `Last reviewed` solo necesita actualizarse si el item esta stale (>30 dias). Esas actualizaciones deben batch-earse en una reconciliacion governance-only, no abrir una ola por item.
- Si `Unknowns remaining` ya contiene un unico experimento ejecutable y falsable conforme al contrato, el item es elegible a `investigation_BL_ready`; si no, permanece en `opportunity`.

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

**Anti-regresion de oportunidades**

Tras cerrar una BL `Work kind: investigation` o `Work kind: expansion`, el `director` debe reconciliar `docs/project/OPPORTUNITIES.md` de forma que el item no reaparezca igual en el siguiente scout pass:

- `promoted`:
  - sale del carril operativo o pasa a `Retired / absorbed`
- `exception_reaffirmed`:
  - permanece en `Exception watchlist`
  - actualiza `Last reviewed`
  - reduce o limpia `Unknowns remaining`
- `technical_followup_opened`:
  - el item sigue vivo, pero queda referenciado al nuevo follow-up y con `Unknowns remaining` actualizado
- `discarded_with_evidence` o `discarded_candidate`:
  - pasa a `Retired / absorbed`
- una curacion de expansion con `0` candidatos:
  - actualiza `Last reviewed`
  - debe reaparecer como `unchanged_since_last_pass=true`, no como recomendacion nueva

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

**Carve-outs governance-only del `director`**

- **Batch packaging**:
  - puede crear hasta `3` BLs en un solo ciclo
  - puede incluir como maximo `1` item `shared-core`
  - si aparece una oportunidad `broad`, viaja sola
  - solo admite dependencias `independientes` o `lineales`
  - un caso mixto `BL-ready + missing/stale` se resuelve en una sola ola governance-only
  - el orden de prioridad del batch es:
    - reconciliacion `missing/stale`
    - `BL-ready`
    - `investigation_BL_ready`
    - `expansion_candidate`
  - las investigaciones tienen prioridad sobre expansion
  - como maximo `1` BL de expansion por batch
  - debe usar por defecto el maximo batch viable dentro de ese presupuesto
  - si empaqueta menos de lo que cabe, debe justificarlo explicitamente en el packet
  - toda BL creada en esta ola debe persistir `Work kind` en `docs/project/BACKLOG.md` con uno de estos valores:
    - `technical`
    - `investigation`
    - `expansion`
  - el exceso no se guarda en `PROJECT_STATE.md`; permanece en `OPPORTUNITIES.md` y, si las firmas no cambian, reaparece como `matched + unchanged_since_last_pass`
- **Hypothesis basis hardening**:
  - antes de abrir una BL `investigation` o `expansion`, el `director` debe producir un `hypothesis_basis` que demuestre que el gap declarado existe; el `orchestrator` no ejecuta ni sustituye este pre-gate
  - para `investigation`, el basis se construye desde el `case.json` del anchor, `filings_manifest.json` cuando exista y sea relevante para la finding, el `eval` del scout pass vigente y el item correspondiente en `docs/project/OPPORTUNITIES.md`
  - para `expansion`, el basis se construye desde el item curado en `docs/project/OPPORTUNITIES.md` y los criterios vigentes de `expansion_candidate`; no exige `case.json` ni `eval` de un ancla inexistente
  - el `director` debe clasificar el pre-check como `gap_confirmed: true | false | inconclusive`
  - `gap_confirmed: false` o `gap_confirmed: inconclusive` no abren BL: se reconcilia `docs/project/OPPORTUNITIES.md`, se actualiza `Live evidence` y/o `Unknowns remaining`, `Disposition` permanece intacto y `Last reviewed` se refresca
  - una finding `inconclusive` solo puede reabrirse con evidencia nueva o override explicito de Elsian; no existe timeout automatico
  - si la BL se empaqueta, `docs/project/BACKLOG.md` debe persistir al menos estos campos parseables:
    - `Hypothesis basis subject`
    - `Hypothesis basis gap`
    - `Hypothesis basis evidence`
    - `Hypothesis basis confirmed`
    - `Hypothesis basis snapshot`
  - `Hypothesis basis evidence` solo puede listar surfaces versionadas o valores reproducibles; nunca rutas `/tmp` ni artefactos efimeros
  - `Hypothesis basis snapshot` usa `HEAD + eval_signature` en `investigation` y `HEAD + n/a` en `expansion`
  - la forma persistida en backlog debe ser minima y canonica: `scout_context_signature` puede vivir en el packet rico del `director`, pero no en la cola ejecutable
  - para BL `technical`, este pre-gate es opcional y solo aplica cuando el motivo no es trivialmente observable
- **Baseline-only governance wave**:
  - solo aplica tras `full scout pass` no parcial
  - requiere `0` `BL-ready`, `0` `missing`, `0` `stale`
  - se usa para persistir `## Discovery Baseline` cuando la baseline esta ausente o sus firmas cambiaron
- **Curacion de expansion**:
  - solo aplica cuando no hay `BL-ready` ni `investigation_BL_ready` packageables y `Expansion candidates` no contiene tickers concretos packageables
  - puede anadir hasta `3` candidatos ticker-level si cumplen los criterios de mercado vigente, no duplicidad, diversidad real, discoverability razonable y blast radius `targeted`
  - `0` candidatos es un resultado valido y debe dejar constancia explicita de que no hay candidatos validos bajo la baseline actual
- **Normalizacion de oportunidades**:
  - se usa para reescribir `Unknowns remaining` de items investigables como experimentos unicos, ejecutables y falsables
  - no crea backlog por si sola
- Los cuatro carve-outs deben cerrar con `claimed_bl_status: none`.

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
- Para `Work kind: investigation` o `Work kind: expansion`, validar que la BL produjo evidencia suficiente y uno de los resultados terminales permitidos, aunque no haya codigo nuevo.
- Para `Work kind: investigation` o `Work kind: expansion`, leer `Hypothesis basis subject/gap/evidence/confirmed/snapshot` desde `docs/project/BACKLOG.md` como superficie canonica y contrastarlo contra el estado factual real.
- Hallazgo de severidad alta si el gap no existia y la BL perdia sentido operativo desde el inicio.
- Hallazgo de severidad media si el framing del gap era mejorable, pero la BL aun produjo evidencia util y reutilizable.
- Hallazgo contractual si `Hypothesis basis evidence` depende de rutas `/tmp` o de artefactos no canonicos.

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
- El pre-gate de hipotesis para `investigation` y `expansion` pertenece al `director` durante el packaging; el `orchestrator` solo decide cuando lanzar ese hijo.
- El `orchestrator` no puede considerar resuelto un hypothesis check por haber hecho scouting, briefing o planning; la confirmacion del gap debe quedar en el packet y, cuando exista BL, persistida en `docs/project/BACKLOG.md`.
- En `briefing` y `planificacion`, si `capacity-scout.pass_summary.bl_ready_count > 0` o `capacity-scout.pass_summary.investigation_bl_ready_count > 0`, el `orchestrator` debe detenerse en la fase read-only, devolver findings + ruta recomendada, exponer todos los packageables relevantes y preguntar si debe pasar a ejecucion; no puede invocar a `director` dentro de esa misma fase read-only.
- En `briefing` y `planificacion`, si `capacity-scout.pass_summary.bl_ready_count = 0`, `investigation_bl_ready_count = 0` y `missing_count + stale_count > 0`, la ruta correcta es reconciliacion governance-only; no se abre packaging tecnico.
- En `briefing` y `planificacion`, si solo hay `expansion_candidate_count > 0`, la ruta correcta es `director -> gates -> auditor -> closeout` para seleccion y packaging de expansion.
- En `briefing` y `planificacion`, si no hay packageables y `Expansion candidates` carece de tickers concretos elegibles, la ruta correcta es una ola governance-only de curacion de expansion.
- En `ejecucion`, si `capacity-scout` detecta `BL-ready`, `investigation_BL_ready` o `expansion_candidate`, el `orchestrator` puede abrir una segunda fase separada con `director`, siempre despues de cerrar la fase read-only.
- Si `capacity-scout.pass_summary.partial_pass = true`, el `orchestrator` no puede disparar packaging tecnico; solo planning o reconciliacion governance-only.
- Si `capacity-scout` devuelve `full pass` limpio, sin `BL-ready`, sin `missing/stale`, y la baseline esta ausente o cambiada, la ruta correcta es `baseline-only governance wave`.
- Si varias BL quedan empaquetadas y priorizadas, el `orchestrator` puede operar en modo `run-next-until-stop`: ejecutar una BL, cerrar, re-ejecutar checker, y continuar solo mientras la siguiente BL siga clara y no aparezca nueva ambigüedad.
- `run-next-until-stop` debe detenerse en el primer fallo de BL y volver a planning; no se salta el fallo ni reordena por heuristica.
- Si Elsian aprueba continuar desde planning con trabajo packageable, el `orchestrator` debe revalidar estado antes de mutar con `python3 scripts/check_governance.py --format json`.
- La revalidacion previa a mutacion debe comparar, como minimo:
  - `summary.next_resolution_mode`
  - `backlog.active_ids`
  - `backlog.active_count`
  - `technical_dirty`
  - `governance_dirty`
  - `other_dirty`
  - `workspace_only_dirty`
  - `project_state.discovery_baseline.present`
  - `project_state.discovery_baseline.valid`
  - `HEAD`
- Si cambia cualquiera de estas senales de hard-abort, el `orchestrator` no puede mutar y debe volver a planning:
  - `HEAD`
  - `summary.next_resolution_mode`
  - `backlog.active_ids`
  - `backlog.active_count`
  - `technical_dirty`
  - `governance_dirty`
  - `project_state.discovery_baseline.present`
  - `project_state.discovery_baseline.valid`
- `workspace_only_dirty` y `other_dirty` son senales de soft-check; si el `orchestrator` no puede demostrar que el cambio es irrelevante para el scope del batch, debe abortar de forma conservadora y volver a planning.
- Si el `orchestrator` transiciona de planning a ejecucion en el mismo thread, el handoff al `director` debe incluir siempre:
  - `capacity-scout.pass_summary`
  - `capacity-scout.findings`
  - `capacity-scout.reconciliation_summary`
  - el snapshot del checker usado en planning
  - el snapshot revalidado justo antes de mutar
  - la instruccion explicita: `empaqueta el batch optimo dentro del presupuesto vigente; no asumas que el parent ya lo ha decidido`
- En `briefing` y `planificacion`, el `orchestrator` debe cerrar siempre con un bloque `## Resumen ejecutivo` de exactamente cuatro lineas:
  - `Estado del modulo`
  - `Hallazgos packageables`
  - `Accion inmediata`
  - `Siguiente tras ejecucion`

**Resultados terminales por `Work kind`**

- `technical`:
  - mantiene los criterios tecnicos normales del packet correspondiente.
- `investigation`:
  - solo puede cerrar como `promoted`, `exception_reaffirmed`, `technical_followup_opened` o `discarded_with_evidence`.
- `expansion`:
  - solo puede cerrar como `onboarded_to_annual_only`, `technical_followup_opened` o `discarded_candidate`.
- `auditor` y `closeout` aceptan BLs `investigation` o `expansion` sin codigo nuevo si la evidencia se genero, la decision terminal quedo tomada y `OPPORTUNITIES.md` / canonicals quedaron reconciliados de forma consistente.

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

## 3.2 Authority / Autonomy Policy v1

Esta seccion define que decisiones operativas pueden ejecutarse sin aprobacion explicita de Elsian y bajo que limites. Si contradice cualquier otra seccion de este documento, prevalece la otra seccion. `BACKLOG.md` sigue siendo la unica cola ejecutable. `briefing` y `planificacion` siguen siendo read-only. `workspace_only_dirty` no bloquea por si solo; cualquier otro dirty repo-tracked bloquea autonomia mutante.

### D1. Handoff stale -> recompute

**Autonomo si:**

- `.runtime/handoff.json` no existe, o
- el schema es invalido, o
- `head_mismatch = true`, o
- `live_state_fingerprint_mismatch = true`
- y `read_handoff.py` / `write_handoff.py` pueden recomputar con exito

**Escalar solo si:**

- el recompute falla, o
- `check_governance.py` no esta disponible, o
- el handoff recomputado contradice el checker vivo de forma material

**Evidencia minima al escalar:**

- `stale_reason`
- `handoff.head`
- `handoff.live_state_fingerprint`
- `checker.head`
- `checker.live_state_fingerprint`
- stderr o excepcion del recompute

**Fallback si no cumple:**

- ignorar handoff
- operar desde checker vivo + kickoff/scout frescos
- no mutar canonicals por causa del handoff

### D2. Auto-commit -> reglas vigentes de `ROLES.md`

**Autonomo si:**

- solo bajo la politica ya vigente en `ROLES.md`

**Escalar solo si:**

- cualquier condicion de `auto-commit` de `ROLES.md` no se cumple

**Evidencia minima al escalar:**

- clasificacion inicial del dirty state
- resultado de gates
- resultado de auditoria
- resultado de closeout
- lista exacta de ficheros que entrarian en commit
- motivo exacto por el que `auto-commit` queda bloqueado

**Fallback si no cumple:**

- cerrar sin `auto-commit`
- dejar el cambio listo para commit manual

### Regla de `session_mode`

El `orchestrator` clasifica el prompt de entrada al inicio del flujo y declara `session_mode` como `briefing`, `planificacion` o `execution`. Si el prompt es ambiguo o no menciona ejecucion explicita, `session_mode` default = `briefing` (read-only). Solo `session_mode = execution` habilita las familias A, B y C.

### Gate comun de autonomia mutante (A/B)

Las familias A/B requieren:

- `session_mode = execution`
- parent = `orchestrator`
- preflight con:
  - `technical_dirty = false`
  - `governance_dirty = false`
  - `other_dirty = false`
  - `workspace_only_dirty` permitido
- checker actual con `next_resolution_mode = empty_backlog_discovery`
- handoff fresco o recomputado correctamente
- ausencia de conflicto material entre:
  - checker vivo
  - handoff vigente
  - salida de `capacity-scout`
- ninguna pregunta abierta de tesis / alcance / prioridad estrategica

### A1. Missing/Stale reconciliation wave

**Autonomo si:**

- se cumple el gate comun
- `capacity-scout.partial_pass = false`
- `missing_count + stale_count > 0`
- `bl_ready_count = 0`
- `investigation_bl_ready_count = 0`
- `expansion_candidate_count = 0`
- todas las entradas a reconciliar caen en `reconciliation_summary.{missing_in_opportunities, stale_in_opportunities}`
- cada item `missing/stale` en `reconciliation_summary` tiene un `recommended_disposition` que mapea directamente a una accion mecanica en `docs/project/OPPORTUNITIES.md` (`anadir` a carril, actualizar `Last reviewed`, mover a `Retired / absorbed`) sin requerir juicio de clasificacion nuevo
- la superficie de mutacion queda limitada a `docs/project/OPPORTUNITIES.md`
- el cierre previsto es `claimed_bl_status: none`

**Escalar si:**

- `partial_pass = true`, o
- existe cualquier packageable (`BL-ready`, `investigation_BL_ready`, `expansion_candidate`), o
- cualquier item requiere decidir entre dos disposiciones plausibles, o
- la mutacion propuesta excede `docs/project/OPPORTUNITIES.md`

**Evidencia minima al escalar:**

- `pass_summary` completo
- `partial_reasons` si existen
- `reconciliation_summary` completo
- diff surface prevista
- motivo exacto del bloqueo de autonomia

**Fallback si no cumple:**

- no mutar
- devolver packet read-only de reconciliacion
- cerrar la sesion con recomendacion explicita

### A2. Baseline-only governance wave

**Autonomo si:**

- se cumple el gate comun
- `capacity-scout.partial_pass = false`
- `bl_ready_count = 0`
- `investigation_bl_ready_count = 0`
- `expansion_candidate_count = 0`
- `missing_count = 0`
- `stale_count = 0`
- `Discovery Baseline` esta ausente o sus firmas cambiaron
- la superficie de mutacion queda limitada a `docs/project/PROJECT_STATE.md` en `## Discovery Baseline`
- el cierre previsto es `claimed_bl_status: none`

**Escalar si:**

- `partial_pass = true`, o
- existe cualquier packageable, o
- hay `missing/stale`, o
- la baseline no puede recomputarse de forma determinista, o
- la mutacion propuesta excede `docs/project/PROJECT_STATE.md :: Discovery Baseline`

**Evidencia minima al escalar:**

- `pass_summary` completo
- firmas baseline antiguas vs nuevas
- estado actual de `Discovery Baseline`
- diff surface prevista
- motivo exacto del bloqueo de autonomia

**Fallback si no cumple:**

- no persistir baseline
- devolver packet read-only con firmas y diagnostico
- cerrar la sesion con recomendacion explicita

**Exclusion mutua A1/A2**

A1 y A2 son mutuamente excluyentes por sus condiciones. En v1, sin `run-next-until-stop`, solo una familia puede dispararse por sesion. Tras completar A1, una sesion posterior puede disparar A2 si las condiciones se cumplen.

### B. Batch packaging narrow

**Autonomo si:**

- se cumple el gate comun
- `capacity-scout.partial_pass = false`
- `missing_count = 0`
- `stale_count = 0`
- existe al menos `1` candidato con `classification in {BL-ready, investigation_BL_ready}`
- todos los items seleccionados cumplen:
  - `blast_radius = targeted`
  - `effort in {minimal, bounded}`
  - `validation_tier = targeted`
  - `disposition_hint = send_to_director_for_packaging`
- para items `investigation_BL_ready`, el `director` autonomo debe completar el pre-gate de `hypothesis_basis` conforme a `§2.1` de este documento:
  - si `gap_confirmed = true`, puede abrir BL
  - si `gap_confirmed != true`, no abre BL: reconcilia `docs/project/OPPORTUNITIES.md` y escala
- ningun item seleccionado es:
  - `shared-core`
  - `broad`
  - `expansion_candidate`
- las dependencias del batch son solo `independientes` o `lineales`
- `1 <= batch_size <= 3`
- existe un unico batch maximo legal bajo este subconjunto v1
- el batch autonomo no empaqueta menos de lo que cabe dentro de ese maximo legal
- toda BL creada puede persistir `Work kind in {technical, investigation}`
- la superficie de mutacion queda limitada a:
  - `docs/project/BACKLOG.md`
  - actualizaciones minimas de consistencia en `docs/project/OPPORTUNITIES.md`
- el exceso no seleccionado permanece en `docs/project/OPPORTUNITIES.md`

**Escalar si:**

- `partial_pass = true`, o
- hay `missing/stale`, o
- cualquier item `investigation_BL_ready` falla el pre-gate de `hypothesis_basis` o tiene `gap_confirmed != true`, o
- no existe batch legal unico, o
- aparece cualquier `shared-core`, `broad` o `expansion_candidate` relevante, o
- el batch maximo legal exigiria juicio no mecanico, o
- el `director` tendria que empaquetar menos de lo que cabe

**Evidencia minima al escalar:**

- `pass_summary` completo
- tabla de candidatos con:
  - `subject_id`
  - `classification`
  - `blast_radius`
  - `effort`
  - `validation_tier`
  - `disposition_hint`
- batches legales calculados
- batch recomendado
- motivo exacto del bloqueo de autonomia

**Fallback si no cumple:**

- no mutar backlog
- devolver `batch_candidates` + `recommended_batch`
- cerrar la sesion con recomendacion explicita

### C. Paso a ejecucion solo en sesion preautorizada como ejecucion

**Autonomo si:**

- `session_mode = execution` (ver regla de `session_mode` arriba)
- no hay instruccion explicita del usuario restringiendo la sesion a read-only
- al inicio del ciclo de discovery, el checker estaba en `next_resolution_mode = empty_backlog_discovery`
- existe exactamente una ruta mutante valida y ya determinada dentro del flujo existente
- la decision previa que habilita esa ruta proviene de:
  - A1 / A2, o
  - B con batch `narrow`
- si la ruta proviene de B:
  - `selected_batch_size = 1`
  - la BL resultante tiene `Work kind in {technical, investigation}`
  - `blast_radius = targeted`
  - `effort in {minimal, bounded}`
  - tras el packaging, el checker pasa a un estado compatible con ejecutar esa BL (`execute_backlog` o backlog activo consistente)
- si la ruta proviene de A1 / A2:
  - la mutacion sigue siendo estrictamente `governance-only`
  - el checker sigue limpio salvo `workspace_only_dirty`
- justo antes de mutar, no hay contradiccion material entre checker vivo, handoff vigente y packet/handoff del `director`

**Escalar si:**

- `session_mode != execution`, o
- hay mas de una ruta mutante plausible, o
- `selected_batch_size > 1`, o
- la ejecucion tocaria `shared-core`, `broad` o `expansion`, o
- el estado vivo cambio entre scout y mutacion, o
- aparece cualquier duda de scope / prioridad / tesis

**Evidencia minima al escalar:**

- `session_mode` de entrada
- checker al inicio y checker justo antes de mutar
- familia que habilita la ejecucion (`A1`, `A2`, `B`)
- ruta candidata exacta
- batch seleccionado y tamano
- `blast_radius`, `effort`, `work_kind`
- motivo exacto del bloqueo de autonomia

**Fallback si no cumple:**

- si aun no hubo mutacion: cerrar en read-only con `Ruta recomendada` + prompt de ejecucion
- si B ya empaqueto batch narrow: parar tras packaging; no lanzar `engineer`; devolver BL creada + prompt de ejecucion

### Fuera de v1

- `run-next-until-stop`
- `expansion-curation`
- cualquier batch con `shared-core`
- cualquier oportunidad `broad`
- cualquier autonomia que requiera reinterpretar tesis, modulo o prioridades

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
- Las olas governance-only de batch packaging y baseline-only deben declarar `claimed_bl_status: none`.
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

**Mirrors bloqueantes Claude Code repo-tracked**

- `.claude/CLAUDE.md`
- `.claude/commands/orchestrator.md`
- `.claude/commands/kickoff.md`
- `.claude/commands/capacity-scout.md`
- `.claude/commands/director.md`
- `.claude/commands/engineer.md`

**Politica de ausencia**

- Si el runtime bajo cierre es `Codex`, la ausencia de una skill requerida deja `closeout` rojo.
- Si el runtime bajo cierre es `Claude Code`, la ausencia de un command requerido deja `closeout` rojo.
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
