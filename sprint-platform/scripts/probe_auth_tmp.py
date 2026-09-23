"""Throwaway probe: confirm (a) teardown closes the adapter's client, and (b)
sign_in_with_password validates against the live test DB auth.users."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from services.supabase_client import get_supabase
from flask import g

app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
with app.app_context():
    sb = get_supabase()
    # detach from g BEFORE context exit -> teardown must NOT close it
    g.pop("supabase", None)
# context exited; is the detached client alive?
try:
    rows = sb.table("job_clusters").select("cluster_key").limit(1).execute()
    print("DETACHED CLIENT ALIVE:", rows.data)
except Exception as e:
    print("DETACHED CLIENT DEAD:", type(e).__name__, e)

# control: same pattern WITHOUT the pop -> teardown should close it
app2 = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
with app2.app_context():
    sb2 = get_supabase()
try:
    rows = sb2.table("job_clusters").select("cluster_key").limit(1).execute()
    print("CONTROL (no pop) ALIVE:", rows.data)
except Exception as e:
    print("CONTROL (no pop) DEAD:", type(e).__name__, e)

# validate the planned login primitive against the live test DB
app3 = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
with app3.app_context():
    sb3 = get_supabase()
    from tests.live_db_adapter import LiveDBAdapter
    adapter = LiveDBAdapter(sb3)
    demo_id = adapter._ensure_demo_user()
    print("demo user:", demo_id)
try:
    res = sb3.auth.sign_in_with_password({"email": "demo@sprint-platform.local", "password": "demo-password-123"})
    ok = getattr(getattr(res, "user", None), "id", None)
except Exception as e:
    ok = f"{type(e).__name__}: {e}"
try:
    res = sb3.auth.sign_in_with_password({"email": "demo@sprint-platform.local", "password": "totally-wrong-pass"})
    err = "UNEXPECTED SUCCESS " + str(getattr(getattr(res, "user", None), "id", None))
except Exception as e:
    err = f"raised {type(e).__name__} (good)"
print("sign_in_with_password correct pw:", ok)
print("sign_in_with_password wrong pw:", err)
