"""Structured table extraction from PDF financial filings using pdfplumber.

Complements the existing text-based PDF extraction pipeline (pdf_to_text.py →
html_tables.extract_tables_from_text) by extracting structured table data
directly from the PDF via pdfplumber.extract_tables().

This module is additive — it does NOT replace the text-based path. Results are
fed into the same alias-resolution and scale-cascade pipeline in phase.py.

Designed for non-SEC filings (Euronext/TEP, ASX/KAR) where PDFs are the
primary filing format.
"""

from __future__ import annotations

import re
from io import BytesIO
from typing import List, Optional, Tuple

try:
    import pdfplumber
except Exception:
    pdfplumber = None  # type: ignore[assignment]

from elsian.extract.html_tables import TableField, parse_number
from elsian.normalize.aliases import AliasResolver


# ── Configuration ────────────────────────────────────────────────────

# Maximum number of pages to process per PDF.  Financial statements
# typically appear within the first ~30 pages of a results announcement.
# Annual reports are handled by the text-based pipeline.
_MAX_PAGES = 40

# Maximum PDF file size in bytes (5 MB).  pdfplumber's extract_tables()
# performs full layout analysis (edges, lines, chars) per page which is
# significantly slower than extract_text().  Large annual reports (10-24 MB,
# 100+ pages) are prohibitively slow and already well-served by the
# text-based .txt pipeline.  This extractor adds value for smaller PDFs
# like results announcements and regulatory filings.
_MAX_FILE_SIZE = 5_000_000


# ── Financial table detection keywords ───────────────────────────────

_FINANCIAL_KEYWORDS_RE = re.compile(
    r"\brevenue\b|\bsales\b|\bprofit\b|\bincome\b|\bloss\b"
    r"|\bassets?\b|\bliabilities\b|\bequity\b"
    r"|\bcash\s*flow\b|\bcash\s*and\b|\boperating\b"
    r"|\bebitda\b|\bebit\b|\bearnings?\b|\bexpenses?\b"
    r"|\bdepreciation\b|\bamortization\b|\bdividend\b"
    r"|\bshares?\b|\bdebt\b|\bcapex\b|\bturnover\b|\btax\b"
    r"|\bchiffre\s+d.affaires\b|\brésultat\b|\bactif\b|\bpassif\b"
    r"|\bcapitaux\b|\btrésorer\b|\bendettement\b"
    r"|\bcost\s+of\b|\bgross\b|\bnet\b|\btotal\b"
    r"|\binvesting\b|\bfinancing\b",
    re.IGNORECASE,
)

# Section header patterns to identify which financial statement a table belongs to
_SECTION_PATTERNS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"income\s+statement|statement\s+of\s+(?:income|operations|profit|loss)"
                r"|profit\s+and\s+loss|compte\s+de\s+résultat"
                r"|consolidated\s+statements?\s+of\s+(?:income|operations|earnings)"
                r"|statement\s+of\s+comprehensive\s+income"
                r"|results?\s+for\s+the", re.I),
     "income_statement"),
    (re.compile(r"balance\s+sheet|statement\s+of\s+financial\s+position"
                r"|bilan\s+consolidé|consolidated\s+balance"
                r"|financial\s+position", re.I),
     "balance_sheet"),
    (re.compile(r"cash\s*flow|statement\s+of\s+cash|flux\s+de\s+trésorerie"
                r"|cash\s+generated", re.I),
     "cash_flow"),
]

# ── Period detection from column headers ─────────────────────────────

_YEAR_RE = re.compile(r"\b(20\d{2})\b")

_PERIOD_HEADER_RE = re.compile(
    r"(?:year|twelve\s+months?)\s+ended\s+.*?(20\d{2})"
    r"|(?:six\s+months?)\s+ended\s+.*?(20\d{2})"
    r"|(?:three\s+months?|quarter)\s+ended\s+.*?(20\d{2})"
    r"|FY\s*(20\d{2})"
    r"|H[12]\s*(20\d{2})"
    r"|Q[1-4]\s*(20\d{2})"
    r"|\b(20\d{2})\b",
    re.IGNORECASE,
)

_HALF_YEAR_RE = re.compile(
    r"(?:six\s+months?|half[\s-]year)\s+ended\s+"
    r"(?:(?:june|juin)\s+30|(?:30\s+(?:june|juin)))\s*,?\s*(20\d{2})",
    re.IGNORECASE,
)

_QUARTER_RE = re.compile(
    r"(?:three\s+months?|quarter)\s+ended\s+",
    re.IGNORECASE,
)


def _parse_period_from_header(header: str) -> str:
    """Parse a period key (e.g. 'FY2024', 'H12024') from a column header.

    Args:
        header: Column header text from the PDF table.

    Returns:
        Period key string, or empty string if unparseable.
    """
    if not header:
        return ""
    header = header.strip()

    # Try half-year first
    m = _HALF_YEAR_RE.search(header)
    if m:
        return f"H1{m.group(1)}"

    # Check for explicit FY/H/Q prefixes
    fy_m = re.search(r"FY\s*(20\d{2})", header, re.I)
    if fy_m:
        return f"FY{fy_m.group(1)}"

    h_m = re.search(r"H([12])\s*(20\d{2})", header, re.I)
    if h_m:
        return f"H{h_m.group(1)}{h_m.group(2)}"

    q_m = re.search(r"Q([1-4])\s*(20\d{2})", header, re.I)
    if q_m:
        return f"Q{q_m.group(1)}{q_m.group(2)}"

    # "Year ended ... YYYY" or "Twelve months ended ... YYYY"
    ye_m = re.search(
        r"(?:year|twelve\s+months?)\s+ended\s+.*?(20\d{2})", header, re.I,
    )
    if ye_m:
        return f"FY{ye_m.group(1)}"

    # Quarter detection
    if _QUARTER_RE.search(header):
        yr = _YEAR_RE.search(header)
        if yr:
            return f"Q{yr.group(1)}"  # simplified — no quarter number

    # Bare year: "2024" or "2023"
    yr = _YEAR_RE.search(header)
    if yr:
        return f"FY{yr.group(1)}"

    return ""


# ── Value parsing ────────────────────────────────────────────────────

def _parse_cell_value(text: str) -> Optional[float]:
    """Parse a numeric value from a PDF table cell.

    Handles parenthetical negatives, dashes, currency prefixes,
    thousand separators, and blank cells.

    Args:
        text: Raw cell text from the PDF table.

    Returns:
        Parsed float value, or None if the cell is empty/non-numeric.
    """
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None

    # Delegate to html_tables.parse_number which already handles all formats
    return parse_number(text)


# ── Financial table detection ────────────────────────────────────────

def _is_financial_table(table: list[list[str | None]]) -> bool:
    """Determine if a pdfplumber table contains financial data.

    A table is considered financial if it has at least one row with a label
    that matches financial keywords AND at least one numeric value.

    Args:
        table: 2D list of cell values from pdfplumber.extract_tables().

    Returns:
        True if the table appears to be a financial table.
    """
    if not table or len(table) < 2:
        return False

    has_financial_label = False
    has_numeric = False

    for row in table:
        if not row:
            continue
        # Check first cell (label column) for financial keywords
        label = str(row[0] or "").strip()
        if label and _FINANCIAL_KEYWORDS_RE.search(label):
            has_financial_label = True

        # Check remaining cells for numeric values
        for cell in row[1:]:
            if cell is not None:
                val = _parse_cell_value(str(cell))
                if val is not None:
                    has_numeric = True

        if has_financial_label and has_numeric:
            return True

    return False


def _detect_section(table: list[list[str | None]], page_text: str = "") -> str:
    """Detect which financial statement section a table belongs to.

    Args:
        table: 2D list of cell values.
        page_text: Full text of the page for context.

    Returns:
        Section identifier (e.g. "income_statement", "balance_sheet", "cash_flow")
        or "financial" as fallback.
    """
    # Build a text blob from the table for matching
    table_text = " ".join(
        str(cell or "") for row in table for cell in row
    )
    combined = page_text + " " + table_text

    for pattern, section in _SECTION_PATTERNS:
        if pattern.search(combined):
            return section

    return "financial"


def _extract_column_headers(
    table: list[list[str | None]],
) -> Tuple[list[str], int]:
    """Extract column headers (period labels) from the table's first rows.

    Scans up to the first 3 rows looking for year/period indicators.
    Returns the header labels and the index of the first data row.

    Args:
        table: 2D list of cell values.

    Returns:
        Tuple of (list of column header strings, first data row index).
    """
    if not table:
        return [], 0

    headers: list[str] = []
    data_start = 0

    # Scan first rows for headers
    for row_idx, row in enumerate(table[:4]):
        if not row:
            continue

        # Check if this row contains year/period indicators in non-first cells
        non_first = [str(c or "").strip() for c in row[1:]]
        has_period = any(_YEAR_RE.search(c) for c in non_first if c)

        if has_period:
            # This is a header row
            headers = [str(c or "").strip() for c in row]
            data_start = row_idx + 1
        elif row_idx == 0:
            # First row — check if it's a title/header
            first_cell = str(row[0] or "").strip()
            # If first cell has a section keyword but no numbers, it's a title
            if first_cell and _FINANCIAL_KEYWORDS_RE.search(first_cell):
                non_first_vals = [_parse_cell_value(str(c or "")) for c in row[1:]]
                if not any(v is not None for v in non_first_vals):
                    data_start = max(data_start, 1)
                    continue
            # Otherwise treat as potential header
            headers = [str(c or "").strip() for c in row]
            data_start = 1

    # If no year found in headers, try combining first two rows
    if not any(_YEAR_RE.search(h) for h in headers) and len(table) >= 2:
        combined = []
        for col_idx in range(max(len(table[0]) if table[0] else 0,
                                  len(table[1]) if table[1] else 0)):
            parts = []
            for r in range(min(2, len(table))):
                if table[r] and col_idx < len(table[r]):
                    cell = str(table[r][col_idx] or "").strip()
                    if cell:
                        parts.append(cell)
            combined.append(" ".join(parts))
        if any(_YEAR_RE.search(c) for c in combined):
            headers = combined
            data_start = 2

    return headers, data_start


def extract_tables_from_pdf(
    pdf_path: str,
    filing_source_id: str = "",
) -> list[TableField]:
    """Extract structured tables from a PDF file using pdfplumber.

    Opens the PDF, iterates pages, extracts tables with
    pdfplumber.extract_tables(), identifies financial tables,
    parses rows into (label, value) pairs, and returns
    TableField objects.

    Performance: skips files > 30 MB and limits processing to the
    first 80 pages to avoid excessive runtime on large annual reports.

    Args:
        pdf_path: Path to the PDF file.
        filing_source_id: Source filing ID for provenance tracking.

    Returns:
        List of TableField objects with extracted financial data.
    """
    if pdfplumber is None:
        return []

    # Check file size before opening — skip very large PDFs
    import os
    try:
        if os.path.getsize(pdf_path) > _MAX_FILE_SIZE:
            return []
    except OSError:
        pass  # File may not exist yet (e.g. during testing) — let open() handle it

    try:
        pdf = pdfplumber.open(pdf_path)
    except Exception:
        return []

    results: list[TableField] = []

    with pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num >= _MAX_PAGES:
                break

            try:
                tables = page.extract_tables() or []
            except Exception:
                continue

            # Get page text for section detection context
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            for table_idx, table in enumerate(tables):
                if not table:
                    continue

                if not _is_financial_table(table):
                    continue

                section = _detect_section(table, page_text)
                headers, data_start = _extract_column_headers(table)

                # Build period map from headers
                col_periods: dict[int, str] = {}
                for col_idx, header in enumerate(headers):
                    if col_idx == 0:
                        continue  # Skip label column
                    period = _parse_period_from_header(header)
                    if period:
                        col_periods[col_idx] = period

                # If no periods found in headers, skip this table
                if not col_periods:
                    continue

                # Compute unique table_index: page_num * 100 + table_idx
                unique_table_idx = page_num * 100 + table_idx

                # Determine table title from section + first few cells
                table_title = section
                if table and table[0]:
                    first_label = str(table[0][0] or "").strip()
                    if first_label and len(first_label) < 100:
                        table_title = f"{section}:{first_label}"

                # Process data rows
                for row_idx in range(data_start, len(table)):
                    row = table[row_idx]
                    if not row or len(row) <= 1:
                        continue

                    label = str(row[0] or "").strip()
                    if not label:
                        continue

                    # Skip sub-header rows (all non-label cells empty or non-numeric)
                    non_label_cells = row[1:]
                    values = [_parse_cell_value(str(c or "")) for c in non_label_cells]
                    if not any(v is not None for v in values):
                        continue

                    # Process each column with a known period
                    for col_idx, period_key in col_periods.items():
                        if col_idx >= len(row):
                            continue

                        raw_text = str(row[col_idx] or "").strip()
                        value = _parse_cell_value(raw_text)
                        if value is None:
                            continue

                        # Build source_location for section bonus matching
                        source_loc = (
                            f"{filing_source_id}:{section}:pdf_tbl{unique_table_idx}"
                            f":row{row_idx}:col{col_idx}"
                        )

                        col_header_text = headers[col_idx] if col_idx < len(headers) else ""

                        tf = TableField(
                            label=label,
                            value=value,
                            column_header=period_key,
                            source_location=source_loc,
                            raw_text=raw_text,
                            col_label=col_header_text,
                            table_title=table_title,
                            row_idx=row_idx,
                            col_idx=col_idx,
                            table_index=unique_table_idx,
                        )
                        results.append(tf)

    return results
