"""Sources compiler — consolidates multi-fetcher outputs into SourcesPack_v1.

Reads from case_dir:
  - filings/                → enumerated to reconstruct filing source entries
  - filings_manifest.json  → acquisition metadata (ticker, CIK, coverage)
  - _market_data.json      → market data snapshot (MarketData.to_dict())
  - _transcripts.json      → transcripts / IR presentations (TranscriptResult.to_dict())

Produces a SourcesPack_v1 dict cataloguing all sources with:
  - Dedup by URL, accession_number, content_hash
  - Cobertura documental (documentary coverage map)
  - Metadata log

Public API:
    compile_sources(ticker, case_dir) -> dict
    save_sources_pack(ticker, case_dir) -> Path
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any

from elsian.acquire.dedup import content_hash as compute_content_hash
from elsian.convert.clean_md_quality import is_clean_md_useful

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Matches filing stems like SRC_001_10-K_FY2024
_STEM_RE = re.compile(r"^(SRC_\d+)_([A-Z0-9\-]+)_(.+)$", re.IGNORECASE)

_REGULATORY_TYPES: frozenset[str] = frozenset({
    "10-K", "10-Q", "20-F", "6-K", "8-K", "DEF14A", "SEC_EXHIBIT",
    "CREDIT_AGREEMENT", "ANNUAL_REPORT", "INTERIM_REPORT", "REGULATORY_FILING",
    "40-F", "QUARTERLY_REPORT",
})
_TRANSCRIPT_TYPES: frozenset[str] = frozenset({
    "EARNINGS_TRANSCRIPT", "TRANSCRIPT", "CALL_TRANSCRIPT",
})
_IR_TYPES: frozenset[str] = frozenset({
    "INVESTOR_PRESENTATION", "IR_NEWS", "PRESS_RELEASE", "SLIDES",
})

# Higher = better; used to pick the surviving entry during hash dedup
_TIPO_PRIORITY: dict[str, int] = {
    "10-K": 10, "20-F": 10, "ANNUAL_REPORT": 10,
    "10-Q": 9, "6-K": 9, "INTERIM_REPORT": 9,
    "REGULATORY_FILING": 8, "8-K": 7, "PRESS_RELEASE": 7,
    "IR_NEWS": 6, "INVESTOR_PRESENTATION": 5, "SLIDES": 5,
    "MARKET_DATA": 4, "OTHER": 1,
}

# ─────────────────────────────────────────────────────────────────────────────
# Type helpers (exported for tests)
# ─────────────────────────────────────────────────────────────────────────────


def normalize_type(value: Any) -> str:
    """Normalize a filing type string to uppercase.

    Args:
        value: Raw filing type (any type; non-str returns "OTHER").

    Returns:
        Uppercase string, e.g. "10-K". If blank/None returns "OTHER".
    """
    if not isinstance(value, str):
        return "OTHER"
    t = value.strip().upper()
    return t if t else "OTHER"


def infer_category(source_type: str) -> str:
    """Infer the document category from the source type.

    Args:
        source_type: Filing type string (will be normalized internally).

    Returns:
        One of "REGULATORIO", "TRANSCRIPCION", "IR", "MERCADO", "OTRA".
    """
    st = normalize_type(source_type)
    if st in _REGULATORY_TYPES:
        return "REGULATORIO"
    if st in _TRANSCRIPT_TYPES or "TRANSCRIPT" in st:
        return "TRANSCRIPCION"
    if st in _IR_TYPES:
        return "IR"
    if st == "MARKET_DATA":
        return "MERCADO"
    return "OTRA"


def source_key(source: dict[str, Any]) -> tuple[str, str]:
    """Return (url_key, accession_key) for deduplication.

    Args:
        source: Source dict with optional "url" and "accession_number" keys.

    Returns:
        Tuple of lowercased/stripped strings. Empty string = no key available.
    """
    url = source.get("url")
    accession = source.get("accession_number")
    url_key = url.strip().lower() if isinstance(url, str) else ""
    acc_key = accession.strip().lower() if isinstance(accession, str) else ""
    return url_key, acc_key


# ─────────────────────────────────────────────────────────────────────────────
# Cobertura / coverage
# ─────────────────────────────────────────────────────────────────────────────


def build_cobertura(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate documentary coverage map from a list of source dicts.

    Args:
        sources: List of compiled source dicts, each with a "tipo" field.

    Returns:
        Dict mapping coverage categories to {encontrado, source_id, tipo}.
    """

    def _find_type(*types: str) -> str | None:
        target = frozenset(t.upper() for t in types)
        for src in sources:
            st = normalize_type(src.get("tipo"))
            if st in target:
                return src.get("source_id")
        return None

    annual = _find_type("10-K", "20-F", "40-F", "ANNUAL_REPORT")
    quarterly = _find_type("10-Q", "6-K", "QUARTERLY_REPORT", "INTERIM_REPORT")
    earnings = _find_type("8-K", "PRESS_RELEASE", "IR_NEWS")
    transcript = _find_type("EARNINGS_TRANSCRIPT", "TRANSCRIPT", "CALL_TRANSCRIPT")
    presentation = _find_type("INVESTOR_PRESENTATION", "SLIDES")
    proxy = _find_type("DEF14A", "PROXY")
    debt = _find_type("CREDIT_AGREEMENT", "NOTE_DEBT", "SEC_EXHIBIT")
    market = _find_type("MARKET_DATA")

    return {
        "informe_anual": {
            "encontrado": annual is not None,
            "source_id": annual,
            "tipo": "10-K",
        },
        "informe_trimestral": {
            "encontrado": quarterly is not None,
            "source_id": quarterly,
            "tipo": "10-Q",
        },
        "earnings_release_mas_reciente": {
            "encontrado": earnings is not None,
            "source_id": earnings,
            "tipo": "8-K",
        },
        "transcripcion_resultados_mas_reciente": {
            "encontrado": transcript is not None,
            "source_id": transcript,
            "tipo": "EARNINGS_TRANSCRIPT",
        },
        "presentacion_inversores_mas_reciente": {
            "encontrado": presentation is not None,
            "source_id": presentation,
            "tipo": "INVESTOR_PRESENTATION",
        },
        "proxy_o_gobierno_corporativo": {
            "encontrado": proxy is not None,
            "source_id": proxy,
            "tipo": "DEF14A",
        },
        "documento_deuda_o_credit_agreement": {
            "encontrado": debt is not None,
            "source_id": debt,
            "tipo": "CREDIT_AGREEMENT",
        },
        "fuente_precio_y_acciones": {
            "encontrado": market is not None,
            "source_id": market,
            "tipo": "MARKET_DATA",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────────────────────────────────────


def _jread(path: Path) -> dict[str, Any] | None:
    """Read and parse a JSON file; return None on any failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _today_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_non_empty(*values: Any) -> Any:
    """Return first non-None, non-empty-string value."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Filename parsing
# ─────────────────────────────────────────────────────────────────────────────


def _parse_filing_stem(stem: str) -> tuple[str, str, str] | None:
    """Parse a filing filename stem into (src_id, form_type, period).

    Expected format: ``SRC_NNN_TYPE_PERIOD`` where:
      - NNN is zero-padded digits (e.g. 001)
      - TYPE is the filing form type (e.g. 10-K, 10-Q, 8-K)
      - PERIOD is the fiscal period label (e.g. FY2024, Q1-2024)

    Args:
        stem: Filename stem without extension, e.g. "SRC_001_10-K_FY2024".

    Returns:
        (src_id, form_type, period) tuple or None if pattern doesn't match.
    """
    m = _STEM_RE.match(stem)
    if not m:
        return None
    return m.group(1).upper(), m.group(2).upper(), m.group(3)


# ─────────────────────────────────────────────────────────────────────────────
# Source construction from filings directory
# ─────────────────────────────────────────────────────────────────────────────


def _best_local_path(filings_dir: Path, src_id: str) -> str | None:
    """Find the best local file for a source in the filings directory.

    Priority: .clean.md (if quality passes) > .txt > .htm/.html > .pdf

    Args:
        filings_dir: Path to the filings directory.
        src_id: Source ID prefix, e.g. "SRC_001".

    Returns:
        Absolute path string or None if no file found.
    """
    for ext in (".clean.md", ".txt", ".htm", ".html", ".pdf"):
        for candidate in sorted(filings_dir.glob(f"{src_id}_*{ext}")):
            if ext == ".clean.md":
                try:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                    if not is_clean_md_useful(text):
                        continue
                except Exception:
                    continue
            return str(candidate)
    return None


def _sources_from_filings_dir(
    case_dir: Path,
    manifest: dict[str, Any],
    today: str,
) -> list[dict[str, Any]]:
    """Enumerate filings/ directory and build one source entry per unique filing.

    Parses ``SRC_NNN_TYPE_PERIOD.*`` filenames, collapses multi-extension
    variants of the same filing into a single source, and picks the best
    available local file (by quality priority).

    Args:
        case_dir: Case directory (must contain a ``filings/`` sub-directory).
        manifest: Parsed filings_manifest.json (may be empty dict).
        today: ISO date string for ``fecha_recuperacion``.

    Returns:
        List of source dicts, one per unique SRC_NNN in the filings dir.
    """
    filings_dir = case_dir / "filings"
    if not filings_dir.is_dir():
        return []

    # Collect unique SRC_NNN → (src_id, form_type, period), ignoring extensions
    stems: dict[str, tuple[str, str, str]] = {}
    for path in sorted(filings_dir.iterdir()):
        name = path.name
        # Strip multi-part extension (.clean.md before stem extraction)
        if name.endswith(".clean.md"):
            stem = name[:-9]
        else:
            stem = Path(name).stem
        parsed = _parse_filing_stem(stem)
        if parsed is None:
            continue
        src_id, form_type, period = parsed
        if src_id not in stems:
            stems[src_id] = (src_id, form_type, period)

    sources: list[dict[str, Any]] = []
    for src_id, form_type, period in sorted(stems.values()):
        local_path = _best_local_path(filings_dir, src_id)
        tipo = normalize_type(form_type)

        # Compute content hash from clean.md when available
        chash: str | None = None
        if local_path and local_path.endswith(".clean.md"):
            try:
                text = Path(local_path).read_text(encoding="utf-8", errors="replace")
                h = compute_content_hash(text)
                chash = h if h else None
            except Exception:
                pass

        sources.append({
            "source_id": src_id,
            "tipo": tipo,
            "categoria": infer_category(tipo),
            "period": period,
            "titulo": f"{tipo} {period}",
            "local_path": local_path,
            "url": "",
            "fecha_publicacion": None,
            "fecha_recuperacion": today,
            "idioma": "en",
            "content_hash": chash,
            "accession_number": None,
        })

    return sources


def _sources_from_transcripts(
    transcripts_data: dict[str, Any],
    today: str,
) -> list[dict[str, Any]]:
    """Convert TranscriptResult.to_dict() output into source dicts.

    Args:
        transcripts_data: Parsed _transcripts.json (may be empty dict).
        today: ISO date string for ``fecha_recuperacion``.

    Returns:
        List of source dicts, one per TranscriptSource entry.
    """
    raw_sources = transcripts_data.get("sources", [])
    if not isinstance(raw_sources, list):
        return []

    result: list[dict[str, Any]] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        tipo = normalize_type(item.get("tipo"))
        result.append({
            "source_id": item.get("source_id", ""),
            "tipo": tipo,
            "categoria": infer_category(tipo),
            "period": item.get("period"),
            "titulo": item.get("title", f"{tipo} source"),
            "local_path": item.get("local_path"),
            "url": item.get("url", ""),
            "fecha_publicacion": item.get("date"),
            "fecha_recuperacion": today,
            "idioma": "en",
            "content_hash": item.get("content_hash"),
            "accession_number": None,
        })
    return result


def _source_from_market_data(
    market_data: dict[str, Any],
    today: str,
) -> dict[str, Any] | None:
    """Convert MarketData.to_dict() output into a MARKET_DATA source entry.

    Args:
        market_data: Parsed _market_data.json (may be empty dict).
        today: ISO date string for ``fecha_recuperacion``.

    Returns:
        Source dict or None if market_data is empty.
    """
    if not market_data:
        return None
    ticker = market_data.get("ticker", "")
    fetched_at = market_data.get("fetched_at", "")
    fecha_pub = (
        fetched_at[:10]
        if isinstance(fetched_at, str) and len(fetched_at) >= 10
        else today
    )
    return {
        "source_id": "SRC_MKT",
        "tipo": "MARKET_DATA",
        "categoria": "MERCADO",
        "period": None,
        "titulo": f"Market Data \u2014 {ticker}" if ticker else "Market Data",
        "local_path": None,
        "url": "",
        "fecha_publicacion": fecha_pub,
        "fecha_recuperacion": today,
        "idioma": "en",
        "content_hash": None,
        "accession_number": None,
        "market_snapshot": {
            "price": market_data.get("price"),
            "currency": market_data.get("currency"),
            "market_cap": market_data.get("market_cap"),
            "exchange": market_data.get("exchange"),
            "sector": market_data.get("sector"),
            "industry": market_data.get("industry"),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────────────────


def _tipo_priority(tipo: str) -> int:
    return _TIPO_PRIORITY.get(normalize_type(tipo), 1)


def _prefer_candidate(
    existing: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    """Return True if *candidate* should replace *existing* (higher quality).

    Comparison rules (in order):
    1. Higher tipo priority wins.
    2. Entry with a local_path wins over one without.
    3. Lexicographically smaller source_id wins (SRC_001 < SRC_002 = older).

    Args:
        existing: Currently winning source dict.
        candidate: Challenger source dict.

    Returns:
        True if candidate should replace existing.
    """
    ep = _tipo_priority(existing.get("tipo", ""))
    cp = _tipo_priority(candidate.get("tipo", ""))
    if cp != ep:
        return cp > ep
    if bool(existing.get("local_path")) != bool(candidate.get("local_path")):
        return bool(candidate.get("local_path"))
    eid = str(existing.get("source_id") or "~")
    cid = str(candidate.get("source_id") or "~")
    return cid < eid


def _dedup_by_url_accession(
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate sources by URL and accession_number.

    For URL collisions, applies quality-aware replacement: if the challenger
    has higher tipo priority or a local_path, it replaces the existing entry.
    Accession collisions favour the first seen entry (unless the challenger
    is strictly better).

    Args:
        sources: Input list of source dicts.

    Returns:
        (deduped_list, count_dropped) where count_dropped >= 0.
    """
    seen_url: dict[str, int] = {}    # url_key -> index in result
    seen_acc: dict[str, int] = {}    # accession_key -> index in result
    result: list[dict[str, Any]] = []
    dropped = 0

    for src in sources:
        url_key, acc_key = source_key(src)

        if url_key and url_key in seen_url:
            existing_idx = seen_url[url_key]
            if _prefer_candidate(result[existing_idx], src):
                logger.debug(
                    "dedup_url: replacing %s with %s",
                    result[existing_idx].get("source_id"),
                    src.get("source_id"),
                )
                result[existing_idx] = src
                if url_key:
                    seen_url[url_key] = existing_idx
                if acc_key:
                    seen_acc[acc_key] = existing_idx
            else:
                logger.debug(
                    "dedup_url: dropping %s (kept %s)",
                    src.get("source_id"),
                    result[existing_idx].get("source_id"),
                )
            dropped += 1
            continue

        if acc_key and acc_key in seen_acc:
            existing_idx = seen_acc[acc_key]
            if _prefer_candidate(result[existing_idx], src):
                result[existing_idx] = src
            logger.debug("dedup_accession: dropping %s", src.get("source_id"))
            dropped += 1
            continue

        idx = len(result)
        if url_key:
            seen_url[url_key] = idx
        if acc_key:
            seen_acc[acc_key] = idx
        result.append(src)

    return result, dropped


def _dedup_by_content_hash(
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Deduplicate sources by content_hash.

    Only applies to sources with a ``content_hash`` of at least 16 hex chars
    (filters out empty strings and placeholder values).  When two sources
    share a hash, ``_prefer_candidate`` selects the survivor.

    Args:
        sources: Input list of source dicts.

    Returns:
        (deduped_list, count_dropped) where count_dropped >= 0.
    """
    seen: dict[str, int] = {}    # hash_key -> index in result
    result: list[dict[str, Any]] = []
    dropped = 0

    for src in sources:
        chash = src.get("content_hash")
        if not isinstance(chash, str) or len(chash) < 16:
            result.append(src)
            continue

        chash_norm = chash.strip().lower()
        if chash_norm in seen:
            existing_idx = seen[chash_norm]
            if _prefer_candidate(result[existing_idx], src):
                logger.debug(
                    "dedup_hash: replacing %s with %s",
                    result[existing_idx].get("source_id"),
                    src.get("source_id"),
                )
                result[existing_idx] = src
            else:
                logger.debug(
                    "dedup_hash: dropping %s (kept %s)",
                    src.get("source_id"),
                    result[existing_idx].get("source_id"),
                )
            dropped += 1
        else:
            seen[chash_norm] = len(result)
            result.append(src)

    return result, dropped


# ─────────────────────────────────────────────────────────────────────────────
# Company metadata
# ─────────────────────────────────────────────────────────────────────────────


def _build_empresa(
    ticker: str,
    manifest: dict[str, Any],
    market_data: dict[str, Any],
    transcripts_data: dict[str, Any],
) -> dict[str, Any]:
    """Build the empresa section from all available fetcher data.

    Args:
        ticker: Ticker symbol.
        manifest: Parsed filings_manifest.json.
        market_data: Parsed _market_data.json.
        transcripts_data: Parsed _transcripts.json.

    Returns:
        Empresa metadata dict.
    """
    md = market_data or {}
    tr_empresa = (
        transcripts_data.get("empresa") or {}
        if isinstance(transcripts_data, dict)
        else {}
    )
    return {
        "ticker": ticker.upper(),
        "nombre": _first_non_empty(
            md.get("company_name"),
            tr_empresa.get("nombre"),
            ticker.upper(),
        ),
        "bolsa": _first_non_empty(
            md.get("exchange"),
            tr_empresa.get("bolsa"),
            manifest.get("source", "UNKNOWN"),
        ),
        "pais": _first_non_empty(md.get("country"), tr_empresa.get("pais"), "US"),
        "sector": _first_non_empty(md.get("sector"), tr_empresa.get("sector"), "UNKNOWN"),
        "industria": _first_non_empty(md.get("industry"), tr_empresa.get("industria"), "UNKNOWN"),
        "currency": _first_non_empty(md.get("currency"), "USD"),
        "cik": str(manifest.get("cik")) if manifest.get("cik") else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def compile_sources(ticker: str, case_dir: Path) -> dict[str, Any]:
    """Compile multi-fetcher outputs into a SourcesPack_v1 dict.

    Reads from *case_dir*:

    - ``filings/``               — files named ``SRC_NNN_TYPE_PERIOD.*``
    - ``filings_manifest.json``  — acquisition coverage metadata
    - ``_market_data.json``      — market data snapshot
    - ``_transcripts.json``      — transcripts / IR presentations

    Deduplication applied in order:

    1. By URL (``url`` field) — quality-aware replacement.
    2. By accession number (``accession_number`` field).
    3. By content hash (``content_hash`` field) — quality-aware replacement.

    Args:
        ticker: Ticker symbol (e.g. "TZOO").
        case_dir: Case directory path (e.g. ``cases/TZOO``).

    Returns:
        SourcesPack_v1 dict with keys:
        ``version_esquema``, ``ticker``, ``empresa``,
        ``cobertura_documental``, ``fuentes``, ``_meta``.

    Raises:
        ValueError: If *case_dir* does not exist.
    """
    if not case_dir.is_dir():
        raise ValueError(f"case_dir does not exist: {case_dir}")

    today = _today_iso()

    # Load fetcher outputs (all optional; missing files -> empty dict)
    manifest = _jread(case_dir / "filings_manifest.json") or {}
    market_data = _jread(case_dir / "_market_data.json") or {}
    transcripts_data = _jread(case_dir / "_transcripts.json") or {}

    # Construct source lists from each input
    filing_sources = _sources_from_filings_dir(case_dir, manifest, today)
    transcript_sources = _sources_from_transcripts(transcripts_data, today)
    mkt_source = _source_from_market_data(market_data, today)

    # Merge: filings first (canonical IDs), then transcripts, then market data
    all_sources: list[dict[str, Any]] = list(filing_sources)
    all_sources.extend(transcript_sources)
    if mkt_source is not None:
        all_sources.append(mkt_source)

    # Dedup
    after_url, url_dropped = _dedup_by_url_accession(all_sources)
    after_hash, hash_dropped = _dedup_by_content_hash(after_url)
    total_dropped = url_dropped + hash_dropped

    cobertura = build_cobertura(after_hash)
    empresa = _build_empresa(ticker, manifest, market_data, transcripts_data)

    # Count by category for _meta
    category_counts: dict[str, int] = {}
    for src in after_hash:
        cat = src.get("categoria", "OTRA")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    return {
        "version_esquema": "SourcesPack_v1",
        "ticker": ticker.upper(),
        "empresa": empresa,
        "cobertura_documental": cobertura,
        "fuentes": after_hash,
        "_meta": {
            "compilado_por": "SOURCES_COMPILER_V1",
            "timestamp_compilacion": _utcnow_iso(),
            "fuentes_consolidadas": {
                "filing_sources": len(filing_sources),
                "transcript_sources": len(transcript_sources),
                "market_data_sources": 1 if mkt_source else 0,
                "total_input": len(all_sources),
                "duplicados_eliminados": total_dropped,
                "total_final": len(after_hash),
            },
            "by_category": category_counts,
        },
    }


def save_sources_pack(ticker: str, case_dir: Path) -> Path:
    """Run compile_sources and persist the result to ``sources_pack.json``.

    Args:
        ticker: Ticker symbol.
        case_dir: Case directory path.

    Returns:
        Path to the saved ``sources_pack.json`` file.
    """
    pack = compile_sources(ticker, case_dir)
    out_path = case_dir / "sources_pack.json"
    out_path.write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "SourcesPack saved: %s (%d sources)",
        out_path,
        len(pack["fuentes"]),
    )
    return out_path
