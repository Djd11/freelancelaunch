"""LLM_API_URL must accept both a base URL and the full chat-completions path.

Operator-facing symptom this guards against (2026-09-17): Render was configured
with LLM_API_URL=https://…trycloudflare.com/v1 — a *base* URL. _env_call POSTed
to it verbatim, the endpoint answered HTTP 405 (no route at POST /v1), and every
lesson generation failed with "No LLM provider answered for the day's lesson".
"""
import os
from unittest.mock import patch

from services.llm import _chat_url, _env_call


class TestChatUrlNormalization:
    def test_full_chat_completions_url_passes_through(self):
        url = "https://tunnel.example.com/v1/chat/completions"
        assert _chat_url(url) == url

    def test_base_v1_url_gets_chat_completions_appended(self):
        assert (_chat_url("https://tunnel.example.com/v1")
                == "https://tunnel.example.com/v1/chat/completions")

    def test_base_v1_url_with_trailing_slash_is_normalized(self):
        assert (_chat_url("https://tunnel.example.com/v1/")
                == "https://tunnel.example.com/v1/chat/completions")

    def test_bare_host_gets_v1_chat_completions(self):
        assert (_chat_url("https://tunnel.example.com")
                == "https://tunnel.example.com/v1/chat/completions")

    def test_other_paths_pass_through_unchanged(self):
        # A URL that already names a resource is never second-guessed.
        url = "https://api.example.com/custom/llm-route"
        assert _chat_url(url) == url


class TestEnvCallUsesNormalizedUrl:
    def test_env_call_posts_to_chat_completions_for_base_url(self):
        posted = {}

        def fake_post_json(url, payload, headers, timeout):
            posted["url"] = url
            return {"choices": [{"message": {"content": "ok"}}]}

        env = {
            "LLM_API_URL": "https://tunnel.example.com/v1",
            "LLM_API_KEY": "sk-test",
            "LLM_MODEL": "auto/best-chat",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("services.llm._post_json", side_effect=fake_post_json):
                assert _env_call("hello", timeout=5) == "ok"
        assert posted["url"] == "https://tunnel.example.com/v1/chat/completions"
