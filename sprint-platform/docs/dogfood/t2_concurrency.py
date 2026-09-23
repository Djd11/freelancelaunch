"""Round 3 — CONCURRENCY re-test (blocker #6).

Same harness as round 2 (which produced 11/12 and 12/12 500s), now against the
request-scoped Supabase client. Bursts on /generation and the dashboard.
"""
import sys, os, json, time, urllib.request, urllib.error, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import BASE, ART

ck = [c["value"] for c in json.load(open(ART / "state.json"))["cookies"] if c["name"] == "session"][0]
sid = "2e2566d8-ac2e-4a58-935d-e71c26a3c750"   # owned by the legacy session's user
HDR = {"Cookie": f"session={ck}"}


def get(p):
    req = urllib.request.Request(BASE + p, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return type(e).__name__


def burst(p, k):
    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as ex:
        return list(ex.map(lambda _: get(p), range(k)))


total_500 = 0
total_req = 0
print(f"sprint {sid}\n", flush=True)
for label, path in [("generation", f"/sprints/{sid}/generation"),
                    ("dashboard", f"/sprints/{sid}"),
                    ("day/3", f"/sprints/{sid}/day/3"),
                    ("landing(anonymous)", "/")]:
    for k in (1, 2, 6, 12):
        codes = burst(path, k)
        bad = sum(1 for c in codes if c != 200)
        total_500 += bad
        total_req += k
        print(f"  {label:19s} k={k:2d} -> {codes}  non200={bad}", flush=True)
        time.sleep(2)

print(f"\nTOTAL: {total_500} non-200 out of {total_req} requests", flush=True)
json.dump({"total_non200": total_500, "total_requests": total_req},
          open(ART / "t2concurrency.json", "w"), indent=1)
