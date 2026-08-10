"""
Post-generation backfill for CLI-generated curricula.

The CLI (generate_full_curriculum.py) creates curricula + curriculum_days +
cohort_videos but does NOT:
  1. re-link cohorts.curriculum_id → new curriculum
  2. set cohort_videos.curriculum_day_id → matching day rows

This script fixes both so progress tracking and preview links work.

Usage: python backfill_curriculum_links.py <topic_slug>
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from services.supabase_client import get_supabase_service


def backfill(topic_slug: str):
    app = create_app()
    with app.app_context():
        sb = get_supabase_service()

        tid_resp = sb.table("topics").select("id").eq("slug", topic_slug).limit(1).execute()
        if not tid_resp.data:
            print(f"❌ Topic not found: {topic_slug}")
            return 1
        tid = tid_resp.data[0]["id"]

        cur_resp = sb.table("curricula").select("id").eq("topic_id", tid).limit(1).execute()
        if not cur_resp.data:
            print(f"❌ No curriculum for {topic_slug} — run generation first")
            return 1
        cid = cur_resp.data[0]["id"]
        print(f"✅ Curriculum: {cid}")

        # 1. Link cohorts → curriculum
        cohorts = sb.table("cohorts").select("id").eq("topic_id", tid).execute()
        linked = 0
        for c in cohorts.data:
            if c.get("curriculum_id") != cid:
                sb.table("cohorts").update({"curriculum_id": cid}).eq("id", c["id"]).execute()
                linked += 1
        print(f"✅ Linked {linked} cohort(s) → curriculum")

        # 2. Map day_number → curriculum_day_id
        days = sb.table("curriculum_days").select("id,day_number") \
            .eq("curriculum_id", cid).execute()
        day_map = {d["day_number"]: d["id"] for d in days.data}
        print(f"✅ {len(day_map)} curriculum days indexed")

        # 3. Backfill cohort_videos.curriculum_day_id
        videos = sb.table("cohort_videos").select("id,day_number,curriculum_day_id") \
            .eq("cohort_id", cohorts.data[0]["id"]).execute() if cohorts.data else None
        filled = 0
        if videos:
            for v in videos.data:
                day_id = day_map.get(v.get("day_number"))
                if day_id and v.get("curriculum_day_id") != day_id:
                    sb.table("cohort_videos").update({"curriculum_day_id": day_id}) \
                        .eq("id", v["id"]).execute()
                    filled += 1
        print(f"✅ Backfilled curriculum_day_id on {filled} cohort_videos")

        # Verify
        v2 = sb.table("cohort_videos").select("id", count="exact") \
            .eq("cohort_id", cohorts.data[0]["id"]).execute() if cohorts.data else None
        print(f"✅ cohort_videos total: {v2.count if v2 else 0}")
        print("🎉 Backfill complete")
        return 0


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "web-scraping-python"
    sys.exit(backfill(slug))
