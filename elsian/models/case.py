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
    company_name: str | None = None
    source_hint: str = "sec"
    currency: str = "USD"
    fiscal_year_end_month: int = 12
    period_scope: str = "FULL"
    case_dir: str = ""
    cik: str | None = None
    exchange: str | None = None
    market: str | None = None
    country: str | None = None
    accounting_standard: str | None = None
    sector: str | None = None
    notes: str = ""
    raw_filings_dir: str | None = None
    web_ir: str | None = None
    filings_expected_count: int | None = None
    filings_sources: list[dict[str, Any]] = field(default_factory=list)
    use_ixbrl_override: bool = False
    additive_fields: list[str] = field(default_factory=list)
    selection_overrides: dict[str, Any] = field(default_factory=dict)
    config_overrides: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, case_dir: str | Path) -> CaseConfig:
        """Load case config from case.json in the given directory."""
        case_path = Path(case_dir) / "case.json"
        if not case_path.exists():
            logger.warning("No case.json found in %s", case_dir)
            return cls(case_dir=str(case_dir))

        data = json.loads(case_path.read_text(encoding="utf-8"))
        known_keys = {
            "ticker",
            "company_name",
            "source_hint",
            "currency",
            "fiscal_year_end_month",
            "period_scope",
            "cik",
            "exchange",
            "market",
            "country",
            "accounting_standard",
            "sector",
            "notes",
            "raw_filings_dir",
            "web_ir",
            "filings_expected_count",
            "filings_sources",
            "use_ixbrl_override",
            "additive_fields",
            "selection_overrides",
            "config_overrides",
        }
        return cls(
            ticker=data.get("ticker", ""),
            company_name=data.get("company_name"),
            source_hint=data.get("source_hint", "sec"),
            currency=data.get("currency", "USD"),
            fiscal_year_end_month=data.get("fiscal_year_end_month", 12),
            period_scope=data.get("period_scope", "FULL"),
            case_dir=str(case_dir),
            cik=data.get("cik"),
            exchange=data.get("exchange"),
            market=data.get("market"),
            country=data.get("country"),
            accounting_standard=data.get("accounting_standard"),
            sector=data.get("sector"),
            notes=data.get("notes", ""),
            raw_filings_dir=data.get("raw_filings_dir"),
            web_ir=data.get("web_ir"),
            filings_expected_count=data.get("filings_expected_count"),
            filings_sources=data.get("filings_sources", []),
            use_ixbrl_override=data.get("use_ixbrl_override", False),
            additive_fields=data.get("additive_fields", []),
            selection_overrides=data.get("selection_overrides", {}),
            config_overrides=data.get("config_overrides", {}),
            extra={
                key: value
                for key, value in data.items()
                if key not in known_keys
            },
        )
