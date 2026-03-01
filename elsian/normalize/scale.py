"""ScaleCascade -- DT-1 5-level scale inference."""

from __future__ import annotations

import logging
import re

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
