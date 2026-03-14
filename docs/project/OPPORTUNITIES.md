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
- **Live evidence:** El outcome aceptado de BL-087 fija `exception_reaffirmed`: el filing intermedio `SRC_003_INTERIM_H1_2025.txt` aporta solo 2 periodos H1, cobertura parcial y una inconsistencia de balance sheet (`assets 90.6` frente a `liabilities + equity 91.8`), insuficiente para promoción a `FULL` y sin follow-up reusable nuevo.
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
- **Live evidence:** El outcome aceptado de BL-088 deja nueve pruebas regulatorias EU sin identificación ni descarga de filing TEP reutilizable en esta ola: `AMF BDIF` y `ESMA OAM` devolvieron `HTTP 500`, las variantes Euronext dieron `404` o respuesta vacía, y `filings.xbrl.org` no validó una ruta reusable para TEP. El carril confirmado sigue siendo `tp.com` + fallback ya documentado, con `python3 -m elsian eval TEP` estable en PASS 100.0% (109/109).
- **Unknowns remaining:** Ninguno packageable hoy a nivel ticker. Cualquier trabajo nuevo debe entrar como candidato concreto fuera de TEP o como evidencia fresca de un carril regulatorio reusable que ya no dependa de esta misma hipótesis fallida.
- **Promotion trigger:** Evidencia nueva y concreta de acquire reusable en Euronext que vaya más allá del ticker TEP o invalide la excepción hoy reafirmada.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** reaffirm_exception

#### OP-005 — 0327: ruta oficial HKEX probada; follow-up shared-core abierto
- **Subject type:** acquire
- **Subject id:** 0327
- **Canonical state:** FULL con documented exception
- **Why it matters:** `BL-090` falsó la lectura de que `0327` solo valida capacidad ticker-level cerrada con `hkex_manual`: la ruta oficial de HKEX ya quedó probada a nivel de evidencia, por lo que el siguiente paso correcto ya no es otra investigación sino un follow-up técnico shared-core (`BL-091`) que convierta esa ruta en acquire reusable.
- **Live evidence:** El experimento aceptado de `BL-090` probó tres piezas oficiales y reproducibles: `prefix.do` / `partial.do` resuelven `stockId=56792` para `00327 PAX GLOBAL`; el Title Search oficial devuelve 638 resultados para el ticker con annual/interim reports visibles; y los PDFs directos `2025082800017.pdf`, `2025041600007.pdf`, `2024082900003.pdf` y `2024041800065.pdf` descargan `200 application/pdf`.
- **Unknowns remaining:** `BL-091` debe implementar en `elsian/acquire/` un path reusable que use lookup oficial + Title Search + descarga directa de PDFs HKEX para `0327`, preservando `hkex_manual` como fallback y sin mezclar extract/merge/eval. Si ese follow-up no consigue convertir la evidencia en fetcher reproducible, la excepción ticker-level deberá reafirmarse de nuevo con evidencia actualizada.
- **Promotion trigger:** Cierre green de `BL-091` o evidencia nueva de que la ruta oficial no puede convertirse en acquire reproducible dentro del fetcher.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

### Extractor / format frontiers

#### OP-006 — TALO: anchor SEC cerrado; cluster de enmiendas 2024-11-12 en watchlist
- **Subject type:** acquire
- **Subject id:** TALO
- **Canonical state:** FULL con autonomía gradual
- **Why it matters:** El closeout aceptado de BL-089 debe impedir que el runtime reabra el mismo gap cache-hit como trabajo packageable nuevo. TALO sigue al 100% y el follow-up reusable de SEC acquire/manifest ya quedó absorbido; lo único residual es la frontera factual del cluster de enmiendas del 2024-11-12, que permanece fuera de backlog activo mientras no haya evidencia nueva.
- **Live evidence:** El packet técnico aceptado de BL-089 deja `python3 -m pytest tests/unit/test_sec_edgar.py -q` en `49 passed`, `python3 -m elsian acquire TALO` vuelve a manifest con `cik=0001724965` y `coverage` no vacía, y la auditoría independiente no encuentra hallazgos materiales. El riesgo residual documentado se acota a que `filings_coverage_pct` siga fijo a `100.0` en cache-hit, sin bloquear el closeout.
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

#### OP-009 — LSE/AIM más allá de SOM
- **Subject type:** market
- **Subject id:** LSE/AIM
- **Canonical state:** mercado no generalizado
- **Why it matters:** SOM no basta para declarar capacidad amplia del mercado; falta masa crítica o patrón reusable.
- **Live evidence:** `PROJECT_STATE.md` y `OP-001` dejan a SOM cerrado como excepción ticker-level reafirmada, mientras esta entrada conserva la generalización de mercado que sigue siendo abstracta y no packageable por sí sola.
- **Unknowns remaining:** Curar un ticker concreto adicional de LSE/AIM antes de proponer onboarding. Mientras no exista candidato ticker-level con filings discoverables y blast radius `targeted`, este item no es packageable.
- **Promotion trigger:** candidato concreto con valor de frontera real y packet mínimo serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

#### OP-010 — Euronext más allá de TEP
- **Subject type:** market
- **Subject id:** Euronext
- **Canonical state:** mercado no generalizado
- **Why it matters:** TEP demuestra un ticker útil, no una capacidad de mercado autónoma.
- **Live evidence:** `PROJECT_STATE.md` deja a TEP como excepción ticker-level reafirmada tras BL-088, mientras esta entrada conserva solo la generalización abstracta del mercado Euronext, que sigue sin candidato ticker-level adicional listo ni carril reusable probado fuera del ancla ya cerrada.
- **Unknowns remaining:** Curar un ticker concreto adicional de Euronext antes de proponer onboarding. Mientras no exista candidato ticker-level con filings discoverables y blast radius `targeted`, este item no es packageable.
- **Promotion trigger:** candidato concreto con capacidad nueva y scope acotado.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-14
- **Disposition:** keep

#### OP-011 — HKEX más allá de 0327
- **Subject type:** market
- **Subject id:** HKEX
- **Canonical state:** mercado no generalizado
- **Why it matters:** `0327` valida un ticker, no discovery/adquisición general HKEX.
- **Live evidence:** `BL-091` abre un follow-up shared-core sobre el ancla `0327` para convertir la ruta oficial HKEX en acquire reusable. Esta entrada conserva la generalización abstracta de mercado más allá del ticker ancla: sigue sin existir hoy un segundo ticker HKEX concreto ya curado y elegible para onboarding.
- **Unknowns remaining:** Curar un ticker concreto adicional de HKEX antes de proponer onboarding. Mientras no exista candidato ticker-level con filings discoverables y blast radius `targeted`, este item no es packageable.
- **Promotion trigger:** candidato concreto con diversidad real de formato o acquire y packet serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-13
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
