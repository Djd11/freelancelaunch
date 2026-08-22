"""
proposal_engine — engineered proposals (engineering-spec §3 J6, arch §5.5).

Drafts are LLM-generated from the cluster's live job postings, grounded in the
learner's Mock Contract proof. Content is LLM-only (decision D9): there are no
hard-coded proposal templates. `generate_drafts` seeds skeleton rows at request
time; the async worker `fill_drafts` writes each draft's engineered body from
the LLM. On LLM failure a draft is marked with score = -1 so the page surfaces
a visible error (and re-fills on the next load). Submission is human-initiated.
"""
import json

from services.llm import call_llm, LLMGenerationError

# score sentinel: -1 means the LLM failed to generate this draft
SCORE_ERROR = -1


def _excerpt(text, limit=300):
    if not text:
        return ""
    text = " ".join((text or "").split())
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def _proposals_prompt(jobs):
    lines = []
    for job in jobs:
        title = job.get("title") or "this job"
        desc = _excerpt(job.get("description") or "")
        lines.append(f"- \"{title}\": {desc}" if desc else f"- \"{title}\"")
    return (
        "You engineer proposal drafts for a freelancer who just completed a "
        "14-day sprint that included a paid-style Mock Contract in the same niche. "
        "For EACH live job posting below, write a short proposal draft with: "
        "an opening hook that starts with \"I see you need\", a proof sentence "
        "that references the Mock Contract the freelancer just fulfilled, and a "
        "call to action. Use only facts from each posting — no invented credentials. "
        'Reply with JSON only: [{"job_title": "...", "hook": "...", "proof": "...", '
        '"cta": "...", "score": 85}, ...]. '
        "Jobs:\n" + "\n".join(lines)
    )


def _parse_proposals(text):
    """Parse the batched proposals JSON array. Returns a dict keyed by job_title."""
    if not text:
        raise LLMGenerationError("No LLM provider answered for the proposal drafts")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").lstrip("json").strip()
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        raise LLMGenerationError("LLM returned unparseable proposal drafts")
    if not isinstance(data, list):
        raise LLMGenerationError("LLM returned unparseable proposal drafts")
    out = {}
    for item in data:
        if not isinstance(item, dict) or not item.get("job_title"):
            continue
        hook = str(item.get("hook") or "").strip()
        proof = str(item.get("proof") or "").strip()
        cta = str(item.get("cta") or "").strip()
        if not hook:
            continue
        body = "\n\n".join(p for p in (hook, proof, cta) if p)
        try:
            score = max(0, min(100, int(item.get("score") or 85)))
        except (TypeError, ValueError):
            score = 85
        out[item["job_title"].strip()] = {
            "template_body": body,
            "hook": hook,
            "score": score,
        }
    return out


def generate_drafts(sb, sprint, cluster_key, user_id):
    """Seed one skeleton draft per live active posting (idempotent).

    Synchronous and fast — the LLM body is filled asynchronously by fill_drafts
    so the proposals request never blocks on the LLM (arch §7 async generation).
    """
    feed = sb.table("job_feed").select("*").eq("cluster_key", cluster_key).eq("status", "active").execute().data
    existing = {p.get("job_feed_id") for p in
                sb.table("proposals").select("job_feed_id").eq("sprint_id", sprint["id"]).execute().data}
    for job in feed:
        if job["id"] in existing:
            continue
        sb.table("proposals").insert({
            "sprint_id": sprint["id"],
            "job_feed_id": job["id"],
            "template_body": None,
            "hooks": [],
            "status": "draft",
            "platform": None,
            "score": None,
        }).execute()
    return list_proposals(sb, sprint, cluster_key)


def fill_drafts(sb, sprint_id, cluster_key=None):
    """Async worker: LLM-generate the engineered body for every empty draft.

    One batched call for all unfilled drafts (score is None or -1). On LLM
    failure the affected drafts are marked score=-1 — the page surfaces a
    visible error and the next load retries the fill (self-healing).
    """
    if not cluster_key:
        rows = sb.table("sprints").select("cluster_key").eq("id", sprint_id).limit(1).execute().data
        cluster_key = (rows[0].get("cluster_key") or "email-automation") if rows else "email-automation"
    drafts = sb.table("proposals").select("id,job_feed_id,template_body,score") \
        .eq("sprint_id", sprint_id).eq("status", "draft").execute().data
    # Pending = never filled (no template_body) or previously failed (score == -1).
    pending = [d for d in drafts if not d.get("template_body") or d.get("score") == SCORE_ERROR]
    if not pending:
        return
    feed = sb.table("job_feed").select("id,title,description") \
        .eq("cluster_key", cluster_key).eq("status", "active").execute().data
    by_id = {j["id"]: j for j in feed}
    jobs = [by_id.get(d["job_feed_id"]) for d in pending]
    jobs = [j for j in jobs if j]
    if not jobs:
        return
    try:
        parsed = _parse_proposals(call_llm(_proposals_prompt(jobs), timeout=90, max_retries=3, backoff_base=2))
    except LLMGenerationError:
        # Mark every pending draft as failed — the page shows a visible error.
        for d in pending:
            sb.table("proposals").update({"score": SCORE_ERROR}).eq("id", d["id"]).execute()
        raise
    for d in pending:
        job = by_id.get(d["job_feed_id"]) or {}
        entry = parsed.get((job.get("title") or "").strip())
        if not entry:
            sb.table("proposals").update({"score": SCORE_ERROR}).eq("id", d["id"]).execute()
            continue
        sb.table("proposals").update({
            "template_body": entry["template_body"],
            "hooks": [entry["hook"]],
            "score": entry["score"],
        }).eq("id", d["id"]).execute()


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
            "template_body": p.get("template_body"),
            "score": p.get("score"),
        })
    return out


def verified_platforms(sb, user_id):
    rows = sb.table("user_platforms").select("platform").eq("user_id", user_id).execute().data
    return [r["platform"] for r in rows]
