# ELSIAN-INVEST 4.0 — Backlog Cerrado

> Archivo histórico de tareas completadas. No es la cola de trabajo activa.
> El backlog operativo actual vive en `docs/project/BACKLOG.md`.

---

## Tareas completadas

---

### BL-065 — T07 — Policies y rule packs (scope filtrado restante)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-063
- **Descripción:** Se cierra BL-065 sobre el alcance estrecho ya absorbido en el extract path de Module 1, sin abrir un policy engine, sin rediseñar merge/runtime y sin vender una capa genérica de rules fuera del problema real. El paquete técnico externaliza de forma declarativa thresholds y quirks de extracción en `config/extraction_rules.json`, resuelve packs reutilizables por mercado/formato (`sec_html`, `pdf_ifrs`, `pdf_asx`) con precedencia base → pack → `config_overrides` de caso, y cablea esa policy solo donde hoy aporta valor factual: `ExtractPhase`, `html_tables` y su routing de `source_hint`. El audit-fix final restaura además la precedencia real del tercer nivel (`config_overrides` desde `CaseConfig`) para que el override de `case.json` no quede silenciosamente ignorado.
- **Criterio de aceptación:** ✓ `BL-065` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ El cierre factual se mantiene estrecho: externalización declarativa de policy en extract, no policy engine ni rediseño de merge/runtime. ✓ `python3 -m pytest -q tests/unit/test_config.py tests/unit/test_extract_phase.py tests/unit/test_html_tables.py` PASS (`121 passed`). ✓ `python3 -m pytest -q --disable-warnings` PASS (`1560 passed, 5 skipped, 1 warning`). ✓ `python3 -m elsian eval --all` PASS 16/16. ✓ `git diff --check` limpio. ✓ Auditoría técnica del paquete ya cerrada en verde.

### BL-068 — T11 — Logging estructurado y métricas por run
- **Prioridad:** BAJA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-063
- **Descripción:** Se cierra BL-068 sobre el scope estrecho y factual ya absorbido en el runtime actual de `elsian run`, sin abrir un framework horizontal de observabilidad. El cierre deja observabilidad machine-readable por run mediante `run_metrics.json`, con identidad de ejecución, timestamps, flags, `final_status`, métricas agregadas por fase y duraciones estructuradas (`duration_ms`) alimentadas desde `PhaseResult` y `Pipeline`. La extracción aporta diagnósticos estructurados mínimos (`filings_used`, `periods`, `fields`) y el artefacto se escribe en best-effort incluso en paths fatales, de modo que el diagnóstico no depende de parsear texto libre ni rompe el contrato actual del pipeline.
- **Criterio de aceptación:** ✓ `BL-068` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ El cierre factual se mantiene estrecho: observabilidad machine-readable por run, no framework horizontal. ✓ `python3 -m pytest -q tests/unit/test_pipeline.py tests/integration/test_run_command.py` PASS (`46 passed`). ✓ `python3 -m elsian run TZOO --skip-assemble` PASS 100.0% (`348/348`). ✓ `python3 -m elsian run TZOO --with-acquire` PASS 100.0% (`348/348`). ✓ `python3 -m pytest -q --disable-warnings` PASS (`1550 passed, 5 skipped, 1 warning`). ✓ `python3 -m elsian eval --all` PASS 16/16. ✓ `git diff --check` limpio.

### BL-077 — Investigar inconsistencias de campos derivados
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-075, BL-076
- **Descripción:** Se cierra BL-077 como trabajo de clasificación y documentación filing-backed de inconsistencias derivadas, no como una ola de fixes shared-core generalizados. La investigación consolidada en `docs/reports/DERIVED_INCONSISTENCIES_RESOLUTION.md` resuelve el universo auditado de 17 discrepancias dejando 16 casos clasificados como **(b) fórmula inaplicable** y 1 caso como **(c) componente mal capturado** (`SONO` Q3-2023), sin abrir correcciones oportunistas sobre `expected.json` ni vender cambios de pipeline que esta BL no ejecutó. El cierre factual deja explícito que la evidencia técnica ya existía en el informe y en `CHANGELOG.md`: no hubo casos **(a)** corregidos en esta ola, no se añadieron `manual_overrides`, y la única deuda técnica remanente queda documentada solo como candidata futura porque requiere reconciliación simultánea de pipeline y truth, sin BL asignada en este cierre.
- **Criterio de aceptación:** ✓ Cada una de las 17 discrepancias `DERIVED_INCONSISTENT` del alcance investigado queda clasificada con evidencia filing-backed en `docs/reports/DERIVED_INCONSISTENCIES_RESOLUTION.md`. ✓ El cierre de BL-077 queda reflejado sin reabrir la parte técnica ni recontar esta ola como fix shared-core amplio. ✓ `BL-077` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ La trazabilidad técnica ya documentada se mantiene veraz: `python3 -m elsian eval ACLS NEXN SONO SOM TZOO` → todos 100.0% y `git diff --check` clean según la evidencia ya registrada en `CHANGELOG.md`.

### BL-072 — Habilitación de paralelismo: criterio `parallel-ready` y proceso operativo
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** director
- **Depende de:** BL-061
- **Descripción:** Se cierra BL-072 como mutación estrictamente de governance y canonicals, sin tocar código técnico ni abrir nuevas BL. El cierre deja explícito y consistente el criterio oficial de `parallel-ready` como elegibilidad operativa controlada, no como permiso general de mutación concurrente. `docs/project/ROLES.md` fija el checklist go/no-go, el modelo obligatorio `git worktree + una rama por BL`, la regla de una BL por hijo mutante, las surfaces seriales por defecto, la disciplina de `write_set`, el rol exclusivo del padre neutral en integración serial y `closeout`, y la política de aborto/rollback. `docs/project/KNOWLEDGE_BASE.md` pasa a remitir a esa fuente de verdad, `DEC-029` canoniza la decisión y `BL-073` deja de estar bloqueada solo en sentido documental: el piloto ya puede empaquetarse, pero sigue condicionado a pasar el checklist `parallel-ready` en cada ejecución concreta.
- **Criterio de aceptación:** ✓ Existe definición explícita de `parallel-ready` en canonicals. ✓ Existe checklist go/no-go antes de lanzar mutación paralela. ✓ Queda fijado el proceso end-to-end con `git worktree + una rama por BL`, ejecución aislada por agente, `gates -> auditor -> closeout` por BL, integración serial y aborto/rollback. ✓ Quedan definidas las surfaces que nunca se paralelizan por defecto. ✓ `BL-072` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ `BL-073` queda desbloqueada documentalmente sin convertirse en permiso general de paralelización. ✓ Validación de governance ejecutada con `python3 scripts/check_governance.py --format json` y `git diff --check`.

### BL-066 — T08 — Hardening de adquisición (scope filtrado restante)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-062
- **Descripción:** Se cierra BL-066 sobre el hardening mínimo real del acquire path vivo de Module 1, sin abrir discover ni un framework HTTP horizontal. El cierre absorbe el paquete útil para `sec_edgar`, `asx` y `eu_regulators`: identidad HTTP configurable y acotada, retry/backoff bounded reutilizable, caché TTL explícita para `company_tickers.json` en SEC y metadatos factuales de observabilidad en `AcquisitionResult` y `filings_manifest.json`. La remediación final post-auditoría restaura además la robustez del path SEC en cache miss o TTL expiry haciendo que `load_json_ttl` pase por `bounded_get`, evitando la regresión que había eliminado retry/backoff en la resolución de CIK.
- **Criterio de aceptación:** ✓ `BL-066` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ `python3 -m pytest -q tests/unit/test_sec_edgar.py tests/unit/test_asx.py tests/unit/test_eu_regulators.py tests/unit/test_acquisition_result.py` PASS (`68 passed`) y, tras el audit-fix final, `python3 -m pytest -q tests/unit/test_acquire_http_helpers.py tests/unit/test_sec_edgar.py tests/unit/test_asx.py tests/unit/test_eu_regulators.py tests/unit/test_acquisition_result.py` PASS (`84 passed`). ✓ `python3 -m pytest -q tests/unit/test_acquire_registry.py tests/unit/test_cli_fetcher_routing.py tests/unit/test_bl062_entrypoints.py` PASS (`32 passed`). ✓ `python3 -m pytest -q tests/integration/test_run_command.py` PASS (`22 passed`). ✓ `python3 -m pytest -q tests/integration/test_ir_crawler_integration.py` PASS (`15 passed`). ✓ `python3 -m elsian acquire TZOO` PASS con coverage 100.0%. ✓ `python3 -m elsian run TZOO --with-acquire` PASS 100.0% (`348/348`). ✓ `python3 -m pytest -q` PASS (`1538 passed, 5 skipped, 1 warning`). ✓ `git diff --check` limpio. ✓ Auditoría final green sin hallazgos materiales.


### BL-063 — T05 — Descomposición real del pipeline
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-062
- **Descripción:** Se cierra BL-063 sobre el alcance mínimo real que el repo necesitaba en el runtime actual de `elsian run`, sin abrir una descomposición amplia del pipeline ni tocar extractores, config o casos. El cierre deja absorbidos los invariantes del packet: `PhaseResult` expresa severidad explícita y diagnósticos mínimos, `Pipeline` acumula resultados por fase y corta solo en fatales, y `elsian run` usa una secuencia real de fases (`acquire` opcional, `convert`, `extract`, `evaluate`, `assemble`) con observabilidad por fase y semántica no fatal para warnings operativos. El remate final de auditoría cierra además el path fatal que ya no pisa `extraction_result.json`, marca `warning` real cuando `ConvertPhase` acumula fallos y cubre el branch `--with-acquire` con tests del run path sin dependencia de red.
- **Criterio de aceptación:** ✓ `BL-063` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ `python3 -m pytest -q tests/unit/test_pipeline.py tests/integration/test_run_command.py` PASS (`34 passed`). ✓ `python3 -m elsian run TZOO --skip-assemble` PASS 100.0% (`348/348`). ✓ `python3 -m elsian eval TZOO` PASS 100.0% (`348/348`). ✓ `python3 -m pytest -q` PASS (`1514 passed, 5 skipped, 1 warning`). ✓ `python3 -m elsian eval --all` exit 0 sin `FAIL`. ✓ `git diff --check` limpio. ✓ Auditoría final green sin hallazgos materiales bloqueantes.


### BL-062 — T04 — Service layer y registry de fetchers
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cierra BL-062 sobre el alcance real ya absorbido y auditado en verde en el repo, sin abrir todavía `BL-063` ni `BL-066`. El cierre factual reconoce un único registry/selector de fetchers dentro de acquire, reutilizado por `elsian/acquire/phase.py` y `elsian/cli.py`, con la CLI reducida a adaptador fino del path de adquisición. La reconciliación documental deja explícito que la ola cerrada fue la eliminación del routing duplicado SEC/ASX/EU/HKEX/manual hacia un único punto reusable en `elsian/acquire/registry.py`, junto con la cobertura unitaria de registry, routing CLI y entrypoints de acquire.
- **Criterio de aceptación:** ✓ `BL-062` sale de `docs/project/BACKLOG.md` y queda archivada aquí. ✓ `python3 -m pytest -q tests/unit/test_cli_fetcher_routing.py tests/unit/test_acquire_registry.py tests/unit/test_bl062_entrypoints.py` PASS (`32 passed`). ✓ `python3 -m elsian eval --all` exit 0 sin `FAIL`. ✓ `python3 -m pytest -q` PASS (`1487 passed, 5 skipped, 1 warning`). ✓ `git diff --check` limpio. ✓ `docs/project/PROJECT_STATE.md` deja a `BL-063` como siguiente prioridad shared-core viva y mantiene `BL-066` solo como frente posterior dependiente.

### BL-061 — T03 — Aterrizar task_manifest real y enforcement mínimo de scope
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** BL-059
- **Descripción:** Se cierra BL-061 sobre el alcance mínimo ya implementado y validado en el repo, sin abrir `BL-062` ni `BL-072`. El cierre deja absorbidos los invariantes que definían la ola: existe un `task_manifest` real repo-trackeado bajo `tasks/`, `scripts/check_governance.py` ya puede ejecutar comprobación manifest-aware contra `write_set`, `blocked_surfaces`, `validation_tier`, `claimed_bl_status` y reconciliación documental requerida, y la reconciliación de closeout queda alineada con el manifest real en `CHANGELOG.md`, `docs/project/BACKLOG.md`, `docs/project/BACKLOG_DONE.md` y `docs/project/PROJECT_STATE.md`.
- **Criterio de aceptación:** ✓ `python3 scripts/check_governance.py --format json` ejecutado como control de gobernanza del repo. ✓ `git diff --check -- docs/project/BACKLOG.md docs/project/BACKLOG_DONE.md docs/project/PROJECT_STATE.md CHANGELOG.md` limpio. ✓ `BL-061` sale de `docs/project/BACKLOG.md`, queda archivada en `docs/project/BACKLOG_DONE.md`, y `docs/project/PROJECT_STATE.md` deja de presentarla como prioridad viva.

### BL-059 — Reconciliación y hardening de la capa contractual existente
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-10)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cierra BL-059 sobre el alcance real ya implementado en el repo, sin vender una capa contractual greenfield. El cierre deja absorbidos los tres invariantes que definían la BL: alineación del set canónico entre `schemas/v1/common.schema.json`, `config/field_aliases.json` y `elsian/evaluate/validation.py`; coherencia cross-file básica entre `case.json`, `expected.json` y artefactos derivados solo cuando están repo-trackeados; y validación contractual explícita en CI mediante `scripts/validate_contracts.py --all` y `tests/contracts`. `BL-061` y `BL-062` permanecen fuera de alcance, y el archivo de BL-059 reconoce ahora el cierre real: la archivación inicial no agotó toda la reconciliación documental, porque después sí fue necesaria una reconciliación mínima adicional de `PROJECT_STATE.md` para retirar a BL-059 como prioridad viva residual.
- **Criterio de aceptación:** ✓ `python3 scripts/validate_contracts.py --all` PASS. ✓ `python3 -m pytest -q tests/contracts` PASS (`21 passed`). ✓ `python3 -m elsian eval --all` PASS 16/16. ✓ `python3 -m pytest -q` PASS (`1450 passed, 5 skipped, 1 warning`). ✓ `git diff --check` limpio. ✓ Auditoría final del padre sin findings materiales.

### BL-084 — Implementar fallback no duplicativo de `finance lease obligation` hacia `total_debt`
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-09)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cierra BL-084 con la policy de `DEC-028` ya absorbida en shared-core y revalidada tras el ajuste final de aislamiento por filing. `total_debt` puede sintetizarse desde `Current portion of finance lease obligation` + `Long-term finance lease obligation` solo como fallback debt-like cuando el filing actual no expone una señal mejor de deuda agregada; la precedencia sigue siendo estricta, el fallback nunca duplica una línea explícita ya totalizada y quedan excluidos `operating lease liabilities`, `lease expense` y `principal payments on finance lease obligation`. El fix final corrige además el bloqueo cruzado entre filings: una señal explícita en otro filing del mismo periodo ya no impide sintetizar el fallback filing-local, y la resolución definitiva sigue delegada al sort key de merge. El cierre no cambia `PROJECT_STATE.md`: el estado operativo del proyecto ya estaba correctamente reflejado por los gates verdes y por la trazabilidad técnica existente.
- **Criterio de aceptación:** ✓ `python3 -m pytest -q tests/unit/test_extract_phase.py` PASS (64 passed). ✓ `python3 -m elsian eval ACLS` PASS 100.0% (486/486) `wrong=0 missed=0 extra=287`. ✓ `python3 -m elsian eval --all` PASS 16/16 tickers. ✓ `python3 -m pytest -q` PASS (`1432 passed, 5 skipped, 1 warning`). ✓ La regresión multi-filing queda cubierta explícitamente y `check_governance` permanece sin drift documental.

### BL-076 — Retroportar campos BL-035/BL-058 y total_debt a expected.json existentes
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-09)
- **Asignado a:** engineer
- **Depende de:** BL-074
- **Descripción:** Se cierra BL-076 con el paquete técnico final realmente verificado, no con la versión intermedia que dejaba gaps abiertos. El cierre incorpora el script nuevo `scripts/backfill_bl076_fields.py` y sus 20 tests unitarios, retroporta los 7 campos objetivo (`cfi`, `cff`, `delta_cash`, `accounts_receivable`, `accounts_payable`, `inventories`, `total_debt`) a 14 `expected.json` existentes (`0327`, `ACLS`, `CROX`, `GCT`, `IOSP`, `KAR`, `NEXN`, `NVDA`, `PR`, `SOM`, `SONO`, `TALO`, `TEP`, `TZOO`), y deja explícito que `ADTN` e `INMD` no recibieron adiciones elegibles en esta ola. El paquete final también absorbió el fix shared-core mínimo en `elsian/extract/phase.py` para descartar `inventories` espurios provenientes de cash flow con named subsection en `clean.md` sin romper rutas `txt`/table, y cerró los ajustes filing-backed finales en `CROX` quarterly `total_debt` y en FY de `SONO` para alinear la verdad canonizada con los winners reales del pipeline respaldados por filing. El efecto operativo es una retroportación cerrada en verde con `eval --all` 16/16, 4,616 campos validados y sin cambiar el conteo efectivo de `DEC-015`, que permanece en **15** (`14 FULL + KAR`).
- **Nota de governance:** El scope final canónico de BL-076 sí incluyó `total_debt`, pero al cierre quedaron gaps residuales de `total_debt` en 11 tickers que no constituyen una omisión probada del retroport final. La verificación posterior con la misma lógica de curate confirma `draft_has=0` en todos esos casos, por lo que los faltantes quedan clasificados como gaps de curate/draft no auto-generados. Resumen factual: `0327` 3 (`FY2024`, `FY2023`, `FY2022`); `ACLS` 21 (`FY2025`, `FY2024`, `FY2023`, `FY2022`, `FY2021`, `FY2020`, `Q1-2021`, `Q2-2021`, `Q3-2021`, `Q1-2022`, `Q2-2022`, `Q3-2022`, `Q1-2023`, `Q2-2023`, `Q3-2023`, `Q1-2024`, `Q2-2024`, `Q3-2024`, `Q1-2025`, `Q2-2025`, `Q3-2025`); `ADTN` 22 (`FY2018`, `FY2020`, `FY2021`, `FY2022`, `FY2023`, `FY2024`, `FY2025`, `Q1-2021`, `Q2-2021`, `Q3-2021`, `Q1-2022`, `Q2-2022`, `Q3-2022`, `Q1-2023`, `Q2-2023`, `Q3-2023`, `Q1-2024`, `Q2-2024`, `Q3-2024`, `Q1-2025`, `Q2-2025`, `Q3-2025`); `GCT` 12 (`FY2025`, `FY2024`, `FY2020`, `Q1-2023`, `Q2-2023`, `Q3-2023`, `Q1-2025`, `Q2-2025`, `Q3-2025`, `Q1-2024`, `Q2-2024`, `Q3-2024`); `INMD` 12 (`FY2020`, `FY2021`, `FY2022`, `FY2023`, `FY2024`, `FY2025`, `Q3-2024`, `Q4-2024`, `Q1-2025`, `Q2-2025`, `Q3-2025`, `Q4-2025`); `IOSP` 22 (`FY2025`, `FY2024`, `FY2023`, `FY2022`, `FY2021`, `Q1-2021`, `Q2-2021`, `Q3-2021`, `Q1-2022`, `Q2-2022`, `Q3-2022`, `Q1-2023`, `Q2-2023`, `Q3-2023`, `Q4-2023`, `Q1-2024`, `Q2-2024`, `Q3-2024`, `Q4-2024`, `Q1-2025`, `Q2-2025`, `Q3-2025`); `NEXN` 6 (`Q1-2024`, `Q2-2024`, `Q3-2024`, `Q1-2025`, `Q2-2025`, `Q3-2025`); `SONO` 16 (`FY2025`, `FY2024`, `FY2023`, `FY2022`, `Q1-2024`, `Q1-2025`, `Q2-2022`, `Q2-2023`, `Q2-2024`, `Q2-2025`, `Q3-2022`, `Q3-2023`, `Q4-2022`, `Q4-2023`, `Q4-2024`, `Q4-2025`); `SOM` 16 (`FY2024`, `FY2023`, `FY2022`, `FY2021`, `FY2020`, `FY2019`, `FY2018`, `FY2017`, `FY2016`, `FY2015`, `FY2014`, `FY2013`, `FY2012`, `FY2011`, `FY2010`, `FY2009`); `TEP` 4 (`FY2019`, `FY2021`, `FY2022`, `H1-2024`); `TZOO` 18 (`FY2024`, `FY2023`, `FY2022`, `FY2021`, `FY2020`, `FY2019`, `Q3-2025`, `Q2-2025`, `Q1-2025`, `Q3-2024`, `Q2-2024`, `Q1-2024`, `Q3-2023`, `Q2-2023`, `Q1-2023`, `Q3-2022`, `Q2-2022`, `Q1-2022`).
- **Criterio de aceptación:** ✓ `python3 -m elsian eval --all` PASS 16/16 con conteos `0327 146/146`, `ACLS 486/486`, `ADTN 520/520`, `CROX 326/326`, `GCT 330/330`, `INMD 234/234`, `IOSP 430/430`, `KAR 61/61`, `NEXN 177/177`, `NVDA 422/422`, `PR 185/185`, `SOM 203/203`, `SONO 404/404`, `TALO 235/235`, `TEP 109/109`, `TZOO 348/348`. ✓ `python3 -m pytest -q` PASS (`1417 passed, 5 skipped, 1 warning`). ✓ `python3 -m pytest -q tests/unit/test_backfill_bl076_fields.py` PASS (`20 passed`). ✓ Contratos post-fix PASS para `cases/CROX/expected.json`, `cases/IOSP/expected.json` y `cases/SONO/expected.json`. ✓ Auditoría final sin hallazgos materiales bloqueantes; queda solo riesgo residual leve por falta de tests unitarios específicos de la nueva rama del extractor que descarta `inventories` espurios desde cash flow con named subsection.

---

### BL-083 — Implementar HkexFetcher y ampliar 0327 con semestrales HKEX
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-09)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cerró el frente HKEX de `0327` sin vender una portabilidad falsa desde 3.0. La referencia 3.0 sólo sirvió para discovery/inventario y contraste de filings; el soporte determinista reusable quedó implementado en 4.0 sobre `elsian/extract/detect.py` y `elsian/extract/html_tables.py`, que ahora reconocen day-first H1 (`Six months ended 30 June 2025`), extraen bloques compactos bilingües de HKEX desde TXT (`income statement`, `balance sheet`, `cash flow`, `expenses by nature`, `receivables`, `per-share`) y resuelven `shares_outstanding` también en la variante `weighted average number of ordinary shares in issue`. Además, el cierre deja de depender de artefactos sólo locales: el repo versiona el set mínimo de TXT `hkex_manual` para `0327` (`SRC_001`-`SRC_006`) mediante una excepción estrecha en `.gitignore`, y un checkout limpio exportado desde git vuelve a validar `0327` al 100%. Con ello `cases/0327/expected.json` incorpora `H1-2023`, `H1-2024` y `H1-2025` filing-backed, `cases/0327/case.json` pasa a `period_scope: FULL`, y `0327` promueve de `ANNUAL_ONLY` a `FULL` con 6 periodos (`3A+3H`) y 131/131 campos validados. FY2018 no se canoniza en esta ola.
- **Criterio de aceptación:** ✓ `python3 scripts/validate_contracts.py --schema case --path cases/0327/case.json` PASS. ✓ `python3 scripts/validate_contracts.py --schema expected --path cases/0327/expected.json` PASS. ✓ `python3 -m pytest -q tests/unit/test_detect.py tests/unit/test_html_tables.py tests/unit/test_extract_phase.py` PASS (110 passed). ✓ `python3 -m pytest -q tests/unit/test_hkex_fetcher.py tests/unit/test_cli_fetcher_routing.py` PASS (17 passed). ✓ `python3 -m elsian eval 0327` PASS 100.0% (131/131) con `wrong=0`, `missed=0`, `extra=62`. ✓ `python3 -m elsian eval --all` PASS 16/16. ✓ `python3 -m pytest -q` PASS (`1397 passed, 5 skipped, 1 warning`). ✓ `git diff --check` limpio. ✓ `python3 scripts/check_governance.py --format json` sin IDs duplicados y con `project_state_lags_changelog=false`. ✓ `git ls-files cases/0327/filings` incluye `SRC_001`-`SRC_006`. ✓ Un checkout limpio exportado desde git vuelve a dar `python3 -m elsian eval 0327` → PASS 100.0% (131/131).

---

### BL-081 — Promover ADTN a FULL (quarterlies)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se promovió ADTN de `ANNUAL_ONLY` a `FULL` sin abrir una BL nueva ni reescribir la verdad anual ya canonizada. `cases/ADTN/case.json` pasa a `period_scope: FULL` y `cases/ADTN/expected.json` incorpora exactamente los 15 trimestrales `Q*` con cobertura suficiente y al menos 15 campos (`Q1-Q3 2021` y `Q1-Q3 2022-2025`), excluyendo `Q1-Q4 2019`, `Q1-Q4 2020`, `Q4-2021`, todos los `H1-*` y cualquier trimestral sparse. Para `Q1-Q3 2023` y `Q1-Q3 2024`, la promoción conserva comparativos restated de filings posteriores sólo cuando el valor restated es explícito y trazable; en el resto de campos se mantiene el `source_filing` real del 10-Q original. Con ello ADTN pasa a validar 23 periodos (`8A+15Q`) y `520/520`, por lo que `DEC-015` sube operativamente de 13/15 a 14/15 sin declarar todavía el target alcanzado.
- **Criterio de aceptación:** ✓ `python3 scripts/validate_contracts.py --schema case --path cases/ADTN/case.json` PASS. ✓ `python3 scripts/validate_contracts.py --schema expected --path cases/ADTN/expected.json` PASS. ✓ `python3 -m elsian eval ADTN` PASS 100.0% (520/520) with `wrong=0`, `missed=0`, `extra=292`. ✓ `python3 -m elsian eval --all` PASS 16/16 and ADTN promoted in-place (`520/520`). ✓ `python3 -m pytest -q` PASS (`1373 passed, 5 skipped, 1 warning`). ✓ `git diff --check` limpio. ✓ `python3 scripts/check_governance.py --format json` queda sin IDs duplicados y con `project_state_lags_changelog=false`.

---

### BL-082 — Resolver wrongs de ADTN por restatements 2023-2024
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cerró el bloqueador shared-core que impedía promover ADTN a `FULL` aunque la curación trimestral ya tuviera 15 periodos candidatos. El fix endurece la selección trimestral restated de forma reutilizable: `elsian/extract/phase.py` centraliza la afinidad de restatement para `total_equity` y la aplica simétricamente en iXBRL, table, narrative y `.txt` tables, con preferencia por comparativos restated sólo cuando hay evidencia válida de balance sheet restatement y sin volver a dar ventaja a equity rollforwards o narrativas amplias. En la misma ola se mantiene el fix ya validado para `depreciation_amortization` mixed-scale y para `total_liabilities`, preservando los verdes de ACLS, GCT y TZOO. La repro `ADTN scratch FULL` pasa a 100.0% (`wrong=0`, `missed=0`), por lo que `BL-081` deja de estar bloqueada y queda lista para su propia promoción targeted.
- **Criterio de aceptación:** ✓ `python3 -m pytest -q tests/unit/test_extract_phase.py tests/unit/test_ixbrl_extractor.py tests/unit/test_merger.py` PASS (106 passed). ✓ `python3 -m elsian eval ACLS` PASS 100.0% (399/399). ✓ `python3 -m elsian eval ADTN` PASS 100.0% (209/209). ✓ `python3 -m elsian eval GCT` PASS 100.0% (267/267). ✓ `python3 -m elsian eval TZOO` PASS 100.0% (312/312). ✓ `python3 -m elsian eval --all` PASS 16/16. ✓ `python3 -m pytest -q` PASS (1373 passed, 5 skipped, 1 warning). ✓ `git diff --check` limpio. ✓ Repro `ADTN scratch FULL` sobre expected trimestral temporal/mergeado: `score=100.0`, `matched=520`, `wrong=0`, `missed=0`, `extra=292`.

### BL-075 — Enriquecer expected.json con campos derivados calculables
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** BL-074
- **Descripción:** Se cerró el backfill determinista de campos derivados en `expected.json` sin mezclar la retroportación de BL-035/BL-058. El nuevo script `scripts/backfill_expected_derived.py` añade `ebitda = ebit + depreciation_amortization` y `fcf = cfo - abs(capex)` solo cuando ambos componentes existen, el derivado no está ya presente y no hay una exclusión canonizada `DERIVED_INCONSISTENT` por `ticker+periodo+campo`. La ola toca 15 tickers (`0327`, `ACLS`, `ADTN`, `CROX`, `GCT`, `INMD`, `IOSP`, `NEXN`, `NVDA`, `PR`, `SOM`, `SONO`, `TALO`, `TEP`, `TZOO`) y deja `KAR` intacto. Para mantener la paridad de Módulo 1, `elsian/evaluate/evaluator.py` y `elsian/curate_draft.py` ahora prefieren el valor derivado cuando el `expected.json` canoniza ese campo como `DERIVED` aunque el extractor haya capturado un valor ruidoso distinto. En la misma ola se absorbió un fix mínimo previo de provenance para las dos filas `dividends_per_share` de SOM en el annual report FY2024, de modo que `pytest -q` vuelva a verde sin cambiar winner selection.
- **Criterio de aceptación:** ✓ `python3 scripts/backfill_expected_derived.py --cases-dir cases --dry-run` pasa y es idempotente: antes del apply reporta `ebitda eligible_missing_before=148` y `fcf eligible_missing_before=110`; tras aplicar y rerunear reporta `eligible_missing_before=0` para ambos campos, con `modified_files=[]`. ✓ Se validan los 15 `expected.json` tocados. ✓ `python3 -m elsian eval --all` vuelve a PASS 16/16 (`0327 62/62`, `ACLS 399/399`, `ADTN 209/209`, `CROX 314/314`, `GCT 267/267`, `INMD 234/234`, `IOSP 366/366`, `KAR 49/49`, `NEXN 169/169`, `NVDA 374/374`, `PR 153/153`, `SOM 197/197`, `SONO 335/335`, `TALO 199/199`, `TEP 90/90`, `TZOO 312/312`). ✓ `python3 -m pytest -q` vuelve a verde: `1359 passed, 5 skipped, 1 warning`. ✓ La gobernanza queda reconciliada con 3,729 campos validados, sin reabrir `BL-076` ni `BL-077`.

---

### BL-080 — Recuperar SourceMap_v1 TZOO (FULL -> PARTIAL)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cerró la regresión acotada de Provenance Level 3 que había degradado `SourceMap_v1` de TZOO de `FULL` a `PARTIAL`. El fix quedó limitado al builder `elsian/assemble/source_map.py`: los punteros `:ixbrl:` con sufijos derivados como `:bs_identity_bridge` vuelven a resolverse contra el fact base de iXBRL en vez de tratar el sufijo como parte del concepto, y los `raw_text` sintéticos de bridge dejan de bloquear el match contra el HTML original. La solución no reabre extractor, merge ni eval de Módulo 1, y TZOO vuelve a validar el piloto L3 con click targets completos.
- **Criterio de aceptación:** ✓ `python3 -m pytest -q tests/unit/test_source_map.py tests/integration/test_source_map.py` PASS (14 passed). ✓ `python3 -m elsian source-map TZOO --output <tmp>` vuelve a `SourceMap_v1 FULL` con 818/818 campos resueltos. ✓ `python3 -m elsian eval TZOO` sigue en PASS 100.0% (300/300). ✓ `python3 -m pytest -q` vuelve a verde: 1349 passed, 6 skipped, 1 warning. ✓ `PROJECT_STATE` deja de vender L3 como regresión abierta.

---

### BL-079 — Corregir drift extractor amplio de ADTN fuera del patrón BL-078
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cerró el fix shared-core amplio que quedaba pendiente para ADTN tras BL-078. El extractor/merge dejó de seleccionar filas y tablas auxiliares equivocadas en múltiples familias de campos y la solución quedó absorbida como patrón reutilizable, no como parche opaco por ticker. ADTN vuelve a verde contra la verdad filing-backed canonizada, GCT y TZOO se mantienen verdes, y los controles adicionales sobre NEXN, NVDA, TEP, TALO, SONO e INMD también quedan en PASS. La revalidación global vuelve a `eval --all` con 16/16 tickers en verde.
- **Criterio de aceptación:** ✓ `python3 -m pytest -q tests/unit/test_extract_phase.py tests/unit/test_merger.py tests/unit/test_ixbrl_extractor.py tests/unit/test_working_capital_fields.py` PASS (110 passed). ✓ `python3 -m elsian eval ADTN` PASS 100.0% (193/193). ✓ `python3 -m elsian eval GCT` PASS 100.0% (252/252). ✓ `python3 -m elsian eval TZOO` PASS 100.0% (300/300). ✓ Controles extra `NEXN`, `NVDA`, `TEP`, `TALO`, `SONO`, `INMD` en PASS 100.0%. ✓ `python3 -m elsian eval --all` PASS 16/16.

---

### BL-074 — Corregir issues críticos en expected.json (ADTN, GCT, TZOO)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-08)
- **Asignado a:** engineer
- **Depende de:** BL-079
- **Descripción:** La curación filing-backed de ADTN, GCT y TZOO ya había quedado canonizada en `expected.json` con `source_filing` explícito. BL-078 absorbió el patrón shared-core estrecho de identidad de balance y D&A; BL-079 cerró el drift extractor amplio restante de ADTN. Con ello, los issues críticos originales quedan resueltos end-to-end sin reabrir la verdad curada, y el cierre contractual pasa a estar plenamente satisfecho.
- **Criterio de aceptación:** ✓ Los `BS_IDENTITY_FAIL` y `SCALE_INCONSISTENT` que originaron la BL quedan absorbidos por la verdad filing-backed ya corregida y por los fixes shared-core posteriores. ✓ `python3 -m elsian eval ADTN` PASS 100.0% (193/193). ✓ `python3 -m elsian eval GCT` PASS 100.0% (252/252). ✓ `python3 -m elsian eval TZOO` PASS 100.0% (300/300). ✓ La revisión independiente posterior no reporta ningún issue crítico nuevo; el único desacople material detectado fue de gobernanza y queda reconciliado en este cierre.

---

### BL-078 — Alinear extractor con BL-074 (BS identity con NCI/mezzanine y D&A de GCT)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** engineer
- **Depende de:** —
- **Descripción:** Se cerró el fix shared-core estrecho que faltaba para que la verdad corregida en BL-074 pudiera evaluarse correctamente donde el patrón sí era reutilizable. `elsian/extract/phase.py` ahora absorbe en `total_liabilities` las partidas presentadas fuera de equity común pero dentro de la identidad de balance usada por el proyecto (`non-controlling interest`, `redeemable non-controlling interest`, `mezzanine equity`) y penaliza con fuerza los candidatos de `depreciation_amortization` que provienen de secciones per-share. `elsian/extract/vertical.py` expone las etiquetas puente necesarias y `tests/unit/test_extract_phase.py` cubre ambos patrones. En la misma oleada quedaron canonizados `cases/ADTN/case.json` y `cases/ADTN/expected.json`. El paquete deja GCT y TZOO alineadas end-to-end con la verdad corregida de BL-074 y deja explícito que la roja restante de ADTN es drift extractor más amplio, fuera del alcance estrecho de esta BL.
- **Criterio de aceptación:** ✓ `python3 scripts/validate_contracts.py --schema case --path cases/ADTN/case.json` PASS. ✓ `python3 scripts/validate_contracts.py --schema expected --path cases/ADTN/expected.json` PASS. ✓ `python3 -m pytest -q tests/unit/test_extract_phase.py` PASS (29 passed). ✓ `python3 -m elsian eval GCT` PASS 100.0% (252/252). ✓ `python3 -m elsian eval TZOO` PASS 100.0% (300/300). ✓ `python3 -m elsian eval ADTN` sigue FAIL 84.97% (164/193) por drift extractor más amplio fuera del patrón BL-078, por lo que BL-074 permanece `BLOCKED`; ese follow-up quedó empaquetado después como `BL-079`.

---

### BL-060 — T02 — Hardening de CI (scope filtrado restante)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** elsian-orchestrator
- **Depende de:** —
- **Descripción:** Se endureció la CI restante sin reabrir runtime code ni depender de BL-059. El workflow principal ahora queda separado en `governance`, `lint`, `typecheck`, `pytest`, `security` y `eval-all`, con `actions/checkout` y `actions/setup-python` pinneadas por SHA, `permissions: contents: read`, `timeout-minutes` por job e instalación consistente de tooling. Se añadió `.github/dependabot.yml` para `pip` y `github-actions`. El cierre se hizo con una baseline conservadora: `ruff` pasa a ser gate real con selección mínima utilizable sobre el repo actual y `mypy` queda activado sobre `elsian/models/*`, sin vender todavía typecheck completo del runtime.
- **Criterio de aceptación:** ✓ CI separada por responsabilidades. ✓ Dependabot activo para `pip` y `github-actions`. ✓ Security checks activos. ✓ Actions pinneadas por SHA y permisos mínimos. ✓ El paquete cierra sin tocar código funcional ni depender del wiring de contratos de BL-059.

---

### BL-057 — Discovery automático de filings LSE/AIM (DEC-025)
- **Prioridad:** BAJA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** elsian-orchestrator
- **Depende de:** BL-013 (IR crawler DONE)
- **Descripción:** Se cerró el gap reconocido en `DEC-025` sin convertirlo en un crawler nuevo ni en infraestructura LSE general. `EuRegulatorsFetcher` ahora usa un modo conservador para LSE/AIM: deduplica variantes `/media` y `/~/media`, descarta documentos no financieros tipo `corporate governance`/`modern slavery`, no descarga endpoints no convertibles como `regulatory-story.aspx`, y limita la selección a un set mínimo estable de annual/interim/regulatory documents. En paralelo, el extractor de DPS de SOM dejó de depender del filename `SRC_001_*` exacto, con lo que la ruta auto-discovered ya no rompe la extracción determinista. El piloto principal queda resuelto en SOM: un caso temporal sin `filings_sources` descarga exactamente annual report 2024 + final results presentation 2024 + interim investor presentation 2025 y evalúa 179/179 al 100%.
- **Criterio de aceptación:** ✓ `elsian acquire SOM` ya no requiere `filings_sources` hardcodeados en `case.json`. ✓ El piloto temporal sin `filings_sources` descarga 3 documentos núcleo (6 artefactos con `.txt`) y `eval SOM` queda en 100%. ✓ Se añaden tests reutilizables para hyphenated URLs, fallback `/~/media`, poda de CTA genéricas, dedup `/media` vs `/~/media`, filtrado de documentos no financieros y skip de endpoints `.aspx` no convertibles.

---

### BL-047 — Mejorar HTML table extractor: interest_income + capex
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** elsian-orchestrator
- **Depende de:** —
- **Descripción:** Se endureció el extractor HTML en dos patrones reutilizables detectados en NVDA. Por un lado, las tablas suplementarias con columnas explícitas de comparación (`$ Change`, `% Change`, quarter-over-quarter, year-over-year, constant currency) pasan a tratarse como comparativas auxiliares y se excluyen de la extracción, evitando mappings ambiguos en notas como `Interest income` sin reabrir truth ni selección de ganadores. Por otro, los split headers tipo `Six Months Ended` / `Nine Months Ended` con fila de fechas separada ya preservan el contexto YTD del periodo anterior en vez de degradarlo a `Q3/Q4` o a un `H2` espurio por mes de cierre; eso corrige de forma reusable el ruido de `capex`, `cfo` y `depreciation_amortization`.
- **Criterio de aceptación:** ✓ Se resuelven patrones reusables del extractor HTML sin convertir BL-047 en fix local de NVDA. ✓ NVDA mejora sin regresiones y mantiene `PASS 100.0%`, reduciendo `extra` de 545 a 503. ✓ `tests/unit/test_html_tables.py` cubre tanto el skip de tablas con `Change` como la preservación de contexto `H1/9M` en split headers YTD.

---

### BL-053 — Provenance Level 3 (source_map.json)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** elsian-orchestrator
- **Depende de:** BL-006 (Provenance L2 DONE)
- **Descripción:** Se implementó un piloto mínimo y cerrable de provenance L3 sin reabrir el pipeline de extracción. `elsian source-map {TICKER}` genera `source_map.json` a partir de `extraction_result.json` y resuelve el salto técnico hasta la fuente usando la provenance L2 ya existente: facts iXBRL apuntan al `.htm` original mediante offsets/caracteres y `id` DOM cuando existe, tablas HTML apuntan a la fila exacta en `.clean.md`, y los casos `vertical_bs` en `.txt` quedan anclados por línea. El piloto validado es `TZOO`, con 851/851 campos resueltos y targets line-addressable/trazables para `table`, `ixbrl` y `text_label`. En la misma oleada se endureció el builder para confinar `source_filing` al caso y se dejó `source_map.json` ignorado por defecto para no ensuciar el repo durante el uso normal del comando.
- **Criterio de aceptación:** ✓ `elsian source-map TZOO --output <tmp>` genera un artefacto `SourceMap_v1` válido. ✓ El piloto TZOO resuelve 851/851 campos. ✓ `python3 -m pytest -q tests/unit/test_source_map.py tests/integration/test_source_map.py` pasa (6 passed). ✓ `python3 -m elsian eval TZOO` sigue en PASS 100.0% (300/300). ✓ La demo técnica de provenance queda demostrada con targets a `.htm#id...`, `.clean.md#L...` y `.txt#L...`.

---

### BL-052 — Auto-curate para tickers no-SEC (expected.json desde PDF)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** elsian-orchestrator
- **Depende de:** BL-007 (PdfTableExtractor DONE)
- **Descripción:** `elsian curate` ya no depende solo de iXBRL. Cuando un caso no tiene `.htm`, el comando convierte PDFs si hace falta, reutiliza `ExtractPhase.extract()` y genera `expected_draft.json` determinista desde `ExtractionResult` en vez de caer a un esqueleto vacío. La ruta no-SEC expone `_confidence`, `_gaps`, `_confidence_summary`, `_gap_policy`, `_validation` y `_comparison_to_expected`; excluye campos de `manual_overrides` para no reciclar verdad manual como si fuera salida del pipeline; y mantiene intacta la ruta SEC/iXBRL existente.
- **Criterio de aceptación:** ✓ `elsian curate TEP` genera draft útil con cobertura 80/80 (100%) y gaps/confianza explícitos. ✓ `elsian curate KAR` genera draft útil con cobertura 49/49 (100%) y gaps/confianza explícitos. ✓ `elsian curate TZOO` sigue funcionando por iXBRL sin regresión. ✓ Tests unitarios e integración de `curate` pasan, incluida la batería lenta sobre TEP/KAR/TZOO.

---

### BL-008 — Reescribir AsxFetcher con endpoint por compañía
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** El AsxFetcher actual usa el endpoint genérico `/asx/1/announcement/list` que devuelve TODOS los anuncios de TODAS las empresas del ASX, y filtra por ticker en Python. Esto requiere ~78 requests HTTP en ventanas de 14 días para cubrir 3 años (DEC-008). **Hallazgo:** El endpoint por compañía (`asx.api.markitdigital.com`) tiene un hard cap de 5 items sin paginación — inutilizable. El endpoint genérico no soporta filtro por compañía ni paginación. Solución implementada: ventanas de 1 día con escaneo hacia atrás desde los meses de reporting esperados. Descarga ≥3 annual reports en 3-6 requests. Filings descargados son byte-idénticos a los manuales.
- **Criterio de aceptación:** ✓ `acquire KAR` descarga ≥3 annual reports automáticamente. ✓ No usa filings_sources. ✓ Tests existentes siguen pasando (339/339). ✓ PDFs son byte-idénticos a los descargados manualmente. **Nota:** Velocidad ~30-90s (API inherentemente lenta, no <30s como se esperaba — el endpoint por compañía no existe).

---

### BL-001 — Rehacer KAR desde cero
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-008 (AsxFetcher funcional) — DONE
- **Descripción:** KAR rehecho desde cero con AsxFetcher autónomo. case.json (source_hint=asx, currency=USD, fiscal_year_end_month=12), filings adquiridos automáticamente vía ASX API (6 PDFs + 6 TXTs), expected.json curado manualmente (49 campos, 3 periodos FY2023-FY2025, ≥15 campos/periodo cubriendo IS+BS+CF). Score: 100% (49/49).
- **Criterio de aceptación:** ✓ KAR en VALIDATED_TICKERS con 100%. ✓ filings/ tiene PDFs + .txt generados por acquire. ✓ expected.json tiene ≥15 campos por periodo. ✓ Regresión 10/10 al 100%.

---

### BL-002 — Nuevo ticker NVDA
- **Prioridad:** ALTA
- **Estado:** DONE ✅
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Añadir NVIDIA como ticker SEC large-cap. **Completado:** case.json ✅, acquire ✅ (28 filings descargados). expected.json ✅ (2 anni, 19 campos/período = 38 total cubriendo IS+BS+CF). **Extraction:** 100% — 38/38 matched.
- **Criterio de aceptación:** ✓ NVDA 100% (38/38). ✓ expected.json con 19 campos por período. ✓ filings/ con 28 archivos (6 annual, 12 quarterly, 10 earnings). ✓ Regresión 7/7 @ 100% (sin cambios en otros tickers). ✓ NVDA añadido a VALIDATED_TICKERS.

---

### BL-004 — Parser iXBRL determinístico (módulo reutilizable)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-027 (governance limpio primero)
- **Descripción:** Construir `elsian/extract/ixbrl.py` — un parser determinístico que extrae datos financieros estructurados de ficheros iXBRL (los mismos .htm que ya descargamos de SEC/ESEF). El parser: (1) localiza tags `ix:nonFraction` / `ix:nonNumeric`, (2) extrae concepto, periodo, valor, unidad, escala (`decimals`), contexto, (3) mapea conceptos GAAP/IFRS a nuestros 23 campos canónicos vía `config/ixbrl_concept_map.json` (nuevo) + `field_aliases.json`, (4) normaliza escala y signos a nuestra convención (DEC-004). **Este módulo es reutilizable:** será consumido por `elsian curate` (BL-025) para generar expected.json, y en el futuro por `IxbrlExtractor(Extractor)` dentro del pipeline de producción. Un parser, dos consumidores (DEC-010). **Portado desde 3.0** `ixbrl_extractor.py` si existe, sino implementar con BeautifulSoup (ya es dependencia). **Plan detallado: WP-3 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Parser extrae correctamente todos los campos canónicos disponibles de al menos 2 tickers SEC (TZOO, NVDA). Tests unitarios con fixtures iXBRL reales. Output es una lista de FieldResult con provenance (concepto iXBRL, contexto, periodo). Sin dependencias nuevas (bs4 ya está).

---

### BL-025 — Comando `elsian curate` (generador de expected.json)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-004 (parser iXBRL)
- **Descripción:** Crear comando `python3 -m elsian.cli curate {TICKER}` que genera `expected_draft.json` de forma automática. Para tickers con iXBRL (SEC, ESEF): usa el parser de BL-004 para extraer todos los campos canónicos de todos los periodos disponibles, filtrando solo campos con representación tabular en IS/BS/CF. Para tickers sin iXBRL (ASX, emergentes): genera un esqueleto vacío con los periodos detectados. El draft incluye metadata de origen (concepto iXBRL, filing fuente, escala original). El draft se depura después manualmente o con LLM para producir el expected.json final. **No forma parte del pipeline de producción** — es herramienta de desarrollo/QA. **Plan detallado: WP-3 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** `elsian curate TZOO` genera un expected_draft.json con ≥90% de los campos del expected.json actual. `elsian curate NVDA` genera draft con periodos anuales Y trimestrales. El draft pasa sanity checks automáticos (revenue>0, assets=liabilities+equity ±1%). Tests del comando.

---

### BL-026 — Promover tickers SEC a FULL vía curate
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-02, oleada 3)
- **Asignado a:** elsian-4
- **Depende de:** BL-025 (comando curate funcional)
- **Descripción:** Oleada 1 (SONO, GCT) + Oleada 2 (TALO) + Oleada 3 (IOSP, GCT Q1-Q3 2024) completadas. SONO→FULL 100% (311/311, 18p). GCT→FULL 100% (202/202→252/252, 15p). TALO→FULL 100% (183/183, 12p). IOSP→FULL 100% (95/95→338/338, 22p, 17 trimestres añadidos). PR promovido a FULL 100% (141/141). NVDA y TZOO ya estaban en FULL.
- **Criterio de aceptación:** ≥5 tickers en FULL al 100% (incluyendo TZOO y NVDA). Sin regresiones en tickers que no cambian de scope. ✅ Cumplido: 7 tickers en FULL (TZOO, NVDA, SONO, GCT, TALO, PR, IOSP). Oleada 3 completada (IOSP desbloqueado por BL-038). 9/9 tickers PASS 100%.

---

### BL-027 — Scope Governance: coherencia case.json vs expected.json
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Corregir inconsistencias de scope detectadas en auditoría: (1) Añadir `period_scope: "FULL"` a NVDA case.json (tiene 18 periodos con Q pero scope implícito ANNUAL_ONLY). (2) Auditar todos los case.json: si expected.json tiene periodos Q*/H* → case.json debe tener period_scope FULL. (3) Corregir referencia a "23 campos canónicos" en docs → son 23. (4) Alinear test count en PROJECT_STATE con la realidad. (5) Crear test automático `tests/integration/test_scope_consistency.py` que verifique coherencia scope↔expected para todos los tickers validados. **Plan detallado: WP-1 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Todos los case.json coherentes con sus expected.json. Test de consistencia pasa. Docs alineados con realidad. Regresión verde.

---

### BL-028 — SEC Hardening: cache lógico + CIK preconfigurado
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** — (paralelo a WP-3)
- **Descripción:** (1) Cache en sec_edgar.py debe contar filings lógicos (stems únicos) no ficheros físicos. (2) Añadir campo `cik: str | None = None` a CaseConfig. (3) SecEdgarFetcher usa case.cik si existe, fallback a API si no. (4) Verificar que eliminación de Pass 2 exhibit_99 no pierde filings. **Plan detallado: WP-2 en `docs/project/PLAN_DEC010_WP1-WP6.md`.**
- **Criterio de aceptación:** Cache cuenta filings lógicos (test). CaseConfig acepta cik. NVDA usa CIK sin resolución API. Regresión verde.

---

### BL-029 — Corregir contrato Python: >=3.11 vs entorno local 3.9.6
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02) — Verificado: codebase usa X|Y unions (3.10+), pyproject.toml >=3.11 es correcto. CI workflow creado.
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** pyproject.toml declara `requires-python = ">=3.11"` pero el entorno local actual es Python 3.9.6. Decidir: (a) bajar el requisito a >=3.9 si no usamos features de 3.10+, o (b) actualizar el entorno local a 3.11+. Verificar uso real de features post-3.9 (`match/case`, `X | Y` type unions, `tomllib`, etc.).
- **Criterio de aceptación:** El contrato en pyproject.toml coincide con el entorno mínimo real donde el pipeline funciona correctamente.

---

### BL-006 — Provenance Level 2 completa en todos los extractores
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** El modelo Provenance tiene campos table_title, row_label, col_label, raw_text pero no siempre se pueblan. Auditar cada extractor y asegurar que todos propagan coordenadas completas.
- **Criterio de aceptación:** ✓ Cada FieldResult tiene provenance completo (source_filing + table_index + table_title + row_label + col_label + row + col + raw_text). ✓ extraction_method (table/narrative/manual). ✓ 0%→100% completitud. ✓ 17 tests nuevos. ✓ 627 tests pass. ✓ 13/13 tickers 100%. CROX mejoró 82.31%→95.24% como efecto colateral.

---

### BL-007 — Crear PdfTableExtractor
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Creado `elsian/extract/pdf_tables.py` (447L). PdfTableExtractor usando pdfplumber.extract_tables() para extracción estructurada de tablas PDF. Complementa pipeline text-based (pdf_to_text.py). Diseñado para Euronext (TEP), ASX (KAR) y futuros tickers PDF. 47 tests.
- **Criterio de aceptación:** ✓ PdfTableExtractor(Extractor) con tests. ✓ TEP sigue al 100%. ✓ 47 tests pass. ✓ Sin regresiones.

---

### BL-009 — Portar Filing Preflight desde 3.0
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar `3_0-ELSIAN-INVEST/scripts/runners/filing_preflight.py` (320 líneas) al 4.0. Este módulo detecta idioma, estándar contable (IFRS/US-GAAP), moneda, secciones financieras, unidades por sección, restatement, y año fiscal — todo determinístico, <1ms por filing. El 4.0 tiene `detect.py` con funcionalidad parcial pero le falta: detección de restatement, unidades por sección (crítico para escala), multiidioma (fr, es, de), y confianza por señal. **Portar, no reimplementar (DEC-009).** Leer el código fuente del 3.0 primero, adaptar a la arquitectura 4.0.
- **Criterio de aceptación:** Preflight corre sobre todos los filings existentes. Detecta correctamente idioma, estándar, moneda, y unidades por sección para TZOO (US-GAAP, USD), TEP (IFRS, EUR, FR), y KAR (IFRS, USD). Tests unitarios con fixtures de cada tipo. Sin regresiones.
- **Referencia 3.0:** `scripts/runners/filing_preflight.py`

---

### BL-010 — Deduplicación de filings por contenido
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar la lógica de content hash del 3.0 (`_content_hash`, `_normalize_text_for_hash` en `sec_fetcher_v2_runner.py` líneas ~411-418). El pipeline puede procesar múltiples representaciones del mismo filing (.htm, .txt, .clean.md) como si fueran documentos distintos, generando colisiones en merge. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Dos filings con el mismo contenido textual se detectan como duplicados. Se procesan una sola vez. TZOO (28 filings, muchos con versiones .htm/.txt) no tiene colisiones por duplicación.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` funciones `_content_hash`, `_normalize_text_for_hash`

---

### BL-011 — Exchange/Country awareness unificada
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar del 3.0 las funciones `normalize_exchange()`, `normalize_country()`, `is_non_us()`, `infer_regulator_code()` (líneas ~297-358 de `sec_fetcher_v2_runner.py`) y las constantes `NON_US_EXCHANGES`, `NON_US_COUNTRIES`, `LOCAL_FILING_KEYWORDS_BY_EXCHANGE`. Unificar en `elsian/config/markets.py`. Usado por AcquirePhase para routing y por futuros fetchers. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Module con funciones puras + tests. AcquirePhase usa el módulo para routing en vez de string matching en `_get_fetcher()`.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` líneas 50-170 (constantes) y 297-358 (funciones)

---

### BL-012 — Filing Classification automática
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portar `_classify_local_filing_type()` del 3.0 (líneas ~686-742 de `sec_fetcher_v2_runner.py`). Clasifica filings en ANNUAL_REPORT / INTERIM_REPORT / REGULATORY_FILING / IR_NEWS basándose en keywords del título, URL y snippet. **Portar, no reimplementar (DEC-009).**
- **Criterio de aceptación:** Función que recibe (title, url, snippet) → filing_type. Tests con ejemplos de SEC, ASX y EU. Integrado en los fetchers que no tienen clasificación propia.
- **Referencia 3.0:** `sec_fetcher_v2_runner.py` función `_classify_local_filing_type`

---

## Tareas completadas

---

### BL-003 — Wire ExtractPhase a PipelinePhase.run(context)
- **Prioridad:** ALTA
- **Estado:** DONE ✅
- **Completado:** 2026-03-03
- **Asignado a:** elsian-4
- **Resultado:** Todas las fases (Acquire, Extract, Evaluate) heredan PipelinePhase con run(context). Pipeline orquesta correctamente. cmd_run usa Pipeline([ExtractPhase(), EvaluatePhase()]). +6 tests nuevos. 157 tests pasando.

---

## Tareas descubiertas durante el port del módulo acquire (2026-03-04)

---

### BL-013 — Integrar IR Crawler en EuRegulatorsFetcher
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-012 (DONE)
- **Descripción:** `elsian/acquire/ir_crawler.py` está portado con todas las funciones de crawling (build_ir_pages, discover_ir_subpages, extract_filing_candidates, select_fallback_candidates, resolve_ir_base_url). Falta integrarlo en EuRegulatorsFetcher como fallback automático cuando `filings_sources` no está definido en case.json. El fetcher debería: 1) intentar `web_ir` → resolve_ir_base_url, 2) crawlear páginas IR, 3) extraer candidatos, 4) seleccionar y descargar. Esto eliminaría la dependencia de URLs manuales para tickers EU.
- **Criterio de aceptación:** ✓ EuRegulatorsFetcher.acquire() tiene fallback IR crawler cuando filings_sources vacío + web_ir definido. ✓ TEP 100% (path existente intacto). ✓ 15 tests nuevos (12 integración + 3 unit). ✓ 13/13 tickers 100%. ✓ Funciones importadas: resolve_ir_base_url, build_ir_pages, discover_ir_subpages, extract_filing_candidates, select_fallback_candidates.

---

### BL-014 — Integrar preflight en el pipeline de extracción
- **Prioridad:** MEDIA
- **Estado:** DONE
- **Asignado a:** Claude (Copilot)
- **Depende de:** BL-009 (DONE)
- **Descripción:** `elsian/analyze/preflight.py` integrado en `ExtractPhase.extract()`. Preflight se ejecuta por filing (non-blocking). Units_by_section alimenta ScaleCascade via `_FIELD_SECTION_MAP`. Provenance incluye `preflight_currency`, `preflight_standard`, `preflight_units_hint`.
- **Completado:** 2026-03-02. 18 tests nuevos. 445 passed, 0 failed. 9/9 tickers al 100%.

---

### BL-015 — Portar calculadora de métricas derivadas (tp_calculator.py)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-022
- **Descripción:** Portado `scripts/runners/tp_calculator.py` (3.0) a `elsian/calculate/derived.py` (714L). TTM cascade (4Q sum → semestral FY+H1 → FY0 fallback), Q4 sintético, FCF, EV, márgenes (gross/op/net/FCF), retornos (ROIC/ROE/ROA), múltiplos (EV/EBIT, EV/FCF, P/FCF), net_debt, per-share. Null propagation. 88 tests.
- **Criterio de aceptación:** ✓ elsian/calculate/derived.py creado (714L). ✓ 88 tests pasando. ✓ 1002 tests total, 0 failed. ✓ Sin regresiones.

---

### BL-016 — Portar sanity checks del normalizer (tp_normalizer.py)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portado de `scripts/runners/tp_normalizer.py` (3.0) a `elsian/normalize/sanity.py`. 4 reglas: capex_positive (auto-fix), revenue_negative, gp_gt_revenue, yoy_jump >10x. Integrado en ExtractPhase (non-blocking logging). 12 tests unitarios en `tests/unit/test_sanity.py`.
- **Criterio de aceptación:** ✓ Sanity checks activos en pipeline (logging, no bloquean). ✓ 12 tests pasando. ✓ 544 tests total, 13/13 tickers 100%. ✓ Sin regresiones.

---

### BL-017 — Portar validate_expected.py
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portado de `deterministic/src/validate_expected.py` (3.0) a `elsian/evaluate/validate_expected.py`. 8 errores estructurales + 2 sanity warnings (revenue>0, BS identity). Integrado en `evaluate()` como pre-check (logging warnings). 22 tests unitarios en `tests/unit/test_validate_expected.py`. Hallazgos: 7 BS warnings (TZOO 6, GCT 1) — NCI no capturado.
- **Criterio de aceptación:** ✓ `evaluate()` valida expected.json antes de comparar. ✓ 22 tests pasando. ✓ 544 tests total, 13/13 tickers 100%. ✓ Sin regresiones.

---

### BL-018 — Extender quality gates de clean.md (gap parcial)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** `elsian/convert/html_to_markdown.py` ya implementa quality gate básico (`_is_clean_md_useful`) y mínimos numéricos por tabla. Portar solo las validaciones granulares faltantes de `scripts/runners/clean_md_quality.py` (métricas por sección, detección avanzada de stubs, diagnóstico exportable).
- **Criterio de aceptación:** ✓ `elsian/convert/clean_md_quality.py` creado (242 líneas). ✓ evaluate_clean_md(), is_clean_md_useful(), detect_clean_md_mode(). ✓ Métricas por sección (IS/BS/CF). ✓ Stub detection. ✓ Integrado en html_to_markdown.py. ✓ 24 tests nuevos. ✓ 13/13 tickers 100%. ✓ Portado de `3_0 clean_md_quality.py`.

---

### BL-020 — Portar validator autónomo de Truth Pack (tp_validator.py)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-015, BL-016
- **Descripción:** Portado `scripts/runners/tp_validator.py` (3.0) a `elsian/evaluate/validation.py` (707L). 9 quality gates intrínsecos: BALANCE_IDENTITY (±2%), CASHFLOW_IDENTITY (±5%), UNIDADES_SANITY (1000x), EV_SANITY, MARGIN_SANITY (20 sectores), TTM_SANITY, TTM_CONSECUTIVE, RECENCY_SANITY, DATA_COMPLETENESS. Confidence score. Sin CLI (librería interna). 104 tests.
- **Criterio de aceptación:** ✓ validation.py creado (707L). ✓ 9 gates. ✓ 104 tests pasando. ✓ 1106 tests total, 0 failed. ✓ Sin regresiones.

---

### BL-021 — Portar prefetch coverage audit
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portado `scripts/runners/prefetch_coverage_audit.py` (3.0) a `elsian/evaluate/coverage_audit.py`. Clasificación issuer (Domestic_US/FPI_ADR/NonUS_Local), thresholds por clase, reporte JSON+Markdown. CLI `elsian coverage [TICKER] --all`. 42 tests.
- **Criterio de aceptación:** ✓ coverage_audit.py creado. ✓ CLI integrado. ✓ 42 tests pasando. ✓ Sin regresiones.

---

### BL-022 — Portar market data fetcher (market_data_v1_runner.py)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portado `market_data_v1_runner.py` (3.0) a `elsian/acquire/market_data.py` (830L). MarketDataFetcher con Finviz (US), Stooq (OHLCV), Yahoo Finance (non-US fallback). Comando CLI `elsian market {TICKER}`. 62 tests.
- **Criterio de aceptación:** ✓ Fetcher funcional. ✓ CLI integrado. ✓ 62 tests pass. ✓ Sin regresiones.

---

### BL-023 — Portar sources compiler
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-022, BL-024
- **Descripción:** Portado `scripts/runners/sources_compiler_runner.py` (3.0) a `elsian/acquire/sources_compiler.py` (749L). Merge multi-fetcher, dedup URL/hash/accession, IDs canónicos SRC_NNN, clasificación por tipo, cobertura documental, SourcesPack_v1. CLI `elsian compile {TICKER}`. 76 tests.
- **Criterio de aceptación:** ✓ sources_compiler.py creado (749L). ✓ CLI integrado. ✓ 76 tests pasando. ✓ Sin regresiones.

---

### BL-024 — Portar transcript finder
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Portado `transcript_finder_v2_runner.py` (3.0) a `elsian/acquire/transcripts.py` (1085L). TranscriptFinder con Fintool transcripts + IR presentations. Reutiliza ir_crawler.py, dedup.py, markets.py. Comando CLI `elsian transcripts {TICKER}`. 58 tests.
- **Criterio de aceptación:** ✓ Fetcher funcional con tests. ✓ CLI integrado. ✓ 58 tests pass. ✓ Sin regresiones.

> Nota: **BL-019 no se crea** porque la extracción financiera por secciones y presupuestos ya está portada en `elsian/convert/html_to_markdown.py`.

---

## Nuevas tareas (descubiertas en BL-002 NVDA)

---

### BL-030 — Test para Exhibit 99 fallback en SecEdgarFetcher
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** 18 tests creados: 14 unitarios en `tests/unit/test_sec_edgar.py` (TestFindExhibit99) + 4 de integración en `tests/integration/test_exhibit_99.py` (fixtures TZOO/GCT 6-K). Pass 2 (HTML fallback) analizado y determinado **NO necesario** — todos los tickers existentes resuelven vía Pass 1 (index.json).
- **Criterio de aceptación:** ✓ 14 tests unitarios + 4 integración para `_find_exhibit_99`. ✓ TZOO/GCT earnings localizados vía index.json. ✓ Pass 2 NOT needed (documentado). ✓ 544 tests total, 13/13 tickers 100%.

---

### BL-031 — Tests de integración para el comando `elsian curate`
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** elsian-4
- **Depende de:** BL-025 (DONE)
- **Descripción:** 18 tests de integración en `tests/integration/test_curate.py`. E2E TZOO (6 tests), skeleton TEP (4 tests), cobertura vs expected.json (2 tests, 100% real), sanity checks (6 tests). Fixtures scope=module con cleanup automático de expected_draft.json.
- **Criterio de aceptación:** ✓ 18 tests pasando. ✓ Cobertura TZOO 100% (102/102 campos). ✓ 463 total passed, 0 failed.

---

### BL-032 — Documentar o limpiar cases/PR
- **Prioridad:** BAJA
- **Estado:** DONE ✅ (2026-03-02) — DEC-013: PR trackeado como WIP.
- **Asignado a:** Director
- **Depende de:** —
- **Descripción:** El directorio `cases/PR/` (Permian Resources Corp, NYSE, CIK 0001658566, period_scope: FULL) fue creado durante WP-3. Decisión tomada en DEC-013: PR se trackea como WIP (88.65%, 125/141). case.json + expected.json añadidos al repo. Falta añadir a WIP_TICKERS en test_regression.py (BL-033).
- **Criterio de aceptación:** ✓ cases/PR documentado en PROJECT_STATE. ✓ DEC-013 registrada.

---

### BL-033 — Promover PR de WIP a VALIDATED (100%)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-02) — PR al 100% (141/141, FULL scope). Commit ede5a4e.
- **Asignado a:** Claude (elsian-4)
- **Depende de:** DEC-013
- **Descripción:** PR (Permian Resources, NYSE) está al 88.65% (125/141). Problemas: (1) shares_outstanding no extraído en 9 periodos (FY2025-FY2023, Q3-Q1 2025, Q3-Q1 2024), (2) total_debt con desviación ~5-15% en 5 periodos, (3) net_income y eps_basic wrong en FY2023. El agente técnico debe: añadir PR a WIP_TICKERS en test_regression.py, diagnosticar los 3 problemas, iterar hasta 100%.
- **Criterio de aceptación:** ✓ PR al 100% (141/141). ✓ PR migrado de WIP_TICKERS a VALIDATED_TICKERS. ✓ Sin regresiones en los 9 tickers existentes (10/10 tickers a 100%).

---

### BL-038 — Pipeline bug: IS no extraído en 10-Q con formato de columna desalineado
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-02)
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** Dos tickers (IOSP, GCT) no podían promoverse a FULL porque el pipeline fallaba al extraer IS desde 10-Q con formatos específicos: (1) IOSP: parenthetical `( value | )` generaba columnas extra. (2) GCT: `$` como celda separada desplazaba valores. (3) IOSP: scale-note cell bloqueaba detección de subheaders. Fix en dos commits: `_collapse_split_parentheticals()` + grouped year assignment + scale-note tolerance en `_is_subheader_row()`. IOSP ahora extrae 24+ periodos Q, GCT Q1-Q3 2024 ahora disponibles.
- **Criterio de aceptación:** ✅ Pipeline extrae IS para IOSP Q* (24+ periodos) y GCT Q1-Q3 2024 (18-20 campos). 10/10 tickers al 100%. 475 tests pass.

---

### BL-036 — SecEdgarFetcher: descargar Exhibit 99.1 de 6-K (NEXN quarterly)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03)
- **Asignado a:** Claude (Copilot)
- **Depende de:** —
- **Descripción:** El SecEdgarFetcher actual descarga `primary_doc` para 6-Ks, pero para foreign private issuers como NEXN (Israel/UK, 20-F/6-K), los datos financieros trimestrales están en el **Exhibit 99.1** adjunto al 6-K, no en el primary_doc (que es solo la portada del formulario, ~48 líneas). El fetcher ya tiene `_find_exhibit_99()` para 8-Ks pero no lo aplica a 6-Ks. Fix: extender la lógica de exhibit discovery a 6-Ks que contengan earnings results. Verificado: SRC_010_6-K_Q4-2025.txt referencia explícitamente "Exhibit 99.1" con financial statements completos (IS/BS/CF para three/nine months). Sin este fix, NEXN no puede promoverse a FULL.
- **Criterio de aceptación:** `acquire NEXN` descarga los .htm de Exhibit 99.1 de los 6-K con earnings results. Los .htm se convierten a .clean.md. `extract NEXN` produce periodos Q* con datos de IS/BS/CF. Tests unitarios para la nueva lógica de 6-K exhibit discovery. Sin regresiones en otros tickers SEC.

---

### BL-039 — Nuevo ticker ACLS (Axcelis Technologies, NASDAQ, SEC)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03) — ACLS FULL 100% (375/375, 21 periodos). Commits 79938bd + 3961d2b.
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** Axcelis Technologies como ticker SEC con iXBRL. NASDAQ, semiconductor (sector nuevo). Cobertura: 6 annual + 15 quarterly = 21 periodos, 375 campos. Cuatro fixes al pipeline: (1) ZWS stripping en html_tables.py, (2) "Twelve/Year Ended" period detection, (3) pro-forma column guard, (4) narrative suppression cuando .clean.md existe. Segundo commit: orphaned date fragment merging, income_tax IS/CF priority, section bonus fix.
- **Criterio de aceptación:** ✅ ACLS en VALIDATED_TICKERS al 100% FULL. 12/12 tickers al 100%. 487 tests pass. **Nota:** source_filing vacío en 223/375 campos quarterly — pendiente de corrección.

---

### BL-040 — Nuevo ticker INMD (InMode, NASDAQ, 20-F/6-K)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03) — INMD ANNUAL_ONLY 100% (108/108, 6 periodos). Commit 58ab9b7.
- **Asignado a:** Claude (elsian-4)
- **Depende de:** BL-036 DONE
- **Descripción:** InMode Ltd. (Israel, NASDAQ, CIK 1742692) foreign private issuer con 20-F/6-K. Sector medical devices/aesthetics (SIC 3845, IFRS). 6 periodos anuales FY2020-FY2025, 108 campos. Fixes al pipeline: (1) em-dash alias para eps_diluted, (2) double-column recalibration para tablas MD&A con sub-columnas $/%, (3) `(income)` pattern en _BENEFIT_RE, (4) income_tax IFRS priority patterns. Fix ACLS regression: guard de porcentaje en recalibration block. Fix SONO expected.json: eps_diluted Q4-2025 0.78→0.75 (era basic, no diluted). Pendiente: promover a FULL con quarterly (6-K Exhibit 99.1).
- **Criterio de aceptación:** ✅ INMD en VALIDATED_TICKERS al 100%. ✅ eval --all 12/12 PASS. ✅ 489 tests pass. Pendiente: period_scope FULL.

---

### BL-041 — Nuevo ticker CROX (Crocs Inc., NASDAQ, SEC)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** CROX (Crocs Inc., NASDAQ, CIK 1334036) — consumo discrecional (footwear), 10-K/10-Q estándar. Score: 100% (294/294). Fix en phase.py: severe_penalty -100→-300 (impide label_priority cancelar penalización), regla canónica ingresos+income_statement:net_income (revenue en sección "Net income" = nota suplementaria), override activo para .txt, afinidad año-periodo para net_income (FY2021 en FY2024 filing deprioritizado vs FY2023). Historial: 82.31% → 95.24% (BL-006) → 98.98% (DEC-020 scope creep) → 100% (BL-041).
- **Criterio de aceptación:** ✓ CROX 100% (294/294). ✓ 14/14 PASS. ✓ 794 tests, 0 failed. ✓ Sin regresiones.

---

### BL-042 — Rehacer SOM completamente (Somero Enterprises, LSE, UK/FCA)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-04, DEC-022 completado)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** SOM reconstruido desde cero: 16 periodos (FY2009-FY2024), 179 campos, 100% (179/179). FY2024/FY2023: 23 campos del Annual Report (US$000). FY2009-FY2022: 9-10 campos de tabla histórica SRC_003 (US$M → US$000). Tres bugs corregidos: (1) SGA alias "sales, marketing and customer support", (2) income_tax sign con raw_text para preservar negativos explícitos, (3) dividends_per_share reject patterns + manual_overrides. **⚠️ Introdujo regresión en TEP (93.75%) → ver BL-046.**
- **Criterio de aceptación:** ✓ 16 periodos ✓ 179 campos ✓ 100% ✓ Provenance L2 ✓ CHANGELOG. ⚠️ eval --all: 13/14 PASS — TEP regresionó (BL-046).

---

### BL-046 — Fix regresión TEP introducida por SOM (DEC-022)
- **Prioridad:** CRÍTICA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-042 (DONE)
- **Descripción:** BL-042 introdujo regresión en TEP (100%→93.75%). Causa raíz: `_normalize_sign` con `raw_text` preservaba signos negativos explícitos en income_tax de TEP (IFRS francés usa "-" como convención de presentación para gastos, no como beneficio fiscal). Fix: eliminar parámetro `raw_text` de `_normalize_sign`; en su lugar, anotar `"(benefit)"` en el label desde `pdf_tables.py:_extract_wide_historical_fields` cuando value < 0 en tablas históricas de SOM. Así `_BENEFIT_RE` detecta el label y preserva el negativo. Resultado: ambos tickers al 100%.
- **Criterio de aceptación:** ✓ TEP 100% (80/80). ✓ SOM 100% (179/179). ✓ eval --all 14/14 PASS. ✓ 1123+ tests, 0 failed.

---

### BL-043 — Nuevo ticker 0327 (PAX Global Technology, HKEX, Hong Kong)
- **Prioridad:** MEDIA
- **Estado:** DONE
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** Primer ticker Hong Kong Exchange. Requiere: (1) Investigar si HKEX tiene API de filings automatizable. (2) Si la hay → construir `HkexFetcher(Fetcher)`. (3) Si no → usar ManualFetcher. Filings son PDF annual reports en formato asiático. Portar filings del 3.0 desde `3_0-ELSIAN-INVEST/casos/0327/`. Sector industrials (nuevo).
- **Criterio de aceptación:** 0327 en VALIDATED_TICKERS al 100%. Fetcher HKEX (o ManualFetcher con justificación) funcional. period_scope: evaluar interim reports en HKEX (H1 obligatorio en HK → debería ser FULL).
- **Resultado:** 0327 PASS 100% (59/59), wrong=0, missed=0. Fixes aplicados: (1) D&A HKFRS split-line pattern (nota cross-ref bare integer), (2) Aliases D&A sub-componentes + reject right-of-use narrowed, (3) Per-case additive_fields en phase.py, (4) HKFRS segment single-year EBITDA extractor, (5) DPS narrativo bilingual (`_extract_hkfrs_dps_narrative`). ManualFetcher usado (filings de 3.0). Period_scope ANNUAL_ONLY (FY2022/2023/2024). Sin regressions en los 10 tickers validados.

---

### BL-044 — Promover TEP a FULL (investigar semestrales Euronext)
- **Prioridad:** MEDIA
- **Estado:** DONE
- **Asignado a:** Claude (elsian-4)
- **Depende de:** —
- **Descripción:** TEP (Teleperformance, Euronext Paris) está en ANNUAL_ONLY con 55 campos y 100%. La EU Transparency Directive obliga a publicar reportes semestrales (H1). Investigar: (1) ¿Teleperformance publica H1 financial statements completos? (2) Si sí → descargar, curar con H1, cambiar period_scope a FULL. (3) Si no → documentar excepción bajo DEC-015.
- **Criterio de aceptación:** Si H1 existe → TEP al 100% con period_scope FULL. Si no → excepción DEC-015 documentada.
- **Resultado:** H1 confirmado (SRC_011 = HALF-YEAR FINANCIAL REPORT AT 30 JUNE 2025). TEP FULL 100% (80/80). H1-2025: 15 campos, H1-2024: 10 campos. Pipeline actualizado para "1st half-year YYYY" (Euronext), "6/30/YYYY" en contexto H1, y filtro de notas decimales restringido a `is_half_year_doc=True`. KAR no regresó (49/49 100%). 3 nuevos tests.

---

### BL-034 — Field Dependency Matrix: análisis de dependencias 3.0→4.0
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-05)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Análisis estático completo de `tp_validator.py` (791L), `tp_calculator.py` (807L), y `tp_normalizer.py` (809L) del 3.0. 26 campos analizados: 8 critical, 12 required, 6 optional. 16 ya existen en 4.0, 10 faltan (3 high-priority critical: cfi, cff, delta_cash). Publicado en `docs/project/FIELD_DEPENDENCY_MATRIX.md` (533L) + `docs/project/field_dependency_matrix.json`. Evidencia rastreable por campo.
- **Criterio de aceptación:** ✓ FIELD_DEPENDENCY_MATRIX.md publicado. ✓ field_dependency_matrix.json publicado. ✓ 26/26 campos con evidencia. ✓ Pendiente revisión final por Elsian antes de Fase B (BL-035).

---

### BL-035 — Expandir campos canónicos según Field Dependency Matrix
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04) — Oleada 1 (critical CF fields) completada
- **Asignado a:** elsian-4
- **Depende de:** BL-034 (matriz revisada) + BL-038 (DONE) + oleada 3 IOSP/NEXN (DONE)
- **Descripción:** Oleada 1 (critical CF fields) completada. `cfi`, `cff`, `delta_cash` añadidos como campos canónicos 24-26. Oleada 2 (working capital: accounts_receivable, inventories, accounts_payable) separada a BL-058.
- **Criterio de aceptación:** ✓ `cfi`, `cff`, `delta_cash` en field_aliases.json (57 nuevas líneas, EN/FR/ES). ✓ 8 mappings iXBRL (US-GAAP + IFRS). ✓ TZOO +18 campos (6FY×3), 288/288 100%. ✓ NVDA +18 campos (6FY×3), 336/336 100%. ✓ 24 tests nuevos (test_cashflow_fields.py). ✓ 13/13 tickers 100%. ✓ Campos canónicos: 23→26.

---

---

### BL-045 — Limpieza post-auditoría: scope, gitignore, ficheros basura, pyproject
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-03)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Auditoría del director (2026-03-03) detectó 6 issues de governance/higiene. Ver instrucción completa más abajo. Resumen: (1) KAR y TEP sin period_scope explícito, (2) ficheros basura en NVDA, (3) _run_acquire.py trackeado, (4) expected_draft.json sin ignorar, (5) pyproject.toml requires-python incorrecto. Ninguno afecta datos ni scores — son deuda de governance.
- **Criterio de aceptación:** (1) KAR y TEP case.json con `"period_scope": "ANNUAL_ONLY"`. (2) `cases/NVDA/simple.txt`, `test.json`, `test.txt` eliminados del repo. (3) `_run_acquire.py` eliminado del repo. (4) `.gitignore` incluye `expected_draft.json` y `_run_*.py`. (5) `pyproject.toml` cambia `requires-python` a `">=3.9"`. (6) Tests 489 pass, eval --all 12/12 100%. Un solo commit.

---

### BL-048 — IxbrlExtractor en producción (WP-6)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** BL-004 (parser iXBRL DONE), BL-025 (curate DONE)
- **Descripción:** `IxbrlExtractor(Extractor)` creado en `elsian/extract/ixbrl_extractor.py`. iXBRL como extractor primario para tickers SEC. Sort key `(filing_rank, affinity, -1, -9999)` beats table extractor. Dominant-scale normalization: `_dominant_monetary_scale()` detecta escala monetaria del filing; tags con escala distinta se convierten y marcan `was_rescaled=True` (sort key debilitado). Calendar quarter fix en `ixbrl.py`: `_resolve_duration_period/instant` usan calendar quarter del end date. 45 tests unitarios. Hotfix posterior (4c80579): D&A priority US-spelling, en-dash normalization, rescaled iXBRL quality override en merger. SONO expected.json recurado (c545d59) para alinear fiscal/calendar quarter labels.
- **Criterio de aceptación:** ✓ 15/15 tickers al 100%. ✓ extraction_method=ixbrl en provenance. ✓ 45 tests. ✓ Sin regresiones.

---

### BL-049 — Truth Pack assembler (output para Módulo 2)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** `elsian/assemble/truth_pack.py` (296L). TruthPackAssembler combina extraction_result.json + _market_data.json + derived metrics + autonomous validation en truth_pack.json (TruthPack_v1 schema). CLI: `elsian assemble {TICKER}`. Secciones: financial_data, derived_metrics (TTM/FCF/EV/margins/returns/multiples/per-share), market_data, quality (9 gates summary), metadata. Piloto TZOO: 51 periodos, 792 campos, quality PASS (confidence=90.0). 45 tests (40 unit + 5 integration).
- **Criterio de aceptación:** ✓ `elsian assemble TZOO` genera truth_pack.json válido. ✓ 45 tests pass. ✓ eval --all 14/14 100%. ✓ Commit a4639af.

---

### BL-050 — Comando `elsian run` (pipeline de procesamiento)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** BL-049 (truth pack assembler)
- **Descripción:** Crear un comando que ejecute el pipeline de procesamiento para un ticker que ya tiene filings descargados, case.json y expected.json: `elsian run {TICKER}` = Convert → Extract → Normalize → Merge → Evaluate → Assemble. **No incluye Acquire** — los filings ya existen porque `elsian acquire` se ejecutó previamente (durante la curación del expected.json o como paso independiente). Hoy el pipeline ejecuta Extract+Evaluate vía `cmd_run`, pero Convert y Assemble son pasos separados. El comando `run` los orquesta en secuencia, con logging de cada fase y reporte final (score, campos, truth_pack generado). Flags opcionales: `--with-acquire` (relanzar acquire, útil cuando hay nuevo trimestre), `--skip-assemble` (solo hasta evaluate), `--force` (re-convert filings). `elsian run --all` ejecuta todos los tickers validados.
- **Criterio de aceptación:** `elsian run TZOO` ejecuta Convert→Extract→Evaluate→Assemble y genera truth_pack.json. `elsian run --all` ejecuta todos los tickers. Logging claro por fase. Tests de integración E2E. No relanza acquire por defecto.

---

### BL-051 — Auto-discovery de ticker (generador de case.json)
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-04)
- **Asignado a:** elsian-4
- **Depende de:** BL-011 (markets.py DONE)
- **Descripción:** `elsian/discover/discover.py` con TickerDiscoverer. Detecta: exchange, country, currency, regulator/source_hint, accounting_standard, CIK (SEC), web_ir, fiscal_year_end_month, company_name, sector. SEC path: EDGAR company search API. Non-US path: Yahoo Finance quoteSummary + suffix parsing (.PA→Euronext, .AX→ASX, .L→LSE, .HK→HKEX). CLI: `elsian discover {TICKER}` → cases/{TICKER}/case.json. Overwrite protection (--force). Verificado: AAPL (SEC, NASDAQ, USD, CIK 320193), TEP.PA (Euronext, EUR, IFRS). 38 tests (35 unit + 3 integration network-gated).
- **Criterio de aceptación:** ✓ `elsian discover AAPL` genera case.json correcto. ✓ `elsian discover TEP.PA` genera case.json correcto. ✓ 38 tests pass. ✓ eval --all 14/14 100%. ✓ Commit d5e04c7.

---

### BL-054 — Eliminar manual_overrides de TEP (target: 0 overrides)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** TEP tenía 6 manual_overrides (7.5% de 80 campos), superando el límite de 5% de DEC-024. El paquete local activo cerró esta deuda sin tocar expected.json: la extracción determinista narrativa ya cubre ingresos FY2022/FY2021, dividends_per_share FY2021 y fcf FY2022/FY2021/FY2019 en los formatos PDF/KPI específicos de TEP.
- **Criterio de aceptación:** ✓ TEP 100% (80/80) con 0 manual_overrides. ✓ Campos ingresos, fcf y dividends_per_share extraídos automáticamente del pipeline. ✓ eval --all verde.
- **Resultado:** Completado en el worktree local y documentado en CHANGELOG 2026-03-06. Validaciones reportadas: `python3 -m pytest -q tests/unit/test_narrative.py` → 9 passed; `python3 -m elsian.cli eval TEP` → PASS 100.0% (80/80); `python3 -m elsian.cli eval --all` → 15/15 PASS 100%; `python3 -m pytest -q` → 1258 passed, 5 skipped.

---

### BL-055 — Clasificar overrides SOM DPS: permanent exception o fixable
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** SOM tenía 2 manual_overrides de `dividends_per_share` (FY2024: $0.169, FY2023: $0.2319). La investigación confirmó que no hacía falta excepción permanente: el dato aparece de forma determinista en la tabla `FINANCIAL HIGHLIGHTS 2024` del annual report FY2024. El fix estrecho en `elsian/extract/phase.py` recupera ambas filas FY2024/FY2023 desde ese bloque y evita falsos positivos de presentaciones con importes en centavos o dividendos supplemental/special.
- **Criterio de aceptación:** ✓ SOM 100% (179/179) con 0 manual_overrides. ✓ `expected.json` intacto. ✓ eval --all verde.
- **Resultado:** Completado en el worktree local y documentado en CHANGELOG 2026-03-06. Validaciones reportadas: `python3 -m pytest -q tests/unit/test_aliases_extended.py tests/unit/test_extract_phase.py` → 34 passed; `python3 -m elsian.cli eval SOM` → PASS 100.0% (179/179); `python3 -m elsian.cli eval --all` → 15/15 PASS 100%; `python3 -m pytest -q` → 1267 passed, 5 skipped.

---

### BL-056 — Hygiene repo: truth_pack.json a .gitignore
- **Prioridad:** MEDIA
- **Estado:** DONE ✅ (2026-03-06)
- **Asignado a:** elsian-4
- **Depende de:** —
- **Descripción:** Existen 3 ficheros `truth_pack.json` (TZOO, SOM, NVDA) generados por `elsian assemble`. Son output regenerable — como extraction_result.json y filings_manifest.json, que ya están en .gitignore. Añadir `cases/*/truth_pack.json` a `.gitignore` y eliminar los 3 ficheros del tracking de git.
- **Criterio de aceptación:** `.gitignore` incluye `cases/*/truth_pack.json`. Los 3 ficheros eliminados del tracking (no del disco). `git status` limpio.

---

### BL-058 — Expandir campos canónicos: oleada 2 (working capital)
- **Prioridad:** ALTA
- **Estado:** DONE ✅ (2026-03-07)
- **Asignado a:** Codex (elsian-engineer)
- **Depende de:** BL-035 (oleada 1 DONE)
- **Descripción:** Añadir `accounts_receivable`, `inventories` y `accounts_payable` como campos canónicos para cerrar la oleada 2 de Field Dependency Matrix. La implementación amplía aliases y concept map, endurece la selección para preferir ending balances de balance sheet sobre movement tables y pilota la curación anual en TZOO y NVDA. El cierre de la tarea también reconcilia `PROJECT_STATE.md`, `BACKLOG.md`, `ROADMAP.md`, `MODULE_1_ENGINEER_CONTEXT.md` y `FIELD_DEPENDENCY_*` con el nuevo set canónico.
- **Criterio de aceptación:** ✓ Los 3 campos existen en la configuración canónica. ✓ TZOO y NVDA quedan curados y validados con ellos. ✓ `eval --all` sigue verde. ✓ Hay tests de patrón para aliases, selection y validation. ✓ BL-058 sale del backlog activo.
- **Resultado:** Completado con 3 nuevos campos canónicos (26→29) y +30 campos validados en los pilotos (TZOO 288→300, NVDA 336→354). Validaciones reportadas: `python3 -m pytest -q tests/unit/test_working_capital_fields.py tests/unit/test_validation.py` → 122 passed; `python3 -m elsian eval TZOO` → PASS 100.0% (300/300); `python3 -m elsian eval NVDA` → PASS 100.0% (354/354); `python3 -m elsian eval --all` → 15/15 PASS 100%; `python3 -m pytest -q` → 1285 passed, 5 skipped, 1 warning.

---

## Nota

- Este archivo preserva el historial técnico y de governance sin cargar el backlog operativo diario.
