#!/usr/bin/env python3
"""Deterministically backfill ebitda/fcf into expected.json files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from elsian.expected_derived import (  # noqa: E402
    DERIVED_COMPONENTS,
    derive_field_value,
    is_period_excluded,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _field_summary() -> dict[str, dict[str, int]]:
    return {
        field_name: {
            "eligible_missing_before": 0,
            "skipped_inconsistent_before": 0,
            "existing_preserved_before": 0,
            "added": 0,
            "eligible_missing_after": 0,
        }
        for field_name in DERIVED_COMPONENTS
    }


def backfill_cases(cases_dir: Path, *, apply: bool) -> dict[str, Any]:
    summary = _field_summary()
    modified_files: list[str] = []

    for expected_path in sorted(cases_dir.glob("*/expected.json")):
        ticker = expected_path.parent.name
        data = _load_json(expected_path)
        periods = data.get("periods", {})
        modified = False

        for period_key, payload in periods.items():
            fields = payload.get("fields", {})
            for field_name in DERIVED_COMPONENTS:
                if field_name in fields:
                    summary[field_name]["existing_preserved_before"] += 1
                    continue

                derived_value = derive_field_value(field_name, fields)
                if derived_value is None:
                    continue

                if is_period_excluded(ticker, period_key, field_name):
                    summary[field_name]["skipped_inconsistent_before"] += 1
                    continue

                summary[field_name]["eligible_missing_before"] += 1
                if apply:
                    fields[field_name] = {
                        "value": derived_value,
                        "source_filing": "DERIVED",
                    }
                    summary[field_name]["added"] += 1
                    modified = True

        if modified:
            expected_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            modified_files.append(str(expected_path.relative_to(cases_dir.parent)))

    for field_name, counters in summary.items():
        counters["eligible_missing_after"] = (
            counters["eligible_missing_before"] - counters["added"]
        )

    return {
        "cases_dir": str(cases_dir),
        "apply": apply,
        "fields": summary,
        "modified_files": modified_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases-dir", type=Path, default=Path("cases"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible backfills without modifying files.",
    )
    args = parser.parse_args()

    result = backfill_cases(args.cases_dir, apply=not args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
