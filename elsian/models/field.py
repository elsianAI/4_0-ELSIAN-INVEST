"""Data models for extracted financial fields with provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Provenance:
    """Tracks exactly where a value was found in the original filing.

    Level 1: source_filing only.
    Level 2: + table coordinates (table_index, row, col, labels).
    Level 3: + original document position (future: bounding box for PDF).
    """

    source_filing: str = ""
    source_location: str = ""
    table_index: int | None = None
    table_title: str = ""
    row_label: str = ""
    col_label: str = ""
    row: int | None = None
    col: int | None = None
    raw_text: str = ""
    # Preflight metadata (optional — populated when preflight analysis runs)
    preflight_currency: str = ""
    preflight_standard: str = ""
    preflight_units_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"source_filing": self.source_filing}
        if self.source_location:
            d["source_location"] = self.source_location
        if self.table_index is not None:
            d["table_index"] = self.table_index
        if self.table_title:
            d["table_title"] = self.table_title
        if self.row_label:
            d["row_label"] = self.row_label
        if self.col_label:
            d["col_label"] = self.col_label
        if self.row is not None:
            d["row"] = self.row
        if self.col is not None:
            d["col"] = self.col
        if self.raw_text:
            d["raw_text"] = self.raw_text
        if self.preflight_currency:
            d["preflight_currency"] = self.preflight_currency
        if self.preflight_standard:
            d["preflight_standard"] = self.preflight_standard
        if self.preflight_units_hint:
            d["preflight_units_hint"] = self.preflight_units_hint
        return d


@dataclass
class FieldCandidate:
    """A candidate extracted value before normalization and merge.

    Multiple candidates may exist for the same (period, field) pair.
    The merge phase picks the winner based on priority rules.
    """

    canonical_name: str
    value: float
    period: str
    provenance: Provenance = field(default_factory=Provenance)
    scale: str = "raw"
    confidence: str = "high"
    source_type: str = "table"
    section: str = ""
    filing_type: str = ""


@dataclass
class FieldResult:
    """A finalized extracted financial field (post-merge winner)."""

    value: float
    provenance: Provenance = field(default_factory=Provenance)
    scale: str = "raw"
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "value": self.value,
            "scale": self.scale,
            "confidence": self.confidence,
        }
        d.update(self.provenance.to_dict())
        return d
