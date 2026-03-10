"""Shared HTTP utilities for acquire fetchers (BL-066).

Provides:
- get_user_agent(): configurable User-Agent via env, bounded to safe length.
- get_eu_user_agent(): browser-style UA for EU/IR sites, configurable via env.
- load_json_ttl(): TTL file-cache for stable JSON resources.
- bounded_get(): GET with bounded retry/exponential backoff and retry counter.

All helpers are narrow-scoped for use within ``elsian/acquire/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

# ── User-Agent ────────────────────────────────────────────────────────

_DEFAULT_UA = (
    "ELSIAN-INVEST-Research/4.0 "
    "(non-commercial research bot; contact=research@elsian-invest.local)"
)
_DEFAULT_EU_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
# Hard upper bound to prevent env-injected values from being unexpectedly long.
_UA_MAX_LEN = 300


def get_user_agent() -> str:
    """Return the User-Agent for regulatory-API fetchers (SEC, ASX, ...).

    Reads ELSIAN_USER_AGENT from env; falls back to the hard-coded research UA
    if the value is absent or longer than _UA_MAX_LEN.
    """
    ua = os.environ.get("ELSIAN_USER_AGENT", "").strip()
    if ua and len(ua) <= _UA_MAX_LEN:
        return ua
    return _DEFAULT_UA


def get_eu_user_agent() -> str:
    """Return the User-Agent for EU/IR-website fetchers.

    Uses a browser-style UA by default because many IR sites block
    well-identified bots.  Configurable via ELSIAN_EU_USER_AGENT.
    """
    ua = os.environ.get("ELSIAN_EU_USER_AGENT", "").strip()
    if ua and len(ua) <= _UA_MAX_LEN:
        return ua
    return _DEFAULT_EU_UA


# ── TTL JSON Cache ────────────────────────────────────────────────────

_CACHE_DIR_ENV = "ELSIAN_CACHE_DIR"
_DEFAULT_CACHE_ROOT = Path("/tmp") / "elsian_cache"


def _cache_dir() -> Path:
    raw = os.environ.get(_CACHE_DIR_ENV, "").strip()
    d = Path(raw) if raw else _DEFAULT_CACHE_ROOT
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json_ttl(
    url: str,
    *,
    session: requests.Session,
    headers: dict[str, str],
    ttl_seconds: int = 86_400,
    timeout: int = 40,
) -> tuple[dict[str, Any], bool]:
    """Fetch JSON from *url* with TTL file-based cache.

    Args:
        url: URL to fetch.
        session: Requests session to reuse.
        headers: HTTP headers for the request.
        ttl_seconds: Cache validity in seconds (default 24 h).
        timeout: Per-request timeout in seconds.

    Returns:
        (data, cache_hit) -- parsed JSON dict and whether the cache was used.
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    cache_dir = _cache_dir()
    data_file = cache_dir / f"json_{url_hash}.json"
    meta_file = cache_dir / f"json_{url_hash}.ts"

    if data_file.exists() and meta_file.exists():
        try:
            age = time.time() - float(meta_file.read_text(encoding="utf-8").strip())
            if age < ttl_seconds:
                data = json.loads(data_file.read_text(encoding="utf-8"))
                logger.debug("Cache hit for %s (age=%.0fs)", url, age)
                return data, True
        except (ValueError, OSError, json.JSONDecodeError):
            pass  # stale or corrupted -- fall through to fetch

    resp = session.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    try:
        data_file.write_text(json.dumps(data), encoding="utf-8")
        meta_file.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        logger.warning("Failed to write TTL cache for %s", url)

    return data, False


# ── Bounded retry GET ─────────────────────────────────────────────────

_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def bounded_get(
    url: str,
    *,
    session: requests.Session,
    headers: dict[str, str],
    params: Optional[dict[str, Any]] = None,
    timeout: int = 40,
    max_retries: int = 3,
    base_backoff: float = 2.0,
    retry_statuses: frozenset[int] = _RETRYABLE_STATUSES,
) -> tuple[requests.Response, int]:
    """GET with bounded retries and exponential backoff.

    Total attempts = max_retries + 1.  Backoff for retry k (0-based)
    is base_backoff * 2^k seconds (2 s, 4 s, 8 s with defaults).

    Args:
        url: URL to fetch.
        session: Session to reuse.
        headers: HTTP headers.
        params: Optional query parameters.
        timeout: Per-attempt timeout in seconds.
        max_retries: Maximum retries after the first failure.
        base_backoff: Base backoff multiplier in seconds.
        retry_statuses: HTTP status codes that trigger a retry.

    Returns:
        (response, retries_used) -- response and number of retries used.

    Raises:
        requests.exceptions.*: on non-retryable failure or exhausted retries.
    """
    retries_used = 0
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp, retries_used
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", 0)
            retryable = status in retry_statuses or isinstance(
                exc,
                (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            )
            if retryable and attempt < max_retries:
                wait = base_backoff * (2 ** attempt)
                logger.debug(
                    "Retry %d/%d for %s (status=%s): waiting %.1fs",
                    attempt + 1, max_retries, url, status, wait,
                )
                time.sleep(wait)
                retries_used += 1
                continue
            raise
    # unreachable -- satisfies type checkers
    raise RuntimeError(f"bounded_get: unexpected exit after {max_retries} retries")
