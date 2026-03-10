"""Tests for elsian.acquire._http — BL-066 shared HTTP helpers."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from elsian.acquire._http import (
    _DEFAULT_EU_UA,
    _DEFAULT_UA,
    _UA_MAX_LEN,
    bounded_get,
    get_eu_user_agent,
    get_user_agent,
    load_json_ttl,
)


# ── get_user_agent ────────────────────────────────────────────────────

class TestGetUserAgent:
    def test_returns_default_when_env_absent(self, monkeypatch):
        monkeypatch.delenv("ELSIAN_USER_AGENT", raising=False)
        ua = get_user_agent()
        assert ua == _DEFAULT_UA
        assert "ELSIAN-INVEST" in ua

    def test_respects_env_var(self, monkeypatch):
        monkeypatch.setenv("ELSIAN_USER_AGENT", "MyBot/1.0 (test)")
        assert get_user_agent() == "MyBot/1.0 (test)"

    def test_rejects_env_value_over_max_len(self, monkeypatch):
        monkeypatch.setenv("ELSIAN_USER_AGENT", "X" * (_UA_MAX_LEN + 1))
        assert get_user_agent() == _DEFAULT_UA

    def test_rejects_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("ELSIAN_USER_AGENT", "   ")
        assert get_user_agent() == _DEFAULT_UA


class TestGetEuUserAgent:
    def test_returns_default_when_env_absent(self, monkeypatch):
        monkeypatch.delenv("ELSIAN_EU_USER_AGENT", raising=False)
        ua = get_eu_user_agent()
        assert ua == _DEFAULT_EU_UA
        assert "Mozilla" in ua

    def test_respects_env_var(self, monkeypatch):
        monkeypatch.setenv("ELSIAN_EU_USER_AGENT", "CustomEU/1.0")
        assert get_eu_user_agent() == "CustomEU/1.0"

    def test_rejects_env_value_over_max_len(self, monkeypatch):
        monkeypatch.setenv("ELSIAN_EU_USER_AGENT", "X" * (_UA_MAX_LEN + 1))
        assert get_eu_user_agent() == _DEFAULT_EU_UA


# ── load_json_ttl ─────────────────────────────────────────────────────

class TestLoadJsonTtl:
    def test_fetches_and_caches(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ELSIAN_CACHE_DIR", str(tmp_path))

        payload = {"key": "value"}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = payload

        session = MagicMock()
        session.get.return_value = resp

        data, hit = load_json_ttl(
            "https://example.com/data.json",
            session=session,
            headers={},
            ttl_seconds=3600,
        )
        assert data == payload
        assert hit is False
        assert session.get.call_count == 1

        # Second call: should hit the cache — no second network call
        data2, hit2 = load_json_ttl(
            "https://example.com/data.json",
            session=session,
            headers={},
            ttl_seconds=3600,
        )
        assert data2 == payload
        assert hit2 is True
        assert session.get.call_count == 1  # still 1: no new fetch

    def test_stale_cache_refetches(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ELSIAN_CACHE_DIR", str(tmp_path))

        import hashlib
        url = "https://example.com/stale.json"
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        data_file = tmp_path / f"json_{url_hash}.json"
        meta_file = tmp_path / f"json_{url_hash}.ts"

        # Write stale cache (5 hours ago)
        data_file.write_text(json.dumps({"old": True}), encoding="utf-8")
        meta_file.write_text(str(time.time() - 18_001), encoding="utf-8")

        new_payload = {"new": True}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = new_payload
        session = MagicMock()
        session.get.return_value = resp

        data, hit = load_json_ttl(
            url, session=session, headers={}, ttl_seconds=3600
        )
        assert data == new_payload
        assert hit is False


# ── bounded_get ───────────────────────────────────────────────────────

class TestBoundedGet:
    def _make_session(self, responses):
        """Build a mock session whose get() returns *responses* in sequence."""
        session = MagicMock(spec=requests.Session)
        session.get.side_effect = responses
        return session

    def test_success_on_first_attempt(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        session = self._make_session([resp])

        result, retries = bounded_get(
            "https://example.com/",
            session=session,
            headers={},
            max_retries=3,
        )
        assert result is resp
        assert retries == 0
        assert session.get.call_count == 1

    def test_retries_on_500_and_succeeds(self, monkeypatch):
        monkeypatch.setattr("elsian.acquire._http.time.sleep", lambda _: None)

        err_resp = MagicMock()
        err_resp.status_code = 500
        http_err = requests.exceptions.HTTPError(response=err_resp)

        ok_resp = MagicMock()
        ok_resp.raise_for_status.return_value = None

        # First call raises HTTPError(500), second succeeds
        def side_effect(*args, **kwargs):
            if side_effect.count == 0:
                side_effect.count += 1
                raise http_err
            return ok_resp

        side_effect.count = 0

        session = MagicMock(spec=requests.Session)
        session.get.side_effect = side_effect

        result, retries = bounded_get(
            "https://example.com/",
            session=session,
            headers={},
            max_retries=2,
            base_backoff=0.01,
        )
        assert result is ok_resp
        assert retries == 1

    def test_exhausts_retries_and_raises(self, monkeypatch):
        monkeypatch.setattr("elsian.acquire._http.time.sleep", lambda _: None)

        err_resp = MagicMock()
        err_resp.status_code = 503
        http_err = requests.exceptions.HTTPError(response=err_resp)

        session = MagicMock(spec=requests.Session)
        session.get.side_effect = http_err

        with pytest.raises(requests.exceptions.HTTPError):
            bounded_get(
                "https://example.com/",
                session=session,
                headers={},
                max_retries=2,
                base_backoff=0.01,
            )
        assert session.get.call_count == 3  # 1 original + 2 retries

    def test_non_retryable_status_raises_immediately(self, monkeypatch):
        monkeypatch.setattr("elsian.acquire._http.time.sleep", lambda _: None)

        err_resp = MagicMock()
        err_resp.status_code = 404
        http_err = requests.exceptions.HTTPError(response=err_resp)

        session = MagicMock(spec=requests.Session)
        session.get.side_effect = http_err

        with pytest.raises(requests.exceptions.HTTPError):
            bounded_get(
                "https://example.com/",
                session=session,
                headers={},
                max_retries=3,
                base_backoff=0.01,
            )
        # Should fail immediately (no retries for 404)
        assert session.get.call_count == 1
