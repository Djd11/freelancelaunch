"""
Topics routes — browse curated topics, view topic detail
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from services.supabase_client import get_supabase

topics_bp = Blueprint("topics", __name__)


# ─── Curated MVP topics (hard-coded, scraper comes Phase 2) ───
CURATED_TOPICS = [
    {
        "slug": "web-scraping-python",
        "name": "Web Scraping with Python",
        "tagline": "Extract data from websites at scale",
        "description": "Learn to build scrapers with requests, BeautifulSoup, Selenium, and Playwright. From static pages to dynamic JavaScript sites.",
        "demand_score": 92,
        "job_count": 247,
        "avg_rate": 30,
        "trend": "growing",
        "difficulty": "Beginner-Intermediate",
        "weeks_to_first_gig": 3,
        "color": "#2563eb",
        "icon": "🕷️",
        "skills": ["Python", "HTTP", "HTML/CSS", "JSON", "APIs"],
        "outcomes": "Land contracts for data extraction, competitor monitoring, lead generation, and research automation."
    },
    {
        "slug": "n8n-automation",
        "name": "n8n Workflow Automation",
        "tagline": "Automate repetitive business processes",
        "description": "Build visual workflows with n8n — connect apps, transform data, trigger actions. No-code automation that clients pay for.",
        "demand_score": 85,
        "job_count": 89,
        "avg_rate": 45,
        "trend": "growing",
        "difficulty": "Beginner",
        "weeks_to_first_gig": 2,
        "color": "#7c3aed",
        "icon": "⚡",
        "skills": ["n8n", "APIs", "JSON", "Webhooks", "Zapier alternatives"],
        "outcomes": "Automate email responses, CRM updates, data syncs, and reporting for small businesses."
    },
    {
        "slug": "seo-content-writing",
        "name": "SEO Content Writing",
        "tagline": "Write content that ranks on Google",
        "description": "Master AI-assisted content creation with SEO optimization. Research keywords, structure articles, and write content businesses pay for.",
        "demand_score": 95,
        "job_count": 1240,
        "avg_rate": 25,
        "trend": "stable",
        "difficulty": "Beginner",
        "weeks_to_first_gig": 1,
        "color": "#059669",
        "icon": "✍️",
        "skills": ["Writing", "SEO", "Keyword Research", "AI Tools", "Editing"],
        "outcomes": "Get paid for blog posts, website copy, newsletters, and social media content."
    },
    {
        "slug": "data-analysis-pandas",
        "name": "Data Analysis with Pandas",
        "tagline": "Turn messy data into actionable insights",
        "description": "Clean, analyze, and visualize data using Python's pandas library. Create reports and dashboards clients love.",
        "demand_score": 88,
        "job_count": 340,
        "avg_rate": 35,
        "trend": "stable",
        "difficulty": "Intermediate",
        "weeks_to_first_gig": 4,
        "color": "#dc2626",
        "icon": "📊",
        "skills": ["Python", "Pandas", "CSV/Excel", "Charts", "Statistics"],
        "outcomes": "Freelance as a data analyst — cleaning datasets, building reports, creating dashboards."
    },
    {
        "slug": "wordpress-development",
        "name": "Basic WordPress Development",
        "tagline": "Build and customize WordPress sites",
        "description": "From setup to custom themes and plugins. WordPress powers 43% of the web — there's endless freelance work.",
        "demand_score": 93,
        "job_count": 2100,
        "avg_rate": 30,
        "trend": "stable",
        "difficulty": "Beginner",
        "weeks_to_first_gig": 2,
        "color": "#d97706",
        "icon": "🌐",
        "skills": ["WordPress", "PHP basics", "CSS", "Plugins", "Themes"],
        "outcomes": "Build sites for small businesses, fix WordPress issues, customize themes, manage hosting."
    }
]


@topics_bp.route("/topics")
def explore():
    """Browse all available topics with demand data."""
    return render_template("topics/explore.html", topics=CURATED_TOPICS)



def _generate_and_save_curriculum(slug, topic_name, user_id):
    """Generate a 30-day LLM curriculum and save to database."""
    import logging
    logger = logging.getLogger(__name__)
    sb = get_supabase()
    
    # Check if curriculum already exists for this topic
    topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
    if not topic_db.data:
        logger.warning(f"No topic found for slug: {slug}")
        return
    
    topic_id = topic_db.data[0]["id"]
    
    # Check existing curriculum
    curr_resp = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
    if curr_resp.data:
        # Check if days already exist
        day_count = sb.table("curriculum_days").select("id", count="exact") \
            .eq("curriculum_id", curr_resp.data[0]["id"]).execute()
        day_ct = getattr(day_count, 'count', 0) or 0
        if day_ct >= 30:
            logger.info(f"Curriculum already exists with {day_ct} days")
            return
        curr_id = curr_resp.data[0]["id"]
    else:
        curr = sb.table("curricula").insert({
            "topic_id": topic_id,
            "total_days": 30,
        }).execute()
        curr_id = curr.data[0]["id"]
    
    # Get linked platforms for platform-specific days
    linked_platforms = []
    try:
        plat_resp = sb.table("user_platforms").select("platform") \
            .eq("user_id", user_id).eq("status", "verified").execute()
        linked_platforms = [p["platform"] for p in (plat_resp.data or [])]
    except Exception:
        pass
    
    # Generate curriculum using LLM
    from services.curriculum_generator import generate_curriculum
    curriculum = generate_curriculum(topic_name, 30, platforms=linked_platforms)
    
    if curriculum and len(curriculum) > 0:
        for day in curriculum:
            try:
                sb.table("curriculum_days").insert({
                    "curriculum_id": curr_id,
                    "day_number": day.get("day_number", 1),
                    "title": day.get("title", f"Day {day.get('day_number', 1)}"),
                    "description": day.get("description", f"Lesson for {topic_name}"),
                    "learning_objectives": day.get("description", ""),
                    "practice_task": day.get("practice_task", "Practice exercise"),
                    "apply_task": day.get("apply_task", "Apply what you learned"),
                    "video_title": day.get("video_title", f"{topic_name} — Day {day.get('day_number', 1)}"),
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to insert day {day.get('day_number')}: {e}")
        
        logger.info(f"Saved {len(curriculum)} curriculum days for {topic_name}")

@topics_bp.route("/topics/<slug>")
def detail(slug):
    """View a specific topic's detail page."""
    topic = next((t for t in CURATED_TOPICS if t["slug"] == slug), None)
    if not topic:
        flash("Topic not found", "error")
        return redirect(url_for("topics.explore"))
    
    # If user is logged in, check if they already have a pipeline for this topic
    existing_pipeline = None
    is_admin = False
    curriculum_days = []
    is_enrolled = False
    
    if g.user:
        sb = get_supabase()
        resp = sb.table("freelance_pipeline").select("*") \
            .eq("user_id", g.user["id"]) \
            .eq("topic", slug) \
            .limit(1) \
            .execute()
        if resp.data:
            existing_pipeline = resp.data[0]
            is_enrolled = True
        
        # Check if admin (email matches)
        admin_email = current_app.config.get("ADMIN_EMAIL", "")
        user_email = g.user.get("avatar_url", "")
        is_admin = bool(admin_email and user_email == admin_email)
        
        # If enrolled OR admin, fetch full curriculum
        if is_enrolled or is_admin:
            try:
                topic_db = sb.table("topics").select("id").eq("slug", slug).limit(1).execute()
                if topic_db.data:
                    topic_id = topic_db.data[0]["id"]
                    curr = sb.table("curricula").select("id").eq("topic_id", topic_id).limit(1).execute()
                    if curr.data:
                        curr_id = curr.data[0]["id"]
                        days = sb.table("curriculum_days").select("*") \
                            .eq("curriculum_id", curr_id) \
                            .order("day_number", ascending=True) \
                            .limit(30) \
                            .execute()
                        curriculum_days = days.data or []
            except Exception as e:
                print(f"Failed to fetch curriculum: {e}")
    
    return render_template("topics/detail.html", 
        topic=topic, 
        pipeline=existing_pipeline,
        is_enrolled=is_enrolled,
        is_admin=is_admin,
        curriculum_days=curriculum_days,
    )


@topics_bp.route("/topics/<slug>/enroll", methods=["POST"])
def enroll(slug):
    """User enrolls in a topic — creates pipeline and assigns to cohort."""
    if not g.user:
        return redirect(url_for("auth.login", next=url_for("topics.detail", slug=slug)))
    
    topic = next((t for t in CURATED_TOPICS if t["slug"] == slug), None)
    if not topic:
        flash("Topic not found", "error")
        return redirect(url_for("topics.explore"))
    
    sb = get_supabase()
    
    # 1. Create or find cohort for this topic
    from datetime import date, timedelta
    today = date.today()
    
    # Find an upcoming or active cohort for this topic
    cohort_resp = sb.table("cohorts").select("*") \
        .eq("topic_id", slug) \
        .in_("status", ["upcoming", "active"]) \
        .order("start_date", desc=True) \
        .limit(1) \
        .execute()
    
    if cohort_resp.data:
        cohort = cohort_resp.data[0]
    else:
        # Determine next cohort start date (1st or 15th of month)
        if today.day < 15:
            start_date = today.replace(day=1)
            if start_date <= today:
                start_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
        else:
            start_date = date(today.year, today.month, 15)
            if start_date <= today:
                start_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
        
        cohort_resp = sb.table("cohorts").insert({
            "topic_id": slug,
            "name": f"{topic['name']} — {start_date.strftime('%B %Y')}",
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=30)).isoformat(),
            "max_days": 30,
            "status": "upcoming",
        }).execute()
        cohort = cohort_resp.data[0]
    
    # 2. Update user profile with cohort + topic
    sb.table("user_profiles").update({
        "cohort_id": cohort["id"],
        "selected_topic_id": slug,
    }).eq("user_id", g.user["id"]).execute()
    
    # 3. Create freelance pipeline entry
    existing = sb.table("freelance_pipeline").select("*") \
        .eq("user_id", g.user["id"]).eq("topic", slug).limit(1).execute()
    
    if not existing.data:
        sb.table("freelance_pipeline").insert({
            "user_id": g.user["id"],
            "topic": slug,
            "stage": "exploring",
        }).execute()
    
    # 4. Update acquisition record
    sb.table("user_acquisition").update({
        "joined_cohort_at": "now()",
        "landing_topic": slug,
    }).eq("user_id", g.user["id"]).execute()
    
    flash(f"You're enrolled in {topic['name']}! Now let's link your freelance platforms.", "success")
    
    # 5. Generate and save curriculum (in background)
    try:
        _generate_and_save_curriculum(slug, topic["name"], g.user["id"])
    except Exception as e:
        print(f"Curriculum generation error: {e}")
    
    return redirect(url_for("platforms.setup"))


