"""Timing harness for the anatomy-first + parallel generation fix.

Creates a throwaway user, enrolls a fresh sprint (measures enroll latency),
then polls the DB with timestamps for: (a) all 3 copy-work projects having a
non-empty rubric (the Gate-A supply that was unreachable), and (b) lesson
count over time. Run against the live dev DB. Prints a compact timeline.

Run:  .venv/bin/python scripts/timing_enroll.py
"""
import secrets
import sys
import time

sys.path.insert(0, ".")
from app import create_app  # noqa: E402

app = create_app()


def main():
    tag = str(int(time.time()))
    with app.app_context():
        from routes import obtain_supabase
        sb = obtain_supabase()
        res = sb.auth.admin.create_user({
            "email": f"timing{tag}@example.com",
            "password": secrets.token_urlsafe(16), "email_confirm": True,
            "data": {"display_name": f"Timing {tag}"}})
        u = getattr(res, "user", res)
        uid = u.id
        sb.table("user_profiles").upsert(
            {"user_id": uid, "display_name": f"Timing {tag}", "is_public": False},
            on_conflict="user_id").execute()

    # Enroll via the real route (test client) — measures synchronous latency.
    c = app.test_client()
    with c.session_transaction() as s:
        s["user_id"] = uid
    t0 = time.time()
    r = c.post(f"/sprints/email-automation/start", data={}, follow_redirects=False)
    # need csrf; pull a token from the picker first
    c.get("/sprints")
    import re
    loc = r.headers.get("Location", "")
    # retry with csrf
    html = c.get("/sprints").get_data(as_text=True)
    tok = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    tok = tok.group(1) if tok else ""
    t0 = time.time()
    r = c.post("/sprints/email-automation/start", data={"csrf_token": tok}, follow_redirects=False)
    enroll_ms = (time.time() - t0) * 1000
    loc = r.headers.get("Location", "")
    m = re.search(r"/sprints/([0-9a-f-]{36})", loc)
    sid = m.group(1) if m else None
    print(f"enroll: HTTP {r.status_code} in {enroll_ms:.0f} ms  sprint={sid}")
    if not sid:
        print("!! enroll did not create a sprint"); return

    # Poll for anatomy (rubrics) + lessons.
    anatomy_done_at = None
    lessons_seen = 0
    poll_start = time.time()
    while time.time() - poll_start < 900:  # 15 min ceiling
        with app.app_context():
            from routes import obtain_supabase
            sb = obtain_supabase()
            projs = sb.table("copywork_projects").select("project_index,rubric,clone_steps") \
                .eq("sprint_id", sid).execute().data
            filled = [p for p in projs if (p.get("rubric") or []) and (p.get("clone_steps") or [])]
            days = sb.table("sprint_days").select("day_no,action_payload").eq("sprint_id", sid).execute().data
            lessons = sum(1 for d in days if (d.get("action_payload") or {}).get("lesson"))
        el = time.time() - poll_start
        if len(filled) == 3 and anatomy_done_at is None:
            anatomy_done_at = el
            print(f"  [{el:6.1f}s] ALL 3 RUBRICS PRESENT  (lessons so far: {lessons})")
        if lessons != lessons_seen:
            print(f"  [{el:6.1f}s] lessons={lessons}/14  rubrics={len(filled)}/3")
            lessons_seen = lessons
        if lessons == 14 and len(filled) == 3:
            print(f"  [{el:6.1f}s] FULLY GENERATED")
            break
        time.sleep(5)

    print(f"\nRESULT: enroll={enroll_ms:.0f}ms  anatomy(all 3 rubrics)={anatomy_done_at and f'{anatomy_done_at:.0f}s'}  total_lessons={lessons_seen}/14")


if __name__ == "__main__":
    main()
