"""Tests for the single-source LLM config module (tests/features/llm-config.feature)."""
import sys
import os
import pytest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_config import (
    get_provider_chain,
    call_llm,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    DEFAULT_BASE_URL,
)


# ── LC1: provider chain ordering ────────────────────────────────────────────

def test_chain_has_primary_big_pickle_and_fallback_deepseek():
    chain = get_provider_chain()
    assert len(chain) == 2, f"expected 2 providers, got {len(chain)}"
    primary, fallback = chain
    assert primary["model"] == "big-pickle"
    assert "opencode" in primary["url"]
    assert fallback["model"] == "deepseek-v4-flash-free"
    assert "opencode" in fallback["url"]


# ── LC2: env vars override (Render deployment) ─────────────────────────────

def test_env_vars_override_primary_provider(monkeypatch):
    monkeypatch.setenv("LLM_API_URL", "https://example.com/v1/chat/completions")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "custom-model")
    chain = get_provider_chain()
    primary, fallback = chain
    assert primary["url"] == "https://example.com/v1/chat/completions"
    assert primary["api_key"] == "test-key"
    assert primary["model"] == "custom-model"
    # fallback reuses the same endpoint/key but deepseek model
    assert fallback["url"] == "https://example.com/v1/chat/completions"
    assert fallback["api_key"] == "test-key"
    assert fallback["model"] == "deepseek-v4-flash-free"


# ── LC3: fallback on primary failure ───────────────────────────────────────

def test_call_llm_falls_back_to_second_provider():
    responses = [
        mock.Mock(status_code=500, raise_for_status=mock.Mock(side_effect=Exception("500"))),
        mock.Mock(status_code=200, raise_for_status=mock.Mock(return_value=None),
                  json=lambda: {"choices": [{"message": {"content": "fallback OK"}}]}),
    ]
    with mock.patch("services.llm_config.httpx.post", side_effect=responses) as m:
        result = call_llm("test prompt", max_tokens=100)
    assert result == "fallback OK"
    assert m.call_count == 2  # tried primary, then fallback


# ── LC4: all providers fail → None ─────────────────────────────────────────

def test_call_llm_returns_none_when_all_fail():
    fail = mock.Mock(raise_for_status=mock.Mock(side_effect=Exception("boom")))
    with mock.patch("services.llm_config.httpx.post", return_value=fail):
        result = call_llm("test prompt", max_tokens=100)
    assert result is None


# ── LC5: no key → None fast (no hang) ─────────────────────────────────────

def test_call_llm_no_key_returns_none_fast(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    # Hermes config missing → no key anywhere
    with mock.patch("services.llm_config._load_hermes_config", return_value=(None, None, None)):
        with mock.patch("services.llm_config.httpx.post") as m:
            result = call_llm("test prompt", max_tokens=100)
    assert result is None
    m.assert_not_called()  # never even tried an HTTP call


# ── constants sanity ───────────────────────────────────────────────────────

def test_defaults_are_big_pickle_and_deepseek():
    assert PRIMARY_MODEL == "big-pickle"
    assert FALLBACK_MODEL == "deepseek-v4-flash-free"
    assert DEFAULT_BASE_URL.startswith("https://opencode.ai/zen/v1")
