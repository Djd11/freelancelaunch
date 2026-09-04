"""One-off: apply scripts/freelancer_seed.json (real Freelancer.com gigs) to job_feed.

  * Inserts every scraped gig (deduped by source_url).
  * The 5 admin-seeded placeholder rows are FK-referenced by capstone_briefs,
    so they cannot be deleted — instead each is UPDATED in place with a real
    email-automation gig (title, description, source_url, rate), which fixes
    the "Open posting → example.com" dogfood finding (M2) while keeping the
    capstone briefs valid.
  * Removes the two Arbeitnow full-time rows an earlier ingest attempt added
    (wrong supply type for this product).
  * Re-runs assign_unlock_days + refresh_cluster so the meter and the
    "N active jobs" counts reflect the real feed.

Run:  .venv/bin/python scripts/apply_freelancer_seed.py
Idempotent: dedup by URL; placeholder update is stable.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SEED = Path(__file__).resolve().parent / "freelancer_seed.json"


def main():
    jobs = json.loads(SEED.read_text())
    print(f"seed has {len(jobs)} gigs")
    from app import create_app
    app = create_app()
    with app.app_context():
        from services.supabase_client import get_supabase
        from services.demand_intelligence import assign_unlock_days, refresh_cluster
        sb = get_supabase()

        existing = {r["source_url"] for r in sb.table("job_feed")
                    .select("source_url").not_.is_("source_url", "null").limit(2000).execute().data}

        # Clean the two Arbeitnow full-time rows from the earlier attempt.
        junk = sb.table("job_feed").select("id,title").eq("source_platform", "arbeitnow").execute().data
        for r in junk:
            sb.table("job_feed").delete().eq("id", r["id"]).execute()
            print("deleted arbeitnow row:", r["title"][:50])

        inserted = {}
        for j in jobs:
            if j["url"] in existing:
                continue
            row = {
                "cluster_key": j["cluster"],
                "title": j["title"][:500],
                "source": "freelancer",
                "source_platform": "freelancer",
                "source_url": j["url"][:1000],
                "description": j["description"][:5000],
                "skills": [j["skill"].replace("-", " ").title()],
                "rate": j["rate"],
                "experience_needed": "intermediate",
                "review_count": 0,
                "unlock_day": 1,
                "status": "active",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                sb.table("job_feed").insert(row).execute()
                existing.add(j["url"])
                inserted[j["cluster"]] = inserted.get(j["cluster"], 0) + 1
            except Exception as exc:
                print("insert failed:", j["title"][:40], str(exc)[:80])
        print("inserted:", inserted)

        # Fix the 5 placeholder rows in place: give each a real email-automation gig.
        # The gig normally already exists as a fresh 'freelancer' row from the
        # insert above — we DELETE that row and move its data onto the
        # placeholder (whose id is FK-referenced by capstone_briefs and cannot
        # be removed), so the feed keeps one row per URL either way.
        placeholders = sb.table("job_feed").select("id,title").like("source_url", "https://example.com%").execute().data
        real_email = [j for j in jobs if j["cluster"] == "email-automation"]
        # Prefer gigs whose title matches the placeholder's theme.
        THEMES = {
            "abandoned cart": ["cart", "abandon", "checkout"],
            "segment": ["segment", "list", "campaign"],
            "upsell": ["upsell", "flow", "automation"],
            "klaviyo": ["klaviyo"],
            "revamp": ["email", "marketing", "campaign"],
        }
        used = set()
        for ph in placeholders:
            title_l = ph["title"].lower()
            want = next((kw for key, kw in THEMES.items() if key in title_l), [])
            pick = next((j for j in real_email
                         if j["url"] not in used and (not want or any(w in j["title"].lower() for w in want))),
                        None)
            if pick is None:
                pick = next((j for j in real_email if j["url"] not in used), None)
            if pick is None:
                continue
            used.add(pick["url"])
            # Remove the standalone row for this gig (added by the insert pass)
            # so the unique-URL index doesn't clash with the placeholder update.
            dupes = sb.table("job_feed").select("id").eq("source_url", pick["url"]).execute().data
            for d in dupes:
                if d["id"] != ph["id"]:
                    sb.table("job_feed").delete().eq("id", d["id"]).execute()
            sb.table("job_feed").update({
                "title": pick["title"][:500],
                "description": pick["description"][:5000],
                "source_url": pick["url"][:1000],
                "source": "freelancer",
                "source_platform": "manual",  # curated anchor gigs keep manual status (never relevance-filtered)
                "rate": pick["rate"],
            }).eq("id", ph["id"]).execute()
            print(f"placeholder '{ph['title'][:30]}' -> real gig '{pick['title'][:40]}'")

        for cluster in ("email-automation", "web-scraping", "ai-chatbots"):
            n = assign_unlock_days(sb, cluster)
            refresh_cluster(sb, cluster)
            cnt = sb.table("job_feed").select("id", count="exact").eq("cluster_key", cluster).eq("status", "active").execute().count
            cl = sb.table("job_clusters").select("job_count,avg_rate").eq("cluster_key", cluster).limit(1).execute().data
            print(f"{cluster}: feed={cnt} job_clusters.job_count={cl[0]['job_count'] if cl else '?'} avg_rate={cl[0]['avg_rate'] if cl else '?'}")


if __name__ == "__main__":
    main()
