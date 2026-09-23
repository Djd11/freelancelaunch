"""Distinguish a real /generation concurrency bug from a currently-unhealthy server.

Runs sequential polls, then small concurrent bursts, on BOTH an active sprint and the
zero-work 'completed' sprint, with the HTTP status of every single request.
"""
import sys, os, json, time, urllib.request, urllib.error
import concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import BASE, ART

cookie = None
import json as _j
st = _j.load(open(ART / "state.json"))
cookie = [c["value"] for c in st["cookies"] if c["name"] == "session"][0]

sid_done = open(ART / "sprint_id_rj.txt").read().strip()          # zero-work completed
sid_active = open(ART / "sprint_id_v.txt").read().strip()         # active sprint


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Cookie": f"session={cookie}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__


print("== sequential baseline ==", flush=True)
for label, sid in [("completed", sid_done), ("active", sid_active)]:
    codes = [get(f"/sprints/{sid}/generation") for _ in range(5)]
    print(f"  {label:9s} /generation x5 sequential : {codes}", flush=True)
    time.sleep(2)

print("== concurrent bursts ==", flush=True)
for k in (2, 4, 8, 12):
    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as ex:
        codes = list(ex.map(lambda _: get(f"/sprints/{sid_active}/generation"), range(k)))
    print(f"  active  k={k:2d} : {codes}  non200={sum(1 for c in codes if c != 200)}", flush=True)
    time.sleep(3)

print("== other routes under the same burst (is it route-specific?) ==", flush=True)
for k in (8,):
    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as ex:
        dash = list(ex.map(lambda _: get(f"/sprints/{sid_active}"), range(k)))
    print(f"  dashboard k={k} : {dash}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as ex:
        home = list(ex.map(lambda _: get("/"), range(k)))
    print(f"  landing   k={k} : {home}", flush=True)

print("== the completed sprint's dashboard (single request) ==", flush=True)
print("  GET /sprints/<completed> ->", get(f"/sprints/{sid_done}"), flush=True)
print("  GET /sprints/<active>    ->", get(f"/sprints/{sid_active}"), flush=True)
