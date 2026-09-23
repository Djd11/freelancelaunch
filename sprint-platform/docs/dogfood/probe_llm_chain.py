"""Is the LLM fallback chain actually alive? The app claims a 3-provider chain.

Tests provider #2 (OpenRouter) and #3 (local omniroute) the way services/llm.py
calls them. If both are dead, the 'chain' is really one provider and any hiccup
becomes a visible generation failure for the learner.
"""
import os, sys, time, json, urllib.request, socket
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from services import llm

prompt = "Reply with the single word OK"

print("--- provider 2: OpenRouter ---")
t = time.time()
try:
    out = llm._openrouter_call(prompt, 45)
    print(f"  elapsed {time.time()-t:.1f}s -> {repr(out)[:200]}")
except urllib.error.HTTPError as e:
    print(f"  elapsed {time.time()-t:.1f}s HTTPError {e.code}: {e.read().decode()[:300]}")
except Exception as e:
    print(f"  elapsed {time.time()-t:.1f}s EXC {type(e).__name__}: {str(e)[:300]}")

print("--- provider 3: local omniroute 127.0.0.1:20128 ---")
try:
    with socket.create_connection(("127.0.0.1", 20128), timeout=3):
        print("  socket: OPEN")
except OSError as e:
    print(f"  socket: CLOSED ({e})")

print("--- provider 1 latency distribution (5 real-ish calls) ---")
for i in range(5):
    t = time.time()
    try:
        out = llm._env_call("Write one short sentence about email automation. " * 3, 120)
        print(f"  call {i+1}: {time.time()-t:5.1f}s -> {len(out or '')} chars")
    except Exception as e:
        print(f"  call {i+1}: {time.time()-t:5.1f}s EXC {type(e).__name__}: {str(e)[:160]}")
