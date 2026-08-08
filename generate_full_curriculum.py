"""
Generate 30-day curriculum using OpenCode.ai LLM (big-pickle → deepseek fallback)
and save to Supabase. All LLM settings come from services/llm_config (single source).
Run: python generate_full_curriculum.py [topic_slug] [topic_name] [model]
"""
import httpx
import json
import time
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from services.supabase_client import get_supabase_service
from services.llm_config import get_provider_chain, call_llm

TOPIC = "Web Scraping with Python"

WEEKS = [
    ("Foundation", [
        "Introduction to Web Scraping",
        "How HTTP Requests Work",
        "HTML Parsing with BeautifulSoup",
        "CSS Selectors & Data Extraction",
        "Handling Dynamic Content",
        "Working with APIs vs Scraping",
        "Week 1 Review & Mini Project",
    ]),
    ("Building", [
        "Scraping at Scale with Best Practices",
        "Rate Limiting & Politeness",
        "Rotating Proxies & User Agents",
        "Error Handling & Retry Logic",
        "Data Storage (CSV, JSON, SQLite)",
        "Real Project: E-commerce Scraper",
        "Week 2 Review & Optimization",
    ]),
    ("Application", [
        "Creating Your Freelance Scraper Service",
        "Pricing Your Scraping Services",
        "Writing Proposals for Scraping Jobs",
        "Building a Client Dashboard",
        "Handling CAPTCHAs & Anti-Bot Measures",
        "Delivering Quality Work to Clients",
        "Week 3 Review & Portfolio Building",
    ]),
    ("Mastery", [
        "Scaling Your Freelance Business",
        "Building Reusable Scraper Templates",
        "Advanced Techniques & Headless Browsers",
        "Managing Multiple Clients",
        "From Scraper to Data Product",
        "Client Communication & Retention",
        "Graduation: Your Action Plan",
    ]),
]


def generate_day(day_num, theme, day_title, next_title, topic_name, model=None):
    prompt = f"""You are designing Day {day_num} of a 30-day "{topic_name}" freelancing curriculum.
Week theme: {theme}
Today's lesson: {day_title}

Generate a lesson with EXACTLY these 6 sections:

## HOOK
(2 sentences) Connect to learner's goal of landing a client. Include a surprising fact. End with a driving question.

## CONCEPT
(3-4 paragraphs, 3-4 sentences each) Teach ONE concept about {day_title}. Use a real freelancing example. Use a metaphor. Answer why it matters for getting clients.

## PRACTICE
(3-5 steps) One hands-on exercise producing a tangible output. Include a template reference. 20-25 min.

## RETRIEVAL
1. Write down the 3 most important things you learned today.
2. Explain the core concept to someone who knows nothing about it.
3. What's one thing you're still confused about?

## SPACED REVIEW
(2-3 sentences) Connect to prior learning from Day {max(1, day_num-1)}. Include one application question.

## PREVIEW
(1 sentence) Tease tomorrow: {next_title}.

Rules: 8th grade level, specific examples, actionable, 45-60 min total."""

    if model:
        # Model override via CLI arg — use the chain's endpoint/key with this model
        from services.llm_config import get_provider_chain
        chain = get_provider_chain()
        if chain:
            provider = dict(chain[0])
            provider["model"] = model
            try:
                headers = {"Content-Type": "application/json"}
                if provider["api_key"]:
                    headers["Authorization"] = f"Bearer {provider['api_key']}"
                resp = httpx.post(
                    provider["url"], headers=headers,
                    json={"model": model, "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 2048, "temperature": 0.7},
                    timeout=90
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                print(f"  Error {resp.status_code} ({model})", flush=True)
                return ""
            except Exception as e:
                print(f"  Error {model}: {e}", flush=True)
                return ""

    # Default path: call_llm handles big-pickle → deepseek chain
    return call_llm(prompt, max_tokens=2048) or ""


def parse_sections(content):
    """Extract the 6 sections from LLM output."""
    hook = concept = practice = retrieval = spaced = preview = ""
    if "## HOOK" in content:
        hook = content.split("## HOOK")[1].split("##")[0].strip()
    if "## CONCEPT" in content:
        concept = content.split("## CONCEPT")[1].split("##")[0].strip()
    if "## PRACTICE" in content:
        practice = content.split("## PRACTICE")[1].split("##")[0].strip()
    if "## RETRIEVAL" in content:
        retrieval = content.split("## RETRIEVAL")[1].split("##")[0].strip()
    if "## SPACED REVIEW" in content:
        spaced = content.split("## SPACED REVIEW")[1].split("##")[0].strip()
    if "## PREVIEW" in content:
        preview = content.split("## PREVIEW")[1].split("##")[0].strip()
    return hook, concept, practice, retrieval, spaced, preview


def main():
    topic_slug = sys.argv[1] if len(sys.argv) > 1 else "web-scraping-python"
    topic_name = sys.argv[2] if len(sys.argv) > 2 else "Web Scraping with Python"
    model = sys.argv[3] if len(sys.argv) > 3 else "big-pickle"

    print(f"🎓 Generating 30-day curriculum for: {topic_name} (slug: {topic_slug})")
    print(f"🤖 Model: {model}")
    # Show the resolved provider chain so it's obvious what's being used
    from services.llm_config import get_provider_chain
    chain = get_provider_chain()
    if chain:
        print(f"🔌 Provider: {chain[0]['url']}")
        print(f"⚡ Chain: {', '.join(p['name'] for p in chain)}")
    else:
        print("⚠️  No LLM key configured — days will use fallback content!")

    # Generic weekly structure — topics adapt via the LLM prompt
    WEEKS = [
        ("Foundation", [
            "Introduction to " + topic_name,
            "Core Concepts & Terminology",
            "First Hands-On Project",
            "Tools & Environment Setup",
            "Real-World Example Walkthrough",
            "Common Pitfalls & How to Avoid Them",
            "Week 1 Review & Portfolio Piece",
        ]),
        ("Building", [
            "Intermediate Techniques",
            "Advanced Concepts",
            "Workflow Optimization",
            "Quality Standards & Best Practices",
            "Client Communication Skills",
            "Project Planning & Scoping",
            "Week 2 Review & Real Project",
        ]),
        ("Application", [
            "Creating Your Freelance Service",
            "Pricing Your Services",
            "Writing Winning Proposals",
            "Building a Client Portfolio",
            "Handling Difficult Clients",
            "Delivering Quality Work",
            "Week 3 Review & Portfolio Building",
        ]),
        ("Mastery", [
            "Scaling Your Freelance Business",
            "Building Reusable Templates",
            "Advanced Techniques",
            "Managing Multiple Clients",
            "From Service to Product",
            "Client Retention & Referrals",
            "Graduation: Your Action Plan",
        ]),
    ]

    day_num = 0
    all_days = []

    for theme, days in WEEKS:
        for i, day_title in enumerate(days):
            day_num += 1
            next_title = days[(i + 1) % len(days)] if day_num < 30 else "Graduation"

            print(f"[{day_num}/30] {day_title}...", end=" ", flush=True)
            content = generate_day(day_num, theme, day_title, next_title, topic_name, model)

            if content:
                print(f"OK ({len(content)} chars)")
            else:
                print("EMPTY — using fallback")

            all_days.append({
                "day": day_num,
                "title": day_title,
                "content": content,
                "theme": theme,
            })
            time.sleep(1.5)  # Rate limiting

    print(f"\nGenerated: {sum(1 for d in all_days if d['content'])}/{len(all_days)} days")

    # Save to database
    print("Saving to database...")
    app = create_app()
    with app.app_context():
        sb = get_supabase_service()
        tid = sb.table("topics").select("id").eq("slug", topic_slug).limit(1).execute().data[0]["id"]

        # Delete old data
        old_curr = sb.table("curricula").select("id").eq("topic_id", tid).limit(1).execute()
        if old_curr.data:
            sb.table("curriculum_days").delete().eq("curriculum_id", old_curr.data[0]["id"]).execute()
            sb.table("curricula").delete().eq("id", old_curr.data[0]["id"]).execute()

        # Create new curriculum
        curr = sb.table("curricula").insert({"topic_id": tid, "total_days": 30}).execute()
        cid = curr.data[0]["id"]

        # Get cohort
        cohort = sb.table("cohorts").select("id").eq("topic_id", tid).limit(1).execute()
        cohort_id = cohort.data[0]["id"] if cohort.data else None

        # Delete old cohort_videos
        if cohort_id:
            sb.table("cohort_videos").delete().eq("cohort_id", cohort_id).execute()

        saved = 0
        for item in all_days:
            hook, concept, practice, retrieval, spaced, preview = parse_sections(item["content"])

            full_desc = f"{hook}\n\n{concept}"[:2000] if hook else concept[:2000]
            full_practice = f"{practice}\n\nRETRIEVAL:\n{retrieval}"[:2000] if practice else ""
            full_apply = f"{spaced}\n\nPREVIEW:\n{preview}"[:1000]

            sb.table("curriculum_days").insert({
                "curriculum_id": cid,
                "day_number": item["day"],
                "title": item["title"],
                "description": full_desc,
                "learning_objectives": hook[:500],
                "practice_task": full_practice,
                "apply_task": full_apply,
                "video_title": f"{topic_name} — Day {item['day']}: {item['title']}",
            }).execute()
            saved += 1

            if cohort_id:
                sb.table("cohort_videos").insert({
                    "cohort_id": cohort_id,
                    "day_number": item["day"],
                    "youtube_title": f"Day {item['day']}: {item['title']}",
                    "production_status": "ready",
                }).execute()

        # Verify
        total = sb.table("curriculum_days").select("id", count="exact").eq("curriculum_id", cid).execute()
        count = getattr(total, "count", 0)
        print(f"Saved {saved} days to database. Verified: {count} days.")

        # Show sample
        sample = sb.table("curriculum_days").select("title,description").eq("curriculum_id", cid).order("day_number").limit(1).execute()
        if sample.data:
            d = sample.data[0]
            print(f"\nSample Day 1:")
            print(f"  Title: {d['title']}")
            print(f"  Description: {d['description'][:150]}...")


if __name__ == "__main__":
    main()
