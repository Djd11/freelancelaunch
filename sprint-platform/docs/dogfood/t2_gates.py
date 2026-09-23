"""Round 3 — GATES re-test (blockers #1, #2, #3, #4).

Uses the legacy session's existing Phase-A sprint (which had empty rubrics in round 2)
plus a freshly started sprint.
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2gates")
from harness import Dogfood, BASE, ART

SID = "2e2566d8-ac2e-4a58-935d-e71c26a3c750"
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


d.goto(f"{BASE}/sprints")
if "Sign out" not in d.text():
    print("!! legacy session no longer authenticates; aborting gates", flush=True)
    sys.exit(1)

d.step("G1", "Empty-rubric days: honest state + Retry, never 'all 0 points'")
for n in (1, 2, 3, 4, 5):
    d.goto(f"{BASE}/sprints/{SID}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(600)
    except Exception:
        pass
    t = d.text()
    rec(f"day{n} task",
        zero_points=bool(re.search(r"all 0 points", t)),
        honest_state=bool(re.search(r"hasn.t been written|not been generated|checklist", t, re.I)),
        retry_btn=d.page.get_by_role("button", name=re.compile("retry", re.I)).count()
        + d.page.locator('a:has-text("Retry")').count(),
        checkboxes=d.page.locator('input[type=checkbox]').count(),
        submit_disabled=d.page.locator('form[action$="/copywork"] button[type=submit]').count()
        and d.page.locator('form[action$="/copywork"] button[type=submit]').first.is_disabled(),
        copy=[l.strip() for l in t.splitlines()
              if re.search(r"points are ticked|checklist|Retry|not been", l, re.I)][:3])
    if n in (2, 3):
        shot(f"94-t2-day{n}-empty-rubric")

d.step("G2", "submit_copywork on an empty rubric — honest flash?")
d.goto(f"{BASE}/sprints/{SID}/day/2")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=5000)
    d.page.wait_for_timeout(500)
except Exception:
    pass
inp = d.page.locator("#rubric_url")
if inp.count():
    inp.first.fill("https://github.com/example/t2-round3")
    d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
    fl = d.page.locator(".flash")
    rec("empty-rubric submit flash",
        flash=fl.inner_text().strip()[:260] if fl.count() else "(NO MESSAGE)",
        still_says_three=bool(re.search(r"all three rubric", fl.inner_text() if fl.count() else "", re.I)))
    shot("95-t2-empty-rubric-flash")
else:
    rec("empty-rubric submit", note="no #rubric_url input — form hidden while checklist missing")

d.step("G3", "GET /contract on a Phase-A sprint — Gate-A lock enforced?")
st = d.goto(f"{BASE}/sprints/{SID}/contract")
t = d.text()
rec("contract phase A", status=st, url=d.page.url.replace(BASE, ""),
    redirected_to_picker="/sprints" in d.page.url and "/contract" not in d.page.url,
    gate_flash=[l.strip() for l in t.splitlines() if "gate" in l.lower() or "unlock" in l.lower()][:3],
    contract_open="MOCK CONTRACT" in t.upper())
shot("96-t2-contract-gateA")

d.step("G4", "POST /complete refuses — sprint must stay active")
d.goto(f"{BASE}/sprints/{SID}")
before = [l.strip() for l in d.text().splitlines() if "SHIFT" in l][:1]
btn = d.page.locator('form[action$="/complete"] button')
rec("complete button present", n=btn.count(), phase_before=before)
if btn.count():
    btn.first.click(timeout=15000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    t = d.text()
    rec("after POST /complete", url=d.page.url.replace(BASE, ""),
        site_error="SITE ERROR" in t,
        refuses=bool(re.search(r"not eligible|can.t complete|before you|missing", t, re.I)),
        claims_finished_all_14=bool(re.search(r"finished all 14 days", t, re.I)),
        claims_badge=bool(re.search(r"badge is on your public profile", t, re.I)),
        flash=[l.strip() for l in t.splitlines() if "complete" in l.lower()][:4])
    shot("97-t2-complete-refused")
    d.goto(f"{BASE}/sprints/{SID}")
    t2 = d.text()
    rec("sprint still active after attempt",
        phase_after=[l.strip() for l in t2.splitlines() if "SHIFT" in l][:1],
        still_generating_or_active="Sprint complete" not in t2,
        status_line=[l.strip() for l in t2.splitlines() if "TRAINING LIVE" in l][:1])
    shot("98-t2-still-active")

d.step("G5", "Gate B — vague deliverable lists the missing requirements")
# Gate B needs Phase B; if contract is locked we verify the lock instead.
st = d.goto(f"{BASE}/sprints/{SID}/contract")
if "/contract" in d.page.url and "MOCK CONTRACT" in d.text().upper():
    ta = d.page.locator("textarea").first
    if ta.count():
        ta.fill("did some stuff, it was fine")
    url = d.page.locator('input[name=deliverable_url], #deliverable_url')
    if url.count():
        url.first.fill("https://github.com/example/vague")
    d.page.locator('form button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    fl = d.page.locator(".flash")
    rec("vague deliverable", flash=fl.inner_text().strip()[:400] if fl.count() else "(NO MESSAGE)")
    shot("99-t2-gateB-vague")
else:
    rec("vague deliverable", note="contract not reachable on this Phase-A sprint (expected lock)")

(ART / "t2gates.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:8], indent=1))
d.close()
print("GATES tests done")
