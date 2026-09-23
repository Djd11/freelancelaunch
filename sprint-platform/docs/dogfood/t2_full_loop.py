"""Round 3 — THE MONEY TEST: is the 14-day loop actually completable now?

Round 2 verdict: Gate A unreachable (#1) and Gate B never passing (#4) meant Phase C
could never be reached on any sprint. This walks the honest path on a fresh sprint:
  days 2-5 rubrics -> submit links -> Gate A pass -> contract ->
  vague deliverable (expect flash listing missing requirements) ->
  case study P/S/R -> Gate B flip to pass (order-independence) -> proposals unlock.
"""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2loop")
from harness import Dogfood, BASE, ART

started = json.load(open(ART / "t2gen_started.json"))
# pick the sprint whose copy-work rubrics actually generated
CAND = [v["sprint_id"] for v in started.values()]
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


def stamps():
    return d.page.evaluate("""() => [...document.querySelectorAll('.stamp')].map(e =>
        ({label: e.innerText.trim(), lit: e.classList.contains('ok')}))""")


def flash():
    f = d.page.locator(".flash")
    return f.inner_text().strip()[:300] if f.count() else "(NO MESSAGE)"


sid = None
d.step("L0", "Choose a sprint whose copy-work rubrics generated")
for c in CAND:
    ok = {}
    for n in (2, 3, 4, 5):
        d.goto(f"{BASE}/sprints/{c}/day/{n}")
        try:
            d.page.locator('button:text-is("Task")').first.click(timeout=5000)
            d.page.wait_for_timeout(500)
        except Exception:
            pass
        ok[n] = d.page.locator('input[type=checkbox]').count()
    rec(f"rubrics {c[:8]}", boxes_by_day=ok)
    if all(v >= 3 for v in ok.values()):
        sid = c
        break
if not sid:
    rec("no sprint has full rubrics yet", note="Gate A still unreachable on every sprint")
    (ART / "t2loop.json").write_text(json.dumps(R, indent=1))
    d.close()
    sys.exit(0)

print("USING SPRINT", sid, flush=True)
d.step("L1", "Honest Phase A: tick every rubric + submit a link on days 2-5")
for n in (2, 3, 4, 5):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(600)
    except Exception:
        pass
    boxes = d.page.locator('input[type=checkbox]')
    for i in range(boxes.count()):
        try:
            boxes.nth(i).check(timeout=3000)
        except Exception:
            pass
    d.page.wait_for_timeout(600)
    inp = d.page.locator("#rubric_url")
    if inp.count():
        inp.first.fill(f"https://github.com/example/t2-day{n}")
        d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=40000)
        d.page.wait_for_timeout(1200)
        rec(f"day{n} submit", boxes=boxes.count(), flash=flash(), stamps=stamps())
        shot(f"b1-t2-day{n}-submitted")
    # punch the day
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    try:
        d.page.locator('button:text-is("Task")').first.click(timeout=5000)
        d.page.wait_for_timeout(500)
    except Exception:
        pass
    c = d.page.locator('form[action$="/complete"] button:visible')
    if c.count():
        c.first.click(timeout=10000)
        d.page.wait_for_load_state("domcontentloaded", timeout=40000)
        d.page.wait_for_timeout(1200)
        rec(f"day{n} completed", meter=[l.strip() for l in d.text().splitlines()
                                         if "POSTINGS" in l.upper() or "unlocked" in l.lower()][:3])

d.step("L2", "Gate A verdict")
d.goto(f"{BASE}/sprints/{sid}")
t = d.text()
rec("gate A", phase=[l.strip() for l in t.splitlines() if "SHIFT" in l][:2],
    stamps=stamps(),
    gateA_pass=bool(re.search(r"Gate A[^\n]*(passed|✓)", t, re.I)),
    shiftB_locked="Unlocks when Phase A passes verification" in t,
    flash=flash())
shot("b2-t2-gateA-verdict")

d.step("L3", "Contract access after Gate A")
st = d.goto(f"{BASE}/sprints/{sid}/contract")
t = d.text()
rec("contract", status=st, url=d.page.url.replace(BASE, ""),
    open_page="MOCK CONTRACT" in t.upper(), flash=flash(),
    gate_flash=[l.strip() for l in t.splitlines() if "Gate A" in l][:2])
shot("b3-t2-contract-after-gateA")

if "MOCK CONTRACT" in t.upper():
    d.step("L4", "Gate B — vague deliverable must list the missing requirements")
    tas = d.page.locator("textarea")
    rec("textareas on contract page", n=tas.count())
    if tas.count():
        tas.first.fill("did some stuff, it was fine")
    u = d.page.locator('input[name=deliverable_url], #deliverable_url')
    if u.count():
        u.first.fill("https://github.com/example/vague")
    d.page.locator('form[method=post] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    rec("vague submit", flash=flash())
    shot("b4-t2-gateB-vague")

    d.step("L5", "Gate B — then a proper Problem/Solution/Result case study (order independence)")
    d.goto(f"{BASE}/sprints/{sid}/contract")
    tas = d.page.locator("textarea")
    if tas.count() >= 2:
        tas.nth(0).fill("Problem: the client's abandoned-cart revenue was unmeasured and no "
                        "recovery flow existed; 62% of checkouts were lost with no follow-up.")
        tas.nth(1).fill("Solution: built a 3-email Klaviyo checkout-recovery flow with a "
                        "Started Checkout trigger, a conditional split on 'Number of Orders' "
                        "equals 0, and a 1-hour delay before the first send.")
        if tas.count() >= 3:
            tas.nth(2).fill("Result: recovered 11% of abandoned carts in two weeks, about "
                            "$4.2k attributed revenue, and the client kept me on retainer.")
    else:
        for i in range(tas.count()):
            tas.nth(i).fill("Problem: unmeasured abandoned carts. Solution: 3-email Klaviyo "
                            "recovery flow with Started Checkout trigger and conditional split. "
                            "Result: 11% recovered, ~$4.2k attributed revenue.")
    u = d.page.locator('input[name=deliverable_url], #deliverable_url')
    if u.count():
        u.first.fill("https://github.com/example/real-deliverable")
    d.page.locator('form[method=post] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(2500)
    rec("full submit", flash=flash())
    shot("b5-t2-gateB-full")

    d.step("L6", "Gate B state after the honest path")
    d.goto(f"{BASE}/sprints/{sid}/contract")
    t = d.text()
    rec("gate B after", gateB=[l.strip() for l in t.splitlines() if re.search(r"gate b", l, re.I)][:3],
        pending="PENDING" in t.upper(), passed=bool(re.search(r"passed|verified", t, re.I)),
        flash=flash())
    shot("b6-t2-gateB-state")

    d.step("L7", "Phase C / proposals unlocked?")
    st = d.goto(f"{BASE}/sprints/{sid}/proposals")
    t = d.text()
    rec("proposals", status=st, locked="locked" in t.lower(),
        open_page=bool(re.search(r"first.?bid|proposal", t, re.I)),
        flash=flash(), lines=[l.strip() for l in t.splitlines() if l.strip()][:14])
    shot("b7-t2-proposals")

    d.step("L8", "Final completion attempt on a legitimately finished sprint")
    d.goto(f"{BASE}/sprints/{sid}")
    btn = d.page.locator('form[action$="/complete"] button')
    if btn.count():
        btn.first.click(timeout=15000)
        d.page.wait_for_load_state("domcontentloaded", timeout=40000)
        d.page.wait_for_timeout(2000)
        t = d.text()
        rec("complete after gates", flash=flash(),
            claims_all_14=bool(re.search(r"finished all 14 days", t, re.I)),
            claims_badge=bool(re.search(r"badge is on your public profile", t, re.I)))
        shot("b8-t2-complete-after-gates")

(ART / "t2loop.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:8], indent=1))
d.close()
print("LOOP test done")
