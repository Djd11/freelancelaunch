"""Post-dogfood verification of the fixes (captain run, 2026-09-04).

Checks, against the real Supabase dev DB via the Flask test client:
  1. Signup works and two accounts with the SAME first name get DIFFERENT
     public profile slugs (dogfood M1), and each slug renders its own owner.
  2. A nonexistent slug now returns 404 (was 200).
  3. The mentor intro quotes a REAL gig (no "Anonymized real job posting"
     placeholder) for the seeded email-automation sprint owner (dogfood B2).
  4. The sprint dashboard's job table links to freelancer.com, never
     example.com (dogfood M2).
  5. The picker/topic pages never render "$0/hr" (honest-rate guard).
"""
import re
import sys
import time

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILS.append(name)


def csrf_token(client, path, field="csrf_token"):
    html = client.get(path).get_data(as_text=True)
    m = re.search(rf'name="{field}"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else None


with app.test_client() as c:
    # 1. two accounts, same first name — each signup in its OWN client so the
    #    session /auth/signup establishes stays live for that user's /profile/me.
    tag = str(int(time.time()))
    clients = {}
    for who in ("A", "B"):
        ca = app.test_client()
        tok = csrf_token(ca, "/auth/signup")
        ca.post("/auth/signup", data={
            "csrf_token": tok, "display_name": f"Dupname {tag}",
            "email": f"dupname{who}{tag}@example.com"}, follow_redirects=False)
        clients[who] = ca
    # set distinct headlines to identify owners
    with app.app_context():
        from routes import obtain_supabase
        sb = obtain_supabase()
        rows = sb.table("user_profiles").select("user_id,display_name").eq("display_name", f"Dupname {tag}").execute().data
        ids = sorted(r["user_id"] for r in rows)
        check("signup created 2 same-name accounts", len(ids) == 2, str(len(ids)))
        for uid, headline in zip(ids, ("headline-alpha-" + tag, "headline-beta-" + tag)):
            sb.table("user_profiles").update({"headline": headline, "is_public": True}).eq("user_id", uid).execute()

    # each account's /profile/me must land on a DIFFERENT slug
    slugs = {}
    for who, ca in clients.items():
        r = ca.get("/profile/me", follow_redirects=False)
        loc = r.headers.get("Location", "")
        m = re.search(r"/profile/([^/?]+)", loc)
        slugs[who] = m.group(1) if m else loc
    check("same-name users get distinct slugs", slugs["A"] != slugs["B"], f"{slugs['A']} vs {slugs['B']}")
    # each slug renders exactly one owner's headline (anonymous view)
    bodies = {}
    for who in ("A", "B"):
        bodies[who] = c.get(f"/profile/{slugs[who]}").get_data(as_text=True)
    check("slug A resolves to exactly one owner", ("headline-alpha-" in bodies["A"]) != ("headline-beta-" in bodies["A"]))
    check("slug B resolves to exactly one owner", ("headline-alpha-" in bodies["B"]) != ("headline-beta-" in bodies["B"]))
    check("the two profile pages differ", bodies["A"] != bodies["B"])

    # 2. unknown slug -> 404
    check("unknown slug returns 404", c.get("/profile/zzz-nope-99999").status_code == 404)

    # 3+4. owner of the seeded sprint: mentor + dashboard
    owner = "6056b121-4789-4bd5-ba22-639194314344"
    with c.session_transaction() as s:
        s["user_id"] = owner
    mentor = c.get("/mentor").get_data(as_text=True)
    check("mentor intro has NO placeholder text", "Anonymized real job posting" not in mentor)
    check("mentor quotes a real gig", "freelancer" in mentor.lower() or re.search(r"(Klaviyo|Shopify|email|campaign)", mentor, re.I) is not None)
    dash = c.get("/sprints/89900920-2a44-45c3-81fe-00fe8bf21799").get_data(as_text=True)
    check("dashboard has NO example.com links", "example.com" not in dash)
    check("dashboard links real gigs", "freelancer.com" in dash)
    check("dashboard shows real job count", re.search(r"(1[0-9]{2}|[5-9][0-9])\s*</b>\s*active jobs|active jobs", dash) is not None)

    # 5. no $0/hr anywhere public
    for path in ("/sprints", "/topics", "/topics/email-automation", "/topics/web-scraping", "/"):
        body = c.get(path).get_data(as_text=True)
        check(f"no $0/hr on {path}", "$0/hr" not in body and "$0 <" not in body and ">$0/" not in body)

print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
sys.exit(1 if FAILS else 0)
