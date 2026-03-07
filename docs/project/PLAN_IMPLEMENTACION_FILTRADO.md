# Plan de implementación filtrado — ELSIAN-INVEST 4.0

> Generado: 2026-03-07
> Origen: `ELSIAN_4.0_plan_final_implementacion.md` (18 tareas, 6 fases)
> Filtrado contra: BACKLOG.md, BACKLOG_DONE.md, PROJECT_STATE.md, DECISIONS.md, ROLES.md, estructura actual del repo
> Propósito: instrucción ejecutable para el orchestrator de Codex

---

## Contexto para el orchestrator

Este documento es un plan de mejora estructural de ELSIAN 4.0 ya filtrado contra el estado real del repo a 2026-03-07. Las tareas marcadas como **YA COMPLETADAS** no deben ejecutarse. Las tareas marcadas como **VÁLIDAS** deben incorporarse al BACKLOG.md y ejecutarse en el orden indicado. Las tareas marcadas como **OPPORTUNITIES** no entran en el backlog activo sino en `docs/project/OPPORTUNITIES.md`.

### Estado actual del repo

- 15 tickers validados 100%, 0 manual_overrides, 29 campos canónicos, 3.278 campos validados
- 1324+ tests pasando
- Backlog activo: solo BL-005 (BAJA) — BL-057 ya completada
- Closeout contract implementado en ROLES.md y runtime
- Provenance L3 pilotado (source_map.py, TZOO 851/851)
- Auto-curate no-SEC implementado (BL-052 DONE)
- Working capital cerrado (BL-058 DONE, 29 campos)
- HTML table extractor endurecido (BL-047 DONE)
- CI básica funcional (.github/workflows/ci.yml)
- No existe `schemas/` ni `contracts/` ni `elsian/services/`

---

## Triaje de las 18 tareas del plan original

### YA COMPLETADAS — No ejecutar

| Tarea original | Razón | Evidencia |
|---|---|---|
| T10 — Auto-curate no-SEC | BL-052 DONE. Ruta determinista no-SEC implementada | BACKLOG_DONE.md |
| T13 — Provenance Level 3 | BL-053 DONE. source_map.py + SourceMap_v1 pilotado | BACKLOG_DONE.md, PROJECT_STATE.md |
| (parcial) T08 — Acquire LSE/AIM | BL-057 DONE. EuRegulatorsFetcher modo conservador LSE/AIM implementado | BACKLOG_DONE.md |

### PARCIALMENTE COMPLETADAS — Ejecutar solo lo pendiente

| Tarea original | Qué ya existe | Qué falta |
|---|---|---|
| T02 — CI hardening | ci.yml básico funcional (pytest, Python 3.11) | Separar jobs (governance/lint/typecheck/tests/security), dependabot.yml, pip-audit, actions pinneadas por SHA, permisos mínimos |
| T07 — Policies y rule packs | BL-047 DONE como fix reusable en html_tables.py; selection_rules.json existe en config/ | Externalizar thresholds y quirks a config/policy/; crear rule packs por mercado/formato (SEC HTML, ASX PDF, Euronext PDF); patrón reusable documentado |
| T08 — Hardening adquisición | sec_edgar.py, eu_regulators.py, asx.py, ir_crawler.py funcionales | User-Agent SEC configurable, rate limit con tope duro, caching TTL, retries/backoff robustos, circuit breakers para scraping terceros, manifests con source_trust_level |

### VÁLIDAS — Incorporar al backlog

Las siguientes tareas son nuevas y no conflictan con trabajo ya hecho. Están ordenadas por dependencia y prioridad.

---

#### Fase 0 — Guardrails y fuente única de verdad

**T01 — Contratos y esquemas versionados**
- **Prioridad recomendada:** ALTA
- **Dependencias:** ninguna
- **Descripción:** Crear carpeta `schemas/` con esquemas versionados para case.json, expected.json, filings_manifest.json, extraction_result.json, truth_pack.json, source_map.json, task_manifest. Script `scripts/validate_contracts.py`. Validadores en CI y CLI. Corregir drift del prompt curate-expected (referencia a "22 campos canónicos" cuando son 29; referencia a `deterministic/...`).
- **Criterio de aceptación:** Todos los `cases/*/case.json` validan contra esquema. `CaseConfig` deja de ser subconjunto engañoso. CI falla si un artefacto no cumple esquema. Prompts sincronizados con set canónico real.
- **Validación:** `python3 scripts/validate_contracts.py --all`, `pytest -q tests/contracts`, `check_governance.py`
- **Nota:** Verificar estado actual de `.github/prompts/curate-expected.prompt.md` antes de ejecutar; puede haber cambiado desde que se redactó el plan original.

**T02-parcial — Hardening de CI (lo que falta)**
- **Prioridad recomendada:** ALTA
- **Dependencias:** ninguna (paralelizable con T01)
- **Descripción:** Separar ci.yml en jobs claros (governance, lint, typecheck, tests, security). Añadir dependabot.yml (pip + github-actions). Integrar pip-audit. Pinnear Actions por SHA. Permisos mínimos por workflow/job. Política documentada de excepciones de seguridad.
- **Criterio de aceptación:** Toda PR ejecuta governance+lint+typecheck+pytest non-network+security. Actions pinneadas por SHA. Dependabot activo. pip-audit pasa o allowlist documentada.
- **Validación:** `actionlint`, `ruff check .`, `mypy elsian`, `pytest -m "not network"`, `pip-audit`

**T03 — Task manifests y core protegido**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T01
- **Descripción:** Esquema `task_manifest`. Carpeta `tasks/` o `work_packets/`. Extensión de check_governance.py para verificar: ficheros permitidos, superficies protegidas, validación requerida, docs a sincronizar, si un diff se sale del contrato.
- **Criterio de aceptación:** Al menos un manifest real para una tarea. check_governance.py detecta cambios fuera de scope permitido. El agente puede recibir tareas con contrato técnico ejecutable.
- **Validación:** `check_governance.py --format json`, `pytest -q tests/governance`
- **Nota:** ROLES.md ya define handoff canónico (sección 4.5) y post-mutation summary (sección 4.4). T03 debe extender eso, no duplicarlo.

---

#### Fase 1 — Reabrir fronteras internas del sistema

**T04 — Service layer y registry de fetchers**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T01, T02-parcial, T03
- **Descripción:** Crear `elsian/services/` con AcquireService, ConvertService, ExtractService, EvaluateService, AssembleService, DiscoverService. Crear `elsian/acquire/registry.py` con routing centralizado por source_hint. CLI convertida en adaptador fino.
- **Criterio de aceptación:** cli.py deja de contener lógica principal del runtime. Routing de fetchers en un único punto. Tests unitarios del registry + integración de services. CLI sigue funcionando sin romper UX.
- **Validación:** `pytest -q tests/services tests/acquire`, `elsian run TICKER`, `elsian eval TICKER`
- **Nota:** Esta es la tarea más grande del plan. Considerar partir en sub-paquetes si el blast radius es excesivo.

**T05 — Descomposición real del pipeline**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T04
- **Descripción:** Fases explícitas para extract_candidates, normalize, merge, evaluate. Modelo de resultado con severidad (fatal/warning/info). Persistencia de artefactos de diagnóstico aunque una fase falle de forma no fatal.
- **Criterio de aceptación:** Arquitectura documentada y real alineadas. assemble y ciertos fallos pueden ser no fatales. Tests cubren fallos fatales y no fatales.
- **Validación:** `pytest -q tests/pipeline tests/extract tests/merge`, `elsian run TICKER`

**T06 — Modelo unificado de readiness**
- **Prioridad recomendada:** BAJA
- **Dependencias:** T05
- **Descripción:** Readiness compuesto que combine matched/expected, cobertura de campos requeridos, gates del validator, cobertura de provenance, penalización de extra. Salida CLI con score legado + readiness nuevo durante transición.
- **Criterio de aceptación:** `elsian eval` reporta readiness compuesto además de score histórico. Los extra ya no son invisibles. Tickers ordenables por readiness real.
- **Validación:** `pytest -q tests/evaluate tests/validator`, `elsian eval --all`

**T07-parcial — Policies y rule packs (lo que falta)**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T05
- **Descripción:** Crear `config/policy/` con thresholds y reglas externalizadas. Rule packs mínimos: SEC HTML/iXBRL, ASX PDF, Euronext PDF/IFRS. Usar patrón ya demostrado en BL-047.
- **Criterio de aceptación:** Reglas no viven solo en extract/phase.py. Cambiar policy no obliga a tocar código core. Al menos un bugfix se resuelve vía rule pack.
- **Validación:** `pytest -q tests/rules tests/extract`, `elsian eval --all`

---

#### Fase 2 — Industrializar adquisición y onboarding

**T08-parcial — Hardening de adquisición (lo que falta)**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T04
- **Descripción:** User-Agent SEC configurable y validado. Rate limit configurable con tope duro. Caching TTL para company_tickers.json. Retries/backoff robustos para 429/5xx. Circuit breakers para scraping terceros. Manifests con source_trust_level, cache_hit, retry_count, gaps.
- **Criterio de aceptación:** Fetcher SEC no usa User-Agent placeholder. Config nunca supera límite definido. Recursos estables se reusan desde caché. Fuentes de scraping degradan con control y dejan rastro.
- **Validación:** `pytest -q tests/acquire`, `elsian acquire TICKER`

**T09 — Factoría de onboarding**
- **Prioridad recomendada:** MEDIA
- **Dependencias:** T04, T08-parcial
- **Descripción:** Comando `elsian onboard TICKER`. Pipeline: discover → acquire → convert → preflight → expected draft → coverage gap report → checklist. Artefacto `onboarding_report.json/md`.
- **Criterio de aceptación:** Un único entrypoint de onboarding. Funciona para al menos un ticker SEC y uno no-SEC. Output claro sobre qué está listo, qué gaps hay y siguiente paso.
- **Validación:** `pytest -q tests/onboarding tests/discover`, `elsian onboard TICKER`
- **Nota:** Absorbe parcialmente BL-005 (expandir cobertura de tickers) al industrializar el proceso.

---

#### Fase 3 — Observabilidad y diagnosis

**T11 — Logging estructurado y métricas por run**
- **Prioridad recomendada:** BAJA
- **Dependencias:** T05
- **Descripción:** Logging estructurado con contexto (ticker, phase, extractor, source_hint, duration). `metrics.json` por run con tiempos, conteos, score/readiness, cobertura provenance.
- **Criterio de aceptación:** Cada ejecución deja artefacto de métricas usable por scripts. Tiempos y ratios agregables sin parsear texto.
- **Validación:** `pytest -q tests/metrics`, `elsian run TICKER`

**T12 — Motor de diagnose**
- **Prioridad recomendada:** BAJA
- **Dependencias:** T11
- **Descripción:** `elsian diagnose --all`. Clustering de fallos por campo/mercado/formato/extractor/gap. Ranking de oportunidades. Output `diagnose_report.json/md`.
- **Criterio de aceptación:** El sistema señala hotspots sin inspección manual. Output sirve para decidir si abrir BL o agrupar fixes.
- **Validación:** `pytest -q tests/diagnose`, `elsian diagnose --all`

---

#### Fase 4 — Layout y DX

**T14 — Separación fixtures vs artefactos runtime**
- **Prioridad recomendada:** BAJA
- **Dependencias:** T04
- **Descripción:** Workspace configurable (--workspace o config). Separación entre metadatos/versionado del caso, golden fixtures mínimas y artefactos generados. Migración gradual.
- **Criterio de aceptación:** Runtime puede ejecutarse en workspace externo. Repo no versiona todos los artefactos generados. Tests reproducibles.
- **Validación:** `pytest -q`, `elsian run TICKER --workspace /tmp/elsian-workspace`

**T15 — Scaffolding y plantillas**
- **Prioridad recomendada:** BAJA
- **Dependencias:** T12, T14
- **Descripción:** Scripts `new_backlog_task.py`, `new_case.py` o `elsian scaffold case`. Plantillas para tarea, PR, closeout, onboarding report, diagnose report. Output de check_governance.py más útil para CI.
- **Criterio de aceptación:** Crear nueva tarea o caso requiere menos pasos manuales. Plantillas obligan a declarar aceptación, riesgos y validación.
- **Validación:** `pytest -q tests/tooling tests/governance`

---

### OPPORTUNITIES — No entran en backlog, van a OPPORTUNITIES.md

| Tarea original | Razón |
|---|---|
| T16 — Read API / serving truth_pack | Depende de que Fases 0-3 estén cerradas. Es producto, no infraestructura de Módulo 1. Ya está mencionada en OPPORTUNITIES.md. |
| T17 — Visor click-to-source + scheduler | Depende de T16 y L3 generalizado. Es producto. Ya está en OPPORTUNITIES.md. |
| T18 — Lane de experimentos y releases | Es disciplina de releases, no tiene urgencia mientras el equipo sea humano+agente. |

---

## Mapeo con backlog existente

| Backlog actual | Relación con este plan |
|---|---|
| BL-057 (Discovery LSE/AIM) | DONE ✅ (2026-03-07). Ya no aplica. |
| BL-005 (Expandir tickers) | Subordinada a T09. Solo ganar prioridad después de cerrar Fase 2. |

---

## Orden de ejecución recomendado

```
Fase 0 (paralelas entre sí):
  T01 — Contratos y esquemas
  T02-parcial — CI hardening

Fase 0 (secuencial tras T01):
  T03 — Task manifests

Fase 1:
  T04 — Service layer + registry
  T05 — Pipeline descomposición
  T06 — Readiness model
  T07-parcial — Rule packs

Fase 2:
  T08-parcial — Acquire hardening
  T09 — Onboarding factory

Fase 3:
  T11 — Logging + métricas
  T12 — Diagnose

Fase 4:
  T14 — Fixtures vs artefactos
  T15 — Scaffolding
```

---

## Principios obligatorios (heredados del plan original)

1. **Cambios por paquetes cerrados.** No mezclar más de una tarea principal por commit. Cada paquete deja el repo verde.
2. **Core protegido.** Superficie protegida con validación reforzada: `elsian/extract/phase.py`, `elsian/merge/`, `elsian/evaluate/`, `elsian/acquire/`, `config/field_aliases.json`, contratos, prompts.
3. **Sin ocultar regresiones.** Nunca bajar listón de validación para cerrar tarea.
4. **Documentación sincronizada.** Toda tarea que cambie comportamiento real revisa CHANGELOG.md, PROJECT_STATE.md, BACKLOG.md, ROLES.md según aplique.
5. **Validación obligatoria.** Cada tarea declara comandos de validación, tests, criterio de aceptación, riesgos y fuera de alcance.

---

## Instrucción para el orchestrator

```
Lee este plan en docs/project/PLAN_IMPLEMENTACION_FILTRADO.md.

Paso 1 — Incorporación al backlog:
Invoca al director para que incorpore al BACKLOG.md las tareas marcadas como VÁLIDAS,
respetando el formato existente del backlog y asignando IDs BL consecutivos desde el
último usado en BACKLOG_DONE.md. El director debe:
- Cruzar cada tarea con BACKLOG_DONE.md para confirmar que no duplica trabajo cerrado.
- Respetar las prioridades recomendadas (ALTA/MEDIA/BAJA).
- Añadir dependencias entre tareas cuando el plan las indique.
- Mover las tareas marcadas como OPPORTUNITIES a docs/project/OPPORTUNITIES.md
  si no están ya cubiertas allí.
- No tocar la BL-005 existente salvo para añadir la nota de subordinación.

Paso 2 — Validación:
Ruta: director -> gates -> auditor -> closeout
El auditor verifica que el backlog resultante es coherente, no duplica tareas cerradas,
y cumple el formato canónico.

No ejecutes ninguna tarea de implementación. Solo incorpora al backlog.
```

---

## Definición de terminado por tarea (referencia)

Una tarea solo se considera terminada cuando cumple todos estos puntos:
- código implementado sin drift con el resto del sistema;
- tests relevantes añadidos o actualizados;
- validación ejecutada con salida verde o excepción documentada;
- documentación sincronizada;
- riesgos residuales explicados;
- no introduce regresiones ocultas;
- deja preparado el terreno para la siguiente tarea según dependencias.
