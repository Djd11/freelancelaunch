"""Seed steps — Givens that establish DB fixtures via LiveDBAdapter (writes to real Supabase)."""
import datetime
import uuid as _uuid
from behave import given

from tests.live_db_adapter import TEST_USER_ID, OTHER_USER_ID, get_live_adapter, get_static_job_id, get_static_cohort_id
from tests.steps.common_steps import _login

PROJECT_TITLES = {
    1: "Rebuild the Checkout Welcome Flow",
    2: "Rebuild the Abandoned-Cart Flow",
    3: "Rebuild the Post-Purchase Upsell Flow",
}
# Day → copy-work project index. MUST mirror routes/sprints.py + lesson_engine.py:
# project 1 spans days 2-3, project 2 = day 4, project 3 = day 5 (all four
# Phase A copy-work days must map, or Gate A can never pass through the UI).
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2, 5: 3}


def _phase_for(day):
    return "A" if day <= 5 else ("B" if day <= 10 else "C")


def _action_for(day):
    if day < 6:
        return "copywork"
    if day <= 8:
        return "contract"
    if day <= 10:
        return "case-study"
    return "proposal"


def _sprint_row(sprint_id, cluster, user_id, current_day, status="active"):
    return {
        "id": sprint_id, "user_id": user_id, "cohort_id": _get_static_cohort_id(),
        "cluster_key": cluster, "phase": _phase_for(current_day),
        "current_day": current_day, "status": status, "badge_id": None,
        "proposals_sent": 0, "responses_received": 0, "interviews_held": 0,
        "offers_received": 0, "contracts_won": 0, "contracts_completed": 0,
        "total_earned": 0, "avg_contract_value": None, "first_contract_at": None,
        "repeat_clients": 0, "is_actively_seeking": True,
    }


def _get_static_cohort_id():
    """Get the cohort ID from module-level static data."""
    return get_static_cohort_id()


def seed_sprint(adapter, sprint_id, cluster, user_id, current_day=4, status="active"):
    """Full sprint fixture: sprint + 14 days + 3 copy-work projects + meter.

    Resets ALL outcome counters so a reused sprint never leaks state from a
    previous scenario (proposals_sent, responses, badge_id, ...).
    """
    real_user_id = adapter.resolve_user_id(user_id)
    real_sprint_id = adapter.resolve_sprint_id(sprint_id, cluster, user_id)

    # The resolve_sprint_id already creates sprint_days and unlock_snapshots
    # (or reused an existing sprint). Reset the row to a clean fixture state.
    adapter.sb.table("sprints").update({
        "current_day": current_day,
        "phase": _phase_for(current_day),
        "status": status,
        "badge_id": None,
        "proposals_sent": 0,
        "responses_received": 0,
        "interviews_held": 0,
        "offers_received": 0,
        "contracts_won": 0,
        "contracts_completed": 0,
        "total_earned": 0,
        "avg_contract_value": None,
        "first_contract_at": None,
        "repeat_clients": 0,
        "is_actively_seeking": True,
        "completed_at": None,
    }).eq("id", real_sprint_id).execute()

    # Copy-work projects (3 per sprint)
    for idx, title in PROJECT_TITLES.items():
        adapter.seed_table("copywork_projects", [{
            "id": f"{sprint_id}-cw{idx}",
            "sprint_id": real_sprint_id,
            "project_index": idx,
            "title": title,
            "source_url": "https://example.com/flow",
            "clone_steps": [],
            "rubric": [],
            "gap_fill_topic": None,
            "done": False,
        }], on_conflict="sprint_id,project_index")

    # Sprint unlock snapshot
    adapter.seed_table("sprint_unlock_snapshots", [{
        "sprint_id": real_sprint_id,
        "user_id": real_user_id,
        "completed_days": 0,
        "unlocked_count": 0,
        "total_in_cluster": 0,
        "last_delta": 0,
    }], on_conflict="sprint_id,user_id")

    # User momentum
    adapter.seed_table("user_momentum", [{
        "user_id": real_user_id,
        "day_streak": 1,
        "best_streak": 1,
        "confidence": 60,
    }], on_conflict="user_id")


_CLUSTER_DISPLAY = {
    "email-automation": "Email Automation",
    "web-scraping": "Web Scraping",
    "ai-chatbots": "AI Chatbots",
}


def _display_name(key):
    return _CLUSTER_DISPLAY.get(key, key.replace("-", " ").title())


# ── clusters & feed ────────────────────────────────────────────────
@given('a job cluster "{key}" with job_count {count} and avg_rate {rate} and growth_score {growth}')
def step_cluster_full(context, key, count, rate, growth):
    adapter = get_live_adapter()
    adapter.seed_table("job_clusters", [{
        "cluster_key": key,
        "display_name": _display_name(key),
        "icon": "📈",
        "description": "Live demand cluster",
        "job_count": int(count),
        "avg_rate": int(rate),
        "growth_score": int(growth),
        "status": "active",
    }], on_conflict="cluster_key", track_cleanup=False)


@given('a job cluster "{key}" with {n} active postings')
def step_cluster_postings(context, key, n):
    adapter = get_live_adapter()
    # Idempotent: only create the cluster when missing. Never clobber a
    # pre-existing static cluster's demand numbers (job_count/avg_rate/...) —
    # zeroing them leaked state into the picker and landing counter.
    existing = adapter.sb.table("job_clusters").select("cluster_key").eq("cluster_key", key).limit(1).execute().data
    if existing:
        return
    adapter.seed_table("job_clusters", [{
        "cluster_key": key,
        "display_name": _display_name(key),
        "icon": "📈",
        "description": "Live demand cluster",
        "job_count": 0,
        "avg_rate": 0,
        "growth_score": 0,
        "status": "active",
    }], on_conflict="cluster_key", track_cleanup=False)

    # The job_feed is pre-seeded by environment.py for email-automation
    # This step is mainly for other clusters; skip if already seeded


@given('job cluster "{key}" has a posting titled "{title}"')
def step_cluster_posting(context, key, title):
    """Seed one live posting for a non-email cluster so content generation can
    ground lessons/projects in a real posting (content-quality.feature)."""
    adapter = get_live_adapter()
    adapter.seed_table("job_feed", [{
        "cluster_key": key,
        "title": title,
        "source": "curated",
        "source_url": f"https://example.com/jobs/{key}",
        "description": f"Anonymized real job posting — {title}.",
        "skills": [key],
        "rate": 150,
        "experience_needed": "intermediate",
        "review_count": 0,
        "unlock_day": 1,
        "status": "active",
    }])


@given('job cluster "{key}" has current job_count {n}')
def step_cluster_count(context, key, n):
    adapter = get_live_adapter()
    adapter.sb.table("job_clusters").update({"job_count": int(n)}).eq("cluster_key", key).execute()


@given('demand snapshots for "{key}" show {n} two weeks ago')
def step_snapshot(context, key, n):
    adapter = get_live_adapter()
    two_weeks = datetime.datetime.utcnow() - datetime.timedelta(days=14)
    # No unique constraint on demand_snapshots, use insert instead
    adapter.seed_table("demand_snapshots", [{
        "cluster_key": key,
        "job_count": int(n),
        "avg_rate": 60,
        "captured_at": two_weeks.isoformat(),
    }], on_conflict=None, track_cleanup=False)


# ── sprint fixtures ────────────────────────────────────────────────
@given('I have an active sprint "{sid}" with {days} days for cluster "{cluster}"')
def step_active_sprint(context, sid, days, cluster):
    adapter = get_live_adapter()
    seed_sprint(adapter, sid, cluster, TEST_USER_ID, current_day=4)


@given('I am on day {n} of sprint "{sid}"')
def step_on_day(context, n, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprints").update({
        "current_day": int(n),
        "phase": _phase_for(int(n)),
    }).eq("id", real_sprint_id).execute()


@given('an active sprint "{sid}" for another user')
def step_other_sprint(context, sid):
    adapter = get_live_adapter()
    seed_sprint(adapter, sid, "email-automation", OTHER_USER_ID, current_day=4)


@given('day {n} of sprint "{sid}" has a generated lesson with a voiceover')
def step_day_lesson_voiceover(context, n, sid):
    """Seed a generated lesson whose payload carries a voiceover URL + duration
    (what the async video worker writes) so the day view can render the
    two-panel lesson player instead of the kinetic-text fallback."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprint_days").update({
        "action_payload": {
            "lesson": {
                "title": "Klaviyo flow setup for store: how to rebuild a real flow",
                "script": "Your target job is 'Klaviyo flow setup for store'. "
                          "Today you rebuild the smallest real version of what it asks for.",
                "key_points": ["What the posting literally asks for", "The smallest reproducible piece"],
                "voiceover": {
                    "url": "https://example.com/voiceover/lesson.mp3",
                    "duration_seconds": 42.0,
                },
            }
        },
    }).eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute()


@given('day {n} of sprint "{sid}" is marked done')
def step_day_done(context, n, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprint_days").update({
        "is_done": True,
        "completed_at": datetime.datetime.utcnow().isoformat(),
    }).eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute()

    # Advance sprint current_day
    adapter.sb.table("sprints").update({
        "current_day": max(int(n) + 1, 1),
    }).eq("id", real_sprint_id).execute()


@given('the meter for sprint "{sid}" has unlocked {unlocked} of {total} with delta {delta}')
def step_meter(context, sid, unlocked, total, delta):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    adapter.seed_table("sprint_unlock_snapshots", [{
        "sprint_id": real_sprint_id,
        "user_id": real_user_id,
        "completed_days": 0,
        "unlocked_count": int(unlocked),
        "total_in_cluster": int(total),
        "last_delta": int(delta),
    }], on_conflict="sprint_id,user_id")


@given('user momentum with streak {streak} and confidence {confidence}')
def step_momentum(context, streak, confidence):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    adapter.seed_table("user_momentum", [{
        "user_id": real_user_id,
        "day_streak": int(streak),
        "best_streak": int(streak),
        "confidence": int(confidence),
    }], on_conflict="user_id")


@given('sprint "{sid}" has {sent} proposals sent and {won} contracts')
def step_sprint_outcomes(context, sid, sent, won):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprints").update({
        "proposals_sent": int(sent),
        "contracts_won": int(won),
    }).eq("id", real_sprint_id).execute()


@given('sprint "{sid}" has proposals_sent equal to {n}')
def step_sprint_proposals(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprints").update({
        "proposals_sent": int(n),
    }).eq("id", real_sprint_id).execute()


@given('sprint "{sid}" has responses_received equal to {n}')
def step_sprint_responses(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprints").update({
        "responses_received": int(n),
    }).eq("id", real_sprint_id).execute()


@given('sprint "{sid}" is completed')
def step_sprint_completed(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("sprints").update({
        "status": "completed",
    }).eq("id", real_sprint_id).execute()


# ── verification gates ─────────────────────────────────────────────
@given('Phase A has passed verification for sprint "{sid}"')
def step_gate_a_pass(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.seed_table("verification_reviews", [{
        "sprint_id": real_sprint_id,
        "gate": "A",
        "status": "pass",
        "verification_type": "auto",
    }], on_conflict="sprint_id,gate")


@given('Phase A has not passed verification for sprint "{sid}"')
def step_gate_a_not(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("verification_reviews").delete().eq("sprint_id", real_sprint_id).eq("gate", "A").eq("status", "pass").execute()


@given('Phase B has passed verification for sprint "{sid}"')
def step_gate_b_pass(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.seed_table("verification_reviews", [{
        "sprint_id": real_sprint_id,
        "gate": "B",
        "status": "pass",
        "verification_type": "auto",
    }], on_conflict="sprint_id,gate")


@given('Phase B has not passed verification for sprint "{sid}"')
def step_gate_b_not(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("verification_reviews").delete().eq("sprint_id", real_sprint_id).eq("gate", "B").eq("status", "pass").execute()


@given('the user has no passing verification for any sprint')
def step_no_passing(context):
    adapter = get_live_adapter()
    # Scoped to the test user's own sprints/badges — never a global wipe.
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    sprints = adapter.sb.table("sprints").select("id").eq("user_id", real_user_id).execute().data
    for s in sprints:
        adapter.sb.table("verification_reviews").delete().eq("sprint_id", s["id"]).execute()
    adapter.sb.table("badges").delete().eq("user_id", real_user_id).execute()


# ── copy-work projects ─────────────────────────────────────────────
@given('copy-work project {n} for sprint "{sid}" flagged gap-fill topic "{topic}"')
def step_gapfill(context, n, sid, topic):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("copywork_projects").update({
        "gap_fill_topic": topic,
    }).eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute()


@given('copy-work projects {a}, {b}, and {c} for sprint "{sid}" are done')
def step_projects_done(context, a, b, c, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    done = {int(a), int(b), int(c)}
    for idx in done:
        # A project is only credibly "done" when the learner submitted a link to
        # the replica — Gate A checks both done and submitted_url (fix #5).
        adapter.sb.table("copywork_projects").update({
            "done": True,
            "submitted_url": f"https://github.com/me/project-{idx}",
        }).eq("sprint_id", real_sprint_id).eq("project_index", idx).execute()


@given('copy-work project {n} for sprint "{sid}" has its submitted URL removed')
def step_project_url_removed(context, n, sid):
    """Strip a done project's submitted URL so negative Gate A paths can prove
    the gate requires evidence, not just a done flag (fix #5)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("copywork_projects").update({
        "submitted_url": None,
    }).eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute()



# ── capstone brief ─────────────────────────────────────────────────
def _seed_brief(adapter, sid, job_fixture, notes=None):
    """Seed one capstone brief for the sprint (delete-then-insert: the table
    has no unique constraint on sprint_id, so upsert-on-conflict is invalid)."""
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("capstone_briefs").delete().eq("sprint_id", real_sprint_id).execute()
    adapter.seed_table("capstone_briefs", [{
        "sprint_id": real_sprint_id,
        "job_feed_id": job_fixture,
        "title": "Set up email automation for my e-commerce brand",
        "requirements": "Klaviyo checkout recovery + post-purchase upsell\nSegmentation for VIP repeat buyers\nDeliverables: flow exports + setup docs\nMust be mobile-responsive emails",
        "constraints": {"deadline_days": 4, "budget": 180, "notes": notes or []},
        "acceptance_criteria": ["flow exports present", "setup docs present", "mobile-responsive"],
        "verification_type": "auto",
    }])


@given('a capstone brief for sprint "{sid}" references job "{job}"')
def step_brief_job(context, sid, job):
    _seed_brief(get_live_adapter(), sid, job, notes=["Client prefers async updates"])


@given('a capstone brief for sprint "{sid}" exists')
def step_brief_exists(context, sid):
    _seed_brief(get_live_adapter(), sid, "email-automation-1")


# ── proposals & platforms ──────────────────────────────────────────
@given('a draft proposal "{pid}" exists for job "{job}" on sprint "{sid}"')
def step_draft_proposal(context, pid, job, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.seed_table("proposals", [{
        "id": pid,
        "sprint_id": real_sprint_id,
        "job_feed_id": job,
        "template_body": "I see you need this job handled.",
        "hooks": ["I see you need this job handled."],
        "status": "draft",
        "platform": None,
        "score": 85,
    }], on_conflict="id")


@given('the user has a verified platform "{platform}"')
def step_verified(context, platform):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    adapter.seed_table("user_platforms", [{
        "user_id": real_user_id,
        "platform": platform,
    }], on_conflict="user_id,platform")


@given('the user has verified platforms "{a}" and "{b}"')
def step_verified_two(context, a, b):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    adapter.seed_table("user_platforms", [{
        "user_id": real_user_id,
        "platform": a,
    }, {
        "user_id": real_user_id,
        "platform": b,
    }], on_conflict="user_id,platform")


# ── profile / badges / case studies ────────────────────────────────
from tests.live_db_adapter import TEST_USER_ID

# Persona names in the features map to the canonical test users — the logged-in
# user IS "Maya Chen" (demo) and "Jordan Lee" is the other user. Creating fresh
# auth users with colliding display names broke slug resolution on /profile/<slug>.
PERSONA_TO_FIXTURE = {
    "maya chen": TEST_USER_ID,
    "jordan lee": OTHER_USER_ID,
}


def _persona_fixture_id(name):
    return PERSONA_TO_FIXTURE.get(name.lower(), f"profile-{name.lower().replace(' ', '-')}")


@given('a badge for user "{name}" on cluster "{cluster}"')
def step_badge_bare(context, name, cluster):
    _seed_badge(get_live_adapter(), cluster, 410)


@given('a badge for user "{name}" on cluster "{cluster}" with jobs_at_issue {n}')
def step_badge(context, name, cluster, n):
    _seed_badge(get_live_adapter(), cluster, int(n))


def _seed_badge(adapter, cluster, jobs_at_issue):
    """Create a badge for the logged-in test user (TEST_USER_ID)."""
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    sprint_id = f"badge-{real_user_id}-{cluster}"
    real_sprint_id = adapter.resolve_sprint_id(sprint_id, cluster, TEST_USER_ID)

    # Ensure gate B passed
    adapter.seed_table("verification_reviews", [{
        "sprint_id": real_sprint_id,
        "gate": "B",
        "status": "pass",
        "verification_type": "auto",
    }], on_conflict="sprint_id,gate")

    adapter.seed_table("badges", [{
        "user_id": real_user_id,
        "cluster_key": cluster,
        "sprint_id": real_sprint_id,
        "jobs_at_issue": jobs_at_issue,
        "issued_at": datetime.datetime.utcnow().isoformat(),
    }], on_conflict="user_id,cluster_key")


@given('freelancer "{name}" has a badge on "{cluster}" issued {days} days ago')
def step_freelancer_badge(context, name, cluster, days):
    adapter = get_live_adapter()
    fixture_id = _persona_fixture_id(name)
    real_user_id = adapter.resolve_user_id(fixture_id)
    sprint_id = f"badge-{real_user_id}-{cluster}"
    real_sprint_id = adapter.resolve_sprint_id(sprint_id, cluster, fixture_id)

    # Ensure user_profiles row exists for this freelancer
    adapter.sb.table("user_profiles").upsert({
        "user_id": real_user_id,
        "display_name": name,
        "headline": f"Freelancer · {cluster.replace('-', ' ').title()}",
        "is_public": True,
    }, on_conflict="user_id").execute()

    adapter.seed_table("verification_reviews", [{
        "sprint_id": real_sprint_id,
        "gate": "B",
        "status": "pass",
        "verification_type": "auto",
    }], on_conflict="sprint_id,gate")

    issued = datetime.datetime.utcnow() - datetime.timedelta(days=int(days))
    adapter.seed_table("badges", [{
        "user_id": real_user_id,
        "cluster_key": cluster,
        "sprint_id": real_sprint_id,
        "jobs_at_issue": 400,
        "issued_at": issued.isoformat(),
    }], on_conflict="user_id,cluster_key")


@given('freelancer "{name}" has profile is_public equal to false')
def step_not_public(context, name):
    adapter = get_live_adapter()
    fixture_id = _persona_fixture_id(name)
    real_user_id = adapter.resolve_user_id(fixture_id)
    # Use upsert to ensure the profile exists, then update is_public
    adapter.sb.table("user_profiles").upsert({
        "user_id": real_user_id,
        "display_name": name,
        "is_public": False,
    }, on_conflict="user_id").execute()


@given('the completed sprint has proposals_sent {sent} and interviews_held {held}')
def step_completed_outcomes(context, sent, held):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    # Find the sprint associated with the user's badge (for profile page)
    badges = adapter.sb.table("badges").select("*").eq("user_id", real_user_id).execute().data
    for badge in badges:
        sprint_id = badge.get("sprint_id")
        if sprint_id:
            adapter.sb.table("sprints").update({
                "proposals_sent": int(sent),
                "interviews_held": int(held),
                "status": "completed",
            }).eq("id", sprint_id).execute()
    # Also update any completed sprints
    sprints = adapter.sb.table("sprints").select("*").eq("user_id", real_user_id).eq("status", "completed").execute().data
    for sprint in sprints:
        adapter.sb.table("sprints").update({
            "proposals_sent": int(sent),
            "interviews_held": int(held),
        }).eq("id", sprint["id"]).execute()


@given('the user has a case study "{title}"')
def step_case_study(context, title):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    # Find a completed sprint
    sprints = adapter.sb.table("sprints").select("*").eq("user_id", real_user_id).eq("status", "completed").limit(1).execute().data
    sprint_id = sprints[0]["id"] if sprints else f"cs-fixture-{title}"
    adapter.seed_table("case_studies", [{
        "id": f"cs-{abs(hash(title)) % 100000}",
        "sprint_id": sprint_id,
        "user_id": real_user_id,
        "title": title,
        "problem": "Store lost 68% of checkouts to cart abandonment.",
        "solution": "Built a 2-step flow with dynamic cart summary + coupon.",
        "result": "Recovered 12% of abandoned carts in 4 weeks.",
        "is_draft": False,
    }], on_conflict="id")


@given('the user has a draft case study "{title}"')
def step_case_study_draft(context, title):
    """A case study still in draft (Mock Contract not passed) — the profile
    check-item must NOT carry the 'done' class for it (profile.html renders
    the done state only when is_draft is false)."""
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    sprints = adapter.sb.table("sprints").select("*").eq("user_id", real_user_id).eq("status", "completed").limit(1).execute().data
    sprint_id = sprints[0]["id"] if sprints else f"cs-fixture-{title}"
    adapter.seed_table("case_studies", [{
        "id": f"cs-draft-{abs(hash(title)) % 100000}",
        "sprint_id": sprint_id,
        "user_id": real_user_id,
        "title": title,
        "problem": "Draft problem statement.",
        "solution": "Draft solution outline.",
        "result": "Draft result notes.",
        "is_draft": True,
    }], on_conflict="id")


# ── mentor ─────────────────────────────────────────────────────────
@given('the mentor context is job "{job}" with progress {pct}%')
def step_mentor_context(context, job, pct):
    adapter = get_live_adapter()
    real_user_id = adapter.resolve_user_id(TEST_USER_ID)
    real_sprint_id = adapter.resolve_sprint_id("s1")
    # Set the sprint's current_day based on progress percentage
    adapter.sb.table("sprints").update({
        "current_day": max(1, round(int(pct) / 100 * 14)),
    }).eq("id", real_sprint_id).execute()
    # Create a capstone brief referencing the target job so the mentor
    # resolves the correct job_feed_id (email-automation-1).
    # delete-then-insert: capstone_briefs has no unique constraint on sprint_id.
    real_job_id = get_static_job_id(job)
    if real_job_id and real_job_id != job:
        adapter.sb.table("capstone_briefs").delete().eq("sprint_id", real_sprint_id).execute()
        adapter.seed_table("capstone_briefs", [{
            "sprint_id": real_sprint_id,
            "job_feed_id": real_job_id,
            "title": "Mentor context brief",
            "requirements": "Target job context for mentor.",
            "constraints": {"deadline_days": 4, "budget": 180, "notes": []},
            "acceptance_criteria": [],
            "verification_type": "auto",
        }])


@given('the target job description mentions "{term}"')
def step_job_desc(context, term):
    adapter = get_live_adapter()
    # Map fixture job ID to real UUID using module-level storage
    real_job_id = get_static_job_id("email-automation-1")
    adapter.sb.table("job_feed").update({
        "description": f"Need help building a {term} for my store.",
    }).eq("id", real_job_id).execute()


@given('the LLM fallback chain returns None')
def step_llm_none(context):
    pass  # mentor_agent always uses its deterministic fallback path