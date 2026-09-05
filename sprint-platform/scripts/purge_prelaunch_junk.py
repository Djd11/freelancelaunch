#!/usr/bin/env python
"""Pre-launch purge of development/QA junk from the live Supabase project.

Why this exists
---------------
Every sprint created during development and Dana's dogfood rounds is still in
the production database (28 sprints, 29 auth users).  Worse, ``app.py`` runs
``_resume_stuck_generations`` on *every* boot: it scans all ``status='active'``
sprints and restarts LLM content generation for any whose day payloads are
still empty.  Nine of these test sprints are partially generated, so each cold
start of the free Render instance fans out up to 9 background generation jobs
(3 projects + 14 lessons each) against the LLM provider.  That is slow, burns
API credit, and is invisible to whoever is watching the dashboard.

What is kept
------------
* users: the three seeded fixture accounts (admin@ / demo@ / other@) that the
  test suite and ``seed_live.py`` rely on.
* sprints: the three fully-generated admin sprints (one per cluster:
  email-automation, web-scraping, ai-chatbots) so the demo account shows real,
  complete content, plus the one phase-B sprint (re-homed onto demo@) so the
  phase-B/capstone experience is demonstrable without re-running generation.

Safety
------
* Dry run by default: prints the plan and writes nothing but the backup.
* A complete JSON dump of every affected table (plus the auth user list) is
  written to ``db/backups/`` BEFORE any delete, so the purge is reversible by
  hand.
* Deletes are ordered child -> parent so FK constraints are respected.

Usage
-----
    .venv/bin/python scripts/purge_prelaunch_junk.py           # dry run
    .venv/bin/python scripts/purge_prelaunch_junk.py --apply   # execute
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from supabase import create_client  # noqa: E402

# --- keep lists -------------------------------------------------------------
KEEP_SPRINTS = {
    "89900920": "email-automation (phase A, complete) - the documented demo",
    "f5803846": "web-scraping (phase A, complete)",
    "7f0c1222": "ai-chatbots (phase A, complete)",
    "2e2566d8": "email-automation (phase B) - re-homed onto demo@",
}
KEEP_USER_EMAILS = {
    "admin@sprint-platform.local",
    "demo@sprint-platform.local",
    "other@sprint-platform.local",
}
REASSIGN_SPRINT_TO = {"2e2566d8": "demo@sprint-platform.local"}

# tables that hang off a sprint
SPRINT_CHILD_TABLES = [
    "sprint_days", "copywork_projects", "capstone_briefs", "case_studies",
    "verification_reviews", "sprint_unlock_snapshots", "mentor_sessions",
    "proposals", "contracts", "badges",
]
# tables dumped for the record (small, all of them)
DUMP_TABLES = SPRINT_CHILD_TABLES + [
    "sprints", "user_profiles", "user_momentum", "platform_connections",
    "user_platforms", "public_freelancers", "demand_snapshots", "cohorts",
    "job_clusters",
]


def _all(table, sel="*"):
    """Fetch a whole table (these are all small; 1000-row page is plenty)."""
    out, start = [], 0
    while True:
        rows = SB.table(table).select(sel).range(start, start + 999).execute().data
        out.extend(rows)
        if len(rows) < 1000:
            return out
        start += 1000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    args = ap.parse_args()

    global SB
    SB = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    sprints = _all("sprints")
    users = sorted(SB.auth.admin.list_users(), key=lambda u: str(u.created_at))
    email_of = {u.id: (u.email or "") for u in users}
    uid_of = {v: k for k, v in email_of.items()}

    keep_ids, del_ids = [], []
    for s in sprints:
        if s["id"][:8] in KEEP_SPRINTS:
            keep_ids.append(s["id"])
        else:
            del_ids.append(s["id"])

    print(f"sprints: {len(sprints)} total -> keep {len(keep_ids)}, delete {len(del_ids)}")
    for s in sprints:
        tag = "KEEP" if s["id"][:8] in KEEP_SPRINTS else "del "
        note = KEEP_SPRINTS.get(s["id"][:8], "")
        print(f'  [{tag}] {s["id"][:8]} {s["cluster_key"]:17} {s["phase"]} d{s["current_day"]:2} '
              f'{s["status"]:9} {email_of.get(str(s["user_id"]), "?"):38} {note}')

    del_users = [u for u in users if (u.email or "") not in KEEP_USER_EMAILS]
    print(f"\nauth users: {len(users)} total -> keep {len(users) - len(del_users)}, "
          f"delete {len(del_users)}")
    for u in del_users:
        print(f"  [del ] {u.id[:8]} {u.email}")

    # ---- backup dump -------------------------------------------------------
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_dir = ROOT / "db" / "backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    bak_path = bak_dir / f"pre_purge_{stamp}.json"
    dump = {"_meta": {
        "created_at": stamp,
        "reason": "state before scripts/purge_prelaunch_junk.py",
        "kept_sprints": {k[:8]: v for k in keep_ids for v in [KEEP_SPRINTS.get(k[:8], "")]},
        "deleted_sprint_ids": del_ids,
        "deleted_user_emails": [u.email for u in del_users],
    }}
    for t in DUMP_TABLES:
        try:
            dump[t] = _all(t)
        except Exception as exc:  # a missing/odd table must not block the backup
            dump[t] = {"_error": str(exc)[:200]}
    dump["_auth_users"] = [{"id": u.id, "email": u.email,
                            "created_at": str(u.created_at)} for u in users]
    bak_path.write_text(json.dumps(dump, indent=1, default=str))
    print(f"\nbackup written: {bak_path.relative_to(ROOT)} "
          f"({bak_path.stat().st_size // 1024} KB)")

    if not args.apply:
        print("\nDRY RUN - nothing deleted. Re-run with --apply.")
        return 0

    # ---- re-home the phase-B demo sprint onto demo@ ------------------------
    for prefix, email in REASSIGN_SPRINT_TO.items():
        sid = next((s["id"] for s in sprints if s["id"][:8] == prefix), None)
        if not sid:
            continue
        SB.table("sprints").update({"user_id": uid_of[email]}).eq("id", sid).execute()
        print(f"re-homed {prefix} -> {email}")

    # ---- delete sprint children, then sprints ------------------------------
    for t in SPRINT_CHILD_TABLES:
        try:
            n = len(SB.table(t).select("id").in_("sprint_id", del_ids).execute().data)
            if n:
                SB.table(t).delete().in_("sprint_id", del_ids).execute()
                print(f"deleted {n:4} rows from {t}")
        except Exception as exc:
            print(f"  skip {t}: {str(exc)[:90]}")
    SB.table("sprints").delete().in_("id", del_ids).execute()
    print(f"deleted {len(del_ids)} sprints")

    # ---- delete synthetic users (and their profile rows) -------------------
    for t in ("user_profiles", "user_momentum", "platform_connections",
              "user_platforms", "public_freelancers", "demand_snapshots"):
        try:
            SB.table(t).delete().in_("user_id", [u.id for u in del_users]).execute()
            print(f"cleared {t} rows for deleted users")
        except Exception as exc:
            print(f"  skip {t}: {str(exc)[:90]}")
    for u in del_users:
        try:
            SB.auth.admin.delete_user(u.id)
        except Exception as exc:
            print(f"  FAILED to delete {u.email}: {str(exc)[:90]}")
    print(f"deleted {len(del_users)} auth users")

    # ---- verify: no kept sprint should auto-resume generation --------------
    sys.path.insert(0, str(ROOT))
    from services.lesson_engine import should_resume_generation
    print("\npost-purge boot-resume check:")
    remaining = _all("sprints")
    bad = 0
    for s in remaining:
        if should_resume_generation(SB, s["id"]):
            print(f"  !! {s['id'][:8]} {s['cluster_key']} would RESUME generation on boot")
            bad += 1
    print(f"  {len(remaining)} sprints left, {bad} would resume generation")
    left_users = SB.auth.admin.list_users()
    print(f"  {len(left_users)} auth users left: "
          f"{sorted(u.email for u in left_users)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
