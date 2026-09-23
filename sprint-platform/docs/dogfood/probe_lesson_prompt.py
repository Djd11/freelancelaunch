"""Time a REAL day-lesson prompt against the configured provider.

Answers: is 'No LLM provider answered' an outage, or does the production prompt
exceed the 90s timeout the app uses? Read-only: builds the prompt and calls the
LLM; writes nothing to the DB.
"""
import os, sys, time, json, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

from flask import Flask
from config import Config
from services.supabase_client import get_supabase
from services import lesson_engine as le
from services.llm import call_llm

app = Flask("probe", template_folder=os.path.join(ROOT, "templates"))
app.config.from_object(Config)

sid = open(os.path.join(HERE, "artifacts", "sprint_id.txt")).read().strip()

with app.app_context():
    sb = get_supabase()
    sprint = sb.table("sprints").select("*").eq("id", sid).limit(1).execute().data[0]
    days = sb.table("sprint_days").select("*").eq("sprint_id", sid).order("day_no").execute().data
    projects = sb.table("copywork_projects").select("*").eq("sprint_id", sid).order("project_index").execute().data
    day1 = days[0]
    prompt = le._lesson_prompt(
        le._top_job(sb, sprint["cluster_key"]), 1, day1.get("action_type"),
        (projects[0].get("title") if projects else None),
        domain_context=le._domain_context(le._domain_tools(sb, sprint["cluster_key"])),
    )
    print("prompt chars:", len(prompt))
    print("prompt head:\n", prompt[:400], "\n...\n", prompt[-400:])

    for tmo in (90, 240):
        t = time.time()
        try:
            out = call_llm(prompt, timeout=tmo, max_retries=1)
        except Exception:
            traceback.print_exc()
            out = None
        el = round(time.time() - t, 1)
        print(f"\n=== timeout={tmo}s  elapsed={el}s  got={'None' if not out else str(len(out))+' chars'}")
        if out:
            print(out[:500])
            try:
                parsed = le._load_json_object(out)
                print("parsed keys:", list(parsed.keys())[:12] if isinstance(parsed, dict) else type(parsed))
            except Exception as e:
                print("parse failed:", e)
            break
