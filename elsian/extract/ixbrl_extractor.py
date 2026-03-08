"""IxbrlExtractor — production extractor for iXBRL .htm filings.

Wraps the existing ``parse_ixbrl_filing()`` parser from ``elsian.extract.ixbrl``
and converts ``IxbrlFact`` objects to ``FieldResult`` objects with full
provenance (``extraction_method="ixbrl"``).

Usage within ExtractPhase::

    extractor = IxbrlExtractor()
    results = extractor.extract(Path("SRC_001_10-K_FY2024.htm"), fiscal_year_end_month=12)
    # results: dict[period, dict[field_name, FieldResult]]
"""

from __future__ import annotations

import logging
from pathlib import Path

from elsian.models.field import FieldResult, Provenance
from elsian.extract.ixbrl import (
    _load_concept_map,
    deduplicate_facts,
    parse_ixbrl_filing,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Fields that must always be stored as positive numbers regardless of how the
# iXBRL tag marks the sign (consistent with phase.py _ALWAYS_POSITIVE_FIELDS).
_ALWAYS_POSITIVE: frozenset[str] = frozenset({
    "cost_of_revenue",
    "sga",
    "research_and_development",
    "depreciation_amortization",
    "interest_expense",
})

# Map iXBRL ``scale`` attribute (power of 10) → FieldResult scale string.
_IXBRL_SCALE_MAP: dict[int, str] = {
    0: "raw",
    3: "thousands",
    6: "millions",
    9: "billions",
}

# Source-type rank for iXBRL: lower is better.  Values of 0 (table) and 1
# (narrative) are used by table/narrative extractors.  Using -1 here ensures
# iXBRL beats both for the same (filing_rank, affinity) pair.
IXBRL_SRC_TYPE_RANK: int = -1

# Semantic rank for iXBRL results.  Lower (more negative) = better quality.
# -9999 ensures iXBRL always wins over any table / narrative candidate that
# competes at the same (filing_rank, affinity, src_type_rank) level.
IXBRL_SEMANTIC_RANK: int = -9999

_TOTAL_EQUITY_CONCEPT_MARKERS = (
    "stockholdersequity",
    "stockholdersequityincludingportionattributabletononcontrollinginterest",
)
_BALANCE_SHEET_RESTATEMENT_MARKERS = (
    "as reported adjustment as restated",
    "as previously reported",
    "adjustment as restated",
)
_BALANCE_SHEET_TABLE_MARKERS = (
    " assets ",
    " total liabilities ",
    " liabilities and stockholders equity ",
    " total liabilities, redeemable non-controlling interest and equity ",
)
_EQUITY_ROLLFORWARD_MARKERS = (
    "common stock",
    "additional paid-in capital",
    "retained earnings",
    "retained deficit",
    "treasury stock",
    "accumulated other comprehensive",
    "total stockholders",
    "total travelzoo stockholders",
    "balances,",
)


# ── Public class ──────────────────────────────────────────────────────────────

class IxbrlExtractor:
    """Extracts financial data from iXBRL .htm filings as ``FieldResult`` objects.

    This class wraps ``parse_ixbrl_filing()`` from ``elsian.extract.ixbrl``
    and is designed to be called from ``ExtractPhase._extract_from_clean_md()``
    before the normal HTML-table extraction pass.  When an iXBRL result is
    present for a (period, field) pair the table/narrative extractors will not
    overwrite it because the sort key assigned by ``make_ixbrl_sort_key()``
    ranks iXBRL above table and narrative sources.

    Example::

        extractor = IxbrlExtractor()
        if extractor.has_ixbrl(htm_path):
            ixbrl_results = extractor.extract(htm_path, fiscal_year_end_month=12)
    """

    # ── Static helpers ─────────────────────────────────────────────────────

    @staticmethod
    def has_ixbrl(filepath: Path) -> bool:
        """Return True if *filepath* appears to be an iXBRL document.

        Reads only the first 8 KB of the file to locate the iXBRL namespace
        declaration (``xmlns:ix=``) or header tag (``<ix:header``), which
        appear near the top of all well-formed iXBRL documents.

        Args:
            filepath: Path to the candidate .htm/.html file.

        Returns:
            True when iXBRL markers are found; False on any read error.
        """
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                chunk = fh.read(8192)
            lower = chunk.lower()
            return "xmlns:ix=" in lower or "<ix:header" in lower
        except OSError:
            return False

    # ── Extraction ─────────────────────────────────────────────────────────

    def extract(
        self,
        filepath: Path,
        fiscal_year_end_month: int = 12,
    ) -> dict[str, dict[str, FieldResult]]:
        """Extract canonical financial fields from an iXBRL .htm filing.

        Calls ``parse_ixbrl_filing()``, deduplicates facts with
        ``deduplicate_facts()``, and converts each winning ``IxbrlFact`` to a
        ``FieldResult`` with:

        - ``extraction_method="ixbrl"``
        - ``confidence="high"``
        - ``scale`` mapped from the iXBRL ``scale`` attribute
        - Provenance including the iXBRL concept name, context_ref, and the
          raw displayed value exactly as shown in the filing

        Args:
            filepath: Path to the .htm iXBRL filing.
            fiscal_year_end_month: Fiscal year-end month (1–12) used for
                period label resolution.  Obtained from the ticker's
                ``case.json`` by the caller.

        Returns:
            Nested dict: ``{period_label: {field_name: FieldResult}}``.
            Only mapped fields (those present in ``ixbrl_concept_map.json``)
            are included.  Empty dict is returned on parse failure.
        """
        try:
            facts = parse_ixbrl_filing(filepath, fiscal_year_end_month)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "IxbrlExtractor: parse_ixbrl_filing failed for %s: %s",
                filepath.name, exc,
            )
            return {}

        if not facts:
            return {}

        _, _, preferred_concepts = _load_concept_map()
        total_equity_context_map = (
            _build_total_equity_context_map(filepath)
            if any(
                fact.field == "total_equity" and fact.tag_id
                for fact in facts
            )
            else {}
        )

        # Determine the dominant monetary scale across all facts so that outlier
        # tags (e.g. a D&A tag at scale=6/millions in a thousands-based filing)
        # are normalised to match the rest of the filing before deduplication.
        dom_scale = _dominant_monetary_scale(facts)

        facts_by_period = deduplicate_facts(facts, preferred_concepts)
        _prefer_balance_sheet_total_equity_facts(
            facts_by_period,
            facts,
            total_equity_context_map,
        )

        result: dict[str, dict[str, FieldResult]] = {}
        filing_name = filepath.name

        for period, field_facts in facts_by_period.items():
            result[period] = {}
            for field_name, fact in field_facts.items():
                preserve_raw_scale = _should_preserve_raw_scale(
                    field_name, fact, dom_scale
                )
                adj = (
                    fact.value
                    if preserve_raw_scale
                    else _adjust_to_dominant_scale(
                        fact.value, fact.scale, dom_scale
                    )
                )
                value = _normalize_sign(field_name, adj)
                # Preserve "raw" scale for per-share / unitless fields (scale=0);
                # use dominant scale for all monetary fields.
                if preserve_raw_scale or fact.scale == 0 or dom_scale == 0:
                    scale = _map_scale(fact.scale)
                else:
                    scale = _map_scale(dom_scale)
                source_location = (
                    f"{filing_name}:ixbrl:{fact.context_ref}:{fact.concept}"
                )
                fr = FieldResult(
                    value=value,
                    provenance=Provenance(
                        source_filing=filing_name,
                        source_location=source_location,
                        table_index=None,
                        table_title="",
                        row_label=fact.concept,
                        col_label=period,
                        row=None,
                        col=None,
                        raw_text=fact.displayed_value,
                        extraction_method="ixbrl",
                    ),
                    scale=scale,
                    confidence="high",
                )
                if field_name == "total_equity" and fact.tag_id:
                    fr._ixbrl_total_equity_context = total_equity_context_map.get(  # type: ignore[attr-defined]
                        fact.tag_id,
                        "",
                    )
                # Mark this FieldResult when the value was rescaled from a
                # non-dominant scale (lower precision — allow table to win).
                was_rescaled = (
                    not preserve_raw_scale
                    and
                    fact.scale != 0
                    and dom_scale != 0
                    and fact.scale != dom_scale
                )
                fr._ixbrl_was_rescaled = was_rescaled  # type: ignore[attr-defined]
                result[period][field_name] = fr

        mapped = sum(len(v) for v in result.values())
        logger.info(
            "IxbrlExtractor: %s → %d fields across %d periods",
            filepath.name, mapped, len(result),
        )
        return result


# ── Sort key helper ───────────────────────────────────────────────────────────

def make_ixbrl_sort_key(
    period: str,
    filing_stem: str,
    filing_rank: int,
    *,
    affinity_override: int | None = None,
    was_rescaled: bool = False,
) -> tuple:
    """Build the sort key tuple for an iXBRL ``FieldResult``.

    The sort key layout mirrors the one used throughout ``phase.py``::

        (filing_rank, affinity, src_type_rank, semantic_rank, stable)

    iXBRL sources use ``IXBRL_SRC_TYPE_RANK`` (-1) and
    ``IXBRL_SEMANTIC_RANK`` (-9999), which rank lower (better) than any
    table or narrative candidate for the same ``(filing_rank, affinity)``
    pair.

    When ``was_rescaled`` is True (the iXBRL tag used a non-dominant scale and
    the value was converted, potentially losing precision), the sort key is
    weakened so the table extractor can override the rounded iXBRL value with
    a more exact one.  The rescaled key has ``src_type_rank=0`` (ties with
    table) and ``semantic_rank=9999`` (worst), ensuring the table wins.

    Args:
        period: Period label (e.g. ``"FY2024"``, ``"Q3-2024"``).
        filing_stem: Stem of the originating ``.htm`` file without extension
            (e.g. ``"SRC_001_10-K_FY2024"``).  Used to determine whether
            this filing is the *primary* source for *period* (affinity=0)
            or a comparative source (affinity=1).
        filing_rank: Integer priority for the filing type, as returned by
            ``_filing_rank()`` in ``phase.py`` (lower = better).
        affinity_override: Optional period affinity computed by the shared
            extractor logic. When present, it replaces the filename-only
            heuristic so iXBRL candidates participate in the same annual
            primary-vs-comparative policy as table and narrative candidates.
        was_rescaled: Whether the winning iXBRL fact had to be normalized from
            a non-dominant monetary scale, weakening the sort key so an exact
            table value from the same priority band can override it.

    Returns:
        Tuple compatible with the sort key used in collision resolution.
    """
    affinity = affinity_override if affinity_override is not None else (
        0 if period in filing_stem else 1
    )
    if was_rescaled:
        # Weaker key: ties with table (src_type_rank=0) but worst semantic
        # rank (9999) so that the table's more precise value wins.
        return (filing_rank, affinity, 0, 9999, ("", 0, 0, 0))
    return (filing_rank, affinity, IXBRL_SRC_TYPE_RANK, IXBRL_SEMANTIC_RANK, ("", 0, 0, 0))


# ── Private helpers ───────────────────────────────────────────────────────────

def _dominant_monetary_scale(facts: list) -> int:
    """Return the most common non-zero ``scale`` value across all facts in a filing.

    Non-zero scale values represent monetary amounts (3=thousands, 6=millions).
    Per-share and other unitless values use scale=0 and are excluded so they
    are not accidentally rescaled.

    Returns 0 if all facts are raw (scale=0), meaning no normalisation is needed.
    """
    from collections import Counter

    monetary = [f.scale for f in facts if f.scale != 0]
    if not monetary:
        return 0
    return Counter(monetary).most_common(1)[0][0]


def _normalize_table_text(text: str) -> str:
    return f" {' '.join(text.lower().split())} "


def _classify_total_equity_table(table_text: str) -> str:
    normalized = _normalize_table_text(table_text)
    if (
        any(marker in normalized for marker in _BALANCE_SHEET_RESTATEMENT_MARKERS)
        and any(marker in normalized for marker in _BALANCE_SHEET_TABLE_MARKERS)
    ):
        return "balance_sheet_restatement"
    if any(marker in normalized for marker in _EQUITY_ROLLFORWARD_MARKERS):
        return "equity_rollforward"
    return ""


def _build_total_equity_context_map(filepath: Path) -> dict[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        filepath.read_text(encoding="utf-8", errors="replace"),
        "html.parser",
    )
    context_map: dict[str, str] = {}
    for tag in soup.find_all(lambda t: t.get("id") and t.get("name")):
        concept = (tag.get("name") or "").lower().replace(":", "")
        if not any(marker in concept for marker in _TOTAL_EQUITY_CONCEPT_MARKERS):
            continue
        table = tag.find_parent("table")
        if table is None:
            continue
        context_map[tag.get("id")] = _classify_total_equity_table(
            table.get_text(" ", strip=True)
        )
    return context_map


def _prefer_balance_sheet_total_equity_facts(
    facts_by_period: dict[str, dict[str, object]],
    facts: list,
    total_equity_context_map: dict[str, str],
) -> None:
    for period, field_facts in facts_by_period.items():
        chosen = field_facts.get("total_equity")
        if chosen is None:
            continue
        chosen_context = total_equity_context_map.get(getattr(chosen, "tag_id", ""), "")
        if chosen_context == "balance_sheet_restatement":
            continue
        replacement = next(
            (
                fact for fact in facts
                if fact.field == "total_equity"
                and fact.period == period
                and total_equity_context_map.get(fact.tag_id, "")
                == "balance_sheet_restatement"
            ),
            None,
        )
        if replacement is not None:
            field_facts["total_equity"] = replacement


def _adjust_to_dominant_scale(value: float, fact_scale: int, dominant_scale: int) -> float:
    """Rescale *value* from *fact_scale* to *dominant_scale*.

    Only applied when both scales are non-zero (monetary fields).  Per-share
    and other raw values (scale=0) are never rescaled.

    Example: value=3.9 at scale=6 (millions) with dominant_scale=3 (thousands)
    → 3.9 × 10^(6−3) = 3900, which aligns with a filing unit of "in thousands".
    """
    if fact_scale == 0 or dominant_scale == 0:
        return value  # raw — no normalisation
    diff = fact_scale - dominant_scale
    return value * (10 ** diff) if diff != 0 else value


def _should_preserve_raw_scale(field_name: str, fact, dominant_scale: int) -> bool:
    """Keep narrow million-denominated D&A facts in their displayed scale.

    Some issuers disclose quarterly D&A as a small decimal amount in millions
    while the rest of the filing is denominated in thousands. Re-scaling those
    facts to the dominant filing unit destroys the intended displayed value and
    can also let a weaker table candidate override the correct iXBRL fact.

    We keep this exception narrow to note-style inline facts whose context does
    not use the standard ``Duration_*`` naming found on filing-wide tables.
    When the context is a standard duration context, the tag typically follows
    the filing's dominant monetary unit and should still be normalized.
    """
    if field_name != "depreciation_amortization":
        return False
    if fact.scale == 0 or dominant_scale == 0 or fact.scale == dominant_scale:
        return False
    if fact.scale < dominant_scale:
        return False
    if abs(fact.value) >= 1000:
        return False
    displayed = (fact.displayed_value or "").replace(",", "")
    if "." not in displayed:
        return False
    if (fact.context_ref or "").lower().startswith("duration_"):
        return False
    concept_suffix = fact.concept.rsplit(":", 1)[-1]
    return concept_suffix in {"Depreciation", "DepreciationAndAmortization"}


def _normalize_sign(canonical: str, value: float) -> float:
    """Return *value* with sign corrected for always-positive expense fields."""
    if canonical in _ALWAYS_POSITIVE:
        return abs(value)
    return value


def _map_scale(ixbrl_scale: int) -> str:
    """Map an iXBRL ``scale`` attribute integer to a FieldResult scale string."""
    return _IXBRL_SCALE_MAP.get(ixbrl_scale, "raw")
