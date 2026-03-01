"""ScaleCascade -- DT-1 5-level scale inference.

Includes both the class-based API and the function API used by the
extraction phase (ported from 3.0 deterministic/src/normalize/scale.py).
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

SCALE_FACTORS: dict[str, float] = {
    "raw": 1.0,
    "thousands": 1_000.0,
    "millions": 1_000_000.0,
    "billions": 1_000_000_000.0,
}

_SCALE_PATTERNS: list[tuple[str, str]] = [
    (r"in\s+billions", "billions"),
    (r"\$\s*B\b", "billions"),
    (r"in\s+millions", "millions"),
    (r"\$\s*M\b", "millions"),
    (r"in\s+thousands", "thousands"),
    (r"\$\s*K\b", "thousands"),
    (r"en\s+milliers", "thousands"),
    (r"en\s+millions", "millions"),
    (r"en\s+milliards", "billions"),
]


def detect_scale_from_text(text: str) -> str | None:
    """Detect scale from a text snippet."""
    for pattern, scale in _SCALE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return scale
    return None


# ── Function API (used by extraction phase) ──────────────────────────

def infer_scale_cascade(
    raw_notes_scale: str,
    header_scale: str,
    preflight_scale: str,
    field_multiplier: Optional[float],
) -> Tuple[str, str]:
    """DT-1 scale inference cascade.

    Priority:
    1. raw_notes (explicit "in millions" in the filing text)
    2. header (from filing section header)
    3. preflight (from detect.py analysis)
    4. field_multiplier (from aliases config)
    5. "raw" with uncertainty

    Returns (scale, confidence).
    """
    if raw_notes_scale and raw_notes_scale != "raw":
        return raw_notes_scale, "high"
    if header_scale and header_scale != "raw":
        return header_scale, "high"
    if preflight_scale and preflight_scale != "raw":
        return preflight_scale, "medium"
    if field_multiplier is not None:
        if field_multiplier == 1000.0:
            return "billions", "low"
        elif field_multiplier == 1.0:
            return "millions", "low"
        elif field_multiplier == 0.001:
            return "thousands", "low"
    return "raw", "low"


def validate_scale_sanity(
    value: float, field_name: str, scale: str
) -> bool:
    """Check if a value+scale combination is plausible.

    Used to catch obvious scale errors (e.g. revenue of $0.0001 millions).
    """
    if scale == "raw":
        return True

    abs_val = abs(value)

    large_fields = {
        "ingresos",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "cfo",
    }
    if field_name in large_fields and scale == "millions":
        if abs_val > 0 and abs_val < 0.01:
            return False

    eps_fields = {"eps_basic", "eps_diluted", "dividends_per_share"}
    if field_name in eps_fields:
        if abs_val > 10000:
            return False

    return True


class ScaleCascade:
    """DT-1 Scale Cascade: 5-level priority for scale inference."""

    def infer(
        self,
        raw_notes: str = "",
        header: str = "",
        preflight_scale: str = "",
        field_multiplier: float | None = None,
    ) -> tuple[str, str]:
        """Infer scale and confidence. Returns (scale, confidence)."""
        if raw_notes:
            detected = detect_scale_from_text(raw_notes)
            if detected:
                return detected, "high"
        if header:
            detected = detect_scale_from_text(header)
            if detected:
                return detected, "high"
        if preflight_scale and preflight_scale in SCALE_FACTORS:
            return preflight_scale, "medium"
        if field_multiplier is not None:
            for name, factor in SCALE_FACTORS.items():
                if abs(field_multiplier - factor) < 0.01:
                    return name, "medium"
        return "raw", "low"
