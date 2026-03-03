"""Validate expected.json files for structural consistency and quality.

Rules (errors — problems that indicate data corruption):
  1. ``version`` must exist in root.
  2. ``ticker`` must exist in root.
  3. ``periods`` must be a non-empty dict.
  4. Every period must have ``fields`` as a non-empty dict.
  5. Every field must have ``value`` (may be 0 but not None or absent).
  6. Every field must have a non-empty ``source_filing``.
  7. If ``restatement`` is present it must contain all required sub-fields:
     applied, trigger, evidence_filing, evidence_text,
     original_source_filing, original_value.
  8. In a restatement ``original_source_filing`` must differ from the
     field's ``source_filing``.

Sanity warnings (informational — do not count as errors):
  W1. ``ingresos`` (revenue) should be > 0 for every period.
  W2. ``total_assets ≈ total_liabilities + total_equity`` within ±2%.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RESTATEMENT_REQUIRED_FIELDS = [
    "applied",
    "trigger",
    "evidence_filing",
    "evidence_text",
    "original_source_filing",
    "original_value",
]


def validate_expected(expected_path: str) -> list[str]:
    """Validate an expected.json file.

    Args:
        expected_path: Path (absolute or relative) to the expected.json file.

    Returns:
        List of error/warning messages.  Empty list means the file is valid.
        Warnings are prefixed with ``[WARNING]``, errors are not.
    """
    path = Path(expected_path)
    if not path.exists():
        return [f"File not found: {expected_path}"]

    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    errors: list[str] = []

    # --- Rule 1: version required ---
    if "version" not in data:
        errors.append("Root: missing 'version'")

    # --- Rule 2: ticker required ---
    if "ticker" not in data:
        errors.append("Root: missing 'ticker'")

    # --- Rule 3: periods must be a non-empty dict ---
    periods: dict[str, Any] = data.get("periods", {})
    if not isinstance(periods, dict) or not periods:
        errors.append("Root: 'periods' must be a non-empty dict")
        return errors  # cannot validate further

    for period_key, period_data in periods.items():
        # --- Rule 4: each period must have ``fields`` as non-empty dict ---
        fields = period_data.get("fields") if isinstance(period_data, dict) else None
        if not isinstance(fields, dict) or not fields:
            errors.append(f"{period_key}: 'fields' must be a non-empty dict")
            continue

        # Collect values for sanity checks
        field_vals: dict[str, float | None] = {}

        for field_name, field_info in fields.items():
            loc = f"{period_key}/{field_name}"

            if not isinstance(field_info, dict):
                errors.append(f"{loc}: field must be a dict")
                continue

            # --- Rule 5: value required (may be 0) ---
            if "value" not in field_info or field_info["value"] is None:
                errors.append(f"{loc}: missing or null 'value'")
            else:
                field_vals[field_name] = field_info["value"]

            # --- Rule 6: source_filing required ---
            if "source_filing" not in field_info or not field_info["source_filing"]:
                errors.append(f"{loc}: missing 'source_filing'")

            # --- Rule 7: restatement completeness ---
            restatement = field_info.get("restatement")
            if restatement is not None:
                if not isinstance(restatement, dict):
                    errors.append(f"{loc}: 'restatement' must be a dict")
                else:
                    for req in _RESTATEMENT_REQUIRED_FIELDS:
                        if req not in restatement:
                            errors.append(f"{loc}: restatement missing '{req}'")

                    # --- Rule 8: original_source_filing ≠ source_filing ---
                    orig = restatement.get("original_source_filing", "")
                    src = field_info.get("source_filing", "")
                    if orig and src and orig == src:
                        errors.append(
                            f"{loc}: restatement 'original_source_filing' "
                            f"should differ from 'source_filing' (both are '{src}')"
                        )

        # --- Sanity W1: revenue > 0 ---
        ingresos = field_vals.get("ingresos")
        if ingresos is not None and ingresos <= 0:
            errors.append(
                f"[WARNING] {period_key}: ingresos={ingresos} — expected > 0"
            )

        # --- Sanity W2: total_assets ≈ total_liabilities + total_equity ---
        ta = field_vals.get("total_assets")
        tl = field_vals.get("total_liabilities")
        te = field_vals.get("total_equity")
        if ta is not None and tl is not None and te is not None:
            expected_sum = tl + te
            if expected_sum != 0:
                pct_diff = abs(ta - expected_sum) / abs(expected_sum) * 100
                if pct_diff > 2.0:
                    errors.append(
                        f"[WARNING] {period_key}: total_assets ({ta}) != "
                        f"total_liabilities ({tl}) + total_equity ({te}) "
                        f"[diff={pct_diff:.1f}%]"
                    )

    return errors


def validate_all_cases(cases_dir: str) -> dict[str, list[str]]:
    """Validate all expected.json files under *cases_dir*.

    Args:
        cases_dir: Path to the ``cases/`` directory.

    Returns:
        Dict mapping ticker → list of issues.  Only tickers with issues
        are included; a ticker absent from the result means it is clean.
    """
    cases_path = Path(cases_dir)
    results: dict[str, list[str]] = {}

    if not cases_path.exists():
        return results

    for case_subdir in sorted(cases_path.iterdir()):
        if not case_subdir.is_dir():
            continue
        expected_file = case_subdir / "expected.json"
        if not expected_file.exists():
            continue
        ticker = case_subdir.name
        issues = validate_expected(str(expected_file))
        if issues:
            results[ticker] = issues

    return results
