"""Content-based deduplication for downloaded filings.

Ported from 3_0-ELSIAN-INVEST sec_fetcher_v2_runner.py
(`_normalize_text_for_hash`, `_content_hash`).
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


def normalize_text_for_hash(text: str) -> str:
    """Collapse whitespace and lowercase for hashing.

    Makes the hash resilient to trivial formatting differences
    (extra newlines, trailing spaces, inconsistent casing).
    """
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def content_hash(text: str) -> str:
    """SHA-256 of normalised text. Empty string → empty string."""
    normalized = normalize_text_for_hash(text)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_duplicate(
    new_text: str,
    seen_hashes: set[str],
) -> bool:
    """Return True if *new_text* has a hash already in *seen_hashes*.

    Does NOT mutate *seen_hashes*. Caller decides whether to add.
    """
    h = content_hash(new_text)
    if not h:
        return False
    return h in seen_hashes


def dedup_texts(
    texts: list[str],
) -> tuple[list[str], list[int]]:
    """Remove duplicate texts, preserving first occurrence order.

    Returns:
        (unique_texts, duplicate_indices) — *duplicate_indices* are 0-based
        positions of discarded items in the original list.
    """
    seen: set[str] = set()
    unique: list[str] = []
    dup_indices: list[int] = []
    for idx, text in enumerate(texts):
        h = content_hash(text)
        if not h:
            unique.append(text)
            continue
        if h in seen:
            dup_indices.append(idx)
        else:
            seen.add(h)
            unique.append(text)
    return unique, dup_indices
