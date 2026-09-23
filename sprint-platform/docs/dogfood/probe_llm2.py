"""Pinpoint why services.llm.call_llm() returns None while the provider answers 200."""
import os, sys, json, traceback, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from services import llm

prompt = "Reply with the single word OK"
print("LLM_API_URL =", os.getenv("LLM_API_URL"))

# 1) call the module's own _env_call, but let the exception escape
url = os.getenv("LLM_API_URL").strip()
key = os.getenv("LLM_API_KEY").strip()
model = os.getenv("LLM_MODEL").strip()
payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json",
                                      "User-Agent": llm._BROWSER_UA,
                                      "Authorization": f"Bearer {key}"})
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read().decode()
    print("raw ok, len", len(raw))
    data = json.loads(raw)
    print("parsed choices[0].message.content =", repr((data["choices"][0]["message"].get("content"))))
    print("_extract_choices ->", repr(llm._extract_choices(data)))
except Exception:
    traceback.print_exc()

# 2) the module path, with the swallow removed
try:
    out = llm._env_call(prompt, 90)
    print("\n_env_call ->", repr(out))
except Exception:
    print("\n_env_call RAISED:")
    traceback.print_exc()

# 3) full chain
print("\ncall_llm ->", repr(llm.call_llm(prompt, timeout=90)))
