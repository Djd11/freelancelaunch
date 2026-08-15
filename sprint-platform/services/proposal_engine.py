"""
proposal_engine — engineered proposals (engineering-spec §3 J6, arch §5.5).
Drafts are pre-generated from the live job feed with job-specific hooks +
proof pulled from the Mock Contract (case study). Submission is human-initiated.
"""

DEFAULT_TEMPLATE = {
    "hook": "I see you need a Klaviyo flow that recovers abandoned carts — "
            "I just rebuilt exactly that flow for a mock client and it passed a "
            "3-point checklist. I can have your version live in 3 days.",
    "proof": "I completed a 4-day brief with checkout recovery + VIP segmentation. "
             "Here's the case study — problem, solution, result.",
    "cta": "Happy to run a quick scope call this week.",
}


def generate_drafts(sb, sprint, cluster_key, user_id):
    """Create a draft proposal for each live active posting in the cluster."""
    feed = sb.table("job_feed").select("*").eq("cluster_key", cluster_key).eq("status", "active").execute().data
    existing = {p.get("job_feed_id") for p in
                sb.table("proposals").select("job_feed_id").eq("sprint_id", sprint["id"]).execute().data}
    for job in feed:
        if job["id"] in existing:
            continue
        hook = f"I see you need {job.get('title', 'this')} — I rebuilt a matching flow for a mock client."
        sb.table("proposals").insert({
            "sprint_id": sprint["id"],
            "job_feed_id": job["id"],
            "template_body": hook,
            "hooks": [hook],
            "status": "draft",
            "platform": None,
            "score": 85,
        }).execute()
    return list_proposals(sb, sprint, cluster_key)


def list_proposals(sb, sprint, cluster_key):
    """Proposals for a sprint, joined with the job title + rate."""
    rows = sb.table("proposals").select("*").eq("sprint_id", sprint["id"]).execute().data
    feed_by_id = {r["id"]: r for r in
                  sb.table("job_feed").select("*").eq("cluster_key", cluster_key).execute().data}
    out = []
    for p in rows:
        job = feed_by_id.get(p.get("job_feed_id"), {})
        out.append({
            "proposal_id": p["id"],
            "job_feed_id": p.get("job_feed_id"),
            "title": job.get("title", "Live job"),
            "rate": job.get("rate", 0),
            "status": p.get("status", "draft"),
            "platform": p.get("platform"),
        })
    return out


def verified_platforms(sb, user_id):
    rows = sb.table("user_platforms").select("platform").eq("user_id", user_id).execute().data
    return [r["platform"] for r in rows]


def template(sprint, cluster):
    """The Proposal Builder card — hook + proof-from-contract + CTA."""
    return dict(DEFAULT_TEMPLATE)
