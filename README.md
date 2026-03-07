# ELSIAN-INVEST 4.0

Pipeline determinista de extracción financiera con provenance completa.

## Qué es hoy

ELSIAN 4.0 está centrado en un único trabajo activo: **Módulo 1**, el pipeline que descarga filings, los convierte, extrae datos cuantitativos, normaliza, fusiona y valida el resultado sin usar LLM dentro de la capa cuantitativa de producción.

La visión operativa y la regla de oro viven en [VISION.md](VISION.md).
El estado vivo del proyecto vive en [PROJECT_STATE.md](docs/project/PROJECT_STATE.md).

## Qué documento manda para cada cosa

- Visión y foco: [VISION.md](VISION.md)
- Contrato de roles y runtime multiagente: [ROLES.md](docs/project/ROLES.md)
- Estado real del proyecto: [PROJECT_STATE.md](docs/project/PROJECT_STATE.md)
- Backlog operativo: [BACKLOG.md](docs/project/BACKLOG.md)
- Historial de tareas cerradas: [BACKLOG_DONE.md](docs/project/BACKLOG_DONE.md)
- Decisiones estratégicas: [DECISIONS.md](docs/project/DECISIONS.md)
- Onboarding transversal: [KNOWLEDGE_BASE.md](docs/project/KNOWLEDGE_BASE.md)
- Manual técnico de Módulo 1: [MODULE_1_ENGINEER_CONTEXT.md](docs/project/MODULE_1_ENGINEER_CONTEXT.md)
- Horizonte de producto: [ROADMAP.md](ROADMAP.md)

## Arquitectura activa

Flujo actual:

`Acquire -> Convert -> Extract -> Normalize -> Merge -> Evaluate`

Superficies principales:

- `elsian/acquire/`: fetchers, crawling, market data, transcripts, source compilation
- `elsian/convert/`: HTML -> Markdown, PDF -> text, quality gates
- `elsian/extract/`: iXBRL, tablas HTML/PDF, narrativa, phase orchestration
- `elsian/normalize/`: aliases, escala, signos, sanity checks
- `elsian/merge/`: resolución multi-filing
- `elsian/evaluate/`: validator, coverage audit, evaluator
- `cases/<TICKER>/`: case metadata, filings, expected truth, extraction outputs

## Instalación

Requisito recomendado: **Python 3.11+**

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e ".[dev]"
```

## CLI principal

```bash
python3 -m elsian.cli --help
python3 -m elsian.cli acquire TICKER
python3 -m elsian.cli extract TICKER
python3 -m elsian.cli run TICKER
python3 -m elsian.cli eval TICKER
python3 -m elsian.cli eval --all
python3 -m elsian.cli curate TICKER
python3 -m elsian.cli coverage --all
python3 -m elsian.cli assemble TICKER
python3 -m elsian.cli discover TICKER
```

## Ciclo de trabajo recomendado

### 1. Ponerte al día

En Codex:

```text
$elsian-orchestrator ponme al día
```

### 2. Planificar

```text
$elsian-orchestrator qué deberíamos hacer para avanzar
```

### 3. Ejecutar una tarea

```text
$elsian-orchestrator ejecuta BL-058 end-to-end. No hagas commit ni push.
```

### 4. Uso experto por rol

```text
$elsian-director ...
$elsian-engineer ...
$elsian-auditor ...
$elsian-kickoff ...
```

## Validación

Validaciones típicas:

```bash
python3 -m pytest -q
python3 -m elsian.cli eval TICKER
python3 -m elsian.cli eval --all
python3 scripts/check_governance.py --format text
```

Los tiers de validación (`targeted`, `shared-core`, `governance-only`) están definidos en [ROLES.md](docs/project/ROLES.md).

## Estado y prioridades

No dupliques métricas vivas en este README. Para cobertura, tests, overrides y tickers validados, consulta siempre:

- [PROJECT_STATE.md](docs/project/PROJECT_STATE.md)
- [BACKLOG.md](docs/project/BACKLOG.md)

## Regla de oro

No se trabaja en módulos futuros, API, visor web ni análisis hasta que el Módulo 1 siga siendo sólido, reproducible y documentado.
