"""Data models for pipeline results and evaluation reports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal

from elsian.models.field import FieldResult

# Explicit severity levels for PhaseResult.
# fatal  — pipeline must stop; the phase could not produce usable output.
# error  — non-blocking problem worth recording; pipeline continues.
# warning — informational degradation; pipeline continues.
# ok     — normal completion.
Severity = Literal["ok", "warning", "error", "fatal"]


@dataclass
class AcquisitionResult:
    """Result of the acquire phase."""

    ticker: str = ""
    source: str = ""
    cik: str | None = None
    filings_downloaded: int = 0
    filings_failed: int = 0
    filings_coverage_pct: float = 0.0
    coverage: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    notes: str = ""
    download_date: str = field(
        default_factory=lambda: dt.date.today().isoformat()
    )
    # ── Reliability / observability fields (BL-066) ────────────────────
    source_kind: str = ""        # e.g. "filing", "transcript", "market_data"
    cache_hit: bool = False      # True when filings loaded from local cache
    retries_total: int = 0       # Total HTTP retries across all requests
    throttle_ms: float = 0.0    # Approximate total throttle wait in ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "source": self.source,
            "cik": self.cik,
            "filings_downloaded": self.filings_downloaded,
            "filings_failed": self.filings_failed,
            "filings_coverage_pct": self.filings_coverage_pct,
            "coverage": self.coverage,
            "gaps": self.gaps,
            "notes": self.notes,
            "download_date": self.download_date,
            "source_kind": self.source_kind,
            "cache_hit": self.cache_hit,
            "retries_total": self.retries_total,
            "throttle_ms": self.throttle_ms,
        }


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
    """Result of a single pipeline phase execution.

    ``severity`` is the authoritative signal used by Pipeline to decide
    whether to continue or stop.  ``success`` is kept for backward
    compatibility only; new code should use ``severity`` and ``is_fatal``.

    Backward-compat rule: constructing ``PhaseResult(success=False)`` with
    no explicit severity automatically promotes severity to ``'fatal'``.

    ``duration_ms`` is set by Pipeline after ``phase.run()`` returns; it is
    0.0 until then.
    """

    phase_name: str = ""
    success: bool = True
    message: str = ""
    data: Any = None
    severity: Severity = "ok"
    diagnostics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0  # filled by Pipeline orchestrator after run()

    def __post_init__(self) -> None:
        # Backward compat: success=False without explicit severity → fatal.
        if not self.success and self.severity == "ok":
            self.severity = "fatal"

    @property
    def is_fatal(self) -> bool:
        """True only when this result must halt the pipeline."""
        return self.severity == "fatal"


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
    # Readiness v1 fields (BL-064) — complementary to legacy score
    readiness_score: float = 0.0
    validator_confidence_score: float = 0.0
    provenance_coverage_pct: float = 0.0
    extra_penalty: float = 0.0

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
            "readiness_score": round(self.readiness_score, 2),
            "validator_confidence_score": round(self.validator_confidence_score, 2),
            "provenance_coverage_pct": round(self.provenance_coverage_pct, 2),
            "extra_penalty": round(self.extra_penalty, 2),
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
