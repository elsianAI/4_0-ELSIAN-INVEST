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

### BL-089 — SEC acquire: preservar `coverage` y `cik` en cache-hit sin reabrir scope TALO
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Work kind:** technical
- **Depende de:** —
- **Referencias:** OP-006
- **Descripción:** Corregir el follow-up técnico reusable aislado por BL-086: cuando `SecEdgarFetcher.acquire()` entra por cache-hit con `filings/` ya poblado, el path actual suprime la verificación de coverage y deja `coverage={}` y `cik=null` en manifest. El scope debe permanecer mínimo y reproducible, restringido al carril SEC acquire/manifest para preservar o recomputar `coverage` y `cik` sin tocar extract/merge/eval, sin reabrir onboarding de mercado SEC y sin mezclar la verificación del cluster de enmiendas TALO del 2024-11-12.
- **Criterio de aceptación:** Existe una corrección shared-core acotada al path SEC acquire/manifest con write-set mínimo; el caso TALO reproduce cache-hit con `coverage` no vacío y `cik=0001724965`; el fix no amplía el alcance a restatements/enmiendas ni a otros carriles fuera de SEC acquire; el outcome queda validado con gates acordes a una BL técnica narrow.

### BL-087 — Ejecutar el experimento único de SOM para promoción o excepción cerrada
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Work kind:** investigation
- **Depende de:** —
- **Referencias:** OP-001, DEC-015
- **Descripción:** Ejecutar un único experimento de acquire sobre SOM para buscar un filing intermedio público utilizable y resolver la única frontera ticker-level abierta de LSE/AIM. La investigación debe cerrarse en una sola salida canónica: `promoted`, `technical_followup_opened`, `exception_reaffirmed` o `discarded_with_evidence`.
- **Criterio de aceptación:** Se ejecuta exactamente un experimento sobre SOM con evidencia factual suficiente; el resultado queda cerrado en una única salida canónica; si aparece follow-up técnico, queda acotado y reusable; si no aparece filing utilizable, la excepción o descarte quedan documentados con evidencia explícita.

### BL-088 — Probar acquire Euronext fuera del carril ya validado con TEP como ancla
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** engineer
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Work kind:** investigation
- **Depende de:** —
- **Referencias:** OP-004
- **Descripción:** Ejecutar un único experimento de acquire en Euronext usando TEP como ticker ancla y un filing adicional fuera del carril ya validado para decidir si existe una limitación reusable de mercado o si TEP sigue siendo solo capacidad ticker-level. La investigación debe terminar en `technical_followup_opened`, `exception_reaffirmed` o `discarded_with_evidence`.
- **Criterio de aceptación:** Se ejecuta exactamente un experimento acotado en Euronext con TEP como ancla; el outcome queda clasificado en una única salida canónica; cualquier follow-up técnico resultante queda narrow y reproducible; no se amplía la ola a expansión de mercado general ni a otros tickers fuera del experimento definido.
---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- `Work kind` vive en la cola ejecutable y lo leen directamente `auditor` y `closeout`; no debe quedar solo implícito en descripciones o packets transitorios.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
