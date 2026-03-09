#!/usr/bin/env python3
"""BL-076: Retroportar cfi, cff, delta_cash, accounts_receivable, accounts_payable,
inventories y total_debt a los expected.json existentes desde los drafts de curate.

No-destructivo: solo añade campos ausentes en expected. Nunca sobreescribe.
Idempotente: una segunda ejecucion sin cambios intermedios no produce modificaciones.

Uso:
    # Dry-run (sin escribir):
    python3 scripts/backfill_bl076_fields.py --dry-run

    # Aplicar sobre todos los casos:
    python3 scripts/backfill_bl076_fields.py

    # Aplicar sobre tickers concretos:
    python3 scripts/backfill_bl076_fields.py TZOO ACLS

Prerequisito: los expected_draft.json deben existir en cada caso.
    Generarlos con: python3 -m elsian curate <TICKER>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Siete campos autorizados por BL-076.
TARGET_FIELDS: frozenset[str] = frozenset({
    "cfi",
    "cff",
    "delta_cash",
    "accounts_receivable",
    "accounts_payable",
    "inventories",
    "total_debt",
})

# Fuentes del draft que se consideran filing-backed.
_FILING_BACKED_SOURCES: frozenset[str] = frozenset({"ixbrl", "pipeline"})


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_source_filing(field_data: dict[str, Any]) -> str | None:
    """Devuelve source_filing si el campo es filing-backed, None si es derivado.

    - ixbrl: usa la clave _filing.
    - pipeline: usa la clave source_filing.
    - derived u otro: retorna None (no es filing-backed).
    """
    src = field_data.get("_source", "")
    if src == "ixbrl":
        return field_data.get("_filing") or None
    if src == "pipeline":
        return field_data.get("source_filing") or None
    return None


def backfill_ticker(
    ticker: str,
    cases_dir: Path,
    *,
    apply: bool,
) -> dict[str, Any]:
    """Backfill no-destructivo de TARGET_FIELDS para un ticker.

    Args:
        ticker: Identificador del caso.
        cases_dir: Path al directorio raiz de casos.
        apply: Si True, escribe los cambios. Si False, modo dry-run.

    Returns:
        Diccionario con resumen de operaciones.
    """
    expected_path = cases_dir / ticker / "expected.json"
    draft_path = cases_dir / ticker / "expected_draft.json"

    result: dict[str, Any] = {
        "ticker": ticker,
        "apply": apply,
        "fields_added": 0,
        "fields_skipped_exists": 0,
        "fields_skipped_no_draft_period": 0,
        "fields_skipped_no_draft_field": 0,
        "fields_skipped_not_filing_backed": 0,
        "periods_with_additions": [],
        "gaps": [],
    }

    if not expected_path.exists():
        result["error"] = "expected.json not found"
        return result

    if not draft_path.exists():
        result["error"] = (
            f"expected_draft.json not found; run: python3 -m elsian curate {ticker}"
        )
        return result

    expected = _load_json(expected_path)
    draft = _load_json(draft_path)

    draft_periods: dict[str, Any] = draft.get("periods", {})
    expected_periods: dict[str, Any] = expected.get("periods", {})

    modified = False

    for period_key, exp_payload in expected_periods.items():
        exp_fields: dict[str, Any] = exp_payload.setdefault("fields", {})
        draft_payload = draft_periods.get(period_key)

        if draft_payload is None:
            # Periodo en expected no presente en draft: todos los campos son gap.
            result["fields_skipped_no_draft_period"] += len(TARGET_FIELDS)
            for field_name in sorted(TARGET_FIELDS):
                if field_name not in exp_fields:
                    result["gaps"].append(
                        {"ticker": ticker, "period": period_key, "field": field_name, "reason": "no_draft_period"}
                    )
            continue

        draft_fields: dict[str, Any] = draft_payload.get("fields", {})
        period_added: list[str] = []

        for field_name in sorted(TARGET_FIELDS):
            if field_name in exp_fields:
                result["fields_skipped_exists"] += 1
                continue

            if field_name not in draft_fields:
                result["fields_skipped_no_draft_field"] += 1
                result["gaps"].append(
                    {"ticker": ticker, "period": period_key, "field": field_name, "reason": "not_in_draft"}
                )
                continue

            draft_field = draft_fields[field_name]
            source_filing = _extract_source_filing(draft_field)

            if source_filing is None:
                result["fields_skipped_not_filing_backed"] += 1
                result["gaps"].append(
                    {
                        "ticker": ticker,
                        "period": period_key,
                        "field": field_name,
                        "reason": "not_filing_backed",
                        "draft_source": draft_field.get("_source", "unknown"),
                    }
                )
                continue

            # Campo elegible: añadir.
            result["fields_added"] += 1
            period_added.append(field_name)

            if apply:
                exp_fields[field_name] = {
                    "value": draft_field["value"],
                    "source_filing": source_filing,
                }
                modified = True

        if period_added:
            result["periods_with_additions"].append(
                {"period": period_key, "fields": period_added}
            )

    if modified:
        expected_path.write_text(
            json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return result


def backfill_all(
    cases_dir: Path,
    *,
    tickers: list[str] | None = None,
    apply: bool,
) -> dict[str, Any]:
    """Backfill no-destructivo para todos los casos con expected.json.

    Args:
        cases_dir: Path al directorio raiz de casos.
        tickers: Lista de tickers a procesar. Si None, procesa todos.
        apply: Si True, escribe los cambios.

    Returns:
        Resumen agregado con resultados por ticker.
    """
    if tickers is None:
        tickers = sorted(
            t.name
            for t in cases_dir.iterdir()
            if t.is_dir() and (t / "expected.json").exists()
        )

    total_added = 0
    modified_files: list[str] = []
    all_gaps: list[dict[str, Any]] = []
    per_ticker: list[dict[str, Any]] = []

    for ticker in tickers:
        r = backfill_ticker(ticker, cases_dir, apply=apply)
        per_ticker.append(r)
        total_added += r["fields_added"]
        all_gaps.extend(r.get("gaps", []))
        if r["fields_added"] > 0 and apply:
            modified_files.append(f"cases/{ticker}/expected.json")

    return {
        "cases_dir": str(cases_dir),
        "apply": apply,
        "target_fields": sorted(TARGET_FIELDS),
        "total_fields_added": total_added,
        "modified_files": modified_files,
        "total_gaps": len(all_gaps),
        "results": per_ticker,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Tickers a procesar (por defecto: todos con expected.json).",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("cases"),
        help="Directorio raiz de casos (por defecto: cases/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Reporta campos elegibles sin modificar ficheros.",
    )
    args = parser.parse_args()

    tickers: list[str] | None = args.tickers if args.tickers else None
    result = backfill_all(
        args.cases_dir,
        tickers=tickers,
        apply=not args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
