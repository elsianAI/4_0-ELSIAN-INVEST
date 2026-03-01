"""Data models for pipeline results and evaluation reports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from elsian.models.field import FieldResult


@dataclass
class PeriodResult:
    """Extraction results for a single fiscal period."""

    fecha_fin: str = ""
    tipo_periodo: str = ""
    fields: dict[str, FieldResult] = field(default_factory=dict)


@dataclass
class AuditRecord:
    """Audit trail for extraction decisions."""

    fields_extracted: int = 0
    fields_discarded: int = 0
    discarded_reasons: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Full extraction result for a case."""

    schema_version: str = "2.0"
    ticker: str = ""
    currency: str = "USD"
    extraction_date: str = field(
        default_factory=lambda: dt.date.today().isoformat()
    )
    filings_used: int = 0
    periods: dict[str, PeriodResult] = field(default_factory=dict)
    audit: AuditRecord = field(default_factory=AuditRecord)

    def to_dict(self) -> dict[str, Any]:
        periods_dict: dict[str, Any] = {}
        for period_key, period in self.periods.items():
            fields_dict: dict[str, Any] = {}
            for fname, fr in period.fields.items():
                fields_dict[fname] = fr.to_dict()
            periods_dict[period_key] = {
                "fecha_fin": period.fecha_fin,
                "tipo_periodo": period.tipo_periodo,
                "fields": fields_dict,
            }
        return {
            "schema_version": self.schema_version,
            "ticker": self.ticker,
            "currency": self.currency,
            "extraction_date": self.extraction_date,
            "filings_used": self.filings_used,
            "periods": periods_dict,
            "audit": {
                "fields_extracted": self.audit.fields_extracted,
                "fields_discarded": self.audit.fields_discarded,
                "discarded_reasons": self.audit.discarded_reasons,
            },
        }


@dataclass
class PhaseResult:
    """Result of a single pipeline phase execution."""

    phase_name: str = ""
    success: bool = True
    message: str = ""
    data: Any = None


@dataclass
class EvalMatch:
    """A single field comparison result."""

    field_name: str
    period: str
    expected: float
    actual: float | None = None
    status: str = "missed"


@dataclass
class EvalReport:
    """Result of evaluating extraction against expected.json."""

    ticker: str = ""
    total_expected: int = 0
    matched: int = 0
    wrong: int = 0
    missed: int = 0
    extra: int = 0
    score: float = 0.0
    filings_coverage_pct: float = 0.0
    required_fields_coverage_pct: float = 0.0
    details: list[EvalMatch] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "total_expected": self.total_expected,
            "matched": self.matched,
            "wrong": self.wrong,
            "missed": self.missed,
            "extra": self.extra,
            "score": round(self.score, 4),
            "filings_coverage_pct": round(self.filings_coverage_pct, 2),
            "required_fields_coverage_pct": round(
                self.required_fields_coverage_pct, 2
            ),
        }


@dataclass
class DashboardRow:
    """A single row in the dashboard report."""

    ticker: str
    source: str
    filings: int
    periods: int
    expected: int
    matched: int
    score: float
