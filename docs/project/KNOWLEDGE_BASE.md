# ELSIAN 4.0 — Knowledge Base Operativa

> Onboarding transversal para `4_0-ELSIAN-INVEST`.
> Si este documento contradice `VISION.md`, `docs/project/ROLES.md`, `DECISIONS.md`, `PROJECT_STATE.md` o el código, ganan los documentos canónicos y el código.

## 1. Qué es este repo

ELSIAN 4.0 está centrado hoy en un único trabajo activo: **Módulo 1**, el pipeline determinista de extracción financiera con provenance completa.

Este documento no es el manual técnico del módulo. Su función es ayudarte a arrancar rápido, orientarte en el repo y saber qué documento manda en cada tipo de decisión.

## 2. Qué documento manda

- Visión y regla de oro: `VISION.md`
- Contrato de roles, routing, gates y anti-fraude: `docs/project/ROLES.md`
- Estado real del proyecto: `docs/project/PROJECT_STATE.md`
- Prioridades activas: `docs/project/BACKLOG.md`
- Decisiones estratégicas: `docs/project/DECISIONS.md`
- Historial de cambios: `CHANGELOG.md`
- Manual técnico de Módulo 1: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`

## 3. Dónde mirar según el problema

- Estado, prioridades o decisiones: `docs/project/PROJECT_STATE.md`, `docs/project/BACKLOG.md`, `docs/project/DECISIONS.md`
- Contratos de roles o comportamiento multiagente: `docs/project/ROLES.md`
- Contexto técnico profundo de Módulo 1: `docs/project/MODULE_1_ENGINEER_CONTEXT.md`
- Acquire y fuentes: `elsian/acquire/`, `cases/<TICKER>/filings_manifest.json`
- Convert: `elsian/convert/`
- Extract: `elsian/extract/`
- Normalize: `elsian/normalize/`, `config/field_aliases.json`, `config/selection_rules.json`
- Merge: `elsian/merge/`
- Evaluate y coverage: `elsian/evaluate/`
- Curación y ground truth: `cases/<TICKER>/case.json`, `expected.json`
- Expansión de campos: `docs/project/FIELD_DEPENDENCY_MATRIX.md`, `docs/project/field_dependency_matrix.json`

## 4. Invariantes transversales

- La extracción cuantitativa de producción es determinista. No introducir dependencia LLM dentro del pipeline principal.
- `VISION.md` prevalece sobre roadmap, entusiasmo o inercia.
- La provenance no es opcional. Un dato sin provenance útil no está terminado.
- Configuración antes que código para reglas que puedan variar por ticker o mercado.
- Un `manual_override` es deuda técnica o excepción documentada, no una victoria.
- Un fix local no está terminado hasta que se comprueba que no rompe otros casos.

## 5. Riesgos recurrentes del repo

- **Scope creep**: meter producto, UI, API, LLM o módulos futuros dentro de una tarea de Módulo 1.
- **Governance drift**: cambiar código o comportamiento sin mantener alineados los documentos canónicos correctos.
- **Expected weakening**: recortar ground truth para inflar score en vez de arreglar el pipeline.
- **Blast radius mal acotado**: un fix local en aliases, selection o merge rompe otros tickers si no se compara con el último estado verde.
- **Contrato duplicado**: redefinir reglas en wrappers o prompts en vez de tocar `docs/project/ROLES.md`.

## 6. Uso correcto de este documento

- Úsalo para arrancar rápido y orientarte.
- Si necesitas política de rol, ve a `docs/project/ROLES.md`.
- Si necesitas doctrina técnica de Módulo 1, ve a `docs/project/MODULE_1_ENGINEER_CONTEXT.md`.
- No dupliques aquí métricas vivas, backlog activo, decisiones completas ni detalle técnico profundo del módulo.

## 7. Paralelismo multiagente: estado actual y criterio futuro

### Estado actual

- El repositorio no debe tratarse hoy como `parallel-ready` para mutaciones concurrentes sobre el mismo árbol principal.
- El paralelismo sí es útil ya para exploración, packaging, auditoría y validación read-only.
- La implementación mutante por defecto sigue siendo secuencial sobre `main`, con integración y cierre seriales.

### Qué aprendimos del primer intento

- El problema no fue escribir código en paralelo, sino integrar y cerrar sin contaminar el árbol principal.
- Un paquete puede ser técnicamente correcto y aun así romper la elegibilidad de `auto-commit` si el worktree deja de estar limpio o si aparece dirty ajeno.
- `CHANGELOG.md`, backlog/gobernanza y varias superficies transversales siguen siendo puntos de serialización natural.
- Tener tareas razonablemente bien descritas en `BACKLOG.md` ayuda, pero no sustituye reglas de write set, aislamiento de workspace y proceso de integración.

### Criterio mínimo de `parallel-ready`

ELSIAN solo podrá considerarse `parallel-ready` para mutaciones reales cuando, como mínimo, se cumpla todo lo siguiente:

- repo limpio al inicio, salvo `workspace_only_dirty`;
- una sola BL por agente;
- write set explícito por BL;
- sin solape material entre write sets;
- surfaces seriales declaradas y respetadas;
- integración siempre serial en el padre neutral;
- `gates -> auditor -> closeout` ejecutados por BL, no en cierre conjunto;
- política explícita de aborto y rollback si aparece conflicto, drift o contaminación del worktree.

### Modelo objetivo recomendado

- Modelo preferido: `git worktree + una rama por BL`.
- El padre neutral (`orchestrator`) sigue siendo el único responsable de integrar, cerrar y decidir commits finales.
- El uso de subagentes forked sin aislamiento git formal puede servir para pilotos o trabajo read-only, pero no debe considerarse el modelo estable de paralelización mutante.

### Surfaces que deben seguir serializadas por defecto

- `docs/project/ROLES.md`
- `docs/project/BACKLOG.md`
- `docs/project/PROJECT_STATE.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `elsian/cli.py`
- `elsian/extract/phase.py`
- `elsian/extract/html_tables.py`
- `elsian/evaluate/validation.py`

### Backlog asociado

- `BL-072` define el criterio oficial de `parallel-ready` y el proceso operativo de paralelización.
- `BL-073` ejecuta el primer piloto real solo cuando `BL-072` y `BL-061` estén cerradas.
- Hasta entonces, el paralelismo mutante debe tratarse como no habilitado de forma general.
