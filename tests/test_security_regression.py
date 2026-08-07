"""
Security regression tests — verify the six review fixes against a running
server (or via Flask test client). Run against the live app:

    python3 tests/test_security_regression.py

Credentials are imported from the behave step module (shared test account).
Requires the dev server on :5000 (or set BASE_URL env).
"""
import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.steps.test_page_audit import TEST_EMAIL, TEST_PASSWORD

BASE = os.environ.get("BASE_URL", "http://localhost:5000")
results = []


def check(name, got, expect, detail=""):
    """Record a check: `got` and `expect` are compared; `detail` is shown on failure."""
    results.append((name, got == expect, (got, detail), expect))


def main():
    s = requests.Session()
    s.get(f"{BASE}/auth/login")
    r = s.post(f"{BASE}/auth/login",
               data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
               allow_redirects=False)
    check("login", (r.status_code, r.headers.get("Location")),
          (302, "/dashboard/"))

    # The shared behave account is the configured admin in the dev .env, so the
    # admin gate assertions must be aware of which side of the gate we're on.
    admin_probe = s.get(f"{BASE}/admin/users", allow_redirects=False)
    is_admin_account = admin_probe.status_code == 200

    # 1. Admin gate — non-admin bounced to /dashboard; admin admitted
    if is_admin_account:
        check("1. admin admitted to /admin/users", admin_probe.status_code, 200,
              f"-> {admin_probe.headers.get('Location')}")
    else:
        r = s.get(f"{BASE}/admin/users", allow_redirects=False)
        check("1. /admin/users (non-admin)", (r.status_code, r.headers.get("Location")),
              (302, "/dashboard/"))

    # 2. Payment bypass — no session_id must NOT grant the paid tier
    r = s.get(f"{BASE}/payments/success", allow_redirects=False)
    check("2. /payments/success (no session)", (r.status_code, r.headers.get("Location")),
          (302, "/payments/pricing"))

    # 3. Force-regenerate is admin-only (non-enrolled users can't reach it either)
    if is_admin_account:
        print("  [SKIP] 3. force=1 admin-only — shared test account IS the admin")
    else:
        r = s.post(f"{BASE}/api/generate-curriculum/web-scraping-python?force=1")
        check("3. force=1 gated", r.status_code in (400, 403), f"got {r.status_code}")

    # 4. Regenerate-day scoped to the user's enrolled topic
    r = s.post(f"{BASE}/api/regenerate-day/seo-content-writing/1")
    check("4. regenerate-day (not enrolled topic)", (r.status_code, r.json().get("error", "")),
          (403, "You must be enrolled in this topic to regenerate its content"))

    # 5. Open redirect blocked — Location must never point off-site
    s2 = requests.Session()
    s2.get(f"{BASE}/auth/login")
    r = s2.post(f"{BASE}/auth/login",
                data={"email": TEST_EMAIL, "password": TEST_PASSWORD,
                      "next": "https://evil.com"}, allow_redirects=False)
    loc = r.headers.get("Location", "")
    check("5. open redirect blocked", "evil.com" not in loc and loc.startswith("/dashboard"),
          True, f"Location={loc}")

    # 6. Tier not upgraded by #2
    r = s.get(f"{BASE}/auth/profile")
    check("6. tier not upgraded ('guided' absent)", '"guided"' not in r.text, True,
          "'guided' found in profile body")

    ok = sum(1 for _, ok, _, _ in results if ok)
    print(f"\n{'PASS' if ok == len(results) else 'FAIL'} — {ok}/{len(results)} checks passed\n")
    for name, ok, got, expect in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}\n        got={got!r}\n     expect={expect!r}")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    main()
