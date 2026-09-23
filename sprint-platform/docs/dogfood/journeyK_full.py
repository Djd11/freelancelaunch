"""Journey K — the clean, complete first-run walkthrough on a PRISTINE account.

Follows the captain's numbered journey exactly, with a fresh signup so earlier
QA mutations don't contaminate the first-run experience.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyK")
from harness import Dogfood, BASE, ART, SHOTS

d = Dogfood()
R = {"steps": []}
EMAIL = f"dana_{int(time.time())}@example.com"
R["account"] = EMAIL


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:700], flush=True)


def shot(name):
    d.shot(name)
    print(f"    [shot] shots/{name}.png", flush=True)


def stamps():
    """Read the Status strip the way a user sees it: which stamps are lit."""
    return d.page.evaluate("""() => [...document.querySelectorAll('.stamp')].map(e =>
        ({label: e.innerText.trim(), ok: e.classList.contains('ok')}))""")


# ============================================================ 1. public pages
d.step("K1", "Anonymous public pages")
for n, path in [(1, "/"), (2, "/sprints"), (3, "/topics"), (4, "/topics/email-automation"),
                (5, "/pricing"), (6, "/clients/freelancers")]:
    st = d.goto(path)
    body = d.text()
    imgs = d.page.evaluate("""() => [...document.images].map(i =>
        ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}))""")
    rec(f"page {path}", status=st, chars=len(body),
        broken_images=[i["src"] for i in imgs if not i["ok"]],
        has_none_literal=" None " in f" {body} ",
        braces="{{" in body)
    shot(f"{n:02d}{path.replace('/', '-').replace('-email-automation', '-email-automation')}")

# ============================================================ 2. first-run funnel
d.step("K2", "Funnel: landing -> signup -> logged in")
d.goto("/")
cta = d.page.locator('a:has-text("Start free")')
rec("start free CTA", n=cta.count(), href=cta.first.get_attribute("href") if cta.count() else None)
d.goto(f"{BASE}/sprints")
link = d.page.locator('a[href="/auth/signup"]')
rec("picker signup link", n=link.count(),
    text=link.first.inner_text().strip()[:60] if link.count() else None)
if link.count():
    link.first.click()
else:
    d.goto("/auth/signup")
d.page.wait_for_load_state("domcontentloaded", timeout=30000)
rec("at signup", url=d.page.url.replace(BASE, ""))
d.page.fill("#display_name", "Dana")
d.page.fill("#email", EMAIL)
t = time.time()
d.page.click('button[type=submit]')
d.page.wait_for_load_state("domcontentloaded", timeout=45000)
rec("signup", ms=round((time.time() - t) * 1000), url=d.page.url.replace(BASE, ""),
    flash=d.page.locator(".flash").inner_text().strip()[:120] if d.page.locator(".flash").count() else "")
shot("20-logged-in-picker")

# ============================================================ 3. start a sprint
d.step("K3", "Start the Email Automation sprint")
t = time.time()
d.page.locator('form[action$="/email-automation/start"] button').first.click()
d.page.wait_for_load_state("domcontentloaded", timeout=90000)
enroll_ms = round((time.time() - t) * 1000)
sid = d.page.url.rstrip("/").split("/")[-1]
rec("enroll", ms=enroll_ms, sprint_id=sid, url=d.page.url.replace(BASE, ""))
(ART / "sprint_id_k.txt").write_text(sid)
shot("21-dashboard-fresh")

# ============================================================ 4. dashboard day 1
d.step("K4", "Dashboard: next-step bar, glossary, phase track, meter")
body = d.text()
rec("next step bar", present="Open Day 1" in body, line=[l.strip() for l in body.splitlines()
                                                          if "Open Day 1" in l][:1])
gloss = d.page.locator('text=What the words on this page mean')
rec("glossary control", n=gloss.count())
if gloss.count():
    before = len(d.text())
    gloss.first.click()
    d.page.wait_for_timeout(700)
    after = len(d.text())
    rec("glossary expands", grew=after > before, delta=after - before)
    shot("22-glossary-open")
meter = [l.strip() for l in body.splitlines() if "unlock" in l.lower() or "of 5" in l or "punched" in l]
rec("meter", lines=meter[:8])
rec("generation banner", present="Generating your sprint content" in body)
rec("cohort line", line=[l.strip() for l in body.splitlines() if "COHORT" in l][:1])
rec("demand chips", chips=[l.strip() for l in body.splitlines() if "ACTIVE JOBS" in l or "/HR" in l][:3])

d.step("K4b", "Poll /generation for 60s like the dashboard does")
gen = []
for i in range(5):
    r = d.page.request.get(f"{BASE}/sprints/{sid}/generation")
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text()[:80]}
    gen.append({"t": i * 15, "status": r.status, "body": {k: j.get(k) for k in
                ("status", "generated", "total", "failed_days") if k in j}})
    print(f"    poll {i}: {gen[-1]}", flush=True)
    time.sleep(15)
R["generation_polls"] = gen

# ============================================================ 5. Day 1 lesson
d.step("K5", "Day 1 — the lesson a new learner actually reads")
d.goto(f"{BASE}/sprints/{sid}/day/1")
body = d.text()
rec("day1 lesson state", failed="generation failed" in body.lower(),
    has_video=d.page.locator("canvas, video, #player, .player").count(),
    lines=[l.strip() for l in body.splitlines() if l.strip()][:16])
shot("23-day1-lesson-failed")

d.step("K5b", "A day that DID generate (Day 3) — judge real lesson quality")
for n in (3, 4, 5, 8, 11):
    d.goto(f"{BASE}/sprints/{sid}/day/{n}")
    b = d.text()
    if "generation failed" in b.lower() or "Pending generation" in b:
        rec(f"day{n}", state="failed/pending")
        continue
    lesson = d.page.evaluate("""() => {
        const el = document.querySelector('.lesson, #lesson, .lesson-body, .prose');
        return el ? el.innerText.slice(0, 4000) : document.body.innerText.slice(0, 4000); }""")
    rec(f"day{n} lesson", chars=len(lesson))
    (ART / f"K5-day{n}-lesson.txt").write_text(lesson)
    quiz = d.page.locator('input[type=radio], .quiz label, button:has-text("A)")').count()
    rec(f"day{n} quiz controls", n=quiz)
    shot(f"24-day{n}-lesson")
    break

# ============================================================ 6. Day 1 task
d.step("K6", "Day 1 — Task tab: reference, rubric, submit, complete")
d.goto(f"{BASE}/sprints/{sid}/day/1")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=6000)
    d.page.wait_for_timeout(600)
except Exception as e:
    rec("task tab", err=str(e)[:120])
body = d.text()
rec("step1 reference", has_spec="reference" in body.lower(),
    clone_steps=d.page.locator("#task ol li, .clone-steps li").count(),
    fallback_copy=[l.strip() for l in body.splitlines() if "couldn't be written" in l][:1])
boxes = d.page.locator('input[type=checkbox]')
rec("step2 rubric checkboxes", n=boxes.count(),
    copy=[l.strip() for l in body.splitlines() if "points are ticked" in l][:1])
rec("status stamps", stamps=stamps())
inp = d.page.locator("#rubric_url")
if inp.count():
    inp.first.fill("https://github.com/example/flow")
    d.page.locator('form[action$="/copywork"] button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
    rec("after submit", flash=d.page.locator(".flash").inner_text().strip()[:220]
        if d.page.locator(".flash").count() else "(no message)", stamps=stamps())
    shot("25-day1-after-submit")

d.step("K6b", "Mark lesson watched, then Mark day 1 complete")
d.goto(f"{BASE}/sprints/{sid}/day/1")
w = d.page.locator('button.check-item:visible')
rec("watch control", n=w.count())
if w.count():
    w.first.click(timeout=10000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1200)
    rec("after watched", url=d.page.url.replace(BASE, ""), site_error="SITE ERROR" in d.text())
    shot("26-day1-after-watched")
d.goto(f"{BASE}/sprints/{sid}/day/1")
try:
    d.page.locator('button:text-is("Task")').first.click(timeout=6000)
    d.page.wait_for_timeout(500)
except Exception as e:
    rec("task tab reopen", err=str(e)[:120])
c = d.page.locator('form[action$="/complete"] button:visible')
rec("complete control", n=c.count())
if c.count():
    c.first.click(timeout=10000)
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    d.page.wait_for_timeout(1500)
    b = d.text()
    rec("after day complete", url=d.page.url.replace(BASE, ""), site_error="SITE ERROR" in b,
        banner=[l.strip() for l in b.splitlines() if "complete" in l.lower() or "postings" in l.lower()][:6])
    shot("27-day1-complete-banner")

# ============================================================ 7. meter + advance
d.step("K7", "Did the Job Unlock Meter move? Did it advance to Day 2?")
d.goto(f"{BASE}/sprints/{sid}")
body = d.text()
rec("meter after day1", lines=[l.strip() for l in body.splitlines()
                               if "unlock" in l.lower() or "punched" in l.lower()][:8])
rec("next step now", line=[l.strip() for l in body.splitlines() if "Open Day" in l][:2])
shot("28-dashboard-after-day1")

# ============================================================ 8. locked states
d.step("K8", "Locked surfaces")
for path in [f"/sprints/{sid}/contract", f"/sprints/{sid}/proposals"]:
    st = d.goto(path)
    b = d.text()
    rec(path, status=st, locked="locked" in b.lower() or "LOCKED" in b,
        site_error="SITE ERROR" in b, chars=len(b),
        first=[l.strip() for l in b.splitlines() if l.strip()][:8])
    shot(("29-contract" if "contract" in path else "30-proposals"))

# ============================================================ 9. other surfaces
d.step("K9", "/profile/me and /mentor")
st = d.goto(f"{BASE}/profile/me")
b = d.text()
rec("profile", status=st, url=d.page.url.replace(BASE, ""), none_literal=" None " in f" {b} ",
    lines=[l.strip() for l in b.splitlines() if l.strip()][:12])
shot("31-profile-me")
st = d.goto(f"{BASE}/mentor")
rec("mentor", status=st, chars=len(d.text()))
shot("32-mentor")
try:
    d.page.locator("textarea, input[type=text]").first.fill("What should I build first?")
    t = time.time()
    d.page.locator('button:has-text("Send")').first.click(timeout=8000)
    replied = False
    for _ in range(30):
        d.page.wait_for_timeout(2000)
        if "What should I build first?" in d.text() and len(d.text()) > 700:
            replied = True
            break
    rec("mentor turn", secs=round(time.time() - t), got_reply=replied, chars=len(d.text()))
    shot("33-mentor-after-ask")
except Exception as e:
    rec("mentor error", err=str(e)[:200])

# ============================================================ 10. mobile
d.step("K10", "Mobile 390x844")
ctx = d.browser.new_context(viewport={"width": 390, "height": 844}, storage_state=str(ART / "state.json"))
mp = ctx.new_page()
merr = []
mp.on("console", lambda m: merr.append(m.text) if m.type == "error" else None)
mp.on("requestfailed", lambda r: merr.append("REQFAIL " + r.url))
for path, tag in [("/", "landing"), (f"/sprints/{sid}", "dashboard"), (f"/sprints/{sid}/day/1", "day1")]:
    mp.goto(BASE + path, wait_until="domcontentloaded")
    mp.wait_for_timeout(1500)
    m = mp.evaluate("""() => ({
      overflowX: document.documentElement.scrollWidth - window.innerWidth,
      tinyTargets: [...document.querySelectorAll('button,a,input')].filter(e => {
        const r = e.getBoundingClientRect(); return r.width>0 && (r.height<32||r.width<32)}).length,
      clippedText: [...document.querySelectorAll('h1,h2,h3,p,button')].filter(e => {
        const s=getComputedStyle(e); return s.overflow==='hidden' && e.scrollHeight>e.clientHeight+4}).length
    })""")
    rec(f"mobile {tag}", **m)
    mp.screenshot(path=str(SHOTS / f"34-mobile-{tag}.png"), full_page=True)
R["mobile_console_errors"] = merr[:10]
ctx.close()

(ART / "journeyK.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:20], indent=1))
d.close()
print("Journey K done")
