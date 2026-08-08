"""
LLM configuration — SINGLE SOURCE OF TRUTH.

Every LLM provider setting in FreelanceLaunch is resolved here.
No other module should hardcode URLs, models, or API keys.

Resolution order:
  1. Environment variables (Render deployment):
       LLM_API_URL, LLM_API_KEY, LLM_MODEL, LLM_FALLBACK_MODEL
  2. Hermes config (~/.hermes/config.yaml) — local dev, OpenCode.ai provider

Provider chain (primary → fallback):
  - Primary:  big-pickle  via OpenCode.ai
  - Fallback: deepseek-v4-flash-free via OpenCode.ai
  Both hit the same endpoint with the same key — only the model differs,
  which is why a single env-var override covers both.
"""
import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

PRIMARY_MODEL = "big-pickle"
FALLBACK_MODEL = "deepseek-v4-flash-free"
DEFAULT_BASE_URL = "https://opencode.ai/zen/v1"
DEFAULT_TIMEOUT = 60  # seconds per LLM call

# Persistent pooled client — opencode.ai's edge refuses rapid NEW TCP
# connections (httpx.post per call → intermittent Errno 111). Reusing a
# pooled client keeps connections alive and avoids the refusal.
_client = httpx.Client(timeout=DEFAULT_TIMEOUT)

# System prompt shared by curriculum generation calls
CURRICULUM_SYSTEM_PROMPT = (
    "You are a curriculum designer and learning science expert. "
    "Output structured lesson content with clear section headings."
)


def _load_hermes_config():
    """Read OpenCode.ai provider settings from ~/.hermes/config.yaml.

    Returns (base_url, api_key, default_model) or (None, None, None).
    """
    try:
        import yaml
        path = os.path.expanduser("~/.hermes/config.yaml")
        if not os.path.exists(path):
            return None, None, None
        with open(path) as f:
            hermes = yaml.safe_load(f) or {}
        mc = hermes.get("model", {}) or {}
        base_url = mc.get("base_url", "")
        api_key = mc.get("api_key", "")
        default_model = mc.get("default", PRIMARY_MODEL)
        return base_url, api_key, default_model
    except Exception as e:
        logger.warning(f"Failed to load Hermes config: {e}")
        return None, None, None


def _resolve_credentials():
    """Return (base_url, api_key, primary_model, fallback_model).

    Env vars win (Render); Hermes config is the local fallback.
    The fallback model comes from LLM_FALLBACK_MODEL or defaults to deepseek.
    """
    env_url = os.environ.get("LLM_API_URL", "").strip()
    env_key = os.environ.get("LLM_API_KEY", "").strip()
    env_model = os.environ.get("LLM_MODEL", "").strip()
    env_fallback = os.environ.get("LLM_FALLBACK_MODEL", "").strip()

    hermes_url, hermes_key, _ = _load_hermes_config()

    base_url = env_url or hermes_url or DEFAULT_BASE_URL
    api_key = env_key or hermes_key or ""
    # Primary is ALWAYS big-pickle (unless env LLM_MODEL overrides for Render).
    # The Hermes config "default" does NOT dictate the curriculum model —
    # the chain is big-pickle primary, deepseek fallback by design.
    primary_model = env_model or PRIMARY_MODEL
    fallback_model = env_fallback or FALLBACK_MODEL

    # Normalize: accept a bare base URL or a full /chat/completions URL
    if not base_url.endswith("/chat/completions"):
        base_url = base_url.rstrip("/") + "/chat/completions"

    return base_url, api_key, primary_model, fallback_model


def get_provider_chain():
    """Return the ordered provider list, primary first.

    Each entry: {"name", "url", "api_key", "model"}
    When no key is configured, returns [] (callers skip LLM → fallback content).
    """
    base_url, api_key, primary_model, fallback_model = _resolve_credentials()
    if not base_url or not api_key:
        logger.warning("No LLM API key configured — provider chain empty")
        return []

    return [
        {
            "name": f"opencode:{primary_model}",
            "url": base_url,
            "api_key": api_key,
            "model": primary_model,
        },
        {
            "name": f"opencode:{fallback_model}",
            "url": base_url,
            "api_key": api_key,
            "model": fallback_model,
        },
    ]


def get_primary_provider():
    """Return the first provider dict, or None."""
    chain = get_provider_chain()
    return chain[0] if chain else None


def call_llm(prompt: str, system: Optional[str] = None, max_tokens: int = 4096,
             temperature: float = 0.7, timeout: Optional[int] = None,
             model: Optional[str] = None) -> Optional[str]:
    """Call the LLM, trying each provider in the chain in order.

    Returns the first successful response's text, or None if all fail
    (callers then fall back to structured content). Never raises.
    """
    chain = get_provider_chain()
    if not chain:
        return None

    system_prompt = system or CURRICULUM_SYSTEM_PROMPT
    timeout = timeout or int(os.environ.get("LLM_TIMEOUT", DEFAULT_TIMEOUT))

    # If a specific model is requested, prepend a provider for it and let the
    # rest of the chain act as fallback (big-pickle → deepseek on failure).
    if model and model != chain[0]["model"]:
        first = dict(chain[0])
        first["model"] = model
        first["name"] = f"opencode:{model}"
        chain = [first] + chain

    for provider in chain:
        try:
            headers = {"Content-Type": "application/json"}
            if provider["api_key"]:
                headers["Authorization"] = f"Bearer {provider['api_key']}"

            payload = {
                "model": provider["model"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            resp = _client.post(provider["url"], headers=headers, json=payload)
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            logger.info(f"LLM OK via {provider['name']} ({len(text)} chars)")
            return text
        except Exception as e:
            logger.warning(f"LLM failed via {provider['name']}: {e}")
            continue

    return None
