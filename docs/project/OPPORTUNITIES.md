# ELSIAN-INVEST 4.0 — Opportunities

> Carril estructurado para frontera operativa y exceso packageable no seleccionado todavía.
> El subtree `Module 1 operational opportunities` alimenta el runtime de planning cuando el backlog queda vacío y también retiene trabajo ya packageable que haya quedado fuera del batch actual solo por presupuesto.
> Las ideas fuera de ese subtree no compiten con el backlog operativo ni bloquean por sí solas el cierre de Module 1.

---

## Reglas de uso

- `BACKLOG.md` sigue siendo la única cola ejecutable.
- `OPPORTUNITIES.md` no crea BLs por sí solo; solo estructura inputs para `capacity-scout` y `director`.
- El subtree operativo puede contener tanto oportunidades todavía no packageables como trabajo ya packageable no seleccionado en el batch actual por presupuesto.
- El subtree operativo de Module 1 debe mantener shape parseable y campos obligatorios por item.
- Cuando un scout pass cambia materialmente la interpretación de un item, o reafirma un item stale, el `director` debe reconciliar este fichero en una ola governance-only.
- Los items investigables solo pueden subir a `investigation_BL_ready` cuando `Unknowns remaining` describe un único experimento ejecutable y falsable.
- Los items de `Expansion candidates` solo pueden subir a `expansion_candidate` cuando representan un ticker concreto; los mercados abstractos siguen como contexto hasta una ola governance-only de curación.
- El exceso packageable que no entra en el batch vigente permanece aquí y reaparece como `matched` + `unchanged_since_last_pass` mientras no cambien las firmas o la prioridad factual.

## Module 1 operational opportunities

### Near BL-ready

### Exception watchlist

#### OP-001 — SOM: excepción ticker-level reafirmada; LSE/AIM general sigue aparte
- **Subject type:** ticker
- **Subject id:** SOM
- **Canonical state:** ANNUAL_ONLY exception_reaffirmed
- **Why it matters:** BL-087 cierra la única frontera ticker-level abierta de SOM sin convertirla en expansión de mercado. El ticker queda cerrado por excepción documentada, mientras la generalización de LSE/AIM sigue separada como frente abstracto no packageable en `OP-009`.
- **Live evidence:** El outcome aceptado de BL-087 fija `exception_reaffirmed`: el filing intermedio `SRC_003_INTERIM_H1_2025.txt` aporta solo 2 periodos H1, cobertura parcial y una inconsistencia de balance sheet (`assets 90.6` frente a `liabilities + equity 91.8`), insuficiente para promoción a `FULL` y sin follow-up reusable nuevo. La formulación normalizada del experimento ya absorbido fue: Ejecutar acquire sobre SOM buscando filings intermedios públicos utilizables.
- **Unknowns remaining:** Ninguno packageable hoy a nivel ticker. Solo revalidación periódica si aparece un filing intermedio público adicional y suficientemente fiable para reconsiderar la promoción.
- **Promotion trigger:** Evidencia nueva de un filing intermedio formal con cobertura suficiente y fiabilidad bastante para sostener promoción a `FULL` o abrir un follow-up reusable distinto del ya descartado.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-14
- **Disposition:** reaffirm_exception

#### OP-002 — KAR: revalidación periódica de la excepción ASX annual-only
- **Subject type:** ticker
- **Subject id:** KAR
- **Canonical state:** ANNUAL_ONLY justificado
- **Why it matters:** KAR ya no es frontera abierta, pero la excepción debe seguir sostenida por evidencia factual y no por inercia histórica.
- **Live evidence:** `PROJECT_STATE.md` y `DEC-015` lo cuentan como ticker ASX `ANNUAL_ONLY` justificado y fuera de backlog vivo.
- **Unknowns remaining:** Verificación periódica de que no ha aparecido filing intermedio público reutilizable ni una ruta de promoción claramente empaquetable.
- **Promotion trigger:** Evidencia nueva de filing intermedio utilizable o de cambio material en la disponibilidad/regulador que invalide la excepción.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
- **Disposition:** reaffirm_exception

#### OP-003 — JBH: revalidación periódica de la excepción ASX annual-only
- **Subject type:** ticker
- **Subject id:** JBH
- **Canonical state:** ANNUAL_ONLY justificado
- **Why it matters:** JBH cuenta hoy para `DEC-015` como excepción ASX cerrada; si aparece evidencia nueva, esa lectura podría cambiar.
- **Live evidence:** `PROJECT_STATE.md` fija la lectura operativa vigente de `DEC-015` como `14 FULL + KAR + JBH`.
- **Unknowns remaining:** Verificación periódica de que no ha aparecido filing intermedio público utilizable o una ruta de promoción mínima.
- **Promotion trigger:** Evidencia nueva de filing intermedio utilizable o de cambio material en la disponibilidad/regulador que invalide la excepción.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
- **Disposition:** reaffirm_exception

#### OP-004 — TEP: excepción de acquire Euronext reafirmada; el mercado sigue aparte
- **Subject type:** acquire
- **Subject id:** TEP
- **Canonical state:** FULL con exception_reaffirmed
- **Why it matters:** TEP ya no mantiene investigación ticker-level viva. El cierre aceptado de BL-088 reafirma que el ticker está resuelto como excepción documentada y que cualquier trabajo posterior sobre Euronext debe plantearse ya como frontera de mercado separada, no como reapertura implícita de TEP.
- **Live evidence:** El outcome aceptado de BL-088 deja nueve pruebas regulatorias EU sin identificación ni descarga de filing TEP reutilizable en esta ola: `AMF BDIF` y `ESMA OAM` devolvieron `HTTP 500`, las variantes Euronext dieron `404` o respuesta vacía, y `filings.xbrl.org` no validó una ruta reusable para TEP. El carril confirmado sigue siendo `tp.com` + fallback ya documentado, con `python3 -m elsian eval TEP` estable en PASS 100.0% (109/109). La formulación normalizada del experimento ya absorbido fue: Ejecutar un experimento de acquire sobre Euronext usando TEP como ticker ancla.
- **Unknowns remaining:** Ninguno packageable hoy a nivel ticker. Cualquier trabajo nuevo debe entrar como candidato concreto fuera de TEP o como evidencia fresca de un carril regulatorio reusable que ya no dependa de esta misma hipótesis fallida.
- **Promotion trigger:** Evidencia nueva y concreta de acquire reusable en Euronext que vaya más allá del ticker TEP o invalide la excepción hoy reafirmada.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** reaffirm_exception

#### OP-005 — 0327: acquire oficial HKEX absorbido; el frente ticker-level queda cerrado
- **Subject type:** acquire
- **Subject id:** 0327
- **Canonical state:** FULL con autonomía gradual
- **Why it matters:** El closeout aceptado de BL-091 debe impedir que el runtime reabra el mismo follow-up técnico sobre `0327`. El ticker ya no depende solo de `hkex_manual`: el carril oficial HKEX quedó absorbido en el fetcher y cualquier trabajo nuevo debe justificarse fuera de este mismo packet.
- **Live evidence:** El packet aceptado de BL-091 deja `elsian/acquire/hkex.py` con lookup oficial `prefix.do` / `partial.do`, búsquedas exact-title en Title Search y descarga directa de `ANNUAL REPORT 2024/2023/2022` + `INTERIM REPORT 2025/2024/2023`, manteniendo fallback cache/manual cuando `filings/` ya está poblado. La validación scratch sobre un case dir vacío devuelve `source=hkex`, `6` filings y los IDs estables `SRC_001_AR_FY2024`…`SRC_006_IR_H12023`; la suite shared-core sigue verde. La formulación normalizada del experimento ya absorbido fue: Ejecutar un experimento de acquire sobre HKEX usando `0327` como ticker ancla.
- **Unknowns remaining:** Ninguno packageable hoy a nivel ticker. Cualquier trabajo nuevo debe entrar como un segundo ticker HKEX concreto o como evidencia fresca de un gap shared-core distinto del ya absorbido.
- **Promotion trigger:** Evidencia nueva de regresión del carril oficial sobre `0327` o de un segundo ticker HKEX concreto que fuerce un packet distinto de generalización/adquisición.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

### Extractor / format frontiers

#### OP-006 — TALO: anchor SEC cerrado; cluster de enmiendas 2024-11-12 en watchlist
- **Subject type:** acquire
- **Subject id:** TALO
- **Canonical state:** FULL con autonomía gradual
- **Why it matters:** El closeout aceptado de BL-089 debe impedir que el runtime reabra el mismo gap cache-hit como trabajo packageable nuevo. TALO sigue al 100% y el follow-up reusable de SEC acquire/manifest ya quedó absorbido; lo único residual es la frontera factual del cluster de enmiendas del 2024-11-12, que permanece fuera de backlog activo mientras no haya evidencia nueva.
- **Live evidence:** El packet técnico aceptado de BL-089 deja `python3 -m pytest tests/unit/test_sec_edgar.py -q` en `49 passed`, `python3 -m elsian acquire TALO` vuelve a manifest con `cik=0001724965` y `coverage` no vacía, y la auditoría independiente no encuentra hallazgos materiales. El riesgo residual documentado se acota a que `filings_coverage_pct` siga fijo a `100.0` en cache-hit, sin bloquear el closeout. La formulación normalizada del experimento ya absorbido fue: Ejecutar acquire y verificación de coverage/manifest sobre TALO.
- **Unknowns remaining:** Ninguno packageable hoy. El cluster de enmiendas TALO del 2024-11-12 (`10-K/A` + `10-Q/A` x2) sigue fuera de backlog activo y no debe mezclarse con este item mientras no exista evidencia nueva de restatement trigger o de impacto real sobre períodos canonizados.
- **Promotion trigger:** Evidencia nueva de que las enmiendas del 2024-11-12 disparan un restatement trigger o revelan un gap reusable distinto del ya cerrado en BL-089.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

#### OP-007 — Fallos de extractor al promover ANNUAL_ONLY o ampliar mercados
- **Subject type:** extractor
- **Subject id:** module1-format-frontiers
- **Canonical state:** frontera técnica abierta
- **Why it matters:** Si promoción u onboarding fallan por formato, tablas o periodos intermedios, esos hallazgos deben poder convertirse en BLs shared-core y no perderse como notas ad hoc.
- **Live evidence:** La historia reciente de LSE/AIM, HKEX y Euronext muestra que los gaps de formato aparecen como patrón recurrente cuando se sale del carril SEC estable.
- **Unknowns remaining:** Qué patrón exacto reaparece con suficiente frecuencia como para convertirse en work packet reusable.
- **Promotion trigger:** Hallazgo repetible con acceptance clara y blast radius acotado en extractor/normalize/merge/acquire.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

#### OP-008 — Gaps opcionales de field dependency
- **Subject type:** extractor
- **Subject id:** field-dependency-optional-gaps
- **Canonical state:** oportunidad opcional
- **Why it matters:** `fx_effect_cash`, `other_cash_adjustments`, `market_cap` y `price` siguen fuera del backlog mientras no pasen de oportunidad a necesidad operativa real.
- **Live evidence:** `PROJECT_STATE.md` y el cierre de BL-085 los mantienen expresamente fuera del backlog vivo.
- **Unknowns remaining:** Si algún flujo factual vuelve uno de estos cuatro campos operativo y justificable como BL.
- **Promotion trigger:** necesidad operativa clara en runtime o evidencia de repetición suficiente en capacidad/diagnose.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

### Expansion candidates

#### OP-014 — ENQ: candidato ticker-level LSE/AIM pendiente de pre-gate de discoverability
- **Subject type:** ticker
- **Subject id:** ENQ
- **Canonical state:** candidato concreto no onboarded; hypothesis_basis inconclusive
- **Why it matters:** ENQ permite separar un candidato ticker-level concreto de la abstracción de mercado de `OP-009` sin vender onboarding validado ni abrir backlog. Hoy SOM sigue siendo el único ancla LSE/AIM del repo y ENQ no existe todavía como caso operativo.
- **Live evidence:** ENQ está ausente del repo operativo actual: no existe `cases/ENQ`, no hay artifacts canonizados ni referencias previas verificadas en surfaces operativas, y SOM sigue siendo el único ancla LSE/AIM documentada. El pre-check de suitability para onboarding técnico inmediato queda clasificado como `inconclusive`, no `true`: todavía no hay evidencia reproducible de discoverability suficiente ni de corpus utilizable que permita promover este candidato a una BL `targeted`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable que ENQ dispone de discoverability automática o semi-determinista suficiente, corpus annual + intermedio utilizable, y viabilidad de generar `case.json`, `filings_manifest.json` y `expected_draft.json` sin intervención manual.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end, sin convertir todavía la abstracción de mercado LSE/AIM en onboarding validado.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

#### OP-015 — AGF: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** AGF
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** AGF abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/AGF/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es AGF Management Limited via `AGF-B.TO`; requiere resolver la share class operativa antes del acquire; hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre AGF, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-016 — AIF: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** AIF
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** AIF abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/AIF/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Altus Group Limited (`AIF.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre AIF, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-017 — CABP: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** CABP
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** CABP abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/CABP/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es CAB Payments Holdings Limited (`CABP.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre CABP, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-018 — CPKR: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** CPKR
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** CPKR abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/CPKR/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Canada Packers Inc. (`CPKR.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre CPKR, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-019 — DBM: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** DBM
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** DBM abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/DBM/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Doman Building Materials Group Ltd. (`DBM.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre DBM, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-020 — DWL: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** DWL
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** DWL abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/DWL/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Dowlais Group plc (`DWL.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre DWL, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-021 — EVS: candidato concreto Euronext Brussels con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** EVS
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** EVS abre un candidato ticker-level concreto para Euronext Brussels sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/EVS/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es EVS Broadcast Equipment SA (`EVS.BR`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para Euronext Brussels sobre EVS, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-022 — FNTL: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** FNTL
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** FNTL abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/FNTL/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Fintel Plc (`FNTL.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre FNTL, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-023 — FRP: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** FRP
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** FRP abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/FRP/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es FRP Advisory Group plc (`FRP.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre FRP, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-024 — LUCE: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** LUCE
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** LUCE abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/LUCE/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Luceco plc (`LUCE.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre LUCE, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-025 — MEGP: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** MEGP
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** MEGP abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/MEGP/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es ME Group International plc (`MEGP.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre MEGP, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-026 — MFI: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** MFI
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** MFI abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/MFI/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Maple Leaf Foods Inc. (`MFI.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre MFI, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-027 — MOON: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** MOON
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** MOON abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/MOON/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Moonpig Group PLC (`MOON.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre MOON, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-028 — NCAB: candidato concreto Nasdaq Stockholm con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** NCAB
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** NCAB abre un candidato ticker-level concreto para Nasdaq Stockholm sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/NCAB/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es NCAB Group AB (`NCAB.ST`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para Nasdaq Stockholm sobre NCAB, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-029 — PANR: candidato concreto LSE/AIM con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** PANR
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** PANR abre un candidato ticker-level concreto para LSE/AIM sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/PANR/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Pantheon Resources Plc (`PANR.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE/AIM sobre PANR, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-030 — PSD: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** PSD
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** PSD abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/PSD/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Pulse Seismic Inc. (`PSD.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre PSD, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-031 — QDT: candidato concreto Euronext Paris con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** QDT
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** QDT abre un candidato ticker-level concreto para Euronext Paris sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/QDT/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Quadient S.A. (`QDT.PA`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para Euronext Paris sobre QDT, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-032 — RWS: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** RWS
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** RWS abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/RWS/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es RWS Holdings plc (`RWS.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre RWS, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-033 — SES: candidato concreto Euronext Paris con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** SES
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** SES abre un candidato ticker-level concreto para Euronext Paris sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/SES/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es SES S.A. (`SESG.PA`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para Euronext Paris sobre SES, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-034 — SMWH: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** SMWH
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** SMWH abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/SMWH/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es WH Smith PLC (`SMWH.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre SMWH, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-035 — SOIL: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** SOIL
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** SOIL abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/SOIL/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Saturn Oil & Gas Inc. (`SOIL.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre SOIL, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-036 — STC: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** STC
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** STC abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/STC/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Sangoma Technologies Corporation (`STC.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre STC, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-037 — SYZ: candidato concreto TSX con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** SYZ
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** SYZ abre un candidato ticker-level concreto para TSX sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/SYZ/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Sylogist Ltd. (`SYZ.TO`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para TSX sobre SYZ, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-038 — VID: candidato concreto LSE con acquire por demostrar
- **Subject type:** ticker
- **Subject id:** VID
- **Canonical state:** candidato concreto no onboarded; mercado sin fetcher funcional
- **Why it matters:** VID abre un candidato ticker-level concreto para LSE sin vender onboarding validado antes de demostrar un carril de acquire reproducible.
- **Live evidence:** `cases/VID/` existe con `filings_manifest.json` (`source=eu_manual`, `filings_downloaded=0`, `filings_coverage_pct=0.0`), `extraction_result.json`, `expected_draft.json` y `truth_pack.json`, pero no hay `case.json` canónico ni corpus descargado. El mercado resuelto para este símbolo es Videndum Plc (`VID.L`); hoy no existe fetcher funcional de repo para ese carril fuera de `eu_manual`.
- **Unknowns remaining:** Demostrar en un único pre-gate falsable un carril de acquire reproducible para LSE sobre VID, capaz de poblar `filings/`, `case.json` y truth filing-backed sin depender de `filings_sources` manuales permanentes.
- **Promotion trigger:** Evidencia nueva y reproducible de que ese pre-gate queda satisfecho end-to-end sobre el ticker ancla, con corpus annual/intermedio utilizable y blast radius seriable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-009 — LSE/AIM más allá de SOM
- **Subject type:** market
- **Subject id:** LSE/AIM
- **Canonical state:** mercado no generalizado
- **Why it matters:** SOM no basta para declarar capacidad amplia del mercado; falta masa crítica o patrón reusable.
- **Live evidence:** `PROJECT_STATE.md` y `OP-001` dejan a SOM cerrado como excepción ticker-level reafirmada, mientras esta entrada conserva la generalización de mercado que sigue siendo abstracta y no packageable por sí sola. ENQ y los nuevos candidatos `CABP`, `DWL`, `FNTL`, `FRP`, `LUCE`, `MEGP`, `MOON`, `PANR`, `RWS`, `SMWH` y `VID` quedan ahora persistidos aparte como tickers concretos, pero todos siguen bloqueados por el mismo gap: no existe todavía un carril de acquire reproducible en repo para LSE/LSE-AIM más allá de `eu_manual`.
- **Unknowns remaining:** Convertir al menos uno de esos candidatos concretos en un pre-gate de acquire satisfecho y reutilizable. Mientras el conjunto siga dependiendo del mismo fetcher ausente y de corpus no descargado, este item de mercado no es packageable por sí solo.
- **Promotion trigger:** candidato concreto con valor de frontera real y packet mínimo serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-010 — Euronext más allá de TEP
- **Subject type:** market
- **Subject id:** Euronext
- **Canonical state:** mercado no generalizado
- **Why it matters:** TEP demuestra un ticker útil, no una capacidad de mercado autónoma.
- **Live evidence:** `PROJECT_STATE.md` deja a TEP como excepción ticker-level reafirmada tras BL-088, mientras esta entrada conserva solo la generalización abstracta del mercado Euronext. `EVS`, `QDT` y `SES` quedan ahora persistidos como candidatos ticker-level concretos, pero todos mantienen `source=eu_manual`, `filings_downloaded=0` y ausencia de un carril de acquire reproducible fuera del ancla ya cerrada.
- **Unknowns remaining:** Convertir al menos uno de esos candidatos concretos en un pre-gate de acquire satisfecho y reutilizable. Mientras no exista corpus discoverable y descargable sin `filings_sources` manuales permanentes, este item no es packageable por sí solo.
- **Promotion trigger:** candidato concreto con capacidad nueva y scope acotado.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-15
- **Disposition:** keep

#### OP-011 — HKEX más allá de 0327
- **Subject type:** market
- **Subject id:** HKEX
- **Canonical state:** mercado no generalizado
- **Why it matters:** `0327` valida un ticker, no discovery/adquisición general HKEX.
- **Live evidence:** `BL-091` ya absorbió la ruta oficial HKEX sobre el ancla `0327` y dejó el ticker cerrado a nivel acquire. Esta entrada conserva la generalización abstracta de mercado más allá del ticker ancla: sigue sin existir hoy un segundo ticker HKEX concreto ya curado y elegible para onboarding.
- **Unknowns remaining:** Curar un ticker concreto adicional de HKEX antes de proponer onboarding. Mientras no exista candidato ticker-level con filings discoverables y blast radius `targeted`, este item no es packageable.
- **Promotion trigger:** candidato concreto con diversidad real de formato o acquire y packet serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

### Retired / absorbed

#### OP-013 — discovery-baseline: reconciliación de baseline y semántica de casos sin manifest absorbida
- **Subject type:** governance
- **Subject id:** discovery-baseline
- **Canonical state:** absorbido por governance-only wave 2026-03-14
- **Why it matters:** El scout factual del 2026-03-14 detectó que la baseline persistida y la semántica vigente de casos sin `filings_manifest.json` ya no estaban reflejadas como item explícito en el subtree operativo.
- **Live evidence:** `PROJECT_STATE.md` seguía anclado a la baseline persistida del 2026-03-13 mientras `CHANGELOG.md` ya estaba por delante y el scout del 2026-03-14 abrió una ola mixta con `1` reconciliación `missing` y `4` `investigation_BL_ready`.
- **Unknowns remaining:** Ninguno en esta ola mientras la reconciliación viva quede absorbida por los canonicals y el siguiente scout ya no lo clasifique como `missing`.
- **Promotion trigger:** Evidencia nueva de drift entre baseline persistida, semántica de manifest y estado vivo del runtime.
- **Blast radius if promoted:** governance-only
- **Expected effort:** minimal
- **Last reviewed:** 2026-03-14
- **Disposition:** retire

#### OP-012 — Tareas de producto futuras ya absorbidas fuera del runtime operativo
- **Subject type:** governance
- **Subject id:** retired-product-intake
- **Canonical state:** retirado del subtree operativo
- **Why it matters:** Sirve de sumidero para no redescubrir como “operativas” ideas ya movidas a carriles no operativos.
- **Live evidence:** El documento histórico mezclaba producto, módulo futuro y capacidad operativa en el mismo plano.
- **Unknowns remaining:** Ninguno mientras no aparezca evidencia nueva material.
- **Promotion trigger:** Evidencia nueva material que justifique reabrirlo como oportunidad operativa.
- **Blast radius if promoted:** governance-only
- **Expected effort:** minimal
- **Last reviewed:** 2026-03-12
- **Disposition:** retire

## Non-operational / future opportunities

### Producto y distribución

- API de datos para servir outputs del Módulo 1 con provenance utilizable.
- Visor web con “click to source” apoyado en provenance L3.
- Scheduler / refresh continuo de tickers validados.
- Packaging de outputs para consumo externo más allá de JSON en disco.

### Módulos futuros

- Módulo 2: extracción cualitativa (MD&A, risk factors, guidance) con trazabilidad al párrafo.
- Módulo 3: fallback LLM cuantitativo para casos donde la capa determinista no pueda recuperar el dato.
- Módulo 4: análisis y decisión sobre truth packs y métricas derivadas.

### Calidad y operación

- Informes de salud de repo periódicos cuando el briefing manual deje de ser suficiente.
- Más tests de patrón reutilizable, no solo por ticker.
- Endurecimiento adicional de CI cuando el coste de ejecución sea estable y asumible.
- Detección más rica de drift documental o operativo si aparece fricción real en el uso diario.

### Operación y releases

- Lane de experimentos y releases para desacoplar pruebas, validación y promoción a runtime estable sin contaminar el backlog ejecutable de Module 1.

### Nota

- Mantener estas ideas fuera del subtree operativo evita que el cierre de Module 1 quede bloqueado por producto futuro o por exploración no ligada al runtime actual.
