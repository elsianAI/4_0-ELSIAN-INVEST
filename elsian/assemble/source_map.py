"""source_map.py - Provenance Level 3 artifact builder for ELSIAN 4.0.

Builds a ``source_map.json`` artifact from ``extraction_result.json`` by
resolving Level 2 provenance into stable click targets on the source document.

Current minimal Level 3 support:

- HTML iXBRL facts -> original ``.htm`` char offsets + optional DOM id anchor
- Markdown table fields -> ``.clean.md`` line anchor for the matching row
- Narrative char offsets -> text/markdown char + line/column anchor

The builder is intentionally post-extraction and deterministic. It does not
change the extraction pipeline or TruthPack schema.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


_TABLE_LOC_RE = re.compile(r":tbl(?P<table>\d+):row(?P<row>\d+):col(?P<col>\d+)")
_CHAR_LOC_RE = re.compile(r":char(?P<char>\d+)")
_IXBRL_NAME_RE = re.compile(r'\bname="(?P<name>[^"]+)"')
_IXBRL_ID_RE = re.compile(r'\bid="(?P<id>[^"]+)"')
_DASH_ONLY_RE = re.compile(r"^[\-\u2013\u2014]+$")
_TEXT_NUM_TOKEN_RE = re.compile(r"\(?[\d,]+(?:\.\d+)?\)?")

_VERTICAL_LABEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "cash_and_equivalents": re.compile(
        r"^cash and cash equivalents\b",
        re.IGNORECASE,
    ),
    "total_assets": re.compile(
        r"^total assets\b",
        re.IGNORECASE,
    ),
    "total_liabilities": re.compile(
        r"^total liabilities\b(?!\s+and\b)",
        re.IGNORECASE,
    ),
    "total_equity": re.compile(
        r"^total\s+(?:stockholders['’ʼ]?|shareholders['’ʼ]?|members['’ʼ]?|owners['’ʼ]?|)"
        r"\s*equity\b",
        re.IGNORECASE,
    ),
    "total_debt": re.compile(
        r"^total debt\b",
        re.IGNORECASE,
    ),
}


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().split())


def _normalise_inline(value: str) -> str:
    return "".join(value.split()).lower()


def _line_col_from_char(text: str, char_index: int) -> tuple[int, int]:
    line = text.count("\n", 0, char_index) + 1
    last_newline = text.rfind("\n", 0, char_index)
    column = char_index + 1 if last_newline == -1 else char_index - last_newline
    return line, column


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_source_path(case_dir: Path, source_filing: str) -> Path | None:
    if not source_filing:
        return None

    filing_path = Path(source_filing)
    if filing_path.is_absolute():
        return None

    case_root = case_dir.resolve()
    for candidate in (
        case_root / filing_path,
        case_root / "filings" / filing_path,
    ):
        resolved = candidate.resolve()
        if _is_within(case_root, resolved) and resolved.exists():
            return resolved

    return None


def _relative_to_case_dir(case_dir: Path, path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None

    case_root = case_dir.resolve()
    resolved = path.resolve()
    if not _is_within(case_root, resolved):
        return None

    return resolved.relative_to(case_root).as_posix()


def _derive_source_variants(
    case_dir: Path,
    source_filing: str,
) -> tuple[str | None, str | None]:
    source_path = _resolve_source_path(case_dir, source_filing)
    if source_path is None:
        return None, None

    original_path: Path | None = None
    clean_path: Path | None = None
    name = source_path.name

    if name.endswith(".clean.md"):
        clean_path = source_path
        stem = name[:-9]
        for suffix in (".htm", ".html", ".pdf", ".txt"):
            candidate = source_path.with_name(f"{stem}{suffix}")
            if candidate.exists():
                original_path = candidate
                break
    elif source_path.suffix.lower() in {".htm", ".html"}:
        original_path = source_path
        candidate = source_path.with_name(f"{source_path.stem}.clean.md")
        if candidate.exists():
            clean_path = candidate
    elif source_path.suffix.lower() == ".pdf":
        original_path = source_path
    elif source_path.suffix.lower() == ".txt":
        original_path = source_path
        base = source_path.with_suffix("")
        for suffix in (".pdf", ".htm", ".html"):
            candidate = base.with_suffix(suffix)
            if candidate.exists():
                original_path = candidate
                break
        clean_candidate = base.with_suffix(".clean.md")
        if clean_candidate.exists():
            clean_path = clean_candidate

    return (
        _relative_to_case_dir(case_dir, original_path),
        _relative_to_case_dir(case_dir, clean_path),
    )


def _iter_table_blocks(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    blocks: list[tuple[int, int, list[str]]] = []
    block_start: int | None = None
    block_lines: list[str] = []

    for line_no, line in enumerate(lines, start=1):
        is_table_line = line.startswith("|") and line.endswith("|")
        if is_table_line:
            if block_start is None:
                block_start = line_no
                block_lines = []
            block_lines.append(line)
            continue

        if block_start is not None:
            blocks.append((block_start, line_no - 1, block_lines))
            block_start = None
            block_lines = []

    if block_start is not None:
        blocks.append((block_start, len(lines), block_lines))

    return blocks


def _match_table_line(
    block_start: int,
    block_lines: list[str],
    *,
    row_label: str,
    raw_text: str,
) -> tuple[int, str] | None:
    norm_label = _normalise_text(row_label)
    norm_raw = _normalise_inline(raw_text)

    candidates: list[tuple[int, str, int]] = []
    for offset, line in enumerate(block_lines):
        norm_line = _normalise_text(line)
        if norm_label and norm_label not in norm_line:
            continue
        score = 1
        if norm_raw and norm_raw in _normalise_inline(line):
            score = 2
        candidates.append((block_start + offset, line, score))

    if candidates:
        candidates.sort(key=lambda item: (-item[2], item[0]))
        line_no, line, _score = candidates[0]
        return line_no, line

    if norm_raw:
        for offset, line in enumerate(block_lines):
            if norm_raw in _normalise_inline(line):
                return block_start + offset, line

    return None


def _resolve_table_pointer(
    case_dir: Path,
    source_path: Path,
    field_data: dict[str, Any],
) -> dict[str, Any] | None:
    source_location = field_data.get("source_location", "") or ""
    match = _TABLE_LOC_RE.search(source_location)
    if not match:
        return None

    lines = source_path.read_text(encoding="utf-8").splitlines()
    blocks = _iter_table_blocks(lines)
    table_index = int(match.group("table"))
    if table_index >= len(blocks):
        return None

    block_start, block_end, block_lines = blocks[table_index]
    matched = _match_table_line(
        block_start,
        block_lines,
        row_label=field_data.get("row_label", "") or "",
        raw_text=field_data.get("raw_text", "") or "",
    )
    if not matched:
        return None

    line_no, snippet = matched
    relative_path = source_path.relative_to(case_dir).as_posix()
    return {
        "kind": "clean_md_table",
        "path": relative_path,
        "line_start": line_no,
        "line_end": line_no,
        "table_index": table_index,
        "table_block_start": block_start,
        "table_block_end": block_end,
        "snippet": snippet,
        "click_target": f"{relative_path}#L{line_no}",
    }


def _resolve_text_table_pointer(
    case_dir: Path,
    source_path: Path,
    field_data: dict[str, Any],
) -> dict[str, Any] | None:
    source_location = field_data.get("source_location", "") or ""
    match = _TABLE_LOC_RE.search(source_location)
    if not match:
        return None

    row_label = field_data.get("row_label", "") or ""
    raw_text = field_data.get("raw_text", "") or ""
    norm_label = _normalise_text(row_label)
    norm_raw = _normalise_inline(raw_text)
    if not norm_raw:
        return None

    lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    candidates: list[tuple[int, int, str]] = []
    target_row = int(match.group("row"))

    for line_no, line in enumerate(lines, start=1):
        norm_line_inline = _normalise_inline(line)
        if norm_raw not in norm_line_inline:
            continue

        window_lines = lines[max(0, line_no - 3):line_no]
        norm_line = _normalise_text(line)
        norm_window = _normalise_text(" ".join(part.strip() for part in window_lines if part.strip()))
        score = 0
        if norm_label and norm_label in norm_line:
            score += 4
        elif norm_label and norm_label in f"{norm_window} {norm_line}".strip():
            score += 3

        tokens = [m.group() for m in _TEXT_NUM_TOKEN_RE.finditer(line)]
        if raw_text in tokens:
            score += 2
        if score <= 0:
            continue

        row_hint_penalty = abs(target_row - len(tokens))
        candidates.append((score * 10 - row_hint_penalty, line_no, line))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    _score, line_no, snippet = candidates[0]
    relative_path = source_path.relative_to(case_dir).as_posix()
    return {
        "kind": "text_table",
        "path": relative_path,
        "line_start": line_no,
        "line_end": line_no,
        "snippet": snippet[:400],
        "click_target": f"{relative_path}#L{line_no}",
        "source_table_hint": int(match.group("table")),
        "source_row_hint": target_row,
        "source_col_hint": int(match.group("col")),
    }


def _find_ixbrl_tag(
    text: str,
    *,
    context_ref: str,
    concept: str,
    raw_text: str,
) -> tuple[int, int, str, str | None] | None:
    context_token = f'contextRef="{context_ref}"'
    concept_token = f'name="{concept}"'
    start = 0

    while True:
        ctx_index = text.find(context_token, start)
        if ctx_index == -1:
            return None

        tag_start = text.rfind("<", 0, ctx_index)
        open_end = text.find(">", ctx_index)
        close_start = text.find("</ix:", open_end)
        close_end = text.find(">", close_start)
        if -1 in {tag_start, open_end, close_start, close_end}:
            return None

        tag = text[tag_start:close_end + 1]
        if concept_token not in tag:
            start = ctx_index + 1
            continue

        inner_text = text[open_end + 1:close_start]
        if (
            raw_text
            and not _DASH_ONLY_RE.fullmatch(raw_text)
            and _normalise_inline(raw_text) not in _normalise_inline(inner_text)
        ):
            start = ctx_index + 1
            continue

        id_match = _IXBRL_ID_RE.search(tag)
        return tag_start, close_end + 1, tag, id_match.group("id") if id_match else None


def _resolve_ixbrl_pointer(
    case_dir: Path,
    source_path: Path,
    field_data: dict[str, Any],
) -> dict[str, Any] | None:
    source_location = field_data.get("source_location", "") or ""
    prefix = f"{field_data.get('source_filing', '')}:ixbrl:"
    if not source_location.startswith(prefix):
        return None

    rest = source_location[len(prefix):]
    if ":" not in rest:
        return None
    context_ref, concept = rest.split(":", 1)

    text = source_path.read_text(encoding="utf-8", errors="ignore")
    matched = _find_ixbrl_tag(
        text,
        context_ref=context_ref,
        concept=concept,
        raw_text=field_data.get("raw_text", "") or "",
    )
    if not matched:
        return None

    char_start, char_end, snippet, element_id = matched
    line, column = _line_col_from_char(text, char_start)
    relative_path = source_path.relative_to(case_dir).as_posix()
    if element_id:
        click_target = f"{relative_path}#{element_id}"
    else:
        click_target = f"{relative_path}#char={char_start}"

    return {
        "kind": "html_ixbrl",
        "path": relative_path,
        "line": line,
        "column": column,
        "char_start": char_start,
        "char_end": char_end,
        "context_ref": context_ref,
        "concept": concept,
        "element_id": element_id,
        "snippet": snippet[:400],
        "click_target": click_target,
    }


def _resolve_char_pointer(
    case_dir: Path,
    source_path: Path,
    field_data: dict[str, Any],
) -> dict[str, Any] | None:
    source_location = field_data.get("source_location", "") or ""
    match = _CHAR_LOC_RE.search(source_location)
    if not match:
        return None

    text = source_path.read_text(encoding="utf-8", errors="ignore")
    char_start = int(match.group("char"))
    if char_start < 0 or char_start >= len(text):
        return None
    raw_text = field_data.get("raw_text", "") or field_data.get("row_label", "") or ""
    char_end = min(len(text), char_start + max(len(raw_text), 1))
    line, column = _line_col_from_char(text, char_start)
    split_lines = text.splitlines()
    line_text = split_lines[line - 1] if split_lines and line - 1 < len(split_lines) else ""
    relative_path = source_path.relative_to(case_dir).as_posix()
    return {
        "kind": "text_char",
        "path": relative_path,
        "line": line,
        "column": column,
        "char_start": char_start,
        "char_end": char_end,
        "snippet": line_text[:400],
        "click_target": f"{relative_path}#char={char_start}",
    }


def _resolve_vertical_text_pointer(
    case_dir: Path,
    source_path: Path,
    field_name: str,
) -> dict[str, Any] | None:
    pattern = _VERTICAL_LABEL_PATTERNS.get(field_name)
    if pattern is None:
        return None

    lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line_no, line in enumerate(lines, start=1):
        if pattern.search(line.strip()):
            relative_path = source_path.relative_to(case_dir).as_posix()
            return {
                "kind": "text_label",
                "path": relative_path,
                "line_start": line_no,
                "line_end": line_no,
                "snippet": line[:400],
                "click_target": f"{relative_path}#L{line_no}",
            }
    return None


class SourceMapBuilder:
    """Build a SourceMap_v1 artifact from extraction_result.json."""

    SCHEMA_VERSION = "SourceMap_v1"

    def build(
        self,
        case_dir: Path,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        case_dir = Path(case_dir).resolve()
        extraction_result = self._load_extraction_result(case_dir)
        source_map = self._build_source_map(extraction_result, case_dir)

        out_path = Path(output_path) if output_path else case_dir / "source_map.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(source_map, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return source_map

    @staticmethod
    def _load_extraction_result(case_dir: Path) -> dict[str, Any]:
        path = case_dir / "extraction_result.json"
        if not path.exists():
            raise FileNotFoundError(
                f"extraction_result.json not found in {case_dir}"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_source_map(
        self,
        extraction_result: dict[str, Any],
        case_dir: Path,
    ) -> dict[str, Any]:
        periods = extraction_result.get("periods", {})
        ticker = extraction_result.get("ticker", case_dir.name)

        mapped_periods: dict[str, Any] = {}
        total_fields = 0
        resolved_fields = 0
        by_method: dict[str, int] = {}
        by_kind: dict[str, int] = {}

        for period_key, period_data in periods.items():
            mapped_fields: dict[str, Any] = {}
            for field_name, field_data in period_data.get("fields", {}).items():
                total_fields += 1
                method = field_data.get("extraction_method", "") or ""
                by_method[method] = by_method.get(method, 0) + 1

                entry = self._build_field_entry(case_dir, field_name, field_data)
                if entry["resolution_status"] == "resolved":
                    resolved_fields += 1
                    kind = entry["pointer"]["kind"]
                    by_kind[kind] = by_kind.get(kind, 0) + 1
                mapped_fields[field_name] = entry

            mapped_periods[period_key] = {
                "fecha_fin": period_data.get("fecha_fin", ""),
                "tipo_periodo": period_data.get("tipo_periodo", ""),
                "fields": mapped_fields,
            }

        unresolved_fields = total_fields - resolved_fields
        return {
            "schema_version": self.SCHEMA_VERSION,
            "ticker": ticker,
            "generated_at": dt.date.today().isoformat(),
            "source_basis": {
                "extraction_result": "extraction_result.json",
            },
            "summary": {
                "total_fields": total_fields,
                "resolved_fields": resolved_fields,
                "unresolved_fields": unresolved_fields,
                "resolution_pct": round(
                    (resolved_fields / total_fields) * 100, 2
                ) if total_fields else 0.0,
                "by_method": by_method,
                "by_pointer_kind": by_kind,
            },
            "periods": mapped_periods,
        }

    def _build_field_entry(
        self,
        case_dir: Path,
        field_name: str,
        field_data: dict[str, Any],
    ) -> dict[str, Any]:
        pointer = self._resolve_pointer(case_dir, field_name, field_data)
        entry = {
            "value": field_data.get("value"),
            "scale": field_data.get("scale", "raw"),
            "confidence": field_data.get("confidence", ""),
            "source_filing": field_data.get("source_filing", ""),
            "source_location": field_data.get("source_location", ""),
            "extraction_method": field_data.get("extraction_method", ""),
            "field_name": field_name,
            "row_label": field_data.get("row_label", ""),
            "col_label": field_data.get("col_label", ""),
            "raw_text": field_data.get("raw_text", ""),
        }
        original_path, clean_path = _derive_source_variants(
            case_dir,
            entry["source_filing"],
        )
        entry["original_path"] = original_path
        entry["clean_path"] = clean_path
        if pointer is None:
            entry["resolution_status"] = "unresolved"
            entry["resolution_reason"] = "unsupported_or_unmatched_source_location"
            return entry

        entry["resolution_status"] = "resolved"
        entry["click_target"] = pointer["click_target"]
        entry["pointer"] = pointer
        return entry

    def _resolve_pointer(
        self,
        case_dir: Path,
        field_name: str,
        field_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        source_filing = field_data.get("source_filing", "") or ""
        if not source_filing:
            return None

        source_path = _resolve_source_path(case_dir, source_filing)
        if source_path is None:
            return None

        extraction_method = field_data.get("extraction_method", "") or ""
        suffix = source_path.suffix.lower()
        if extraction_method == "ixbrl" and suffix == ".htm":
            return _resolve_ixbrl_pointer(case_dir, source_path, field_data)
        if ":table:" in (field_data.get("source_location", "") or "") and suffix == ".md":
            return _resolve_table_pointer(case_dir, source_path, field_data)
        if ":table:" in (field_data.get("source_location", "") or "") and suffix == ".txt":
            return _resolve_text_table_pointer(case_dir, source_path, field_data)
        if ":vertical_bs:" in (field_data.get("source_location", "") or "") and suffix == ".txt":
            return _resolve_vertical_text_pointer(case_dir, source_path, field_name)
        if ":char" in (field_data.get("source_location", "") or ""):
            return _resolve_char_pointer(case_dir, source_path, field_data)
        return None
