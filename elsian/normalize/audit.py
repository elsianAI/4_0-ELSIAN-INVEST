"""AuditLog -- tracks accept/discard decisions with reasons.

Ported from 3.0 deterministic/src/normalize/audit.py.
API matches the extraction phase's call sites exactly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit record for a field extraction decision."""

    field_name: str
    period: str
    action: str  # "accepted" | "discarded" | "uncertain"
    reason: str = ""
    source_filing: str = ""
    raw_label: str = ""
    raw_value: float = 0.0
    scale: str = ""


class AuditLog:
    """Collects audit entries during extraction."""

    def __init__(self) -> None:
        self.entries: List[AuditEntry] = []

    def accept(
        self,
        field_name: str,
        period: str,
        source_filing: str = "",
        raw_label: str = "",
        raw_value: float = 0.0,
        scale: str = "",
    ) -> None:
        self.entries.append(
            AuditEntry(
                field_name=field_name,
                period=period,
                action="accepted",
                source_filing=source_filing,
                raw_label=raw_label,
                raw_value=raw_value,
                scale=scale,
            )
        )

    def discard(
        self,
        field_name: str,
        period: str,
        reason: str,
        source_filing: str = "",
        raw_label: str = "",
        raw_value: float = 0.0,
        scale: str = "",
    ) -> None:
        self.entries.append(
            AuditEntry(
                field_name=field_name,
                period=period,
                action="discarded",
                reason=reason,
                source_filing=source_filing,
                raw_label=raw_label,
                raw_value=raw_value,
                scale=scale,
            )
        )
        logger.debug("Discarded %s/%s: %s (value=%s)", period, field_name, reason, raw_value)

    @property
    def accepted_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "accepted")

    @property
    def discarded_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "discarded")

    @property
    def discard_reasons(self) -> List[str]:
        return list(
            set(e.reason for e in self.entries if e.action == "discarded" and e.reason)
        )
