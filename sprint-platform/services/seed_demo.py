"""
Demo seed — mirrors the product mockup's numbers and copy so `localhost`
renders exactly like docs/mockups/product-mockup.html with zero setup.
"""
import datetime

DEMO_USER_ID = "demo-user"
DEMO_SPRINT_ID = "s1"

_CLUSTERS = [
    {
        "cluster_key": "email-automation",
        "display_name": "Email Automation",
        "icon": "✉️",
        "description": "Klaviyo · Mailchimp · n8n flows",
        "job_count": 450,
        "avg_rate": 62,
        "growth_score": 18,
        "keywords": ["klaviyo", "mailchimp", "n8n", "email", "flow"],
        "status": "active",
    },
    {
        "cluster_key": "web-scraping",
        "display_name": "Web Scraping & Data",
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
        "display_name": "AI Chatbot Builds",
        "icon": "🤖",
        "description": "OpenAI API · RAG · deployment",
        "job_count": 268,
        "avg_rate": 55,
        "growth_score": 15,
        "keywords": ["openai", "rag", "chatbot", "deployment"],
        "status": "active",
    },
]

# Job feed postings — exactly the rows on the mockup's proposal screen.
_FEED = [
    {"title": "Klaviyo flow setup for store", "rate": 180, "experience_needed": "intermediate"},
    {"title": "Email automation revamp", "rate": 250, "experience_needed": "expert"},
    {"title": "Abandoned cart series", "rate": 140, "experience_needed": "entry"},
    {"title": "Segment + campaign build", "rate": 210, "experience_needed": "intermediate"},
    {"title": "Post-purchase upsell flow", "rate": 165, "experience_needed": "intermediate"},
]


# Mockup: Day 4 = Project 2 (Abandoned-Cart). Day 2/3 use projects 1/2 as filler.
DAY_TO_PROJECT = {2: 1, 3: 2, 4: 2}


def _day_payload(d):
    if d in DAY_TO_PROJECT:
        return {"project_index": DAY_TO_PROJECT[d]}
    if d == 5:
        return {"detect": True}
    if 6 <= d <= 10:
        step = {"6": "brief", "7": "execute1", "8": "execute2", "9": "case-problem", "10": "case-result"}.get(str(d), "execute")
        return {"step": step}
    return {"step": "engineer" if d == 11 else ("first-bid" if d in (12, 13) else "iterate")}


def seed_demo(db):
    """Seed the in-memory store so localhost matches the mockup."""
    for c in _CLUSTERS:
        db.seed("job_clusters", [dict(c)])

    feed = []
    for i, f in enumerate(_FEED, start=1):
        feed.append({
            "id": f"email-automation-{i}",
            "cluster_key": "email-automation",
            "title": f["title"],
            "source": "curated",
            "source_url": "https://example.com/job",
            "description": "Anonymized real job posting — checkout recovery + segmentation.",
            "skills": ["klaviyo", "email", "automation"],
            "rate": f["rate"],
            "experience_needed": f["experience_needed"],
            "review_count": 0,
            "unlock_day": min(i + 8, 14),
            "status": "active",
        })
    db.seed("job_feed", feed)

    two_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(days=14)
    db.seed("demand_snapshots", [
        {"cluster_key": "email-automation", "job_count": 410, "avg_rate": 60,
         "captured_at": two_weeks_ago.isoformat()},
    ])

    db.seed("cohorts", [{
        "id": "c12", "cluster_key": "email-automation", "name": "Cohort #12",
        "start_date": "2026-08-10", "end_date": "2026-08-23", "status": "active",
    }])

    db.seed("user_profiles", [{
        "user_id": DEMO_USER_ID, "display_name": "Maya Chen",
        "headline": "Freelancer · Email Automation & Web Scraping",
        "avatar_url": "", "is_public": True,
    }])
    db.seed("user_platforms", [
        {"user_id": DEMO_USER_ID, "platform": "upwork"},
        {"user_id": DEMO_USER_ID, "platform": "fiverr"},
    ])

    db.seed("sprints", [{
        "id": DEMO_SPRINT_ID, "user_id": DEMO_USER_ID, "cohort_id": "c12",
        "cluster_key": "email-automation", "phase": "A", "current_day": 4,
        "status": "active", "badge_id": None,
        "proposals_sent": 0, "responses_received": 0, "interviews_held": 0,
        "offers_received": 0, "contracts_won": 0, "contracts_completed": 0,
        "total_earned": 0, "avg_contract_value": None, "first_contract_at": None,
        "repeat_clients": 0, "is_actively_seeking": True,
    }])

    phase_map = {d: "A" for d in range(1, 6)} | {d: "B" for d in range(6, 11)} | {d: "C" for d in range(11, 15)}
    for d in range(1, 15):
        phase = phase_map[d]
        action_type = (
            "copywork" if d < 6
            else ("contract" if 6 <= d <= 8 else ("case-study" if d <= 10 else "proposal"))
        )
        db.seed("sprint_days", [{
            "id": f"{DEMO_SPRINT_ID}-d{d}", "sprint_id": DEMO_SPRINT_ID,
            "phase": phase, "day_no": d,
            "title": f"Day {d}", "description": "",
            "action_type": action_type, "action_payload": _day_payload(d),
            "is_done": d < 4, "completed_at": None,
        }])

    db.seed("copywork_projects", [
        {"id": f"{DEMO_SPRINT_ID}-cw1", "sprint_id": DEMO_SPRINT_ID, "project_index": 1,
         "title": "Rebuild the Checkout Welcome Flow",
         "description": "Replicate a real, high-performing flow from scratch.",
         "status": "todo", "gap_fill_topic": None},
        {"id": f"{DEMO_SPRINT_ID}-cw2", "sprint_id": DEMO_SPRINT_ID, "project_index": 2,
         "title": "Rebuild the Abandoned-Cart Flow",
         "description": "Replicate a real, high-performing flow from scratch.",
         "status": "todo", "gap_fill_topic": "mobile responsiveness"},
        {"id": f"{DEMO_SPRINT_ID}-cw3", "sprint_id": DEMO_SPRINT_ID, "project_index": 3,
         "title": "Rebuild the Post-Purchase Upsell Flow",
         "description": "Replicate a real, high-performing flow from scratch.",
         "status": "todo", "gap_fill_topic": None},
    ])

    db.seed("sprint_unlock_snapshots", [{
        "sprint_id": DEMO_SPRINT_ID, "user_id": DEMO_USER_ID,
        "completed_days": 3, "unlocked_count": 186, "total_in_cluster": 450,
        "last_delta": 38,
    }])

    db.seed("user_momentum", [{
        "user_id": DEMO_USER_ID, "day_streak": 4, "best_streak": 4,
        "confidence": 72,
    }])

    db.seed("capstone_briefs", [{
        "id": "cb1", "sprint_id": DEMO_SPRINT_ID, "job_feed_id": "email-automation-1",
        "title": "Set up email automation for my e-commerce brand",
        "requirements": "Klaviyo checkout recovery + post-purchase upsell\n"
                        "Segmentation for VIP repeat buyers\n"
                        "Deliverables: flow exports + setup docs\n"
                        "Must be mobile-responsive emails",
        "constraints": {"deadline_days": 4, "budget": 180, "notes": ["Client prefers async updates"]},
        "acceptance_criteria": ["flow exports present", "setup docs present", "mobile-responsive"],
        "verification_type": "auto",
    }])

    db.seed("case_studies", [
        {
            "id": "cs1", "sprint_id": DEMO_SPRINT_ID, "user_id": DEMO_USER_ID,
            "title": "Abandoned-Cart Recovery Flow",
            "problem": "Store lost 68% of checkouts to cart abandonment.",
            "solution": "Built a 2-step Klaviyo flow with dynamic cart summary + 10% coupon.",
            "result": "Recovered 12% of abandoned carts in the first 4 weeks.",
            "is_draft": False,
        },
        {
            "id": "cs2", "sprint_id": DEMO_SPRINT_ID, "user_id": DEMO_USER_ID,
            "title": "VIP Segmentation Strategy",
            "problem": "", "solution": "", "result": "", "is_draft": True,
        },
    ])
