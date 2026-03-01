"""Multi-filing, multi-source merge with priority and confidence. Stub."""

from __future__ import annotations

from elsian.models.field import FieldCandidate, FieldResult


def merge_candidates(candidates: list[FieldCandidate]) -> dict[str, dict[str, FieldResult]]:
    """Merge candidates into final results. Stub: picks first per (period, field)."""
    result: dict[str, dict[str, FieldResult]] = {}
    for c in candidates:
        if c.period not in result:
            result[c.period] = {}
        if c.canonical_name not in result[c.period]:
            result[c.period][c.canonical_name] = FieldResult(
                value=c.value,
                provenance=c.provenance,
                scale=c.scale,
                confidence=c.confidence,
            )
    return result
