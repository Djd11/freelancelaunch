"""Journey A — anonymous first impression (marketing surfaces + auth gating).

Plays the role of a first-time freelancer evaluating whether to trust this product
with their time, then checks what happens when they poke at the app parts.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "journeyA")
from harness import Dogfood, BASE, ART

d = Dogfood()
findings = []


def check(name, ok, detail=""):
    findings.append({"check": name, "ok": bool(ok), "detail": detail})
    print(("  PASS " if ok else "  FAIL ") + name + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------- landing
d.step("A1", "Landing page as a first-time visitor")
d.goto("/")
d.shot("A1-landing-top", full=False)
body = d.text()
check("landing renders hero", "Start landing clients" in body)
check("landing shows a live demand counter", "active jobs" in body and "median hourly rate" in body)
check("no template/placeholder leakage", all(s not in body for s in ["{{", "None", "nan", "undefined"]))
check("footer/legal present", any(s in body.lower() for s in ["terms", "privacy", "©", "(c)"]),
      "footer text: " + body.strip().splitlines()[-1][:80] if body.strip() else "")
d.dump("A1-landing")

# ---------------------------------------------------------------- nav targets
d.step("A2", "Nav links resolve")
for path in ["/pricing", "/topics", "/sprints"]:
    s = d.goto(path)
    check(f"GET {path} -> 200", s == 200, f"status={s}")

d.goto("/pricing")
d.shot("A2-pricing", full=False)
pb = d.text()
print("  --- pricing page ---")
print(pb[:1200])
check("pricing states a price", any(c in pb for c in ["$", "free", "Free"]), "no price found")

d.goto("/topics")
d.shot("A3-topics", full=False)
tb = d.text()
print("  --- topics page (first 900 chars) ---")
print(tb[:900])

d.goto("/sprints")
d.shot("A4-sprint-picker-anon", full=False)
sp = d.text()
print("  --- sprint picker (anonymous, first 1500 chars) ---")
print(sp[:1500])
check("anonymous picker shows a way in", "sign in" in sp.lower() or "start free" in sp.lower() or "create" in sp.lower())

# ---------------------------------------------------------------- SEO surfaces
d.step("A5", "SEO / crawler surfaces")
for path in ["/robots.txt", "/sitemap.xml", "/llms.txt"]:
    s = d.goto(path)
    txt = d.text()[:200].replace("\n", " | ")
    check(f"GET {path} -> 200", s == 200, f"status={s} body={txt[:120]}")

# ---------------------------------------------------------------- auth gating
d.step("A6", "What can an anonymous visitor reach? (authz probe)")
protected = ["/dashboard/", "/mentor", "/profile/me", "/sprints/1", "/sprints/1/day/1",
             "/sprints/1/proposals", "/sprints/1/contract", "/admin/", "/admin/clusters"]
for path in protected:
    d.page.goto(BASE + path, wait_until="domcontentloaded")
    final = d.page.url
    status = "redirected" if "/auth/login" in final or "/auth/signup" in final else "OPEN"
    check(f"{path} gated", status == "redirected", f"landed on {final.replace(BASE,'')}")

# ---------------------------------------------------------------- 404 / bad input
d.step("A7", "Error handling for junk URLs")
for path in ["/sprints/does-not-exist-xyz", "/topics/nope-nope", "/day/99", "/totally-bogus"]:
    s = d.goto(path)
    check(f"GET {path} handled", s in (200, 302, 404), f"status={s}")
    if s == 500:
        check(f"{path} not a 500", False, "server error")

d.step("A8", "Console/network health across the run")
errs = d.errors()
print(f"  {len(errs)} error-level events")
for e in errs[:25]:
    print("   ", e)

(ART / "journeyA.json").write_text(json.dumps({"findings": findings, "timings": d.timings}, indent=1))
d.close()
print("\nJourney A done.")
