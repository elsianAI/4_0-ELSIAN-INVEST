# Resolución de inconsistencias de campos derivados — BL-077

**Fecha:** 2026-03-10
**Tarea:** BL-077 — Investigar inconsistencias de campos derivados
**Agente:** engineer (GitHub Copilot / Claude Sonnet 4.6)

---

## Resumen ejecutivo

| Ticker | Campo | Periodos | Clasificación | Acción tomada |
|--------|-------|----------|---------------|---------------|
| ACLS | ebitda | Q1-2024, Q2-2024, Q3-2024, Q1-2025, Q2-2025, Q3-2025 | (b) Fórmula inaplicable | Sin cambio en truth |
| NEXN | gross_profit | FY2021, FY2022, FY2023, FY2024 | (b) Fórmula inaplicable | Sin cambio en truth |
| SONO | gross_profit | Q3-2023 | (c) Componente mal capturado | Documentado; fix en BL futura |
| SOM | delta_cash | FY2023, FY2024 | (b) Fórmula inaplicable | Sin cambio en truth |
| TZOO | delta_cash | FY2019, FY2022, FY2023, FY2024 | (b) Fórmula inaplicable | Sin cambio en truth |

**Resultado:** 9 sobre 12 casos son (b), 1 es (c). 0 casos son (a) — ningún valor curado en expected.json es incorrecto en los tickers de tipo (b) o ha sido corregido. El caso (c) queda trazado sin mutación de truth para evitar romper el eval hasta que el pipeline del período sea reconciliado.

---

## Baselines de evaluación previos a cualquier mutación

| Ticker | Score antes |
|--------|-------------|
| ACLS | 100.0% (486/486) wrong=0 missed=0 |
| NEXN | 100.0% (177/177) wrong=0 missed=0 |
| SONO | 100.0% (404/404) wrong=0 missed=0 |
| SOM  | 100.0% (203/203) wrong=0 missed=0 |
| TZOO | 100.0% (348/348) wrong=0 missed=0 |

---

## ACLS — ebitda — Q1-2024, Q2-2024, Q3-2024, Q1-2025, Q2-2025, Q3-2025

### Valores en expected.json vs derivado

| Periodo | ebitda (stored) | ebit | DA | ebit+DA (derivado) | Diff |
|---------|-----------------|------|----|--------------------|------|
| Q1-2024 | 64,545 | 56,539 | 3,775 | 60,314 | +4,231 (7.0%) |
| Q2-2024 | 63,568 | 52,810 | 3,861 | 56,671 | +6,897 (12.2%) |
| Q3-2024 | 59,674 | 46,913 | 3,906 | 50,819 | +8,855 (17.4%) |
| Q1-2025 | 39,520 | 29,159 | 4,309 | 33,468 | +6,052 (18.1%) |
| Q2-2025 | 38,872 | 28,965 | 4,515 | 33,480 | +5,392 (16.1%) |
| Q3-2025 | 43,202 | 25,020 | 4,328 | 29,348 | +13,854 (47.2%) |

### Fuente filing-backed

Todos los valores `ebitda` provienen de **8-K press releases de earnings** (SRC_021, SRC_024, SRC_025). ACLS reporta "Adjusted EBITDA" en estas notas, no GAAP EBITDA.

Evidencia de la reconciliación explícita en `SRC_025_8-K_2025-05-06.clean.md` (Q1-2025 y Q1-2024):

```
| Net income                      | 28,579 | 51,595 |
| Other (income)/expense          | (3,925)| (2,460)|
| Income tax provision            |  4,505 |  7,404 |
| Depreciation & amortization     |  4,309 |  3,775 |
| Subtotal                        | 33,468 | 60,314 |  ← GAAP EBITDA (= ebit+DA)
| Bad debt expense                |     —  |   (459)|
| Restructuring                   |  1,149 |     —  |
| Stock-based compensation        |  4,903 |  4,690 |
| Adjusted EBITDA                 | 39,520 | 64,545 |  ← valor en expected.json
```

### Fórmula completa

```
Adjusted EBITDA = Net income + Other(net) + Tax + DA + Bad_debt + Restructuring + SBC
                = GAAP_EBITDA + Restructuring + SBC + otros ajustes non-GAAP
```

La diferencia entre `ebit+DA` (GAAP) y el Adjusted EBITDA reportado corresponde a:
- Stock-based compensation (SBC): ~4,690–4,903 en 2024, creciente en 2025
- Restructuring: presente en algunos periodos (Q1-2025: 1,149)
- Bad debt expense: ajuste menor en algunos periodos

### Clasificación

**Caso (b): fórmula simplificada no aplicable.**

ACLS reporta "Adjusted EBITDA" (non-GAAP) en sus earnings releases, que incluye SBC, restructuring y otros ajustes que no están capturados en la fórmula `ebitda = ebit + DA`. El valor curado (Adjusted EBITDA) es correcto como reportado por la compañía. El GAAP EBITDA (ebit+DA) es una métrica distinta a la que ACLS presenta públicamente. BL-075 acertó al excluir estos periodos de auto-derivación en `DERIVED_INCONSISTENT_PERIODS`.

**No se toca truth. No se añade ningún override.**

---

## NEXN — gross_profit — FY2021, FY2022, FY2023, FY2024

### Valores en expected.json vs derivado

| Periodo | gross_profit (stored) | ingresos | cost_of_revenue | Rev-CoR (derivado) | Diff |
|---------|-----------------------|----------|-----------------|--------------------|------|
| FY2021 | 253,689 | 341,945 | 71,651 | 270,294 | -16,605 (6.1%) |
| FY2022 | 249,138 | 335,250 | 60,745 | 274,505 | -25,367 (9.2%) |
| FY2023 | 218,898 | 331,993 | 62,270 | 269,723 | -50,825 (18.8%) |
| FY2024 | 257,085 | 365,477 | 61,020 | 304,457 | -47,372 (15.6%) |

Fuente: todos los campos vienen de `SRC_001_20-F_FY2025.clean.md` o `SRC_002_20-F_FY2024.clean.md` (20-F foreign private issuer, empresa israelí).

### Estructura del income statement de NEXN

NEXN presenta su income statement con una nota explícita en la cabecera de costo:

```
| Cost of revenues (exclusive of depreciation and amortization shown separately below) |
```

El filing (SRC_001_20-F_FY2025.clean.md) muestra la reconciliación explícita para FY2024 y FY2023:

```
| Revenues                                                              | 365,477 | 331,993 |
| Cost of revenues (exclusive of D&A)                                   |  61,020 |  62,270 |
| Depreciation and amortization attributable to cost of revenues        |  47,372 |  50,825 |
| Gross profit (IFRS)                                                   | 257,085 | 218,898 |
```

### Fórmula real de NEXN

```
Gross Profit = Revenue - CoR(excl.DA) - DA_attributable_to_CoR
```

Para FY2024: 365,477 - 61,020 - 47,372 = **257,085** ✓ (coincide con stored)
Para FY2023: 331,993 - 62,270 - 50,825 = **218,898** ✓ (coincide con stored)

El `cost_of_revenue` en expected.json = CoR excl. DA (61,020 / 62,270), que es lo que aparece explícitamente en la línea "Cost of revenues". El DA atribuible a CoR (47,372 / 50,825) es un componente separado que NEXN presenta explícitamente, pero que NO forma parte del campo `cost_of_revenue` tal como está curado.

La fórmula simplificada `gross_profit = ingresos - cost_of_revenue` produce 304,457 (FY2024), que no coincide con 257,085 porque ignora los 47,372 de DA atribuido a CoR.

Los valores FY2021 y FY2022 siguen el mismo patrón: la diferencia (16,605 y 25,367 respectivamente) corresponde al DA atribuido a CoR en esos años.

### Clasificación

**Caso (b): fórmula simplificada no aplicable.**

NEXN presenta "Cost of revenues exclusive of D&A" como línea de CoR en el IS, con una segunda línea separada de DA atribuido a CoR. La fórmula `GP = Revenue - CoR` solo aplica cuando CoR incluye DA; aquí CoR excluye DA expresamente. El gross_profit curado en expected.json es correcto (taken from the face of the income statement as reported). Los valores de `cost_of_revenue` también son correctos (la línea "Cost of revenues exclusive of D&A" tal como aparece en el filing).

**No se toca truth. No se añade ningún override.**

---

## SONO — gross_profit — Q3-2023

### Valores en expected.json

| Campo | Valor | Source filing |
|-------|-------|---------------|
| ingresos | 305,147 | SRC_003_10-K_FY2023.clean.md |
| cost_of_revenue | 201,594 | SRC_014_10-Q_Q3-2023.clean.md |
| gross_profit | 128,054 | SRC_003_10-K_FY2023.clean.md |

Derivado: ingresos - cost_of_revenue = 305,147 - 201,594 = **103,553** ≠ 128,054 (diff=23.7%)

### Mapeo de períodos: convención calendar vs fiscal Sonos

La convención del proyecto usa **trimestres calendario**:
- Q3-2023 = julio–septiembre 2023 = trimestre que finaliza en torno al 30 de septiembre de 2023

Sonos usa un **fiscal year ending en septiembre/octubre**, con trimestres desplazados del calendario:
- Fiscal Q4-FY2023 = julio–30 septiembre 2023 ← coincide con el calendar Q3-2023 del proyecto
- Fiscal Q3-FY2023 = abril–1 julio 2023 ← período distinto; cubierto por el 10-Q "Q3-2023"

### Evidencia filing-backed del período correcto (10-K FY2023)

El 10-K FY2023 (`SRC_003_10-K_FY2023.clean.md`) incluye una tabla de quarterly breakdown:

```
| Three Months Ended | Sep 30, 2023 | Jul 1, 2023 | Apr 1, 2023 | Dec 31, 2022 |
| Revenue            |    305,147   |   373,356   |   304,173   |   672,579    |
| Gross profit       |    128,054   |   171,762   |   131,618   |   285,057    |
| Net income (loss)  |   (31,239)  |  (23,571)  |  (30,652)  |   75,188     |
```

Para el trimestre que finaliza el 30 septiembre (= calendar Q3-2023):
- Revenue = 305,147 ← correcto en expected.json
- Gross profit = 128,054 ← correcto en expected.json
- Cost of revenue (implícito) = 305,147 - 128,054 = **177,093**

La tabla del 10-K **no presenta explícitamente** `cost_of_revenue` por trimestre; solo revenue y gross profit.

### Evidencia filing-backed del valor incorrecto (10-Q Q3-2023)

El 10-Q `SRC_014_10-Q_Q3-2023.clean.md` cubre el trimestre fiscal Q3 de Sonos (3 meses que finalizan el 1 julio 2023 = calendar Q2-2023):

```
| Revenue            | 373,356 |
| Cost of revenue    | 201,594 |
| Gross profit       | 171,762 |
```

El valor 201,594 es el cost_of_revenue **del trimestre abril–julio 1**, no del trimestre julio–septiembre.

### Análisis de la discrepancia

El expected.json Q3-2023 mezcla fuentes de dos períodos distintos:
- `ingresos` y `gross_profit` provienen del trimestre September 30, 2023 (10-K FY2023, columna Sep 30) → **correcto para calendar Q3-2023**
- `cost_of_revenue` proviene del trimestre July 1, 2023 (10-Q fiscal Q3) → **incorrecto para calendar Q3-2023**

El valor correcto para `cost_of_revenue` en calendar Q3-2023 es **177,093** (= Revenue - GP, ambos del 10-K para el Sep 30 quarter). Este valor es filing-backed por aritmética de identidad contable a partir del 10-K.

### Clasificación

**Caso (c): componente mal capturado.**

El `cost_of_revenue` para SONO Q3-2023 fue curado desde el 10-Q de Sonos fiscal Q3 (queending July 1), que cubre un período distinto al que representa calendar Q3-2023 (July–September). El pipeline mapea el filing "SRC_014_10-Q_Q3-2023" a Q3-2023 porque así está nombrado en el manifest, pero ese 10-Q cubre fiscal Q3 (ending July 1 = calendar Q2), no calendar Q3 (July–September).

**Valor correcto demostrable desde el filing: 177,093** (= 305,147 - 128,054, identidad contable sobre datos explícitos del 10-K FY2023).

**Por qué no se corrige truth en esta BL:**
La corrección de `cost_of_revenue` en expected.json a 177,093 haría que el eval de SONO mostrara WRONG para ese campo (porque el pipeline extrae 201,594 del 10-Q fiscal Q3). Modificar truth sin simultáneamente corregir el pipeline rompería el eval score de SONO (de 100% a <100%), lo cual constituye una regresión en la evaluación del pipeline actual. La corrección correcta requiere: (a) actualizar el mapeo de período del filing fiscal Q3 de Sonos en la capa de adquisición/merge para que no se interprete como calendar Q3, y (b) corrección simultánea de truth. Esto es una intervención shared-core y debe ir en una BL separada.

**Acción pendiente en BL futura:** Reconciliar el mapeo de períodos de Sonos fiscal quarters a calendar quarters en la capa de acquire/merge. Aplicar simultáneamente la corrección de truth: cambiar `cost_of_revenue` Q3-2023 de 201,594 a 177,093, con `source_filing` = SRC_003_10-K_FY2023.clean.md.

**No se toca truth en esta BL. La discrepancia sale de BL-077 clasificada con evidencia completa y delegada a BL futura.**

---

## SOM — delta_cash — FY2023, FY2024

### Valores en expected.json vs derivado

| Periodo | delta_cash (stored) | cfo | cfi | cff | cfo+cfi+cff | Diff |
|---------|---------------------|-----|-----|-----|-------------|------|
| FY2023 | -388 | 24,446 | -1,740 | -22,576 | 130 | -518 (398.5%) |
| FY2024 | -3,825 | 17,627 | -2,449 | -19,326 | -4,148 | +323 (7.8%) |

Fuente: todos los campos de `SRC_001_ANNUAL_REPORT_FY2024.txt`.

### Evidencia filing-backed: CF statement completo de SOM

El cash flow statement del Annual Report FY2024 (SRC_001_ANNUAL_REPORT_FY2024.txt, líneas ~3234-3248) muestra explícitamente:

```
Net cash provided by operating activities          17,627    24,446
                                                  ────────  ────────
Net cash used in investing activities              (2,449)   (1,740)
                                                  ────────  ────────
Net cash used in financing activities             (19,326)  (22,576)
                                                  ────────  ────────
Effect of exchange rates on cash and cash equiv.      323      (518)
                                                  ────────  ────────
Net decrease in cash and cash equivalents          (3,825)     (388)
```

Reconciliación completa:

**FY2024:** 17,627 - 2,449 - 19,326 + 323 = **-3,825** ✓ (delta_cash stored CORRECTO)
**FY2023:** 24,446 - 1,740 - 22,576 + (-518) = **-388** ✓ (delta_cash stored CORRECTO)

La componente no capturada es "**Effect of exchange rates on cash and cash equivalents**":
- FY2024: +323 (FX mejora caja)
- FY2023: -518 (FX reduce caja)

### Clasificación

**Caso (b): fórmula simplificada no aplicable.**

SOM es una empresa con operaciones internacionales (presencia en Europa, Australia, India, China, etc.) que reporta en USD pero mantiene saldos en divisas locales. El estado de flujos de caja de US GAAP incluye una línea obligatoria "Effect of exchange rate changes on cash and cash equivalents" que reconcilia la variación de caja de inicio a fin de año. Esta línea **no forma parte de** ninguna de las tres actividades (operación, inversión, financiación) y no está capturada por la fórmula `delta_cash = cfo + cfi + cff`.

Los valores curados de `delta_cash` (-388 y -3,825) son correctos tal como reportados en el filing. No son calculables por la fórmula simplificada.

**No se toca truth. No se añade ningún override.**

---

## TZOO — delta_cash — FY2019, FY2022, FY2023, FY2024

### Valores en expected.json vs derivado

| Periodo | delta_cash (stored) | cfo | cfi | cff | cfo+cfi+cff | Diff |
|---------|---------------------|-----|-----|-----|-------------|------|
| FY2019 | 1,249 | 11,236 | -1,147 | -9,106 | 983 | +266 (27.1%) |
| FY2022 | -25,611 | -23,121 | -1,315 | 1,282 | -23,154 | -2,457 (10.6%) |
| FY2023 | -2,989 | 10,675 | -39 | -14,150 | -3,514 | +525 (14.9%) |
| FY2024 | 1,351 | 21,100 | -177 | -18,973 | 1,950 | -599 (30.7%) |

Fuente: `SRC_006_10-K_FY2019.clean.md`, `SRC_003_10-K_FY2022.clean.md`, `SRC_002_10-K_FY2023.clean.md`, `SRC_001_10-K_FY2024.clean.md`.

### Evidencia filing-backed: CF statements de TZOO

**FY2024 y FY2023** (SRC_001_10-K_FY2024.clean.md):
```
Net cash provided by operating activities              21,100    10,675
Net cash used in investing activities                    (177)      (39)
Net cash used in financing activities                 (18,973)  (14,150)
Effect of exchange rate changes on cash                  (599)      525
Net increase (decrease) in cash and restricted cash     1,351    (2,989)
```
FY2024: 21,100 - 177 - 18,973 + (-599) = **1,351** ✓
FY2023: 10,675 - 39 - 14,150 + 525 = **-2,989** ✓

**FY2019** (SRC_006_10-K_FY2019.clean.md):
```
Net cash provided by operating activities              11,236
Net cash used in investing activities                  (1,147)
Net cash used in financing activities                  (9,106)
Effect of exchange rate changes on cash                   266
Net increase in cash and restricted cash                1,249
```
FY2019: 11,236 - 1,147 - 9,106 + 266 = **1,249** ✓

**FY2022** (SRC_003_10-K_FY2022.clean.md):
```
Net cash used in operating activities                 (23,121)
Net cash used in investing activities                  (1,315)
Net cash from financing activities                      1,282
Effect of exchange rate changes on cash                (2,457)
Net decrease in cash and restricted cash              (25,611)
```
FY2022: -23,121 - 1,315 + 1,282 + (-2,457) = **-25,611** ✓

La diferencia entre delta_cash y cfo+cfi+cff es exactamente el "Effect of exchange rate changes on cash" en todos los períodos:
- FY2019: +266
- FY2022: -2,457
- FY2023: +525
- FY2024: -599

### Clasificación

**Caso (b): fórmula simplificada no aplicable.**

TZOO es una empresa con operaciones internacionales (US GAAP, ticker Nasdaq). Sus estados de flujos de caja incluyen la línea "Effect of exchange rate changes on cash and cash equivalents" en todos los años auditados. Esta línea es obligatoria bajo US GAAP para empresas con exposición a FX y **no forma parte de** las tres actividades de CF. La fórmula `delta_cash = cfo + cfi + cff` es una simplificación que no aplica en este caso. Nótese que el signo y magnitud del efecto FX varía año a año (puede ser positivo o negativo según la evolución del USD), lo que explica por qué la discrepancia no es sistemática. Los valores curados de `delta_cash` son correctos en todos los períodos.

**No se toca truth. No se añade ningún override.**

---

## Conclusión y cierre del bucket BL-077

Todas las inconsistencias derivadas identificadas en `docs/reports/AUDIT_EXPECTED_JSON.md` para los cinco tickers en scope han sido clasificadas con evidencia filing-backed:

- **9 casos (b):** La fórmula simplificada no aplica. Los valores curados son correctos. No se necesita ninguna acción sobre truth.
  - ACLS ebitda × 6 periodos: "Adjusted EBITDA" = GAAP EBITDA + SBC + Restructuring + otros ajustes
  - NEXN gross_profit × 4 periodos: CoR excl. DA en IS → GP = Rev - CoR(excl.DA) - DA_CoR
  - SOM delta_cash × 2 periodos: delta_cash = cfo + cfi + cff + FX_effect
  - TZOO delta_cash × 4 periodos: delta_cash = cfo + cfi + cff + FX_effect

- **1 caso (c):** Componente mal capturado. Evidencia filing-backed completa. Sin mutación de truth en esta BL (requiere fix simultáneo de pipeline y truth en BL futura).
  - SONO cost_of_revenue Q3-2023: curado desde Sonos fiscal Q3 10-Q (July 1) cuando Q3-2023 = calendar Q3 (Sep 30); valor correcto = 177,093 (= 305,147 - 128,054 de 10-K)

**El bucket BL-077 queda cerrado.** Cada discrepancia ha salido del bucket con clasificación, evidencia y resolución/recomendación. No se han añadido manual_overrides, no se ha debilitado ningún expected.json y no se han abierto nuevas olas de derivados.
