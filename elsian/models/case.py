"""Data model for case configuration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CaseConfig:
    """Configuration for a single extraction case (ticker)."""

    ticker: str = ""
    source_hint: str = "sec"
    currency: str = "USD"
    fiscal_year_end_month: int = 12
    period_scope: str = "ANNUAL_ONLY"
    case_dir: str = ""
    config_overrides: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, case_dir: str | Path) -> CaseConfig:
        """Load case config from case.json in the given directory."""
        case_path = Path(case_dir) / "case.json"
        if not case_path.exists():
            logger.warning("No case.json found in %s", case_dir)
            return cls(case_dir=str(case_dir))

        data = json.loads(case_path.read_text(encoding="utf-8"))
        return cls(
            ticker=data.get("ticker", ""),
            source_hint=data.get("source_hint", "sec"),
            currency=data.get("currency", "USD"),
            fiscal_year_end_month=data.get("fiscal_year_end_month", 12),
            period_scope=data.get("period_scope", "ANNUAL_ONLY"),
            case_dir=str(case_dir),
            config_overrides=data.get("config_overrides", {}),
        )
