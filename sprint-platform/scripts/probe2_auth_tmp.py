"""Throwaway probe #2: validate sign_in_with_password with a client that is
NEVER owned by an app context (create_client directly, like app.py's
_resume_stuck_generations does)."""
from supabase import create_client
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()
import config

url = config.Config.SUPABASE_URL
key = config.Config.SUPABASE_SERVICE_KEY
sb = create_client(url, key)

from tests.live_db_adapter import LiveDBAdapter
adapter = LiveDBAdapter(sb)
demo_id = adapter._ensure_demo_user()
print("demo user:", demo_id)

try:
    res = sb.auth.sign_in_with_password({"email": "demo@sprint-platform.local", "password": "demo-password-123"})
    print("correct pw ->", getattr(getattr(res, "user", None), "id", None))
except Exception as e:
    print("correct pw ->", type(e).__name__, str(e)[:200])
try:
    res = sb.auth.sign_in_with_password({"email": "demo@sprint-platform.local", "password": "totally-wrong-pass"})
    print("wrong pw -> UNEXPECTED SUCCESS", getattr(getattr(res, "user", None), "id", None))
except Exception as e:
    print("wrong pw ->", type(e).__name__, str(e)[:120])
try:
    res = sb.auth.sign_in_with_password({"email": "nobody-wrong@nonexistent.example", "password": "whatever"})
    print("nonexistent email -> UNEXPECTED SUCCESS", getattr(getattr(res, "user", None), "id", None))
except Exception as e:
    print("nonexistent email ->", type(e).__name__, str(e)[:120])
