"""Data models for filing metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Filing:
    """A single regulatory filing."""

    source_id: str = ""
    form: str = ""
    filing_date: str = ""
    accession: str = ""
    primary_doc: str = ""
    local_path: str = ""
    clean_md_path: str = ""
    fiscal_year_end: str = ""
    period_label: str = ""

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")


@dataclass
class FilingMetadata:
    """Detected metadata from a filing's content."""

    currency: str = "USD"
    scale: str = "raw"
    language: str = "en"
    periods: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    filing_type: str = ""
