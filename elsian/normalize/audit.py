"""AuditLog -- tracks accept/discard decisions with reasons."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit decision."""

    field_name: str
    period: str
    action: str
    reason: str
    value: float | None = None
    source: str = ""


class AuditLog:
    """Collects audit entries for all extraction decisions."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def accept(self, field_name: str, period: str, value: float, source: str, reason: str) -> None:
        self.entries.append(AuditEntry(
            field_name=field_name, period=period, action="accept",
            reason=reason, value=value, source=source,
        ))

    def discard(self, field_name: str, period: str, value: float | None, source: str, reason: str) -> None:
        self.entries.append(AuditEntry(
            field_name=field_name, period=period, action="discard",
            reason=reason, value=value, source=source,
        ))
        logger.debug("Discarded %s/%s: %s (value=%s)", period, field_name, reason, value)

    @property
    def accepted_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "accept")

    @property
    def discarded_count(self) -> int:
        return sum(1 for e in self.entries if e.action == "discard")

    @property
    def discard_reasons(self) -> list[str]:
        return [e.reason for e in self.entries if e.action == "discard"]
