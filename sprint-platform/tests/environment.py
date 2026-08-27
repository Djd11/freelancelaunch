"""
Behave BDD Environment — LIVE Supabase mode.
Each scenario runs against the REAL Supabase project with a LiveDBAdapter that:
- Maps readable fixture IDs ("test-user-123", "s1") → real UUIDs
- Seeds/cleans per scenario in FK-safe order
- Uses real auth.users for login sessions
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from tests.live_db_adapter import (LiveDBAdapter, get_live_adapter, reset_live_adapter,
                                   set_static_job_ids, set_static_cohort_id, TEST_USER_ID)


class SprintIDRewritingClient:
    """Wrapper around Flask test client that rewrites fixture sprint IDs in URLs to real UUIDs."""

    def __init__(self, client, adapter_getter):
        self._client = client
        self._adapter_getter = adapter_getter
        # Rewrite both /sprints/<fixture_id> and /sprints/<id>/proposals/<fixture_pid>
        self._sprint_id_pattern = re.compile(r'/sprints/([^/]+)(/.*)?$')
        self._proposal_id_pattern = re.compile(r'/sprints/([^/]+)/proposals/([^/]+)(/.*)?$')

    def _rewrite_url(self, path):
        """Replace fixture sprint IDs and proposal IDs in path with real UUIDs."""
        import uuid as _uuid

        def is_uuid(s):
            try:
                _uuid.UUID(s)
                return True
            except (ValueError, AttributeError):
                return False

        def rewrite_proposal(match):
            fixture_sprint = match.group(1)
            fixture_proposal = match.group(2)
            rest = match.group(3) or ""
            adapter = self._adapter_getter()
            real_sprint = adapter.resolve_sprint_id(fixture_sprint, resolve_only=True) if not is_uuid(fixture_sprint) else fixture_sprint
            real_proposal = adapter.resolve_proposal_id(fixture_proposal) if not is_uuid(fixture_proposal) else fixture_proposal
            return f"/sprints/{real_sprint}/proposals/{real_proposal}{rest}"

        def rewrite_sprint(match):
            fixture_id = match.group(1)
            rest = match.group(2) or ""
            if not is_uuid(fixture_id):
                adapter = self._adapter_getter()
                # resolve_only: unknown fixture ids pass through unchanged so the
                # route sees a nonexistent sprint and returns the specced 302.
                real_id = adapter.resolve_sprint_id(fixture_id, resolve_only=True)
                return f"/sprints/{real_id}{rest}"
            return match.group(0)

        # Try proposal pattern first (more specific), then sprint pattern
        path = self._proposal_id_pattern.sub(rewrite_proposal, path)
        path = self._sprint_id_pattern.sub(rewrite_sprint, path)
        return path

    def get(self, path, *args, **kwargs):
        return self._client.get(self._rewrite_url(path), *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self._client.post(self._rewrite_url(path), *args, **kwargs)

    def put(self, path, *args, **kwargs):
        return self._client.put(self._rewrite_url(path), *args, **kwargs)

    def delete(self, path, *args, **kwargs):
        return self._client.delete(self._rewrite_url(path), *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self._client.patch(self._rewrite_url(path), *args, **kwargs)

    def __getattr__(self, name):
        # Delegate any other attributes to the wrapped client
        return getattr(self._client, name)


def before_all(context):
    # Ensure we're using LIVE Supabase config (do NOT unset env vars)
    context.app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "WTF_CSRF_ENABLED": False,
    })
    # Wrap the test client to rewrite sprint IDs
    context.client = SprintIDRewritingClient(context.app.test_client(), lambda: get_live_adapter())

    # Pre-seed static reference data that persists across scenarios
    with context.app.app_context():
        adapter = get_live_adapter()
        _seed_static_data(adapter)


def _seed_static_data(adapter: LiveDBAdapter):
    """Seed reference tables that persist across all scenarios (job_clusters, cohorts, job_feed).

    All IDs are DETERMINISTIC (uuid5 of the fixture id) so upserts are idempotent
    across runs — re-running the suite never multiplies static rows.
    """
    import uuid
    sb = adapter.sb

    def static_uuid(name: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sprint-platform-test:{name}"))

    # Job clusters (already exist from seed_live.py, but ensure they're there)
    clusters = [
        {
            "cluster_key": "email-automation",
            "display_name": "Email Automation",
            "icon": "📧",
            "description": "Klaviyo · Mailchimp · n8n flows",
            "job_count": 450,
            "avg_rate": 62,
            "growth_score": 18,
            "keywords": ["klaviyo", "mailchimp", "n8n", "email", "flow"],
            "status": "active",
        },
        {
            "cluster_key": "web-scraping",
            "display_name": "Web Scraping",
            "icon": "🕷️",
            "description": "Python · BeautifulSoup · APIs",
            "job_count": 322,
            "avg_rate": 48,
            "growth_score": 12,
            "keywords": ["python", "beautifulsoup", "scraping", "api"],
            "status": "active",
        },
        {
            "cluster_key": "ai-chatbots",
            "display_name": "AI Chatbots",
            "icon": "🤖",
            "description": "OpenAI API · RAG · deployment",
            "job_count": 268,
            "avg_rate": 55,
            "growth_score": 15,
            "keywords": ["openai", "rag", "chatbot", "deployment"],
            "status": "active",
        },
    ]
    for c in clusters:
        sb.table("job_clusters").upsert(c, on_conflict="cluster_key").execute()

    # Cohort - deterministic UUID (idempotent across runs)
    cohort_id = static_uuid("cohort-12")
    sb.table("cohorts").upsert({
        "id": cohort_id,
        "cluster_key": "email-automation",
        "name": "Cohort #12",
        "start_date": "2026-08-10",
        "end_date": "2026-08-23",
        "status": "active",
    }, on_conflict="id").execute()
    # Store cohort_id for other steps to use
    set_static_cohort_id(cohort_id)

    # Job feed (5 postings for email-automation) - deterministic UUIDs
    feed = []
    job_ids = {}
    for i, f in enumerate([
        {"title": "Klaviyo flow setup for store", "rate": 180, "experience_needed": "intermediate"},
        {"title": "Email automation revamp", "rate": 250, "experience_needed": "expert"},
        {"title": "Abandoned cart series", "rate": 140, "experience_needed": "entry"},
        {"title": "Segment + campaign build", "rate": 210, "experience_needed": "intermediate"},
        {"title": "Post-purchase upsell flow", "rate": 165, "experience_needed": "intermediate"},
    ], start=1):
        job_id = static_uuid(f"job:email-automation-{i}")
        job_ids[f"email-automation-{i}"] = job_id
        feed.append({
            "id": job_id,
            "cluster_key": "email-automation",
            "title": f["title"],
            "source": "curated",
            "source_url": f"https://example.com/job/{i}",
            "description": "Anonymized real job posting — checkout recovery + segmentation.",
            "skills": ["klaviyo", "email", "automation"],
            "rate": f["rate"],
            "experience_needed": f["experience_needed"],
            "review_count": 0,
            "unlock_day": min(i + 8, 14),
            "status": "active",
        })
    for row in feed:
        sb.table("job_feed").upsert(row, on_conflict="id").execute()

    # Store job IDs for other steps
    set_static_job_ids(job_ids)

    # Demand snapshot - no unique constraint, so replace any prior test snapshot
    import datetime
    sb.table("demand_snapshots").delete().eq("cluster_key", "email-automation").eq("job_count", 410).execute()
    two_weeks_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).isoformat()
    sb.table("demand_snapshots").insert({
        "cluster_key": "email-automation",
        "job_count": 410,
        "avg_rate": 60,
        "captured_at": two_weeks_ago,
    }).execute()

    # Demo user's verified platforms — canonical static fixture. Per-scenario
    # cleanup deletes tracked user_platforms rows, so restore them on every
    # run (idempotent upsert) or proposal submission breaks for the demo user.
    demo_id = adapter.resolve_user_id(TEST_USER_ID)
    for platform in ("upwork", "fiverr"):
        sb.table("user_platforms").upsert(
            {"user_id": demo_id, "platform": platform},
            on_conflict="user_id,platform",
        ).execute()


def _fake_mentor_llm(prompt, timeout=30, **kwargs):
    """Deterministic stand-in for the mentor LLM — echoes the target job's
    exact wording so the grounding gate passes and answers stay stable. When
    the prompt carries earlier turns (mentor memory), the answer references
    the learner's earlier question so memory is observable in tests. Accepts
    **kwargs (timeout/max_retries/backoff_base) so it can stand in for the
    real call_llm signature used by mentor_agent.answer."""
    import re
    m = re.search(r"job posting says: (['\"])(.*?)\1", prompt or "", re.DOTALL)
    desc = m.group(2) if m else ""
    h = re.search(r"learner asked: (['\"])(.*?)\1", prompt or "", re.DOTALL)
    earlier = h.group(2) if h else ""
    if earlier and "Earlier in this conversation" in (prompt or ""):
        return (f"Earlier you asked about \"{earlier}\" — keep going from there. "
                f"Re-read the posting: \"{desc}\". What's the smallest piece to rebuild today?")
    return (f"Work from the posting's own words: \"{desc}\" — what's the "
            "smallest piece you can rebuild today, and how will you verify it?")


def before_scenario(context, scenario):
    # Get fresh adapter for this scenario (cleans up previous scenario)
    reset_live_adapter()
    # Default-stub the mentor LLM with a grounded fake so every /mentor/turn
    # scenario is deterministic (no live provider). Scenarios that need the
    # LLM unavailable override this via the "LLM fallback chain returns None"
    # step; after_scenario restores the real call_llm.
    import services.mentor_agent as ma
    ma.call_llm = _fake_mentor_llm
    # Default-stub the lesson worker LLM as well, so any background worker
    # thread spawned during a scenario (enrollment, the generation-retry
    # endpoint) is deterministic instead of hitting a live provider.
    import services.lesson_engine as le
    from tests.steps.action_steps import _fake_generation_llm, _fake_proposals_llm
    le.call_llm = _fake_generation_llm
    # Default-stub the proposal fill LLM so the proposals route's background
    # fill thread is deterministic too.
    import services.proposal_engine as pe
    pe.call_llm = _fake_proposals_llm
    with context.app.app_context():
        adapter = get_live_adapter()
        # Resolve admin user ID and store in app config for admin check
        admin_id = adapter.resolve_user_id("admin-user")
        context.app.config["ADMIN_USER_ID"] = admin_id
    context.db = adapter  # Steps will use adapter.seed_table() and adapter.rows()

    # Restore the demo user's canonical verified platforms — scenarios that
    # seed user_platforms via seed_table track them for cleanup, and after
    # cleanup the demo user's upwork/fiverr rows are gone (they're never
    # re-upserted until before_all re-runs). Any later scenario relying on
    # the static platforms (e.g. ui-ux proposal submit) then fails with
    # "platform not verified". Idempotent restore here keeps the suite
    # order-independent.
    with context.app.app_context():
        demo_id = adapter.resolve_user_id(TEST_USER_ID)
        for platform in ("upwork", "fiverr"):
            adapter.sb.table("user_platforms").upsert(
                {"user_id": demo_id, "platform": platform},
                on_conflict="user_id,platform",
            ).execute()

    context.response = None
    context.page_html = ""
    context.last_json = None

    # Clear session
    try:
        with context.client.session_transaction() as sess:
            sess.pop("user_id", None)
            sess.pop("_flashes", None)
    except Exception:
        pass


def after_scenario(context, scenario):
    # Clean up scenario-specific data
    reset_live_adapter()
    # Restore content-generation module globals that worker/mentor steps may
    # have patched (worker tests stub call_llm, mentor tests stub call_llm) so
    # a later scenario in the same process never inherits a patched call_llm.
    import services.lesson_engine as le
    import services.video_engine as ve
    import services.mentor_agent as ma
    import services.proposal_engine as pe
    from services.llm import call_llm
    from services.video_engine import voiceover_for_lesson as _real_vo
    le.call_llm = call_llm
    ma.call_llm = call_llm
    pe.call_llm = call_llm
    ve.voiceover_for_lesson = _real_vo


def after_all(context):
    # Final cleanup
    reset_live_adapter()