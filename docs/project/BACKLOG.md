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

### BL-091 — HKEX acquire: implementar búsqueda oficial y descarga PDF reusable para 0327
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Work kind:** technical
- **Depende de:** —
- **Referencias:** DEC-016
- **Descripción:** `BL-090` cerró el experimento de `OP-005` con outcome `technical_followup_opened`: HKEX ya ofrece una ruta oficial reusable fuera del carril `hkex_manual` para `0327` (`prefix.do` / `partial.do` -> `stockId=56792`, Title Search oficial con resultados históricos y PDFs directos descargables para annual/interim reports). Este follow-up debe convertir esa evidencia en un path de acquire reusable y estrecho dentro de `elsian/acquire/`, preservando `hkex_manual` como fallback y sin tocar extract/merge/eval.
- **Criterio de aceptación:** Existe un path live de acquire HKEX capaz de localizar y descargar filings oficiales de `0327` desde la ruta validada por `BL-090` sin depender del corpus trackeado; `hkex_manual` sigue funcionando como fallback; hay cobertura unitaria para lookup, resolución de resultados y descarga; `python3 -m pytest -q` y `python3 -m elsian eval --all` permanecen verdes al cierre.
---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- `Work kind` vive en la cola ejecutable y lo leen directamente `auditor` y `closeout`; no debe quedar solo implícito en descripciones o packets transitorios.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
