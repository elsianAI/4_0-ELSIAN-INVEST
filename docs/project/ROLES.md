# ELSIAN 4.0 — Roles y Runtime Multiagente

> Fuente de verdad versionada para los roles `director`, `engineer` y `auditor`.
> El `orchestrator` es infraestructura de runtime, no un cuarto rol del dominio.
> Si este documento contradice `VISION.md` o `docs/project/DECISIONS.md`, prevalecen esos documentos.

## 1. Modelo del sistema

ELSIAN 4.0 usa tres roles de negocio:

- `director`: decide alcance, prioridad, criterio de exito y packaging del trabajo.
- `engineer`: implementa cambios tecnicos dentro del alcance permitido.
- `auditor`: verifica de forma independiente y findings-first.

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
- **Ejecucion**: hace preflight, decide la ruta segun este documento, y ejecuta `director -> engineer -> gates -> auditor` o la variante minima correcta.

**Reglas**

- No es un rol de negocio.
- No redefine contratos, routing, gates ni Vision Enforcement.
- No implementa codigo directamente ni sustituye el juicio del `auditor`.
- En `briefing` y `planificacion` no muta nada.
- En `ejecucion` puede mutar solo a traves de los hijos correctos y de los gates del padre.

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
- `git status --short`

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

- El `Estado actual` debe distinguir entre hechos de los documentos y estado real del worktree.
- Si no se puede leer el worktree real, debe decirlo explicitamente en `Estado actual`.
- `Top 3 siguientes tareas` salen del backlog y del estado real; no de repriorizacion creativa.
- `Ruta recomendada` debe ser una de estas:
  - `director -> engineer -> gates -> auditor`
  - `engineer -> gates -> auditor`
  - `auditor`
- `Prompt recomendado` debe ser copiable y coherente con la ruta recomendada.
- Si `kickoff` se usa dentro de `orchestrator`, el prompt recomendado debe ser reutilizable por `orchestrator`, no por `kickoff`.

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

- Flujo completo estandar: `director -> engineer -> gates -> auditor`
- Flujo tecnico local: `engineer -> gates -> auditor`
- Flujo de review: `auditor`

## 4. Packets y handoff

Todos los hijos deben recibir prompts autosuficientes. No se asume herencia fiable del contexto del padre.

### 4.1 `director packet`

Incluye:

- peticion original de Elsian;
- documentos a leer;
- formato de salida obligatorio;
- recordatorio de Vision Enforcement.

Salida esperada: un handoff ejecutable por `engineer`.

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
- resumen factual del engineer;
- documentos de referencia a leer.

No debe incluir framing favorable del `director`.

### 4.4 Formato canonico de handoff

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
- Devolver packet + salida de gates al `engineer`.
- Solo auditar con gates rojos si Elsian lo pide explicitamente.

## 6. Retry, failure y limites del runtime

- Primer intento: `spawn_agent`.
- Si falla por imposibilidad de fork del thread, retry inmediato con prompt standalone completo.
- No depender de subagentes anidados.
- Si un hijo detecta que necesita decisiones nuevas, devuelve follow-up al padre; no improvisa expansion.
- Si el `engineer` entrega un cambio fuera de alcance permitido, el padre lo trata como gate rojo de scope.

## 7. Consistencia y mantenimiento

- `docs/project/ROLES.md` es la referencia canónica de contratos y flujo.
- `docs/project/KNOWLEDGE_BASE.md` es onboarding transversal y orientacion del repo; no sustituye ni `VISION.md` ni `DECISIONS.md`.
- Cada modulo tiene su propio manual tecnico.
  - trabajo actual: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- Las implementaciones operativas deben mantenerse coherentes con este documento:
  - skills locales de Codex en `$CODEX_HOME/skills/`;
  - el orquestador explicito de Codex en `$CODEX_HOME/skills/elsian-orchestrator/`;
  - el kickoff experto de Codex en `$CODEX_HOME/skills/elsian-kickoff/`;
  - agent files repo-tracked en `.github/agents/`;
  - el orquestador de Copilot en `.github/agents/elsian-orchestrator.agent.md`;
  - el kickoff experto de Copilot en `.github/agents/elsian-kickoff.agent.md`.
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
