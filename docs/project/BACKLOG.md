# ELSIAN-INVEST 4.0 — Backlog Activo

> Cola de trabajo ejecutable. Este fichero contiene solo tareas vivas (`TODO`, `IN_PROGRESS`, `BLOCKED`).
> El histórico de tareas completadas vive en `docs/project/BACKLOG_DONE.md`.

---

## Protocolo de uso

**Quién escribe:** el agente director (prioriza, añade, reordena y cierra).
**Quién lee:** `orchestrator`, `kickoff` y agentes técnicos para conocer la cola viva.
**Estados válidos aquí:** `TODO`, `IN_PROGRESS`, `BLOCKED`.
**Work kinds válidos aquí:** `technical`, `investigation`, `expansion`.

**Formato por tarea:**

```md
### BL-XXX — Título corto
- **Prioridad:** CRÍTICA | ALTA | MEDIA | BAJA
- **Estado:** TODO | IN_PROGRESS (agente) | BLOCKED (razón)
- **Asignado a:** rol o agente
- **Módulo:** Module 1 | Governance
- **Validation tier:** targeted | shared-core | governance-only
- **Work kind:** technical | investigation | expansion
- **Depende de:** BL-XXX (si aplica)
- **Referencias:** DEC-XXX (si aplica)
- **Descripción:** Qué hay que hacer y por qué
- **Criterio de aceptación:** Cómo sabemos que está terminado
```

---

## Tareas activas

Este backlog representa solo el subconjunto **ejecutable seleccionado** de la **Fase B** del programa de capacidad de Module 1. La **Fase A** vive en `docs/project/PROJECT_STATE.md` como capacidad factual ya cerrada. `docs/project/OPPORTUNITIES.md` sigue alojando la **Fase C** no packageable, pero también puede alojar investigación ya packageable que haya quedado fuera del batch actual solo por presupuesto; esos items no pasan a Fase C por ese motivo.

### BL-092 — Onboarding SEC directo tranche A (DCBO, DNOW, FRPH, HBB)
- **Prioridad:** ALTA
- **Estado:** BLOCKED (DNOW, FRPH y HBB ya quedan verdes; DCBO sigue sin estados financieros anuales extraíbles porque el corpus SEC directo solo trae wrappers 40-F y no el Exhibit 99.2 enlazado)
- **Asignado a:** elsian-engineer
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Work kind:** technical
- **Depende de:** BL-095
- **Referencias:** VISION.md, docs/project/OPPORTUNITIES.md
- **Descripción:** SEC directo con fetcher funcional y corpus local ya presente; mezcla un 40-F (`DCBO`) y tres emisores domésticos para abrir una primera ola acotada de canonización sin redescarga. Cada ticker ya tiene `filings_manifest.json` con `source=sec_edgar`, `expected_draft.json`, `truth_pack.json` y `extraction_result.json`; el packet debe reutilizar esos artefactos locales y evitar redescarga salvo evidencia nueva.
- **Criterio de aceptación:** `cases/<ticker>/case.json` canonizado para DCBO, DNOW, FRPH y HBB; `expected.json` filing-backed curado por ticker; artifacts locales reconciliados sin degradar acquire; `python3 -m elsian eval <ticker>` PASS para cada ticker de la tranche; `python3 scripts/validate_contracts.py --schema case` / `--schema expected` PASS en todos los casos tocados.

### BL-094 — Onboarding SEC directo tranche C (MREO, PRDO, SLVM, TRS)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** elsian-engineer
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Work kind:** technical
- **Depende de:** none
- **Referencias:** VISION.md, docs/project/OPPORTUNITIES.md
- **Descripción:** Tercera ola SEC con un issuer extranjero listado en Nasdaq (`MREO`) y tres emisores domésticos; completa el batch máximo viable de tickers directos sin abrir aún mercados sin fetcher. Cada ticker ya tiene `filings_manifest.json` con `source=sec_edgar`, `expected_draft.json`, `truth_pack.json` y `extraction_result.json`; el packet debe reutilizar esos artefactos locales y evitar redescarga salvo evidencia nueva.
- **Criterio de aceptación:** `cases/<ticker>/case.json` canonizado para MREO, PRDO, SLVM y TRS; `expected.json` filing-backed curado por ticker; artifacts locales reconciliados sin degradar acquire; `python3 -m elsian eval <ticker>` PASS para cada ticker de la tranche; `python3 scripts/validate_contracts.py --schema case` / `--schema expected` PASS en todos los casos tocados.

### BL-095 — SEC 40-F directo: adquirir exhibits financieros anuales enlazados
- **Prioridad:** CRÍTICA
- **Estado:** TODO
- **Asignado a:** elsian-engineer
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Work kind:** technical
- **Depende de:** none
- **Referencias:** VISION.md, docs/project/OPPORTUNITIES.md
- **Descripción:** Follow-up reusable mínimo abierto por el bloqueo aislado de `DCBO` en BL-092. El `acquire` SEC directo materializa wrappers `40-F` y `6-K`, pero no sigue el Exhibit `99.2` enlazado desde el `40-F` (`docebo-20251231.htm` en FY2025), por lo que `python3 -m elsian run DCBO --skip-assemble` sigue en `0 fields / 0 periods` pese a `Coverage 100.0%`. El packet debe extender el carril SEC directo para capturar los exhibits anuales financieros requeridos por `40-F` sin degradar `10-K`/`10-Q`/`6-K` ni el corpus ya verde del resto de la ola.
- **Criterio de aceptación:** `python3 -m elsian acquire DCBO` materializa en `cases/DCBO/filings/` el exhibit financiero anual enlazado por el `40-F` FY2025 (o equivalente canonizado por naming estable); `python3 -m elsian run DCBO --skip-assemble` deja de quedar en `0 fields / 0 periods`; las validaciones shared-core mínimas del carril SEC quedan verdes; `python3 -m elsian eval DNOW`, `FRPH` y `HBB` se mantienen en PASS 100.0%.
---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- `Work kind` vive en la cola ejecutable y lo leen directamente `auditor` y `closeout`; no debe quedar solo implícito en descripciones o packets transitorios.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
