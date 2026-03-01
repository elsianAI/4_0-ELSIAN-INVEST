"""AliasResolver -- maps row labels to canonical field names."""

from __future__ import annotations

import logging
import re
from typing import Any

from elsian.config import load_field_aliases

logger = logging.getLogger(__name__)


class AliasResolver:
    """Resolves free-text row labels to the 22 canonical field names."""

    def __init__(self, config_dir: str | None = None) -> None:
        from pathlib import Path
        cdir = Path(config_dir) if config_dir else None
        raw = load_field_aliases(cdir)

        self._exact: dict[str, str] = {}
        self._canonical_names: set[str] = set()

        for canonical, info in raw.items():
            if canonical.startswith("_"):
                continue
            self._canonical_names.add(canonical)
            aliases = info.get("aliases", []) if isinstance(info, dict) else []
            for alias in aliases:
                key = self._normalize(alias)
                self._exact[key] = canonical
            self._exact[self._normalize(canonical)] = canonical

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, strip, collapse whitespace, remove common punctuation."""
        t = text.lower().strip()
        t = re.sub(r"[\u2018\u2019\u201c\u201d'\"(),]", "", t)
        t = re.sub(r"\s+", " ", t)
        return t

    def resolve(self, label: str) -> str | None:
        """Resolve a label to its canonical field name, or None."""
        key = self._normalize(label)
        return self._exact.get(key)

    @property
    def canonical_names(self) -> set[str]:
        return self._canonical_names
