"""Throwaway probe #3: inspect live test DB cohorts for email-automation."""
from supabase import create_client
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
import config

sb = create_client(config.Config.SUPABASE_URL, config.Config.SUPABASE_SERVICE_KEY)
rows = sb.table("cohorts").select("*").eq("cluster_key", "email-automation").execute().data
for r in rows:
    print({k: r.get(k) for k in ("id", "name", "status", "start_date", "end_date", "cluster_key")})
import uuid
det = str(uuid.uuid5(uuid.NAMESPACE_URL, "sprint-platform-test:cohort-12"))
print("deterministic cohort-12 id:", det)
print("present with that id:", any(r["id"] == det for r in rows))
# any sprints referencing the non-deterministic active cohort?
counts = sb.table("sprints").select("cohort_id").execute().data
from collections import Counter
print("sprint cohort_id counts:", Counter(str(c.get("cohort_id")) for c in counts))
