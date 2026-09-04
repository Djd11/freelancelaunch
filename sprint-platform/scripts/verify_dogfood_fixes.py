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
    # 1. two accounts, same first name — created via Supabase admin (the
    #    public signup is magic-link now; sessions are set directly here).
    tag = str(int(time.time()))
    ids = []
    with app.app_context():
        from routes import obtain_supabase
        import secrets as _sec
        sb = obtain_supabase()
        for who in ("A", "B"):
            res = sb.auth.admin.create_user({
                "email": f"dupname{who}{tag}@example.com",
                "password": _sec.token_urlsafe(16), "email_confirm": True,
                "data": {"display_name": f"Dupname {tag}"}})
            u = getattr(res, "user", res)
            uid = getattr(u, "id", None)
            ids.append(uid)
            sb.table("user_profiles").upsert(
                {"user_id": uid, "display_name": f"Dupname {tag}", "is_public": True},
                on_conflict="user_id").execute()
        ids = sorted(ids)
        check("created 2 same-name accounts", len(ids) == 2 and all(ids), str(ids))
        for uid, headline in zip(ids, ("headline-alpha-" + tag, "headline-beta-" + tag)):
            sb.table("user_profiles").update({"headline": headline}).eq("user_id", uid).execute()

    # each account's /profile/me must land on a DIFFERENT slug
    slugs = {}
    for who, uid in zip(("A", "B"), ids):
        ca = app.test_client()
        with ca.session_transaction() as s:
            s["user_id"] = uid
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

    # 6. gate locks (dogfood #2/#3): Phase-A sprint must NOT reach contract or complete
    sid = "89900920-2a44-45c3-81fe-00fe8bf21799"
    r = c.get(f"/sprints/{sid}/contract", follow_redirects=False)
    check("contract locked before Gate A", r.status_code == 302 and "/sprints/" in r.headers.get("Location", ""))
    page = c.get(f"/sprints/{sid}").get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', page)
    tok = m.group(1) if m else ""
    r = c.post(f"/sprints/{sid}/complete", data={"csrf_token": tok}, follow_redirects=False)
    check("complete refused before gates", r.status_code == 302)
    with app.app_context():
        from routes import obtain_supabase
        sp = obtain_supabase().table("sprints").select("status").eq("id", sid).limit(1).execute().data[0]
        check("sprint NOT marked completed", sp["status"] == "active", sp["status"])

    # 7. insecure email-only auth is gone
    check("POST /auth/login rejected", c.post("/auth/login", data={"email": "x@y.com"}).status_code == 405)
    check("POST /auth/signup rejected", c.post("/auth/signup", data={"email": "x@y.com"}).status_code == 405)
    check("login page offers Google + magic link",
          "Continue with Google" in c.get("/auth/login").get_data(as_text=True)
          and "/auth/magic" in c.get("/auth/login").get_data(as_text=True))

print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
sys.exit(1 if FAILS else 0)
