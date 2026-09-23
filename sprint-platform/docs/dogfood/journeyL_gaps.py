"""Journey L — the remaining gaps: a properly-generated day's Task tab, the video
player's real markup, request-a-sprint, Gate B submit, and accessibility.
"""
import sys, os, json, time, urllib.request, urllib.parse, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyL")
from harness import Dogfood, BASE, ART, SHOTS

B = json.load(open(ART / "journeyB.json"))
sid, email = B["sprint_id"], B["email"]
d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def STAMPS():
    return d.page.evaluate("""() => [...document.querySelectorAll('.stamp')].map(e =>
        ({label: e.innerText.trim(), lit: e.classList.contains('ok')}))""")


def shot(n):
    d.shot(n)
    print(f"    [shot] shots/{n}.png", flush=True)


d.goto(f"{BASE}/auth/login")
d.page.fill("#email", email)
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=40000)

# ------------------------------------------------ generated day's Task tab
d.step("L1", "Day 3 (content generated) — Task tab: steps, rubric, stamps")
d.goto(f"{BASE}/sprints/{sid}/day/3")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=6000)
    d.page.wait_for_timeout(700)
except Exception as e:
    rec("tab err", err=str(e)[:120])
body = d.text()
rec("day3 task", checkboxes=d.page.locator('input[type=checkbox]').count(),
    steps=d.page.locator("#task-panel ol li, ol li").count(),
    vacuous=[l.strip() for l in body.splitlines() if "points are ticked" in l][:1],
    stamps=STAMPS())
shot("40-day3-task")

# ------------------------------------------------ tick rubric and submit
d.step("L2", "Tick every rubric item, then submit a build link (the honest path)")
boxes = d.page.locator('input[type=checkbox]')
n = boxes.count()
rec("ticking", n=n)
for i in range(n):
    try:
        boxes.nth(i).check(timeout=4000)
        d.page.wait_for_timeout(400)
    except Exception as e:
        rec("tick error", i=i, err=str(e)[:150])
d.page.wait_for_timeout(1200)
inp = d.page.locator("#rubric_url")
if inp.count():
    inp.first.fill("https://github.com/example/checkout-welcome-flow")
    d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    rec("after honest submit", flash=d.page.locator(".flash").inner_text().strip()[:250]
        if d.page.locator(".flash").count() else "(none)",
        stamps=STAMPS())
    shot("41-day3-after-honest-submit")

# ------------------------------------------------ player markup
d.step("L3", "The 'TwoPanel video player' — what actually renders")
d.goto(f"{BASE}/sprints/{sid}/day/3")
p = d.page.evaluate("""() => {
  const audios=[...document.querySelectorAll('audio')].map(a=>({src:a.src, ready:a.readyState, err:a.error?a.error.code:null}));
  const kinetic=[...document.querySelectorAll('*')].filter(e=>/^[A-Z][a-z]?\\S{25,}$/.test((e.innerText||'').trim().split('\\n')[0]||''));
  return {canvas:document.querySelectorAll('canvas').length, video:document.querySelectorAll('video').length,
          audio:audios, js:[...document.querySelectorAll('script[src]')].map(s=>s.src),
          kineticSuspects: kinetic.slice(0,3).map(e=>e.innerText.trim().slice(0,90))}; }""")
rec("player", **p)
# do the voiceover URLs resolve?
for a in (p.get("audio") or [])[:3]:
    try:
        req = urllib.request.Request(a["src"], method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            rec("voiceover HEAD", status=r.status, url=a["src"][:110])
    except Exception as e:
        rec("voiceover HEAD", error=str(e)[:120], url=a["src"][:110])

d.step("L3b", "Kinetic text spacing (no-space rendering bug?)")
kt = d.page.evaluate("""() => {
  const els=[...document.querySelectorAll('div,span,p,h2')].filter(e=>{
    const t=(e.innerText||'').trim(); return t.length>40 && !/\\s/.test(t.slice(0,40));});
  return els.slice(0,3).map(e=>e.innerText.trim().slice(0,120)); }""")
rec("no-space text blocks", blocks=kt)

# ------------------------------------------------ request a sprint
d.step("L4", "Request a sprint that doesn't exist")
d.goto(f"{BASE}/sprints")
d.page.locator('input[name="skill"]').fill("Shopify Apps")
d.page.locator('form[action="/sprints/request"] button').first.click()
d.page.wait_for_load_state("domcontentloaded", timeout=30000)
d.page.wait_for_timeout(800)
body = d.text()
rec("request sprint", url=d.page.url.replace(BASE, ""),
    flash=d.page.locator(".flash").inner_text().strip()[:200] if d.page.locator(".flash").count() else "(no confirmation)",
    appears="Shopify Apps" in body or "shopify" in body.lower())
shot("42-after-request-sprint")

# ------------------------------------------------ Gate B submit with nothing
d.step("L5", "Gate B: submit the Mock Contract with no case study")
d.goto(f"{BASE}/sprints/{sid}/contract")
btn = d.page.locator('form[action$="/contract/submit"] button')
rec("contract submit control", n=btn.count())
if btn.count():
    btn.first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    rec("gate B empty submit", flash=d.page.locator(".flash").inner_text().strip()[:250]
        if d.page.locator(".flash").count() else "(no message)", url=d.page.url.replace(BASE, ""))
    shot("43-gateB-empty-submit")
    body = d.text()
    rec("gate B state", lines=[l.strip() for l in body.splitlines() if "GATE" in l.upper()][:5])

d.step("L5b", "Save a case study, then submit again (Gate B honest path)")
d.goto(f"{BASE}/sprints/{sid}/contract")
cs = d.page.locator('form[action$="/case-study"]')
if cs.count():
    for name, val in [("title", "Checkout recovery flow for a DTC skincare brand"),
                      ("problem", "The store lost 30% of revenue at checkout and had no recovery emails."),
                      ("solution", "Built a Klaviyo Started Checkout flow with conditional splits and dynamic tags."),
                      ("result", "Recovered 12% of abandoned carts in the first two weeks after launch.")]:
        loc = cs.first.locator(f'[name="{name}"]')
        if loc.count():
            loc.first.fill(val)
    cs.first.locator('button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
    rec("case study saved", flash=d.page.locator(".flash").inner_text().strip()[:200]
        if d.page.locator(".flash").count() else "(no message)")
    shot("44-case-study-saved")
    btn = d.page.locator('form[action$="/contract/submit"] button')
    if btn.count():
        inp = d.page.locator('input[name="submission_url"]')
        if inp.count():
            inp.first.fill("https://github.com/example/checkout-recovery")
        btn.first.click()
        d.page.wait_for_load_state("domcontentloaded", timeout=40000)
        d.page.wait_for_timeout(2000)
        body = d.text()
        rec("gate B after honest submit", flash=d.page.locator(".flash").inner_text().strip()[:250]
            if d.page.locator(".flash").count() else "(no message)",
            gate_lines=[l.strip() for l in body.splitlines() if "GATE" in l.upper() or "PHASE C" in l.upper()][:6])
        shot("45-gateB-honest-submit")

# ------------------------------------------------ accessibility + a11y basics
d.step("L6", "Accessibility basics on the money path")
for path in ["/", f"/sprints/{sid}", f"/sprints/{sid}/day/3", "/auth/signup"]:
    d.goto(path)
    a = d.page.evaluate("""() => {
      const inputs=[...document.querySelectorAll('input,select,textarea')];
      const unlabeled=inputs.filter(i=>{
        if(i.type==='hidden') return false;
        const id=i.id; const lab=id&&document.querySelector(`label[for="${id}"]`);
        return !(lab||i.getAttribute('aria-label')||i.closest('label'));});
      const btns=[...document.querySelectorAll('button,a')].filter(b=>!(b.innerText||'').trim()&&!b.getAttribute('aria-label'));
      return {unlabeled:unlabeled.length, totalInputs:inputs.filter(i=>i.type!=='hidden').length,
              unnamedControls:btns.length, h1:document.querySelectorAll('h1').length,
              lang:document.documentElement.lang||null}; }""")
    rec(f"a11y {path}", **a)

# ------------------------------------------------ concurrent generation load
d.step("L7", "Concurrency: 12 parallel polls of /generation (dashboard auto-poll x users)")
cookie = d.ctx.cookies()[0]["value"]
codes = []


def hit(i):
    req = urllib.request.Request(f"{BASE}/sprints/{sid}/generation", headers={"Cookie": f"session={cookie}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return "ERR"


import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    codes = list(ex.map(hit, range(12)))
rec("parallel generation polls", codes=codes, non200=sum(1 for c in codes if c != 200))

(ART / "journeyL.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:12], indent=1))
d.close()
print("Journey L done")
