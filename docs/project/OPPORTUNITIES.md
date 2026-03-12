# ELSIAN-INVEST 4.0 — Opportunities

> Carril estructurado para trabajo no ejecutable todavía.
> El subtree `Module 1 operational opportunities` alimenta el runtime de planning cuando el backlog queda vacío.
> Las ideas fuera de ese subtree no compiten con el backlog operativo ni bloquean por sí solas el cierre de Module 1.

---

## Reglas de uso

- `BACKLOG.md` sigue siendo la única cola ejecutable.
- `OPPORTUNITIES.md` no crea BLs por sí solo; solo estructura inputs para `capacity-scout` y `director`.
- El subtree operativo de Module 1 debe mantener shape parseable y campos obligatorios por item.
- Cuando un scout pass cambia materialmente la interpretación de un item, o reafirma un item stale, el `director` debe reconciliar este fichero en una ola governance-only.

## Module 1 operational opportunities

### Near BL-ready

#### OP-001 — SOM: promoción a FULL o cierre como excepción documentada
- **Subject type:** ticker
- **Subject id:** SOM
- **Canonical state:** frontera abierta
- **Why it matters:** SOM es el único ticker actual validado `ANNUAL_ONLY` que sigue abierto de forma explícita y mantiene LSE/AIM en Fase C.
- **Live evidence:** `PROJECT_STATE.md` lo mantiene fuera de `DEC-015` y `OPPORTUNITIES.md` lo trata como la única frontera ticker-level abierta.
- **Unknowns remaining:** Confirmar si existe filing intermedio público utilizable y si esa evidencia basta para empaquetar una promoción o una reafirmación de excepción.
- **Promotion trigger:** Evidencia factual nueva que acote una única ola serial: promoción a `FULL` o excepción cerrada con soporte documental suficiente.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

### Exception watchlist

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

#### OP-004 — TEP: capacidad Euronext sigue siendo ticker-level, no de mercado
- **Subject type:** acquire
- **Subject id:** TEP
- **Canonical state:** FULL con documented exception
- **Why it matters:** TEP está cerrado a nivel ticker, pero la autonomía operativa de acquire en Euronext sigue siendo parcial y no prueba un carril de mercado general.
- **Live evidence:** `PROJECT_STATE.md` lo clasifica como `FULL` con `documented exception` y mercado `gradual`.
- **Unknowns remaining:** Si existe una ruta de acquire reproducible sin manualismo suficiente para convertir esta limitación en BL-ready de capacidad de mercado.
- **Promotion trigger:** Evidencia nueva de patrón reusable en Euronext o de limitación clara y acotada susceptible de una BL técnica mínima.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-12
- **Disposition:** reaffirm_exception

#### OP-005 — 0327: capacidad HKEX sigue siendo ticker-level, no de mercado
- **Subject type:** acquire
- **Subject id:** 0327
- **Canonical state:** FULL con documented exception
- **Why it matters:** `0327` valida un ticker HKEX, pero no canoniza discovery/adquisición general del mercado.
- **Live evidence:** `PROJECT_STATE.md` lo deja como `FULL` con `hkex_manual` reproducible y HKEX en Fase C de mercado.
- **Unknowns remaining:** Si existe un patrón de acquire reusable más allá de este ticker o una limitación de mercado suficientemente acotada para BL-ready.
- **Promotion trigger:** Evidencia nueva de acquire reusable en HKEX o de limitación shared-core claramente empaquetable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-12
- **Disposition:** reaffirm_exception

### Extractor / format frontiers

#### OP-006 — TALO: gap factual de coverage/manifest y autonomía operativa parcial
- **Subject type:** acquire
- **Subject id:** TALO
- **Canonical state:** FULL con autonomía gradual
- **Why it matters:** TALO sigue validado al 100%, pero mantiene un gap factual abierto de coverage/manifest que hoy no está empaquetado como BL-ready y que bloquea el cierre fuerte de Module 1.
- **Live evidence:** `PROJECT_STATE.md` mantiene el gap factual de `coverage/manifest` como limitación ticker-level del runtime actual.
- **Unknowns remaining:** Si el gap puede acotarse a una BL targeted/shared-core pequeña o si requiere replantear la semántica de excepción.
- **Promotion trigger:** Evidencia nueva que reduzca el problema a una sola aceptación técnica clara o que justifique una excepción documentada estable.
- **Blast radius if promoted:** targeted
- **Expected effort:** bounded
- **Last reviewed:** 2026-03-12
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
- **Live evidence:** `PROJECT_STATE.md` mantiene LSE/AIM en Fase C y `SOM` como único frente ticker-level abierto.
- **Unknowns remaining:** Qué candidato o formato adicional probaría capacidad nueva en vez de repetir el piloto actual.
- **Promotion trigger:** candidato concreto con valor de frontera real y packet mínimo serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

#### OP-010 — Euronext más allá de TEP
- **Subject type:** market
- **Subject id:** Euronext
- **Canonical state:** mercado no generalizado
- **Why it matters:** TEP demuestra un ticker útil, no una capacidad de mercado autónoma.
- **Live evidence:** `PROJECT_STATE.md` lo deja en Fase A solo a nivel ticker y en Fase C a nivel de mercado.
- **Unknowns remaining:** Qué candidato o patrón nuevo probaría acquire/convert/extract reusable en Euronext.
- **Promotion trigger:** candidato concreto con capacidad nueva y scope acotado.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

#### OP-011 — HKEX más allá de 0327
- **Subject type:** market
- **Subject id:** HKEX
- **Canonical state:** mercado no generalizado
- **Why it matters:** `0327` valida un ticker, no discovery/adquisición general HKEX.
- **Live evidence:** `PROJECT_STATE.md` y el cierre de BL-083 dejan explícito que HKEX sigue en frontera de mercado.
- **Unknowns remaining:** Qué candidato y qué filing probarían capacidad nueva sin rehacer el mismo piloto.
- **Promotion trigger:** candidato concreto con diversidad real de formato o acquire y packet serializable.
- **Blast radius if promoted:** shared-core
- **Expected effort:** broad
- **Last reviewed:** 2026-03-12
- **Disposition:** keep

### Retired / absorbed

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
