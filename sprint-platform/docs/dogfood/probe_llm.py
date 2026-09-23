"""Read-only probe: is the configured LLM provider actually answering?

Root-causes the 'No LLM provider answered' generation error seen on Day 1.
Does not modify app code or state.
"""
import os, sys, json, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

url = os.getenv("LLM_API_URL")
key = os.getenv("LLM_API_KEY")
model = os.getenv("LLM_MODEL")
print("LLM_API_URL :", url)
print("LLM_MODEL   :", model)
print("LLM_API_KEY set:", bool(key), "len", len(key or ""))
print("OPENROUTER key set:", bool(os.getenv("OPENROUTER_API_KEY")))

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def post(u, payload, headers, timeout=60):
    req = urllib.request.Request(u, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


if url:
    try:
        st, body = post(url, {"model": model, "messages": [{"role": "user", "content": "Reply with the single word OK"}]},
                        {"Authorization": f"Bearer {key}"})
        print("\n[primary] HTTP", st)
        print(body[:700])
    except urllib.error.HTTPError as e:
        print("\n[primary] HTTPError", e.code, e.read().decode()[:700])
    except Exception as e:
        print("\n[primary] EXC", type(e).__name__, str(e)[:500])

# what the app actually sends for a lesson (no system role, long prompt)
from services import llm
out = llm.call_llm("Reply with the single word OK", timeout=60)
print("\ncall_llm() ->", (repr(out)[:300] if out else "None  <-- generation would fail"))
