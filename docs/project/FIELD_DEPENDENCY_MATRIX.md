# Field Dependency Matrix: 3.0 → 4.0

> **BL-034** — Análisis exhaustivo de campos financieros consumidos por `tp_validator.py` y `tp_calculator.py` del 3.0, con mapping a campos canónicos del 4.0.
>
> Generado: 2026-03-03  
> Fuentes analizadas:
> - `3_0-ELSIAN-INVEST/scripts/runners/tp_validator.py` (791 líneas)
> - `3_0-ELSIAN-INVEST/scripts/runners/tp_calculator.py` (807 líneas)
> - `4_0-ELSIAN-INVEST/config/field_aliases.json` (23 campos canónicos, v1.0)

---

## 1. Resumen ejecutivo

| Métrica | Valor |
|---------|-------|
| Total de campos analizados | **26** |
| Clasificación `critical` | **8** |
| Clasificación `required` | **12** |
| Clasificación `optional` | **6** |
| Ya existen en 4.0 | **16** |
| Faltan en 4.0 (filing fields) | **8** |
| Faltan en 4.0 (market data) | **2** |

---

## 2. Tabla resumen (ordenada por clasificación)

### 2.1 Critical (8 campos)

| # | Campo 3.0 | 4.0 canónico | Fuente | Gates impactados | Métricas impactadas |
|---|-----------|-------------|--------|-------------------|---------------------|
| 1 | `ingresos_usd` | `ingresos` ✅ | ambos | UNIDADES_SANITY, TTM_SANITY, DATA_COMPLETENESS, CORE_FILING_COVERAGE | TTM, márgenes (gross/operating/net/FCF), FY0 eligibility (mandatory) |
| 2 | `activos_totales_usd` | `total_assets` ✅ | ambos | BALANCE_IDENTITY (critical), DATA_COMPLETENESS | ROA, reconciliation threshold |
| 3 | `pasivos_totales_usd` | `total_liabilities` ✅ | ambos | BALANCE_IDENTITY (critical), DATA_COMPLETENESS | (balance identity) |
| 4 | `patrimonio_usd` | `total_equity` ✅ | ambos | BALANCE_IDENTITY (critical), DATA_COMPLETENESS | ROE, BV/share, invested capital |
| 5 | `cfo_usd` | `cfo` ✅ | ambos | CASHFLOW_IDENTITY (critical), UNIDADES_SANITY, DATA_COMPLETENESS | FCF, FCF margin, FCF yield, FCF/share, TTM |
| 6 | `cfi_usd` | ❌ **MISSING** | ambos | CASHFLOW_IDENTITY (critical) | TTM semestral |
| 7 | `cff_usd` | ❌ **MISSING** | ambos | CASHFLOW_IDENTITY (critical) | TTM semestral |
| 8 | `delta_cash_usd` | ❌ **MISSING** | ambos | CASHFLOW_IDENTITY (critical, SKIP→FAIL) | TTM semestral |

### 2.2 Required (12 campos)

| # | Campo 3.0 | 4.0 canónico | Fuente | Gates impactados | Métricas impactadas |
|---|-----------|-------------|--------|-------------------|---------------------|
| 9 | `ebit_usd` | `ebit` ✅ | ambos | UNIDADES_SANITY, DATA_COMPLETENESS | Operating margin, ROIC, EV/EBIT, TTM |
| 10 | `net_income_usd` | `net_income` ✅ | ambos | UNIDADES_SANITY, DATA_COMPLETENESS | Net margin, ROE, ROA, EPS, TTM |
| 11 | `capex_usd` | `capex` ✅ | calculator | DATA_COMPLETENESS | FCF (=CFO−\|capex\|), FCF margin, FCF/share |
| 12 | `cogs_usd` | `cost_of_revenue` ✅ | calculator | DATA_COMPLETENESS | Gross margin (alternativa a gross_profit), FY0 key field |
| 13 | `gross_profit_usd` | `gross_profit` ✅ | calculator | — | Gross margin (alternativa a cogs) |
| 14 | `deuda_total_usd` | `total_debt` ✅ | calculator | DATA_COMPLETENESS | EV, net debt, invested capital (ROIC) |
| 15 | `caja_usd` | `cash_and_equivalents` ✅ | calculator | DATA_COMPLETENESS | EV, net debt |
| 16 | `depreciation_usd` | `depreciation_amortization` ✅ | ambos | DATA_COMPLETENESS | TTM semestral |
| 17 | `income_tax_usd` | `income_tax` ✅ | ambos | DATA_COMPLETENESS | TTM semestral |
| 18 | `interest_expense_usd` | `interest_expense` ✅ | calculator | — | TTM semestral |
| 19 | `market_cap_usd` | ❌ **MISSING** (market data) | calculator | — | EV, P/FCF, FCF yield |
| 20 | `shares_outstanding` | `shares_outstanding` ✅ | calculator | — | EPS, FCF/share, BV/share |

### 2.3 Optional (6 campos)

| # | Campo 3.0 | 4.0 canónico | Fuente | Gates impactados | Métricas impactadas |
|---|-----------|-------------|--------|-------------------|---------------------|
| 21 | `fx_effect_cash_usd` | ❌ **MISSING** | ambos | CASHFLOW_IDENTITY (mejora precisión, default=0) | TTM semestral |
| 22 | `otros_ajustes_caja_usd` | ❌ **MISSING** | validator | CASHFLOW_IDENTITY (mejora precisión, default=0) | — |
| 23 | `cuentas_por_cobrar_usd` | ❌ **MISSING** | calculator | — | Working capital |
| 24 | `inventarios_usd` | ❌ **MISSING** | calculator | — | Working capital |
| 25 | `cuentas_por_pagar_usd` | ❌ **MISSING** | calculator | — | Working capital |
| 26 | `price` | ❌ **MISSING** (market data) | calculator | — | Market data enrichment |

---

## 3. Detalle por campo

### 3.1 `ingresos_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: `ingresos` ✅
- **Aliases 3.0**: `ingresos_usd`
- **source_file**: ambos (validator + calculator)
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 37, 56, 63, 67, 70, 72) — campo esperado en TODOS los doc types
  - `_gate_unidades_sanity` (línea 376) — detecta saltos 1000x entre periodos
  - `_gate_ttm_sanity` (líneas 440-441) — compara TTM vs FY0 revenue
  - `_compute_completitud_ajustada` (líneas 635-645) — completeness check
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 28) — campo obligatorio para eligibilidad FY0
  - `_find_eligible_fy0` (línea 58) — **mandatory**: sin ingresos numéricos, FY0 descartado
  - `calculate` (líneas 96, 103) — fuente para TTM o FY0
  - `_ttm` (línea 636) — sumado en TTM 4 trimestres
  - `_ttm_semestral` (línea 518) — sumado en TTM semestral
  - `_build_synthetic_q4_quarters` (línea 413) — sintetiza Q4
  - `_margins` (línea 740) — denominador de TODOS los márgenes
- **Gates impactados**: UNIDADES_SANITY (FAIL si 1000x jump), TTM_SANITY (SKIP sin revenue), DATA_COMPLETENESS
- **Métricas impactadas**: TTM, margen bruto, margen operativo, margen neto, margen FCF, FCF yield (indirectamente)
- **Justificación**: Campo más referenciado en ambos ficheros. Obligatorio para FY0 eligibility — sin él, todo el cálculo de métricas derivadas colapsa a null.

### 3.2 `activos_totales_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: `total_assets` ✅
- **Aliases 3.0**: `activos_totales_usd`, `total_assets_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 49, 60, 67) — esperado en 10-K, 20-F, ANNUAL_REPORT
  - `_gate_balance_identity` (línea 211) — Assets = L + E con tolerancia ±2%
  - `_reconcile_cross_filing` (línea 680) — base para threshold de materialidad
- **Funciones — calculator**:
  - `calculate` → `_bs_val` (línea 130) — extrae de balance sheet
  - `_returns` (línea 780) — denominador de ROA
- **Gates impactados**: BALANCE_IDENTITY (critical=True, FAIL si falta), DATA_COMPLETENESS
- **Métricas impactadas**: ROA, reconciliation threshold
- **Justificación**: Pilar del gate BALANCE_IDENTITY. Si falta junto con otro componente, el gate es FAIL (sin posibilidad de imputación), lo que produce overall FAIL.

### 3.3 `pasivos_totales_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: `total_liabilities` ✅
- **Aliases 3.0**: `pasivos_totales_usd`, `total_liabilities_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 50, 61, 68) — esperado en 10-K, 20-F, ANNUAL_REPORT
  - `_gate_balance_identity` (línea 212) — componente de L+E
- **Funciones — calculator**:
  - `calculate` → `_bs_val` (línea 131) — extrae de balance sheet
- **Gates impactados**: BALANCE_IDENTITY (critical=True)
- **Métricas impactadas**: (indirectamente, balance identity)
- **Justificación**: Componente directo del gate BALANCE_IDENTITY. Si falta, el gate puede imputar (si assets y equity presentes) o FAIL.

### 3.4 `patrimonio_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: `total_equity` ✅
- **Aliases 3.0**: `patrimonio_usd`, `equity_usd`, `total_stockholders_equity`, `total_shareholders_equity`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 51, 62, 69) — esperado en 10-K, 20-F, ANNUAL_REPORT
  - `_gate_balance_identity` (línea 213) — componente de L+E
- **Funciones — calculator**:
  - `calculate` → `_bs_val` (línea 132) — extrae de balance sheet
  - `_returns` (línea 773) — denominador de ROE
  - `_per_share` (línea 809) — BV/share = equity/shares
  - `calculate` (línea 154) — invested_capital = debt + equity → ROIC
- **Gates impactados**: BALANCE_IDENTITY (critical=True)
- **Métricas impactadas**: ROE, BV/share, ROIC (vía invested capital)
- **Justificación**: Componente del gate BALANCE_IDENTITY y de 3 métricas de retorno. Su ausencia degrada severamente la validación y los retornos.

### 3.5 `cfo_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: `cfo` ✅
- **Aliases 3.0**: `cfo_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 40, 57, 65, 68) — en 10-K, 20-F, ANNUAL_REPORT, 10-Q
  - `_find_best_cf_entry` (línea 278) — requerido para CF bridge
  - `_gate_cashflow_identity` (línea 300) — componente del bridge CFO+CFI+CFF≈ΔCash
  - `_gate_unidades_sanity` (línea 376) — detecta saltos 1000x
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 28) — key field para eligibilidad FY0
  - `calculate` (líneas 96, 103) — fuente TTM/FY0
  - `_ttm` (línea 636) — sumado en TTM
  - `_ttm_semestral` (líneas 518, 535) — componente TTM semestral y min_field requerido
  - `_fcf` (línea 691) — FCF = CFO − |capex|
- **Gates impactados**: CASHFLOW_IDENTITY (critical=True, FAIL), UNIDADES_SANITY, DATA_COMPLETENESS
- **Métricas impactadas**: FCF, FCF margin, FCF yield, P/FCF, EV/FCF, FCF/share, TTM
- **Justificación**: Sin CFO, el gate CASHFLOW_IDENTITY es FAIL (overall FAIL) y FCF + 5 métricas derivadas son null.

### 3.6 `cfi_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `cfi` (cash from investing activities)
- **Aliases 3.0**: `cfi_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 40, 57, 65) — en 10-K, 20-F, ANNUAL_REPORT
  - `_find_best_cf_entry` (línea 279) — requerido para elegir FY con CF completo
  - `_gate_cashflow_identity` (línea 301) — componente del bridge
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519) — incluido en _TTM_FIELDS
- **Gates impactados**: CASHFLOW_IDENTITY (critical=True, FAIL)
- **Métricas impactadas**: TTM semestral
- **Justificación**: Componente directo del cash bridge. Sin él, CASHFLOW_IDENTITY FAIL → overall FAIL. **Necesario para 4.0.**

### 3.7 `cff_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `cff` (cash from financing activities)
- **Aliases 3.0**: `cff_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 40, 57, 65) — en 10-K, 20-F, ANNUAL_REPORT
  - `_find_best_cf_entry` (línea 280) — requerido para elegir FY con CF completo
  - `_gate_cashflow_identity` (línea 302) — componente del bridge
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519) — incluido en _TTM_FIELDS
- **Gates impactados**: CASHFLOW_IDENTITY (critical=True, FAIL)
- **Métricas impactadas**: TTM semestral
- **Justificación**: Componente directo del cash bridge. Sin él, CASHFLOW_IDENTITY FAIL → overall FAIL. **Necesario para 4.0.**

### 3.8 `delta_cash_usd` — CRITICAL

- **Clasificación**: `critical`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `delta_cash` (net change in cash and equivalents)
- **Aliases 3.0**: `delta_cash_usd`, `cambio_caja_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (línea 43) — en 10-K
  - `_gate_cashflow_identity` (línea 319) — denominador del cross-check
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519) — incluido en _TTM_FIELDS
- **Gates impactados**: CASHFLOW_IDENTITY (critical=True, SKIP→overall FAIL vía `_overall_status` línea 734)
- **Métricas impactadas**: TTM semestral
- **Justificación**: Sin delta_cash, CASHFLOW_IDENTITY retorna SKIP. Dado que es gate critical, SKIP provoca overall FAIL. **Necesario para 4.0.**

### 3.9 `ebit_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `ebit` ✅
- **Aliases 3.0**: `ebit_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 38, 56, 63) — en 10-K, 20-F, ANNUAL_REPORT
  - `_gate_unidades_sanity` (línea 376) — 1000x jump check
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 28) — key field
  - `calculate` (líneas 97, 105) — fuente TTM/FY0
  - `_ttm` (línea 636), `_ttm_semestral` (línea 518, 535)
  - `_margins` (línea 751) — operating margin
  - `_returns` (línea 767) — ROIC = EBIT×(1−tax)/IC
  - `_multiples` (línea 795) — EV/EBIT
- **Gates impactados**: UNIDADES_SANITY, DATA_COMPLETENESS
- **Métricas impactadas**: Operating margin, ROIC, EV/EBIT, TTM
- **Justificación**: Afecta 3 métricas derivadas clave. No provoca FAIL en gate critical, pero su ausencia deja ROIC, operating margin y EV/EBIT en null.

### 3.10 `net_income_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `net_income` ✅
- **Aliases 3.0**: `net_income_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 39, 57, 64, 68, 72) — en TODOS los doc types excepto TRANSCRIPT
  - `_gate_unidades_sanity` (línea 376)
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 28)
  - `calculate` (líneas 98, 106)
  - `_margins` (línea 752) — net margin
  - `_returns` (línea 773, 778) — ROE, ROA
  - `_per_share` (línea 806) — EPS
- **Gates impactados**: UNIDADES_SANITY, DATA_COMPLETENESS
- **Métricas impactadas**: Net margin, ROE, ROA, EPS, TTM
- **Justificación**: Afecta 4 métricas derivadas. Campo esperado en casi todos los doc types.

### 3.11 `capex_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `capex` ✅
- **Aliases 3.0**: `capex_usd`
- **source_file**: calculator (validador solo en EXPECTED_FIELDS)
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 41, 58) — en 10-K, 20-F
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 29)
  - `calculate` (líneas 100, 108)
  - `_fcf` (línea 691) — FCF = CFO − |capex|
  - `_ttm` (línea 636)
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: FCF, FCF margin, FCF yield, P/FCF, EV/FCF, FCF/share
- **Justificación**: Componente directo de FCF. Sin él, toda la cadena FCF→multiples→per_share se anula.

### 3.12 `cogs_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `cost_of_revenue` ✅
- **Aliases 3.0**: `cogs_usd`, `costo_ventas_usd`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_FY0_KEY_FIELDS` (línea 29)
  - `calculate` (líneas 117-118) — extraído de FY0
  - `_ttm` (línea 637)
  - `_margins` (línea 746) — gross margin (alternativa cuando gross_profit no disponible)
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: Gross margin (alternativa)
- **Justificación**: Respaldo para cálculo de gross margin cuando gross_profit no está disponible. FY0 key field.

### 3.13 `gross_profit_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `gross_profit` ✅
- **Aliases 3.0**: `gross_profit_usd`, `beneficio_bruto_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (línea 38) — en 10-K
- **Funciones — calculator**:
  - `calculate` (líneas 119-120) — preferido sobre cogs para gross margin
  - `_ttm` (línea 637)
  - `_margins` (línea 744) — gross margin = GP/revenue
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: Gross margin (preferido)
- **Justificación**: Vía preferida para gross margin. Alternativa: cogs. Uno de los dos es necesario.

### 3.14 `deuda_total_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `total_debt` ✅
- **Aliases 3.0**: `deuda_total_usd`, `total_debt`
- **source_file**: calculator
- **Funciones — calculator**:
  - `calculate` → `_bs_val` (línea 134) — de balance sheet o FY0
  - `_ev` (línea 704) — EV = market_cap + debt − cash
  - `calculate` (línea 154) — invested_capital = debt + equity
  - `calculate` (línea 160) — deuda_neta = debt − cash
- **Gates impactados**: —
- **Métricas impactadas**: EV, net debt, invested capital (ROIC), deuda_neta, EV/EBIT, EV/FCF
- **Justificación**: Componente de EV y net debt. Sin él, EV y todas las métricas basadas en EV son null.

### 3.15 `caja_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `cash_and_equivalents` ✅
- **Aliases 3.0**: `caja_usd`, `cash_usd`, `cash_and_cash_equivalents`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (líneas 52, 62, 69) — en 10-K, 20-F, ANNUAL_REPORT
- **Funciones — calculator**:
  - `calculate` → `_bs_val` (línea 136)
  - `_ev` (línea 704) — EV = market_cap + debt − cash
  - `calculate` (línea 160) — deuda_neta = debt − cash
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: EV, net debt
- **Justificación**: Componente de EV y net debt.

### 3.16 `depreciation_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `depreciation_amortization` ✅
- **Aliases 3.0**: `depreciation_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (línea 43) — en 10-K
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519) — incluido en _TTM_FIELDS
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: TTM semestral
- **Justificación**: Necesario para TTM semestral completo en empresas europeas.

### 3.17 `income_tax_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `income_tax` ✅
- **Aliases 3.0**: `income_tax_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `EXPECTED_FIELDS_BY_DOC_TYPE` (línea 44) — en 10-K
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519)
- **Gates impactados**: DATA_COMPLETENESS
- **Métricas impactadas**: TTM semestral
- **Justificación**: Similar a depreciation — completeness y TTM semestral.

### 3.18 `interest_expense_usd` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `interest_expense` ✅
- **Aliases 3.0**: `interest_expense_usd`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 518) — incluido en _TTM_FIELDS
- **Gates impactados**: —
- **Métricas impactadas**: TTM semestral
- **Justificación**: Necesario para TTM semestral completo.

### 3.19 `market_cap_usd` — REQUIRED (market data)

- **Clasificación**: `required`
- **4.0 canónico**: ❌ **NO EXISTE** (market data, no filing field)
- **Aliases 3.0**: `market_cap_usd`, `market_cap_millones` (×1M)
- **source_file**: calculator
- **Funciones — calculator**:
  - `_extract_market_data` (líneas 220-259) — de fuentes externas
  - `_ev` (línea 703) — EV = market_cap + debt − cash
  - `_multiples` (línea 797) — P/FCF = market_cap / FCF
  - `_safe_div` en calculate (línea 169) — FCF yield = FCF / market_cap
- **Gates impactados**: EV_SANITY (indirectamente, vía EV)
- **Métricas impactadas**: EV, P/FCF, FCF yield
- **Justificación**: Sin market_cap, EV y múltiplos de mercado son null. Dato de mercado, no extraíble de filings.

### 3.20 `shares_outstanding` — REQUIRED

- **Clasificación**: `required`
- **4.0 canónico**: `shares_outstanding` ✅
- **Aliases 3.0**: `shares_outstanding`, `shares_outstanding_millones`, `shs_outstand`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_extract_market_data` (líneas 246-248) — de fuentes externas
  - `_per_share` (líneas 806-809) — EPS, FCF/share, BV/share
- **Gates impactados**: —
- **Métricas impactadas**: EPS, FCF/share, BV/share
- **Justificación**: Denominador de todas las métricas per-share. Nota: en 3.0 viene de market data; en 4.0 se extrae de filings (weighted avg shares).

### 3.21 `fx_effect_cash_usd` — OPTIONAL

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `fx_effect_cash`
- **Aliases 3.0**: `fx_effect_cash_usd`
- **source_file**: ambos
- **Funciones — validator**:
  - `_gate_cashflow_identity` (línea 312) — sumado al bridge, **default=0 si None**
- **Funciones — calculator**:
  - `_ttm_semestral` (línea 519) — incluido en _TTM_FIELDS
- **Gates impactados**: CASHFLOW_IDENTITY (mejora precisión pero no bloquea — default 0)
- **Métricas impactadas**: TTM semestral
- **Justificación**: Mejora la precisión del cash bridge. Sin él, el bridge puede tener desviación moderada que produce WARNING (no FAIL). Tratado como 0.

### 3.22 `otros_ajustes_caja_usd` — OPTIONAL

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `other_cash_adjustments`
- **Aliases 3.0**: `otros_ajustes_caja_usd`
- **source_file**: validator
- **Funciones — validator**:
  - `_gate_cashflow_identity` (línea 313) — sumado al bridge, **default=0 si None**
- **Gates impactados**: CASHFLOW_IDENTITY (mejora precisión, default=0)
- **Métricas impactadas**: —
- **Justificación**: Ajustes menores del cash bridge. Tratado como 0 si ausente.

### 3.23 `cuentas_por_cobrar_usd` — OPTIONAL

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `accounts_receivable`
- **Aliases 3.0**: `cuentas_por_cobrar_usd`, `accounts_receivable_usd`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_working_capital` (línea 718) — componente de current assets
- **Gates impactados**: —
- **Métricas impactadas**: Working capital
- **Justificación**: Solo afecta working capital, que en 3.0 tiene impacto limitado (no alimenta ningún gate ni métrica derivada estándar).

### 3.24 `inventarios_usd` — OPTIONAL

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `inventories`
- **Aliases 3.0**: `inventarios_usd`, `inventories_usd`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_working_capital` (línea 719) — componente de current assets
- **Gates impactados**: —
- **Métricas impactadas**: Working capital
- **Justificación**: Solo afecta working capital.

### 3.25 `cuentas_por_pagar_usd` — OPTIONAL

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** — sugerido: `accounts_payable`
- **Aliases 3.0**: `cuentas_por_pagar_usd`, `accounts_payable_usd`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_working_capital` (línea 720) — componente de current liabilities
- **Gates impactados**: —
- **Métricas impactadas**: Working capital
- **Justificación**: Solo afecta working capital.

### 3.26 `price` — OPTIONAL (market data)

- **Clasificación**: `optional`
- **4.0 canónico**: ❌ **NO EXISTE** (market data)
- **Aliases 3.0**: `price`, `precio`, `precio_cierre`
- **source_file**: calculator
- **Funciones — calculator**:
  - `_extract_market_data` (líneas 240, 254)
  - `calculate` (línea 196) — inyectado en sección `mercado`
- **Gates impactados**: —
- **Métricas impactadas**: Enriquecimiento de mercado (no alimenta métricas derivadas directamente)
- **Justificación**: Dato informativo. No alimenta ningún cálculo ni gate. Pure enrichment.

---

## 4. Campos faltantes en 4.0 — Recomendación de expansión

### 4.1 Prioridad ALTA (Critical — necesarios para gates)

| Campo sugerido 4.0 | Campo 3.0 | Clasificación | Justificación |
|---------------------|-----------|---------------|---------------|
| `cfi` | `cfi_usd` | critical | Componente de CASHFLOW_IDENTITY. Sin él, gate critical FAIL. |
| `cff` | `cff_usd` | critical | Componente de CASHFLOW_IDENTITY. Sin él, gate critical FAIL. |
| `delta_cash` | `delta_cash_usd` | critical | Cross-check de CASHFLOW_IDENTITY. Sin él, gate critical SKIP→FAIL. |

### 4.2 Prioridad MEDIA (Required — degradan métricas)

| Campo sugerido 4.0 | Campo 3.0 | Clasificación | Justificación |
|---------------------|-----------|---------------|---------------|
| `market_cap` | `market_cap_usd` | required | Necesario para EV, P/FCF, FCF yield. Market data, no filing field. |

### 4.3 Prioridad BAJA (Optional — enriquecimiento)

| Campo sugerido 4.0 | Campo 3.0 | Clasificación | Justificación |
|---------------------|-----------|---------------|---------------|
| `fx_effect_cash` | `fx_effect_cash_usd` | optional | Mejora precisión de cash bridge. Default=0. |
| `other_cash_adjustments` | `otros_ajustes_caja_usd` | optional | Mejora precisión de cash bridge. Default=0. |
| `accounts_receivable` | `cuentas_por_cobrar_usd` | optional | Working capital. |
| `inventories` | `inventarios_usd` | optional | Working capital. |
| `accounts_payable` | `cuentas_por_pagar_usd` | optional | Working capital. |
| `price` | `price` | optional | Market data enrichment. |

### 4.4 Campos en 4.0 NO consumidos por 3.0

Los siguientes campos canónicos del 4.0 **no aparecen** en `tp_validator.py` ni `tp_calculator.py`:

| 4.0 canónico | Observación |
|--------------|-------------|
| `ebitda` | El calculator tiene `net_debt_ebitda: None` con comentario "EBITDA not always available". Concepto deseado pero no implementado. |
| `eps_basic` | El calculator **computa** EPS como `net_income/shares`. No lee `eps_basic` de filings. |
| `eps_diluted` | Ídem. No leído de filings. |
| `fcf` | El calculator **computa** FCF como `CFO−|capex|`. El 4.0 lo extrae directamente de filings cuando disponible. |
| `dividends_per_share` | No consumido por ninguno de los dos ficheros. |
| `research_and_development` | No consumido. |
| `sga` | No consumido. |

---

## 5. Notas metodológicas

1. **Clasificación criteria**:
   - `critical` = campo cuya ausencia produce `FAIL` o `SKIP` en un gate con `critical: True` en la config de GATES, lo que resulta en `overall_status: "FAIL"`.
   - `required` = campo cuya ausencia produce `null` en métricas derivadas clave (TTM, FCF, márgenes, retornos, multiples) o `WARNING` en gates no-critical.
   - `optional` = campo cuya ausencia solo afecta enriquecimiento no-bloqueante (working capital, bridge precision con default=0).

2. **Aliases**: Muchos campos tienen múltiples aliases en el 3.0 (`patrimonio_usd`/`equity_usd`, `caja_usd`/`cash_usd`/`cash_and_cash_equivalents`). El 4.0 ya normaliza esto vía `field_aliases.json`.

3. **Market data vs Filing data**: `market_cap_usd`, `shares_outstanding`, y `price` provienen de fuentes de mercado externas en el 3.0, no de filings SEC. El 4.0 extrae `shares_outstanding` de filings (weighted avg). Los otros dos son inherentemente datos de mercado.

4. **Campos computados vs extraídos**: El 3.0 **computa** FCF y EPS internamente; el 4.0 los **extrae** de filings cuando están disponibles. Esto es una diferencia de diseño, no un gap.
