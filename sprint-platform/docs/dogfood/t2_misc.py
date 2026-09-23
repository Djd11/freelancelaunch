"""Round 3 — MISC re-test: footer/disclaimer, $0/hr guards, enroll spinner, cohort date."""
import sys, os, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2misc")
from harness import Dogfood, BASE, ART

d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


d.step("M1", "Footer + disclaimer on public and app pages")
for p in ("/", "/pricing", "/sprints", "/auth/login", "/topics/email-automation",
          "/clients/freelancers"):
    d.goto(f"{BASE}{p}")
    t = d.text()
    foot = d.page.locator("footer")
    rec(f"footer {p}", footer_el=foot.count(),
        has_contact=bool(re.search(r"hello@|contact|support", t, re.I)),
        has_terms=d.page.locator('a[href*="terms"]').count(),
        has_privacy=d.page.locator('a[href*="privacy"]').count(),
        disclaimer=[l.strip() for l in t.splitlines()
                    if re.search(r"no income|earnings depend|not a guarantee|results vary", l, re.I)][:1])
d.shot("c1-t2-footer-landing")

d.step("M2", "$0/hr guards across every surface that shows a rate")
bad = {}
for p in ("/", "/sprints", "/topics", "/topics/email-automation", "/topics/web-scraping",
          "/topics/ai-chatbots", "/clients/freelancers"):
    d.goto(f"{BASE}{p}")
    t = d.text()
    rates = re.findall(r"\$0\s*/\s*hr|\$\s*/\s*hr|0/HR", t, re.I)
    bad[p] = {"zero_rate_hits": len(rates),
              "rates_shown": sorted(set(re.findall(r"\$\d+\s*/\s*HR", t, re.I)))[:5]}
rec("zero-rate scan", **{k: v for k, v in bad.items()})

d.step("M3", "Enroll button spinner (observe during a real start)")
d.goto(f"{BASE}/sprints")
if "Sign out" not in d.text():
    rec("spinner", note="not logged in")
else:
    sel = 'form[action$="/notion-automation/start"]'
    if not d.page.locator(sel).count():
        sel = 'form[action$="/shopify-apps/start"]'
    if d.page.locator(sel).count():
        btn = d.page.locator(sel + ' button').first
        btn.click()
        d.page.wait_for_timeout(700)          # mid-flight
        rec("spinner mid-request",
            disabled=btn.is_disabled() if btn.count() else None,
            text=btn.inner_text().strip()[:60] if btn.count() else "",
            spinner_el=d.page.locator(f'{sel} .spinner, {sel} [class*=spin]').count())
        d.shot("c2-t2-enroll-spinner")
        d.page.wait_for_load_state("domcontentloaded", timeout=120000)
        rec("after enroll", url=d.page.url.replace(BASE, ""))
        d.shot("c3-t2-after-enroll")
        sid = d.page.url.rstrip("/").split("/")[-1]
        t = d.text()
        rec("new enrollee cohort line",
            cohort=[l.strip() for l in t.splitlines() if "COHORT" in l][:1],
            ends=[l.strip() for l in t.splitlines() if "ENDS" in l][:1])
        (ART / "t2_misc_sprint.txt").write_text(sid)
    else:
        rec("spinner", note="no unstarted cluster available")

d.step("M4", "Cohort end date is in the future for a new enrollee")
import datetime
today = datetime.date.today().isoformat()
rec("today", today)

(ART / "t2misc.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:6], indent=1))
d.close()
print("MISC done")
