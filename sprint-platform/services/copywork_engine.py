"""
copywork_engine — select/sequence the 3 replication projects + gap-fill
detection (architecture.md §4.3, eng-spec §3 J4).

Each sprint gets 3 copy-work projects with a 3-point rubric (auto-checkable)
and a gap-fill topic on project 2 — the nuance flagged from rubric results
that Day 5 serves as a targeted 30-min micro-lesson.

v2: create_projects seeds a placeholder SKELETON (mockup titles/source_url,
EMPTY clone_steps/rubric) so the async worker's lesson_engine.project_anatomy
path (LLM-only) actually runs. The LLM fills every title/step/rubric from the
cluster's live posting — content is never hard-coded here (content-quality H1).
If the LLM is unavailable the worker records a visible generation_error; the
skeleton titles are transient scaffolding, never presented as generated content.
"""

# The 3 replication projects. Titles match the mockup (Day 4 = Project 2,
# "Rebuild the Abandoned-Cart Flow"). gap_fill_topic on project 2 is the
# auto-detected nuance surfaced on the day view before Day 5.
PROJECTS = [
    {
        "project_index": 1,
        "title": "Rebuild the Checkout Welcome Flow",
        "source_url": "https://example.com/checkout-welcome",
        "clone_steps": [
            "Trigger: Checkout Started",
            "Blocks: 1 welcome email",
            "Dynamic block: order + cart summary",
        ],
        "rubric": [
            "Welcome email sends within 1 hour of checkout",
            "Dynamic cart summary present in the email",
            "Email renders correctly on mobile",
        ],
        "gap_fill_topic": None,
    },
    {
        "project_index": 2,
        "title": "Rebuild the Abandoned-Cart Flow",
        "source_url": "https://example.com/abandoned-cart",
        "clone_steps": [
            "Trigger: Checkout Abandoned",
            "Sequence: 2-step recovery (30 min + 24 hr)",
            "Dynamic block: cart summary + coupon at step 2",
        ],
        "rubric": [
            "Recovery flow triggers when a cart is abandoned",
            "Dynamic cart summary present",
            "Coupon step included",
        ],
        "gap_fill_topic": "mobile responsiveness",
    },
    {
        "project_index": 3,
        "title": "Rebuild the Post-Purchase Upsell Flow",
        "source_url": "https://example.com/post-purchase",
        "clone_steps": [
            "Trigger: Purchase Completed",
            "Upsell block: complementary product",
            "Winback: 30-day cadence",
        ],
        "rubric": [
            "Post-purchase trigger fires on completion",
            "Upsell block renders with the product",
            "Winback sequence is scheduled",
        ],
        "gap_fill_topic": None,
    },
]


def create_projects(sb, sprint_id):
    """Create the 3 copy-work project rows for a sprint. Idempotent per sprint.

    Seeds a placeholder skeleton (mockup titles/source, EMPTY clone_steps/rubric)
    — the async worker's LLM-only project_anatomy fills every content field so
    it matches the learner's actual cluster. If the LLM is unavailable the
    worker records a visible generation_error instead of template content.
    """
    for p in PROJECTS:
        sb.table("copywork_projects").upsert({
            "sprint_id": sprint_id,
            "project_index": p["project_index"],
            "title": p["title"],
            "source_url": p["source_url"],
            "clone_steps": [],
            "rubric": [],
            "gap_fill_topic": p["gap_fill_topic"],
            "done": False,
        }, on_conflict="sprint_id,project_index").execute()
    return len(PROJECTS)
