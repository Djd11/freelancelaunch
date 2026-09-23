"""Round 3 — AUTH surface tests (t2 scope 1).

Verifies the new verified-email auth: 405 on the old email-only POST endpoints,
magic-link send, safe failure of bogus/expired/mismatched callbacks with NO session
set, Google redirect shape (PKCE), and flow-state single use (fixation).
"""
import sys, os, json, re, time, urllib.request, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DOGFOOD_LOG", "t2auth")
from harness import Dogfood, BASE, ART

d = Dogfood()
R = {"steps": []}


def rec(name, **kw):
    R["steps"].append(dict(name=name, **kw))
    print(f"  > {name}: " + json.dumps(kw, default=str)[:600], flush=True)


def post(path, form, cookie=None, allow_redirects=False):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        req.add_header("Cookie", cookie)
    opener = urllib.request.build_opener(
        urllib.request.HTTPRedirectHandler() if allow_redirects
        else type("No", (urllib.request.HTTPRedirectHandler,),
                  {"redirect_request": lambda *a: None})())
    try:
        with opener.open(req, timeout=30) as r:
            return r.status, r.read().decode("utf8", "replace"), dict(r.headers), r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf8", "replace"), dict(e.headers), path
    except Exception as e:
        return type(e).__name__, "", {}, path


d.step("A1", "Old email-only endpoints must be gone (405)")
for p in ("/auth/login", "/auth/signup"):
    st, body, _, _ = post(p, {"email": "attacker@example.com", "display_name": "X"})
    rec(f"POST {p}", status=st,
        session_set=bool(_.get("Set-Cookie", "").startswith("session=") if isinstance(_, dict) else False),
        body_snip=body[:90].replace("\n", " "))

d.step("A2", "GET /auth/login and /auth/signup render the new providers")
for p in ("/auth/login", "/auth/signup"):
    st, body, _, _ = post(p, {}, allow_redirects=False)
    d.goto(f"{BASE}{p}")
    t = d.text()
    rec(f"GET {p}", has_google=bool(re.search(r"google", t, re.I)),
        has_magic=bool(re.search(r"email|link|magic", t, re.I)),
        password_field=d.page.locator('input[type=password]').count(),
        first_lines=[l.strip() for l in t.splitlines() if l.strip()][:12])
    d.shot("90-t2-" + p.strip("/").replace("/", "-"))

d.step("A3", "/auth/google redirects to Supabase authorize with PKCE")
st, body, hdrs, _ = post("/auth/google", {})  # GET-only; expect 405 on POST
d.goto(f"{BASE}/auth/google")   # Playwright follows redirects
loc = d.page.url
rec("google POST status", status=st)
# capture the redirect chain without following to GoTrue's error page
req = urllib.request.Request(f"{BASE}/auth/google")
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        final = r.geturl()
        rec("google redirect (followed)", final=final[:200])
except urllib.error.HTTPError as e:
    rec("google redirect (followed)", http_error=e.code,
        note="GoTrue error page expected until provider enabled")
# now read the Location header itself
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None
try:
    urllib.request.build_opener(NR()).open(urllib.request.Request(f"{BASE}/auth/google"), timeout=20)
except urllib.error.HTTPError as e:
    loc = e.headers.get("Location", "")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    rec("google Location header", status=e.code, base=urllib.parse.urlparse(loc).netloc,
        path=urllib.parse.urlparse(loc).path,
        has_provider=q.get("provider"), has_challenge=bool(q.get("code_challenge")),
        challenge_method=q.get("code_challenge_method"), state=q.get("state"),
        redirect_to=q.get("redirect_to"))
d.shot("91-t2-google-redirect")

d.step("A4", "/auth/magic — real OTP request + 'Link sent' page")
email = f"t2auth_{int(time.time())}@example.com"
d.goto(f"{BASE}/auth/signup")
try:
    d.page.fill('input[name=email]', email)
    dn = d.page.locator('input[name=display_name]')
    if dn.count():
        dn.first.fill("T2 Auth")
    d.page.locator('button[type=submit]').first.click()
    d.page.wait_for_load_state("domcontentloaded", timeout=40000)
    t = d.text()
    rec("magic via form", url=d.page.url.replace(BASE, ""),
        link_sent=bool(re.search(r"link sent|check your email|sent to", t, re.I)),
        email_echoed=email in t,
        lines=[l.strip() for l in t.splitlines() if l.strip()][:14])
    d.shot("92-t2-magic-sent")
    (ART / "t2_magic_email.txt").write_text(email)
except Exception as e:
    rec("magic via form err", err=str(e)[:200])

d.step("A5", "/auth/magic — invalid email rejected")
st, body, hdrs, _ = post("/auth/magic", {"email": "notanemail", "display_name": ""})
rec("invalid email", status=st, rejected="valid email" in body.lower(),
    session_set=bool(hdrs.get("Set-Cookie", "").startswith("session=")))

d.step("A6", "/auth/callback — bogus code, expired code, state mismatch: no session")
# (a) no flow in this fresh cookie jar at all
st, body, hdrs, _ = post("/auth/callback", {"code": "bogus123"})
rec("callback no-flow", status=st, location=hdrs.get("Location"),
    session_set=bool(hdrs.get("Set-Cookie", "").startswith("session=")))
# (b) flow present (from A4's browser session) + bogus code
cookie = "; ".join(f"{c['name']}={c['value']}" for c in d.ctx.cookies())
st, body, hdrs, _ = post("/auth/callback", {"code": "bogus123"}, cookie=cookie)
loc = hdrs.get("Location", "")
sc = hdrs.get("Set-Cookie", "")
rec("callback bogus code (flow present)", status=st, location=loc,
    session_cookie_reset=sc, session_established=bool("user_id" in sc and "Max-Age" in sc),
    note="must redirect to /auth/login and NOT set an authenticated session")
d.goto(BASE + loc) if loc.startswith("/") else d.goto(loc or f"{BASE}/auth/login")
t = d.text()
rec("after bogus callback", flash=[l.strip() for l in t.splitlines()
                                   if "didn" in l.lower() or "expired" in l.lower() or "try again" in l.lower()][:3],
    logged_in="Sign out" in t)
d.shot("93-t2-callback-bogus")

# (c) state mismatch
email2 = f"t2auth2_{int(time.time())}@example.com"
st, body, hdrs, _ = post("/auth/magic", {"email": email2, "display_name": "T2B"}, cookie=cookie)
sc2 = hdrs.get("Set-Cookie", "")
c2 = cookie  # session cookie now carries a new flow verifier
st, body, hdrs, _ = post("/auth/callback", {"code": "x", "state": "wrongstate"}, cookie=c2)
rec("callback state mismatch", status=st, location=hdrs.get("Location"),
    session_set=bool(hdrs.get("Set-Cookie", "").startswith("session=")))

d.step("A7", "Flow-state single use (fixation / replay)")
email3 = f"t2auth3_{int(time.time())}@example.com"
st, body, hdrs, _ = post("/auth/magic", {"email": email3, "display_name": "T2C"}, cookie=c2)
sc3 = hdrs.get("Set-Cookie", "")
jar = c2.split("; ")[0] + "=" + re.search(r"session=([^;]*)", sc3).group(1) if "session=" in sc3 else c2
# first callback consumes the flow
st1, _, h1, _ = post("/auth/callback", {"code": "aaa"}, cookie=jar)
# replay the same callback again
st2, _, h2, _ = post("/auth/callback", {"code": "aaa"}, cookie=jar)
rec("flow single use", first=st1, first_loc=h1.get("Location"),
    replay=st2, replay_loc=h2.get("Location"),
    replay_sets_session=bool(h2.get("Set-Cookie", "").startswith("session=")))

d.step("A8", "Does a legacy email-only session still authenticate? (B1 regression)")
legacy = [c["value"] for c in json.load(open(ART / "state.json"))["cookies"] if c["name"] == "session"]
if legacy:
    lck = "session=" + legacy[0]
    st, body, hdrs, url = post("/profile/me", {}, cookie=lck, allow_redirects=False)
    import urllib.request as u
    req = u.Request(BASE + "/profile/me", headers={"Cookie": lck})
    try:
        with u.urlopen(req, timeout=20) as r:
            rec("legacy session GET /profile/me", status=r.status, final=r.geturl().replace(BASE, ""),
                signed_in="Sign out" in r.read().decode("utf8", "replace"))
    except urllib.error.HTTPError as e:
        rec("legacy session", status=e.code)
    req = u.Request(BASE + "/sprints", headers={"Cookie": lck})
    with u.urlopen(req, timeout=20) as r:
        rec("legacy session /sprints", status=r.status, url=r.geturl().replace(BASE, ""))

(ART / "t2auth.json").write_text(json.dumps(R, indent=1))
print("\nERRORS:", json.dumps(d.errors()[:10], indent=1))
d.close()
print("AUTH tests done")
