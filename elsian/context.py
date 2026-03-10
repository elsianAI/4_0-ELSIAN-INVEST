"""PipelineContext -- shared state through all pipeline phases."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from elsian.models.field import FieldCandidate
from elsian.models.filing import Filing
from elsian.models.case import CaseConfig
from elsian.models.result import ExtractionResult, AuditRecord, PhaseResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Carries data, provenance, audit log, and candidates through all phases."""

    case: CaseConfig = field(default_factory=CaseConfig)
    filings: list[Filing] = field(default_factory=list)
    candidates: list[FieldCandidate] = field(default_factory=list)
    result: ExtractionResult = field(default_factory=ExtractionResult)
    audit: AuditRecord = field(default_factory=AuditRecord)
    config_dir: str = ""
    errors: list[str] = field(default_factory=list)
    phase_results: list[PhaseResult] = field(default_factory=list)

    def add_candidates(self, new: list[FieldCandidate]) -> None:
        """Append new field candidates."""
        self.candidates.extend(new)
        logger.debug("Added %d candidates (total: %d)", len(new), len(self.candidates))

    def add_error(self, msg: str) -> None:
        """Record a non-fatal error."""
        self.errors.append(msg)
        logger.warning("Pipeline error: %s", msg)
