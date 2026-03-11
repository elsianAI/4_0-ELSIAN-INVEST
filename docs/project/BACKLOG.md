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

Este backlog representa solo la **Fase B** del programa de capacidad de Module 1. La **Fase A** vive en `docs/project/PROJECT_STATE.md` como capacidad factual ya cerrada, y la **Fase C** vive en `docs/project/OPPORTUNITIES.md` como frontera abierta o excepción no empaquetable todavía.

### BL-085 — Cubrir con regresión unitaria el descarte de `inventories` espurios desde cash flow con named subsection
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** —
- **Referencias:** BL-076
- **Descripción:** El cierre de `BL-076` dejó documentado un único riesgo residual leve y acotado: falta cobertura unitaria específica para la rama shared-core que descarta `inventories` espurios cuando provienen de cash flow con named subsection en `clean.md`. La tarea se limita a convertir esa deuda en una regresión reproducible y, solo si el test revela un comportamiento incorrecto real, aplicar el fix mínimo necesario en las mismas superficies.
- **Criterio de aceptación:** Existe una regresión unitaria específica para ese patrón en la suite de extract; `python3 -m pytest -q tests/unit/test_extract_phase.py` pasa; si el packet toca superficies shared-core de extracción, `python3 -m elsian eval --all` y `python3 -m pytest -q` siguen verdes; no se debilitan `cases/` ni `expected.json`.
---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
