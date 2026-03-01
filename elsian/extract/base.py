"""Abstract base class for data extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from elsian.models.field import FieldCandidate
from elsian.models.filing import Filing


class Extractor(ABC):
    """Base for data extraction strategies."""

    @abstractmethod
    def extract(self, filing: Filing) -> list[FieldCandidate]:
        """Extract field candidates from a single filing."""
        ...
