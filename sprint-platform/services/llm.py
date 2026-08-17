"""
llm — the one shared LLM provider chain (architecture.md §6, eng-spec §5).

call_llm() tries, in order:
  1. env-configured endpoint  (LLM_API_URL / LLM_API_KEY / LLM_MODEL)
  2. OpenRouter               (OPENROUTER_API_KEY)
  3. Omniroute local          (127.0.0.1:20128, socket probe)
  4. ❌ → None (caller raises LLMGenerationError — content is LLM-only,
     there is no deterministic content fallback; failures surface visibly).

Every step is wrapped in try/except with short timeouts so a missing key or
an unreachable provider never crashes a request — it becomes a visible
generation error instead of silent template content.
"""
import json
import os
import socket
import urllib.request


class LLMGenerationError(RuntimeError):
    """Raised when no provider answered or the output was unusable.

    Content generation is LLM-only: callers must NOT substitute deterministic
    templates. This exception surfaces the failure so the UI can show it.
    """


# Cloudflare fronting Zen/OpenRouter blocks default urllib signatures (HTTP 1010)
# — send a browser User-Agent so the app's LLM calls are not rejected.
_BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _post_json(url, payload, headers, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": _BROWSER_UA, **headers},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_choices(data):
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content or None


def _env_call(prompt, timeout):
    url = (os.getenv("LLM_API_URL") or "").strip()
    if not url:
        return None
    key = (os.getenv("LLM_API_KEY") or "").strip()
    model = (os.getenv("LLM_MODEL") or "gpt-4o-mini").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    data = _post_json(url, {"model": model, "messages": [{"role": "user", "content": prompt}]},
                      headers, timeout)
    return _extract_choices(data)


def _openrouter_call(prompt, timeout):
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return None
    data = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        {"model": (os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip(),
         "messages": [{"role": "user", "content": prompt}]},
        {"Authorization": f"Bearer {key}"}, timeout,
    )
    return _extract_choices(data)


def _omniroute_call(prompt, timeout):
    """Omniroute local (127.0.0.1:20128) — socket probe then OpenAI-style POST."""
    host, port = "127.0.0.1", 20128
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    data = _post_json(
        f"http://{host}:{port}/v1/chat/completions",
        {"model": "omniroute", "messages": [{"role": "user", "content": prompt}]},
        {}, timeout,
    )
    return _extract_choices(data)


def call_llm(prompt, timeout=3):
    """Return a completion string, or None when no provider answered."""
    for fn in (_env_call, _openrouter_call, _omniroute_call):
        try:
            out = fn(prompt, timeout)
        except Exception:
            out = None
        if out and str(out).strip():
            return str(out).strip()
    return None
