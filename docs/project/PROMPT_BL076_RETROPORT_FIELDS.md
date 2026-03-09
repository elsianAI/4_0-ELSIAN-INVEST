# Prompt: BL-076 — Retroportar campos faltantes a expected.json

> **Instrucción:** Este prompt define la ejecución de BL-076. Genera un solo commit al finalizar. Ruta: director → gates → auditor → closeout → auto-commit.

---

## Contexto

BL-035 y BL-058 añadieron campos canónicos al pipeline de extracción, pero nunca se propagaron a los `expected.json` existentes. Además, `total_debt` es canónico desde el inicio pero tiene cobertura muy desigual (solo 7/16 tickers). El resultado es que la auditoría reportó cientos de `MISSING_EXPECTED` que son campos que el pipeline sabe extraer pero que la verdad curada no incluye.

BL-076 ya está en BACKLOG.md (línea 187), estado TODO, prioridad ALTA, validation tier targeted.

---

## Campos objetivo

| Campo | Origen | Periodos faltantes (aprox.) |
|---|---|---|
| `cfi` | BL-035 (oleada 1 CF) | ~200 (16/16 tickers afectados) |
| `cff` | BL-035 (oleada 1 CF) | ~200 (16/16 tickers afectados) |
| `delta_cash` | BL-035 (oleada 1 CF) | ~220 (16/16 tickers afectados) |
| `accounts_receivable` | BL-058 (oleada 2 WC) | ~210 (16/16 tickers afectados) |
| `accounts_payable` | BL-058 (oleada 2 WC) | ~210 (16/16 tickers afectados) |
| `inventories` | BL-058 (oleada 2 WC) | ~190 (16/16, pero solo donde inventory-bearing) |
| `total_debt` | canónico original | ~170 (8 tickers con 0 periodos: ACLS, GCT, INMD, IOSP, SOM, SONO, TALO, TZOO; parcial en otros) |

**Estado actual detallado por ticker:**

```
0327     ( 6 per): cfi=6/6, cff=6/6, delta_cash=6/6, AR=3/6, AP=3/6, inv=3/6, debt=3/6
ACLS     (21 per): TODOS los 7 campos faltan en 21/21 periodos
ADTN     (23 per): cfi=10/23, cff=10/23, delta_cash=23/23, AR=4/23, AP=4/23, inv=4/23, debt=22/23
CROX     (18 per): TODOS los 7 campos faltan en 12-18/18 periodos
GCT      (15 per): TODOS los 7 campos faltan en 15/15 periodos
INMD     (12 per): TODOS los 7 campos faltan en 12/12 periodos
IOSP     (22 per): TODOS los 7 campos faltan en 22/22 periodos
KAR      ( 3 per): 6 campos faltan en 3/3 (total_debt ya presente)
NEXN     (10 per): TODOS los 7 campos faltan en 6-10/10 periodos
NVDA     (18 per): 6 campos faltan en 12/18 (total_debt ya presente)
PR       ( 9 per): 6 campos faltan en 9/9 (total_debt ya presente)
SOM      (16 per): TODOS los 7 campos faltan en 14-16/16 periodos
SONO     (18 per): TODOS los 7 campos faltan en 16-18/18 periodos
TALO     (12 per): TODOS los 7 campos faltan en 12/12 periodos
TEP      ( 8 per): TODOS los 7 campos faltan en 4-8/8 periodos
TZOO     (18 per): TODOS los 7 campos faltan en 12-18/18 periodos
```

---

## Qué hacer

### Paso 1: Crear script determinista `scripts/backfill_expected_fields.py`

El script debe:

1. Para cada `cases/*/expected.json`:
   a. Ejecutar `python3 -m elsian curate <TICKER>` para regenerar el draft actualizado.
   b. Leer el draft generado.
   c. Para cada periodo del expected.json, para cada campo objetivo (`cfi`, `cff`, `delta_cash`, `accounts_receivable`, `accounts_payable`, `inventories`, `total_debt`):
      - Si el campo **NO existe** en el expected.json actual Y **SÍ existe** en el draft → copiarlo al expected.json con su `source_filing` del draft.
      - Si el campo **YA existe** en el expected.json → NO tocarlo.
      - Si el campo **NO existe** en el draft → documentar como gap (no fabricar valores).
2. El script debe ser **idempotente**: ejecutar dos veces produce el mismo resultado.
3. NO sobrescribir campos existentes bajo ninguna circunstancia.

### Paso 2: Casos especiales

- **`inventories`**: solo añadir donde la empresa sea inventory-bearing. Tickers que probablemente NO tienen inventories significativos: TZOO (travel), GCT (semiconductors fabless), INMD (medical devices — verificar). Si `curate` no genera inventories para un ticker, aceptar como gap justificado.
- **`total_debt`**: si una empresa genuinamente no tiene deuda financiera, documentar con justificación (e.g. "company is debt-free per balance sheet"). No fabricar `total_debt: 0` sin verificar.
- **`delta_cash`**: es `cash_t - cash_{t-1}`. Si el draft lo calcula, usarlo. Si no, puede derivarse de `cfo + cfi + cff` o de la diferencia de `cash_and_equivalents` entre periodos consecutivos. Documentar el método.
- **KAR y TEP** (PDF tickers): `curate` puede ser menos preciso con PDFs. Revisar los valores con más cuidado.

### Paso 3: Validación

- `python3 scripts/backfill_expected_fields.py` → ejecuta sin errores, es idempotente.
- `python3 -m elsian eval --all` → 16/16 PASS 100%. Si algún ticker baja, investigar antes de continuar.
- `python3 -m pytest -q` → verde.
- Verificar que el número total de campos validados sube significativamente (actualmente 4,109).

### Paso 4: Gobernanza

- Mover BL-076 de BACKLOG.md a BACKLOG_DONE.md.
- Actualizar PROJECT_STATE.md: nuevo total de campos validados, nota sobre retroportación completada.
- Actualizar CHANGELOG.md.
- Un solo commit.

---

## Write set

`scripts/backfill_expected_fields.py`, `tests/unit/test_backfill_expected_fields.py` (si se crea), `cases/*/expected.json` (los 16), `docs/project/BACKLOG.md`, `docs/project/BACKLOG_DONE.md`, `docs/project/PROJECT_STATE.md`, `CHANGELOG.md`.

## Dependencias

- BL-074 (DONE) — prerequisito ya cerrado.
- No bloquea ni depende de BL-082/081/083 (ya cerradas).
- BL-077 depende de BL-076 (investigar inconsistencias después de retroportar).

## Notas para el engineer

- El volumen es alto (~1,400 campos nuevos potenciales). El script debe ser robusto y generar un log de lo añadido vs lo que quedó como gap.
- Si `curate` tarda mucho en los 16 tickers, considerar paralelizar o cachear los drafts.
- Los campos de cash flow (`cfi`, `cff`, `delta_cash`) pueden tener signos invertidos según la convención del filing. Respetar la convención del draft sin corregir signos.
