"""Abstract base class for filing fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from elsian.models.case import CaseConfig
from elsian.models.filing import Filing


class Fetcher(ABC):
    """Base for filing acquisition strategies."""

    @abstractmethod
    def fetch(self, case: CaseConfig) -> list[Filing]:
        """Download/locate filings for the given case."""
        ...
