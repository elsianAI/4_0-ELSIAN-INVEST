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

### BL-058 — Expandir campos canónicos: oleada 2 (working capital)
- **Prioridad:** ALTA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-035 (oleada 1 DONE)
- **Referencias:** DEC-021
- **Descripción:** Añadir `accounts_receivable`, `inventories` y `accounts_payable` como campos canónicos para completar el bloque de working capital. Seguir el mismo patrón de la oleada 1: ampliar `field_aliases.json` e `ixbrl_concept_map.json`, pilotar primero en TZOO y NVDA, y después expandir al resto de tickers donde exista representación clara en el filing.
- **Criterio de aceptación:** Los 3 campos nuevos existen en la configuración canónica, al menos dos tickers piloto quedan curados y validados con ellos, `eval --all` sigue verde y hay tests nuevos o ampliados para el patrón exacto de working capital.

### BL-052 — Auto-curate para tickers no-SEC (expected.json desde PDF)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-007 (PdfTableExtractor DONE)
- **Referencias:** DEC-009
- **Descripción:** `elsian curate` hoy depende de iXBRL y por eso solo automatiza tickers SEC/ESEF. Añadir una ruta alternativa para tickers no-SEC basada en extracción PDF determinista, cross-reference entre filings y generación de `expected_draft.json` con huecos y confianza explícitos, sin fingir precisión iXBRL.
- **Criterio de aceptación:** `elsian curate TEP` y al menos otro ticker no-SEC generan un `expected_draft.json` útil, con cobertura material respecto al `expected.json` manual y con gaps/confianza marcados de forma explícita.

### BL-053 — Provenance Level 3 (source_map.json)
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** targeted
- **Depende de:** BL-006 (Provenance L2 DONE)
- **Referencias:** DEC-024
- **Descripción:** Añadir el mapeo inverso desde cada dato validado a la posición exacta en el documento original (HTML/PDF). Esto implica generar `source_map.json` o artefacto equivalente con offsets, páginas o líneas, manteniendo la separación entre el pipeline determinista y futuros visores/productos.
- **Criterio de aceptación:** Al menos un ticker genera artefactos de provenance L3 trazables, con tests unitarios y una demostración clara de “click to source” a nivel técnico.

### BL-057 — Discovery automático de filings LSE/AIM (DEC-025)
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** BL-013 (IR crawler DONE)
- **Referencias:** DEC-025
- **Descripción:** Cerrar la limitación conocida de adquisición en LSE/AIM. El `ir_crawler` integrado sigue sin descubrir automáticamente ciertos paths CDN/media de compañías como SOM. Sigue siendo una mejora válida, pero no bloqueante y subordinada a que exista masa crítica LSE/AIM o un trigger claro que justifique invertir en esa infraestructura.
- **Criterio de aceptación:** `elsian acquire SOM` funciona sin `filings_sources` hardcodeados en `case.json`, o queda documentado con evidencia técnica verificable por qué no es factible aún.

### BL-047 — Mejorar HTML table extractor: interest_income + capex
- **Prioridad:** MEDIA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** —
- **Referencias:** —
- **Descripción:** NVDA sigue marcando gaps reutilizables del extractor HTML: `interest_income`, `capex` y un caso de `total_debt` con row selection incorrecta. Tratarlo como mejora de patrón y no como un fix exclusivo de NVDA.
- **Criterio de aceptación:** Al menos uno de los patrones se resuelve de forma reusable, NVDA mejora o se mantiene al máximo posible sin regresiones, y hay tests de patrón o de ticker que reproduzcan el bug corregido.

### BL-005 — Expandir cobertura de tickers (diversidad de mercados/formatos)
- **Prioridad:** BAJA
- **Estado:** TODO
- **Asignado a:** sin asignar
- **Módulo:** Module 1
- **Validation tier:** shared-core
- **Depende de:** —
- **Referencias:** DEC-015
- **Descripción:** Añadir tickers nuevos no por volumen, sino por diversidad real de mercados, reguladores, sectores y formatos. Debe ejecutarse solo cuando las prioridades técnicas inmediatas estén suficientemente cerradas y cada ticker nuevo cubra un gap concreto que hoy no está representado.
- **Criterio de aceptación:** Cada ticker nuevo validado cubre un gap documentado de diversidad y no introduce regresiones en el conjunto existente.

---

## Notas

- Las prioridades activas las establece el director según `VISION.md`, `PROJECT_STATE.md`, `DECISIONS.md` y el estado real del repo.
- Una tarea pasa a `BACKLOG_DONE.md` cuando deja de competir por atención operativa.
- Las ideas de medio/largo plazo y el trabajo fuera del perímetro ejecutable van a `docs/project/OPPORTUNITIES.md`, no a este fichero.
