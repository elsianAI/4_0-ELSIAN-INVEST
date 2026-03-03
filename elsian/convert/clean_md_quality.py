"""Semantic quality gates for .clean.md content.

Ported from 3_0-ELSIAN-INVEST/scripts/runners/clean_md_quality.py (241 lines).
Provides granular section-level validation, mode detection (html_table vs
pdf_text), stub detection, and exportable diagnostic stats.

Public API:
    detect_clean_md_mode(text) -> str
    evaluate_clean_md(text, mode=None) -> dict
    is_clean_md_useful(text, mode=None) -> bool
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

CORE_SECTIONS: tuple[str, ...] = ("INCOME STATEMENT", "BALANCE SHEET", "CASH FLOW")

_MODE_HEADER_RE = re.compile(r"_Extractor mode:\s*([a-z_]+)_", re.IGNORECASE)
_TABLE_NUMERIC_ROW_RE = re.compile(r"^\|.*\d[\d,\.]*.*\|$", re.MULTILINE)
_NUMERIC_TOKEN_RE = re.compile(r"(?<!\w)[\(\-]?\$?\d[\d,]*(?:\.\d+)?%?\)?")

_STUB_MARKER = "_Section not found in filing._"

_PDF_FIN_HINTS: tuple[str, ...] = (
    "revenue",
    "net revenue",
    "income",
    "profit",
    "loss",
    "cash flow",
    "operating activities",
    "investing activities",
    "financing activities",
    "assets",
    "liabilities",
    "equity",
    "ebit",
    "ebitda",
    "capex",
    "chiffre d'affaires",
    "résultat net",
    "resultat net",
    "flux de trésorerie",
    "actifs",
    "passifs",
    "capitaux propres",
)


# ── Mode detection ────────────────────────────────────────────────────

def detect_clean_md_mode(text: str) -> str:
    """Detect clean.md mode from explicit header or structural heuristics.

    Args:
        text: Full clean.md content.

    Returns:
        ``"html_table"`` or ``"pdf_text"``.
    """
    if not text:
        return "pdf_text"
    match = _MODE_HEADER_RE.search(text)
    if match:
        mode = match.group(1).lower().strip()
        if mode in {"html_table", "pdf_text"}:
            return mode
    # Heuristic: markdown-table heavy → html_table; otherwise pdf_text.
    numeric_rows = len(_TABLE_NUMERIC_ROW_RE.findall(text))
    return "html_table" if numeric_rows >= 5 else "pdf_text"


# ── Helpers ───────────────────────────────────────────────────────────

def _section_text(text: str, section_name: str) -> str:
    """Extract markdown text belonging to a single ``## SECTION`` block."""
    idx = text.find(f"## {section_name}")
    if idx < 0:
        return ""
    next_section = text.find("\n## ", idx + 1)
    if next_section > idx:
        return text[idx:next_section]
    return text[idx:]


def _count_stubs(text: str) -> int:
    """Count ``_Section not found in filing._`` placeholders."""
    return text.count(_STUB_MARKER)


# ── HTML-table gate ───────────────────────────────────────────────────

def _evaluate_html_table(text: str) -> Dict[str, Any]:
    """Quality gate for clean.md produced by HTML table extraction.

    Checks:
        - Total numeric rows ≥ 5
        - Missing-section stub count < 4
        - At least 1 core section with ≥ 3 numeric rows
    """
    numeric_rows = len(_TABLE_NUMERIC_ROW_RE.findall(text))
    missing_sections = _count_stubs(text)

    section_numeric_rows: Dict[str, int] = {}
    valid_core_sections = 0
    for section_name in CORE_SECTIONS:
        section = _section_text(text, section_name)
        if not section or _STUB_MARKER in section:
            section_numeric_rows[section_name] = 0
            continue
        count = len(_TABLE_NUMERIC_ROW_RE.findall(section))
        section_numeric_rows[section_name] = count
        if count >= 3:
            valid_core_sections += 1

    stats: Dict[str, Any] = {
        "numeric_rows": numeric_rows,
        "missing_sections": missing_sections,
        "valid_core_sections": valid_core_sections,
        "section_numeric_rows": section_numeric_rows,
    }

    if missing_sections >= 4:
        return {"useful": False, "reason": "ALL_SECTIONS_MISSING", "stats": stats}

    if numeric_rows < 5:
        return {"useful": False, "reason": "LOW_NUMERIC_ROWS", "stats": stats}

    if valid_core_sections < 1:
        return {"useful": False, "reason": "NO_VALID_CORE_SECTION", "stats": stats}

    return {"useful": True, "reason": "OK", "stats": stats}


# ── PDF-text gate ─────────────────────────────────────────────────────

def _evaluate_pdf_text(text: str) -> Dict[str, Any]:
    """Quality gate for clean.md produced by PDF text extraction.

    Checks:
        - Not a PDF placeholder stub
        - ≥ 6 financial-keyword signal hits
        - ≥ 8 000 characters
        - ≥ 80 numeric tokens
        - ≥ 2 core sections with ≥ 20 numeric tokens each
    """
    normalized = re.sub(r"\s+", " ", text.lower())
    chars = len(text)
    signal_hits: List[str] = sorted({h for h in _PDF_FIN_HINTS if h in normalized})
    signal_hit_count = len(signal_hits)
    numeric_token_count = len(_NUMERIC_TOKEN_RE.findall(text))

    core_sections = 0
    for section_name in CORE_SECTIONS:
        section = _section_text(text, section_name)
        if not section or _STUB_MARKER in section:
            continue
        if len(_NUMERIC_TOKEN_RE.findall(section)) >= 20:
            core_sections += 1

    stats: Dict[str, Any] = {
        "chars": chars,
        "signal_hits": signal_hits,
        "signal_hit_count": signal_hit_count,
        "numeric_token_count": numeric_token_count,
        "core_sections": core_sections,
    }

    if text.startswith("[PDF original"):
        return {"useful": False, "reason": "PDF_PLACEHOLDER", "stats": stats}

    if signal_hit_count < 6:
        return {"useful": False, "reason": "LOW_SIGNAL", "stats": stats}

    if chars < 8_000:
        return {"useful": False, "reason": "LOW_TEXT", "stats": stats}

    if numeric_token_count < 80:
        return {"useful": False, "reason": "LOW_NUMERIC_DENSITY", "stats": stats}

    if core_sections < 2:
        return {"useful": False, "reason": "LOW_CORE_SECTIONS", "stats": stats}

    return {"useful": True, "reason": "OK", "stats": stats}


# ── Public API ────────────────────────────────────────────────────────

def evaluate_clean_md(text: str, mode: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate clean.md quality under html_table or pdf_text gates.

    Args:
        text: Full clean.md content.
        mode: ``"html_table"`` or ``"pdf_text"``.  Auto-detected when *None*.

    Returns:
        Dict with keys ``mode``, ``useful`` (bool), ``reason`` (str),
        ``stats`` (dict of diagnostic metrics).
    """
    selected_mode = (mode or detect_clean_md_mode(text)).strip().lower()
    if selected_mode not in {"html_table", "pdf_text"}:
        selected_mode = detect_clean_md_mode(text)

    if not text:
        return {"mode": selected_mode, "useful": False, "reason": "EMPTY", "stats": {}}

    if selected_mode == "html_table":
        result = _evaluate_html_table(text)
    else:
        result = _evaluate_pdf_text(text)

    result["mode"] = selected_mode

    if not result["useful"]:
        logger.debug(
            "clean.md rejected: mode=%s reason=%s stats=%s",
            selected_mode,
            result["reason"],
            result.get("stats"),
        )

    return result


def is_clean_md_useful(text: str, mode: Optional[str] = None) -> bool:
    """Boolean wrapper — *True* if the clean.md passes its quality gate.

    Args:
        text: Full clean.md content.
        mode: ``"html_table"`` or ``"pdf_text"``.  Auto-detected when *None*.

    Returns:
        Whether the file is useful for downstream extraction.
    """
    return bool(evaluate_clean_md(text, mode=mode).get("useful"))
