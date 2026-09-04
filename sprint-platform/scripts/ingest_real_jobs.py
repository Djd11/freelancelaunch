"""One-off: replace placeholder job_feed rows with REAL live postings.

Context (dogfood 2026-09-04): job_feed held only 5 admin-seeded rows whose
description was the literal string "Anonymized real job posting — …" and whose
source_url was https://example.com/job/N — clicking "Open posting →" sent users
to example.com. The configured RSS connection (backend-programming feed →
email-automation cluster) relevance-filters every item out, so the feed never
grew. This script ingests from keyless sources that actually respond:

  * Arbeitnow job-board API (175 listings, all categories)
  * WeWorkRemotely programming + design category RSS (marketing/writing 403)

Matching uses word-boundary regex against each cluster's keywords (the plain
substring check in feed_ingest lets "rag" match "storage"). After inserting,
the 5 example.com placeholders are deleted and each cluster gets a proper
unlock_day distribution + honest job_count via demand_intelligence.

Run:  .venv/bin/python scripts/ingest_real_jobs.py
Idempotent: URL dedup against existing job_feed rows.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

# cluster_key -> extra regex keywords (lowercase). Word-boundary matched.
CLUSTER_PATTERNS = {
    "email-automation": [
        r"\bklaviyo\b", r"\bmailchimp\b", r"\bhubspot\b", r"\bemail\b",
        r"\bn8n\b", r"\b(zapier|make\.com)\b", r"\bnewsletter\b",
    ],
    "web-scraping": [
        r"\bscrap(?:ing|er)\b", r"\bbeautifulsoup\b", r"\bdata extraction\b",
        r"\blead generation\b", r"\bdata mining\b",
    ],
    "ai-chatbots": [
        r"\bchat\s?bot\b", r"\bchatgpt\b", r"\bopenai\b", r"\bllm\b",
        r"\b\bagi\b", r"(?<![a-z])rag(?![a-z])", r"\bconversational ai\b",
        r"\bai agent\b",
    ],
}


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read()


def fetch_arbeitnow():
    data = json.loads(_get("https://www.arbeitnow.com/api/job-board-api"))
    out = []
    for j in data.get("data", []):
        ts = j.get("published_at")
        posted = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        rate = None
        sal = j.get("salary") or {}
        if isinstance(sal, dict):
            rate = sal.get("min") or sal.get("max")
        out.append({
            "title": j.get("title", "").strip(),
            "company": j.get("company_name", ""),
            "url": j.get("url", ""),
            "description": re.sub(r"<[^>]+>", " ", j.get("description", ""))[:2000],
            "skills": (j.get("tags") or [])[:10],
            "rate": float(rate) if rate else None,
            "posted_at": posted,
            "source_platform": "arbeitnow",
        })
    return out


def _parse_rss(xml_text, platform):
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml_text, re.S):
        def tag(name):
            m = re.search(rf"<{name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>", item, re.S)
            return m.group(1).strip() if m else ""
        link = tag("link")
        title = re.sub(r"\s+", " ", tag("title"))
        desc = re.sub(r"<[^>]+>", " ", tag("description"))[:2000]
        desc = re.sub(r"\s+", " ", desc).strip()
        posted = None
        try:
            if tag("pubDate"):
                posted = parsedate_to_datetime(tag("pubDate"))
        except Exception:
            pass
        if link and title:
            out.append({
                "title": title, "company": "", "url": link, "description": desc,
                "skills": [], "rate": None, "posted_at": posted,
                "source_platform": platform,
            })
    return out


def fetch_wwr():
    out = []
    for slug in ("programming", "design"):
        try:
            xml = _get(f"https://weworkremotely.com/categories/remote-{slug}-jobs.rss").decode("utf-8", "ignore")
            out.extend(_parse_rss(xml, "rss"))
        except Exception as exc:
            print(f"  WWR {slug} failed: {exc}")
    return out


def match_cluster(job):
    hay = (job["title"] + " " + job["description"][:300]).lower()
    for cluster, pats in CLUSTER_PATTERNS.items():
        if any(re.search(p, hay) for p in pats):
            return cluster
    return None


def main():
    from app import create_app
    app = create_app()
    with app.app_context():
        from services.supabase_client import get_supabase
        from services.demand_intelligence import assign_unlock_days, refresh_cluster
        sb = get_supabase()

        existing_urls = {r["source_url"] for r in sb.table("job_feed")
                         .select("source_url").not_.is_("source_url", "null").limit(2000).execute().data}

        jobs = fetch_arbeitnow() + fetch_wwr()
        print(f"fetched {len(jobs)} postings from live sources")

        inserted = {}
        for job in jobs:
            cluster = match_cluster(job)
            if not cluster or not job["url"] or job["url"] in existing_urls:
                continue
            row = {
                "cluster_key": cluster,
                "title": job["title"][:500],
                "source": job["source_platform"],
                "source_platform": job["source_platform"],
                "source_url": job["url"][:1000],
                "description": job["description"][:5000] or None,
                "skills": job["skills"][:10],
                "rate": job["rate"],
                "experience_needed": "intermediate",
                "review_count": 0,
                "unlock_day": 1,
                "status": "active",
                "posted_at": job["posted_at"].isoformat() if job["posted_at"] else None,
            }
            try:
                sb.table("job_feed").insert(row).execute()
                existing_urls.add(job["url"])
                inserted[cluster] = inserted.get(cluster, 0) + 1
                print(f"  + [{cluster}] {job['title'][:60]}")
            except Exception as exc:
                print(f"  ! insert failed for {job['title'][:40]}: {exc}")
        print("inserted:", inserted or "none")

        # Remove the fake seed rows (example.com URLs + placeholder description).
        junk = sb.table("job_feed").select("id,title").like("source_url", "https://example.com%").execute().data
        for r in junk:
            sb.table("job_feed").delete().eq("id", r["id"]).execute()
        print(f"deleted {len(junk)} placeholder rows")

        # Honest counts + unlock distribution for every cluster that got jobs.
        for cluster in set(inserted) | {"email-automation", "web-scraping", "ai-chatbots"}:
            n = assign_unlock_days(sb, cluster)
            refresh_cluster(sb, cluster)
            print(f"cluster {cluster}: {n} postings redistributed + counts refreshed")


if __name__ == "__main__":
    main()
