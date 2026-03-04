"""Field alias resolution: map raw labels to canonical field names.

Loads config/field_aliases.json and provides fast lookup.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ── Context-based rejection rules ────────────────────────────────────
# Maps canonical field name -> list of regex patterns. If a raw label
# matches any pattern for the resolved canonical, that resolution is
# rejected (returns None).

# Global reject patterns: applied to ALL canonical fields before
# per-field patterns.  These catch section titles / headers that the
# space-aligned parser might misinterpret as data rows.
_GLOBAL_REJECT_PATTERNS: List[re.Pattern] = [
    re.compile(r"for\s+the\s+years?\s+ended", re.I),
    re.compile(r"statements?\s+of\s+changes?\s+in", re.I),
    re.compile(r"we\s+have\s+audited", re.I),
]

_REJECT_PATTERNS: Dict[str, List[re.Pattern]] = {
    "net_income": [
        re.compile(r"per\s*share", re.I),
        re.compile(r"\beps\b", re.I),
        re.compile(r"\bdiluted\b", re.I),
        re.compile(r"\bbasic\b", re.I),
        re.compile(r"before\s+income\s+tax", re.I),
    ],
    "eps_diluted": [
        re.compile(r"anti.?dilutive", re.I),
        re.compile(r"excluded\s+from", re.I),
        re.compile(r"\badjusted\b", re.I),
        re.compile(r"non[\s-]?gaap", re.I),
        re.compile(r"weighted\s+average", re.I),
        re.compile(r"number\s+of.*shares", re.I),
    ],
    "eps_basic": [
        re.compile(r"anti.?dilutive", re.I),
        re.compile(r"excluded\s+from", re.I),
        re.compile(r"\badjusted\b", re.I),
        re.compile(r"non[\s-]?gaap", re.I),
        re.compile(r"weighted\s+average", re.I),
        re.compile(r"number\s+of.*shares", re.I),
        # Reject "diluted" labels UNLESS "basic" is also present
        # (combined "basic and diluted" labels are valid eps_basic).
        re.compile(r"^(?!.*\bbasic\b).*\bdiluted\b", re.I),
    ],
    "ebit": [
        re.compile(r"non[\s-]?gaap", re.I),
        re.compile(r"loss\s+carryforward", re.I),
        re.compile(r"operating\s+loss\s+carryforward", re.I),
    ],
    "ingresos": [
        re.compile(r"non[\s-]?gaap", re.I),
    ],
    "total_assets": [
        re.compile(r"discontinued\s+operations", re.I),
    ],
    "total_liabilities": [
        re.compile(r"liabilities\s+and\s+stockholders", re.I),
        re.compile(r"liabilities\s+and\s+shareholders", re.I),
        re.compile(r"liabilities\s+and\s+equity", re.I),
        re.compile(r"mezzanine\s+equity", re.I),
        re.compile(r"discontinued\s+operations", re.I),
        re.compile(r"equity\s+and\s+liabilities", re.I),
        # Reject sub-totals: "total current liabilities" and
        # "total non-current liabilities" are subsets, not the full total.
        # The pipeline has a post-processing fallback that sums sub-totals
        # when no direct "total liabilities" line exists (IFRS filings).
        re.compile(r"\bcurrent\b", re.I),
    ],
    "total_equity": [
        re.compile(r"liabilities\s+and\s+", re.I),
        re.compile(r"equity\s+and\s+liabilities", re.I),
        re.compile(r"discontinued\s+operations", re.I),
    ],
    "cash_and_equivalents": [
        re.compile(r"restricted\s*cash", re.I),
        # Reject labels where "cash and cash equiv..." appears as substring
        # but is NOT at the start (e.g., "Effect of exchange rate changes
        # on cash and cash equivalents", "Net increase (decrease) in cash
        # and cash equivalents").  Only "Cash and cash equivalents" (BS row)
        # should resolve to this canonical.
        re.compile(r"^(?!cash\b).*cash\s+and\s+cash\s+equiv", re.I),
    ],
    "gross_profit": [
        re.compile(r"per\s+(?:active\s+)?customer", re.I),
        re.compile(r"per\s+(?:active\s+)?advertiser", re.I),
        re.compile(r"\bmargin\b", re.I),
    ],
    "capex": [
        re.compile(r"finance\s+lease", re.I),
        re.compile(r"accrued\s+but\s+not\s+paid", re.I),
        # Reject supplemental non-cash disclosures like "Capital expenditures
        # included in accounts payable and accrued liabilities" — these are
        # not actual capex from the investing section.
        re.compile(r"included\s+in\s+accounts\s+payable", re.I),
        # Reject "Accrued purchases of property, equipment, and software" —
        # supplemental non-cash disclosure at end of CF table; fuzzy-matches
        # genuine capex aliases but is NOT a cash outflow.
        re.compile(r"^\s*accrued\b", re.I),
    ],
    "income_tax": [
        re.compile(r"before\s+.*income\s+tax", re.I),
        re.compile(r"accrued\s+income\s+tax", re.I),
        re.compile(r"prepaid\s+income\s+tax", re.I),
        re.compile(r"income\s+tax\s+payable", re.I),
        re.compile(r"cash\s+paid.*income\s+tax", re.I),
        re.compile(r"cash.*refund.*income\s+tax", re.I),
        re.compile(r"deferred\s+income\s+tax", re.I),
        re.compile(r"^add:", re.I),
        re.compile(r"\bcurrent\s+tax\s+expense", re.I),
        re.compile(r"\bdeferred\s+tax\s+expense", re.I),
        re.compile(r"\btaxes\s+paid\b", re.I),
        re.compile(r"\btaxes\s+received\b", re.I),
        re.compile(r"taxes\s+other\s+than\s+income", re.I),
        re.compile(r"current\s+income\s+tax\b(?!\s+expense)", re.I),
        re.compile(r"income\s+tax\s+receivable", re.I),
        # NOTE: "Income tax benefit (expenses)" labels (benefit-first) are now
        # accepted and their sign is corrected in phase._normalize_sign via
        # _BENEFIT_FIRST_RE — values are negated so positive=benefit→negative
        # storage and parenthesized=expense→positive storage.
    ],
    "shares_outstanding": [
        re.compile(r"par\s+value", re.I),
        re.compile(r"preferred\s+stock", re.I),
        # Reject "diluted" labels UNLESS "basic" is also present
        # (combined "basic and diluted" labels are valid share counts).
        re.compile(r"^(?!.*\bbasic\b).*\bdiluted\b", re.I),
        # Reject balance-sheet equity rows that START with "Class A/B/C"
        # (e.g. "Class A Common Stock, $0.0001 par value…") — anchored to ^
        # so that IS labels like "Basic weighted average shares of Class A
        # Common Stock outstanding" are NOT rejected.
        re.compile(r"^class\s+[a-z]\b", re.I),
        # Reject balance-sheet caption rows that describe shares issued/outstanding
        # (e.g. "Class A: 757,854,120 shares issued and 751,746,410 shares
        # outstanding") — the numeric value is par value in $K, not shares counts.
        re.compile(r"shares\s+issued\s+and", re.I),
        re.compile(r"class\s+[a-z]:", re.I),
    ],
    # eps_diluted and eps_basic patterns are consolidated above (lines ~36-50).
    # Do NOT add a second eps_diluted/eps_basic key — Python dicts silently
    # overwrite duplicate keys, losing the earlier patterns.
    "sga": [
        re.compile(r"\bper\s+boe\b", re.I),
        re.compile(r"\bunallocated\b", re.I),
        re.compile(r"\bupstream\b", re.I),
        re.compile(r"non[\s-]?gaap", re.I),
        # Reject segment-specific SGA rows footnoted with (2), (3), etc.
        # e.g. "Selling, general and administrative expenses (2)" is a brand-
        # segment breakdown — summing it with the consolidated (1) row
        # double-counts the expense.  Note (1) is always consolidated.
        re.compile(r"\(\s*[2-9]\d*\s*\)\s*$", re.I),
    ],
    "dividends_per_share": [
        # Reject supplemental/special one-off dividends — these are NOT the
        # ordinary annual DPS and would incorrectly replace it.
        re.compile(r"\bsupplemental\b", re.I),
        re.compile(r"\bspecial\s+dividend", re.I),
        # Reject "ordinary dividend per share" labels from results
        # presentations that report DPS in cents (e.g. "16.9c") — the
        # text parser strips the "c" suffix and produces 16.9 instead of
        # 0.169.  The correct value comes from manual_overrides in case.json.
        re.compile(r"^ordinary\s+dividend\b", re.I),
    ],
    "total_debt": [
        re.compile(r"\brepayment\b", re.I),
        re.compile(r"\breceipt\b", re.I),
        re.compile(r"\bproceeds\b", re.I),
        re.compile(r"\bsecurities\b", re.I),
        re.compile(r"fair\s+value\s+adjust", re.I),
        # Reject supplemental non-cash M&A disclosures like "Equity issued
        # and long-term debt assumed to acquire oil and gas properties" —
        # these are non-cash financing activities, not balance-sheet debt.
        re.compile(r"assumed\s+to\s+acquire", re.I),
        re.compile(r"assumed\s+in\s+(?:merger|acquisition)", re.I),
        # Reject "Current portion of long-term debt" — this is a re-classification
        # of part of the net debt for balance-sheet presentation (the current-
        # maturity slice is already included in the net long-term debt total).
        # Summing it would double-count the near-term maturities.
        re.compile(r"current\s+portion\s+of\s+(?:long.term|lt)\s+debt", re.I),
    ],
    "interest_expense": [
        re.compile(r"^add:", re.I),
        re.compile(r"\bpaid\b", re.I),
        re.compile(r"lease\s+liabilities", re.I),
        re.compile(r"net\s+financial\s+interest", re.I),
    ],
    "depreciation_amortization": [
        re.compile(r"right-of-use", re.I),
        re.compile(r"right[\s-]?of[\s-]?use", re.I),
        re.compile(r"intangible\s+assets\s+acquired", re.I),
        # Reject the balance-sheet contra-asset row ("Accumulated depreciation,
        # depletion and amortization") — it carries a cumulative stock value,
        # not the income-statement period charge.
        re.compile(r"\baccumulated\b", re.I),
    ],
    "research_and_development": [
        re.compile(r"tax\s+credit", re.I),
        re.compile(r"in[\s-]process", re.I),
    ],
}

# Priority patterns: when multiple rows could map to same canonical,
# a label matching one of these gets preference (score=100 exact, else 50).
_PRIORITY_PATTERNS: Dict[str, List[re.Pattern]] = {
    # "Total equity" is the fully-consolidated line including noncontrolling
    # interests (NCI).  It should win over "Total shareholders/stockholders'
    # equity" which reflects only the parent company's interest.  This matters
    # for Up-C structures (e.g. Permian Resources) where both rows appear on
    # the same balance sheet.
    "total_equity": [
        re.compile(r"^total\s+equity$", re.I),
    ],
    "ebit": [
        re.compile(r"^operating\s+income", re.I),
        re.compile(r"^operating\s+loss", re.I),
    ],
    "net_income": [
        re.compile(r"^net\s+income(\s*\(loss\))?\s*$", re.I),
    ],
    "cash_and_equivalents": [
        re.compile(r"^cash\s+and\s+cash\s+equivalents$", re.I),
    ],
    "cfo": [
        re.compile(r"net\s+cash\s+(?:provided|used)\s+(?:by|in)\s+operating", re.I),
    ],
    "income_tax": [
        re.compile(r"^(total\s+)?income\s+tax\s+expense(\s*\(benefit\))?\s*$", re.I),
        re.compile(r"^income\s+tax$", re.I),
        re.compile(r"provision\s+for\s+income\s+tax", re.I),
        re.compile(r"^income\s+tax\s+provision", re.I),
        # IFRS 20-F notes IS row — e.g. InMode: "Total expenses (income) taxes on income"
        re.compile(r"^total\s+(?:expenses?\s+)?\(?income\)?\s+taxes?\s+on\s+income$", re.I),
    ],
    "interest_expense": [
        re.compile(r"\bgross\s+financing", re.I),
        re.compile(r"^interest\s+expense", re.I),
    ],
    "shares_outstanding": [
        re.compile(r"shares\s+used\s+in\s+per\s+share\s+calc", re.I),
        re.compile(r"weighted\s+average.*shares.*outstanding", re.I),
        re.compile(r"weighted\s+average\s+common\s+shares", re.I),
        re.compile(r"\bbasic\b", re.I),
    ],
    # E&P companies report primary revenue as "Oil and gas sales" or
    # "Oil and gas revenues" — these should beat generic "Total Revenue"
    # or "Total revenues" appearing in secondary note tables.
    "ingresos": [
        re.compile(r"oil\s+and\s+gas\s+(?:sales|revenues?)\b", re.I),
    ],
    # PR filings use "Income per share—Basic" in the primary IS instead
    # of the more common "Earnings per share—Basic".  Giving it priority
    # ensures it beats secondary-note EPS tables (e.g. predecessor entity
    # combined metrics) that reference a different share-count universe.
    "eps_basic": [
        re.compile(r"\bincome\s+per\s+share\b", re.I),
    ],
}


class AliasResolver:
    """Resolves raw field labels to canonical names using aliases config."""

    def __init__(self, config_path: str = ""):
        self._aliases: Dict[str, List[str]] = {}
        self._multipliers: Dict[str, Optional[float]] = {}
        self._additive: set = set()  # canonical names marked additive
        self._lookup: Dict[str, str] = {}  # normalized alias -> canonical

        if not config_path:
            config_path = str(
                Path(__file__).parent.parent.parent / "config" / "field_aliases.json"
            )

        self._load(config_path)

    def _load(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        for canonical, config in data.items():
            if canonical.startswith("_"):
                continue
            aliases = config.get("aliases", [])
            multiplier = config.get("multiplier")
            self._aliases[canonical] = aliases
            self._multipliers[canonical] = multiplier
            if config.get("additive", False):
                self._additive.add(canonical)

            # Build lookup: normalized alias -> canonical
            self._lookup[self._normalize(canonical)] = canonical
            for alias in aliases:
                self._lookup[self._normalize(alias)] = canonical

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize a label for matching."""
        text = text.lower().strip()
        # Remove parenthetical qualifiers that add noise to financial labels.
        # E.g. "Net income (loss) per share" → "Net income  per share"
        text = re.sub(
            r"\(\s*(?:loss|benefit(?:\s+from)?|deficit|expense|income|used\s+in)\s*\)",
            "", text,
        )
        # Replace common punctuation with space (not just remove) so that
        # "share—basic" becomes "share basic" not "sharebasic".
        # Also normalise U+02BC (modifier letter apostrophe, used in SEC filings
        # as in "stockholdersʼ equity") alongside regular apostrophes.
        text = re.sub(r"['\'\u02BC\u2018\u2019\u201C\u201D\",():/\u2014\u2013]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _is_rejected(canonical: str, raw_label: str) -> bool:
        """Return True if raw_label is contextually invalid for canonical."""
        for pat in _GLOBAL_REJECT_PATTERNS:
            if pat.search(raw_label):
                return True
        patterns = _REJECT_PATTERNS.get(canonical, [])
        for pat in patterns:
            if pat.search(raw_label):
                return True
        return False

    @staticmethod
    def label_priority(canonical: str, raw_label: str) -> int:
        """Return a priority score (higher = better) for label-to-canonical match.

        100 = exact priority match, 50 = contains priority substring, 0 = default.
        Labels with dash qualifiers (e.g. "D&A – oil and gas") get -10 as they
        are typically sub-categories, not totals.
        """
        patterns = _PRIORITY_PATTERNS.get(canonical, [])
        for pat in patterns:
            if pat.fullmatch(raw_label.strip()):
                return 100
            if pat.search(raw_label):
                return 50
        # Penalize dash-qualified sub-category labels (space-surrounded dashes
        # only, e.g. "D&A \u2013 oil and gas assets").  Embedded dashes like
        # "Net income per share\u2014Diluted" are NOT penalized.
        if " \u2013 " in raw_label or " \u2014 " in raw_label:
            return -10
        return 0

    def resolve(self, raw_label: str) -> Optional[str]:
        """Resolve a raw label to its canonical field name.

        Returns None if no match found or if contextual rejection applies.
        """
        normalized = self._normalize(raw_label)
        if normalized in self._lookup:
            canonical = self._lookup[normalized]
            if self._is_rejected(canonical, raw_label):
                return None
            return canonical

        # Fuzzy: try substring match (label contains a multi-word alias).
        # Only multi-word aliases (containing a space) are eligible for fuzzy,
        # to prevent single-word aliases like "revenue" matching inside
        # unrelated labels like "deferred revenue".
        for alias_norm, canonical in self._lookup.items():
            if " " in alias_norm and len(alias_norm) >= 6 and alias_norm in normalized:
                if self._is_rejected(canonical, raw_label):
                    continue
                return canonical

        return None

    def get_multiplier(self, canonical_name: str) -> Optional[float]:
        """Get the scale multiplier for a canonical field. None = no assumption."""
        return self._multipliers.get(canonical_name)

    def is_additive(self, canonical: str) -> bool:
        """Return True if canonical field uses additive accumulation."""
        return canonical in self._additive

    def get_all_canonical_names(self) -> List[str]:
        """Return all known canonical field names."""
        return list(self._aliases.keys())
