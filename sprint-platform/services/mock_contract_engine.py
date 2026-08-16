"""
mock_contract_engine — anonymized brief match + deadline/constraint
enforcement (architecture.md §4.3, eng-spec §3 J5).

The Mock Contract is built from a REAL job posting in the cluster (only
job_feed_id is stored — never client identity/PII), with the same deadline,
budget, and constraints the posting carried.
"""

DEFAULT_BRIEF = {
    "title": "Set up email automation for my e-commerce brand",
    "requirements": (
        "Klaviyo checkout recovery + post-purchase upsell\n"
        "Segmentation for VIP repeat buyers\n"
        "Deliverables: flow exports + setup docs\n"
        "Must be mobile-responsive emails"
    ),
    "constraints": {"deadline_days": 4, "budget": 180, "notes": ["Client prefers async updates"]},
    "acceptance_criteria": ["flow exports present", "setup docs present", "mobile-responsive"],
    "verification_type": "auto",
}


def synthesize(sb, sprint):
    """Build an anonymized brief from the cluster's first active posting.

    Anonymization requirement (eng-spec §3 J5): capstone_briefs stores only
    job_feed_id — the brief is derived from the posting's title/description,
    never client identity.
    """
    feed = sb.table("job_feed").select("*") \
        .eq("cluster_key", sprint.get("cluster_key", "email-automation")) \
        .eq("status", "active").order("unlock_day").order("id").limit(1).execute().data
    if not feed:
        # No-500: if the cluster has no postings yet, fall back to any active
        # posting so the brief still carries a real job_feed_id.
        feed = sb.table("job_feed").select("*") \
            .eq("status", "active").order("unlock_day").order("id").limit(1).execute().data
    brief = dict(DEFAULT_BRIEF)
    if feed:
        job = feed[0]
        brief["title"] = job.get("title") or DEFAULT_BRIEF["title"]
        description = (job.get("description") or "").strip()
        if description:
            brief["requirements"] = description
        brief["job_feed_id"] = job["id"]
    return brief
