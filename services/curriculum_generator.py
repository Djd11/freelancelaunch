"""
Curriculum Generator — Uses LLM to create a 30/60 day learning plan for any topic
Optionally appends platform-specific application training days.
"""
import json
import httpx
from flask import current_app

# Platform-specific application modules (pre-written, not LLM-generated)
PLATFORM_MODULES = {
    "upwork": {
        "name": "Upwork Proposal Mastery",
        "days": [
            {"title": "Profile Optimization for Upwork Search", "description": "Learn how Upwork's algorithm ranks freelancers and optimize your profile to appear in search results.", "practice_task": "Write your profile overview using Problem → Solution → Proof format", "apply_task": "Update your Upwork profile with the new overview and add 3 skill tags", "video_title": "Upwork Profile Optimization — Get Found by Clients"},
            {"title": "Writing Proposals That Convert", "description": "The first 2 lines decide everything. Learn how to open with the client's problem, not your skills.", "practice_task": "Rewrite 3 sample proposals — one for each of 3 real Upwork job posts", "apply_task": "Submit 1 real proposal to an Upwork job using the new format", "video_title": "Upwork Proposals — The First 2 Lines Decide Everything"},
            {"title": "Pricing Strategy for New Upwork Freelancers", "description": "Start with $50-100 projects for reviews, then raise aggressively. Budget for connects.", "practice_task": "Calculate your minimum rate using the pricing calculator, then set your Upwork rate", "apply_task": "Set your Upwork hourly rate and create 3 fixed-price project templates", "video_title": "Upwork Pricing — How to Price as a New Freelancer"},
            {"title": "Portfolio Presentation (Upwork-Specific)", "description": "Self-initiated projects count as portfolio. Show process, not just results.", "practice_task": "Create 3 portfolio items with Problem → Approach → Result format", "apply_task": "Upload portfolio items to your Upwork profile", "video_title": "Upwork Portfolio — Show Proof, Not Claims"},
            {"title": "Handling Interviews & Client Communication", "description": "Reply within 10-20 minutes. Keep first replies short. One smart question. No pricing talk initially.", "practice_task": "Role-play 3 client interview scenarios with different personality types", "apply_task": "Respond to any pending client messages within 10 minutes", "video_title": "Upwork Interviews — Win Them in the First Message"},
            {"title": "Common Upwork Mistakes & How to Avoid Them", "description": "AI proposals, spray-and-pray, lowballing, bad timing, ignoring client red flags.", "practice_task": "Audit your last 5 proposals against the 10 common mistakes checklist", "apply_task": "Fix mistakes in your active proposals", "video_title": "10 Upwork Mistakes That Cost You Contracts"},
            {"title": "Building Job Success Score & Getting Repeat Clients", "description": "JSS > 90% unlocks everything. Deliver early, communicate proactively, ask for reviews.", "practice_task": "Create a client communication schedule template", "apply_task": "Send a check-in message to your current/previous clients", "video_title": "Upwork JSS — Your Most Important Metric"},
        ]
    },
    "fiverr": {
        "name": "Fiverr Gig Mastery",
        "days": [
            {"title": "Fiverr Gig Creation & SEO", "description": "Your gig title must match EXACTLY what buyers search. Research top 5 competitors first.", "practice_task": "Research 5 top-selling gigs in your category and analyze their titles, descriptions, and tags", "apply_task": "Create your first Fiverr gig with SEO-optimized title and tags", "video_title": "Fiverr Gig SEO — Rank #1 in Search Results"},
            {"title": "Pricing Packages (Basic/Standard/Premium)", "description": "Basic = 70% of market, Standard = market rate, Premium = 130% with extras.", "practice_task": "Create your 3 pricing packages with clear scope for each tier", "apply_task": "Set up your gig packages and add 2 gig extras", "video_title": "Fiverr Packages — Price Your Gigs for Maximum Profit"},
            {"title": "Buyer Request Mastery", "description": "Send 10+ buyer requests daily. This is Fiverr's proposal equivalent — your first orders come from here.", "practice_task": "Write 5 custom buyer request responses using the proven format", "apply_task": "Send 10 buyer requests today", "video_title": "Fiverr Buyer Requests — Your Path to First Orders"},
            {"title": "First 5 Reviews Strategy", "description": "Price 20-30% below market for first 5 orders. Over-deliver on every order.", "practice_task": "Create a delivery checklist that ensures you over-deliver on every order", "apply_task": "Offer your gig at 50% discount to 5 potential buyers via custom offers", "video_title": "Fiverr First 5 Reviews — Build Trust Fast"},
            {"title": "Delivery Excellence & Review Generation", "description": "Ask for a review 2-3 days after delivery (not immediately). Handle revisions professionally.", "practice_task": "Draft 3 professional messages: delivery, follow-up, review request", "apply_task": "Apply the message sequence to your active orders", "video_title": "Fiverr Reviews — Turn One-Time Buyers into Regulars"},
            {"title": "Handling Revisions & Disputes", "description": "Protect your completion rate. Set clear scope in gig description. Handle disputes calmly.", "practice_task": "Write clear revision and cancellation policies for your gig", "apply_task": "Update your gig FAQ with scope, revision, and refund policies", "video_title": "Fiverr Disputes — Protect Your Completion Rate"},
            {"title": "Scaling from 1 Gig to 5 Gigs", "description": "Analyze which gigs perform, expand to related niches, enable gig extras.", "practice_task": "Identify 3 related gig ideas based on your first gig's success", "apply_task": "Create your second and third gigs", "video_title": "Fiverr Scaling — From 1 Gig to Full-Time Income"},
        ]
    },
    "contra": {
        "name": "Contra Portfolio Success",
        "days": [
            {"title": "Portfolio Creation (Contra-Specific)", "description": "Contra is portfolio-first. 3-5 items with Problem → Approach → Result format. Show process, not just results.", "practice_task": "Write 3 portfolio case studies with the Problem → Approach → Result format", "apply_task": "Upload your portfolio items to your Contra profile", "video_title": "Contra Portfolio — Stand Out Without Paying Commission"},
            {"title": "Profile Optimization & Skills Targeting", "description": "Complete EVERY field. Add availability status. Link external work (GitHub, Dribbble, etc.).", "practice_task": "Audit your Contra profile against the 10-point checklist", "apply_task": "Complete all missing profile fields and link your external portfolios", "video_title": "Contra Profile — Get Discovered by Clients"},
            {"title": "Pricing on a Commission-Free Platform", "description": "You keep 100% — price 15-20% higher than Upwork. Project-based pricing preferred.", "practice_task": "Calculate your Contra rate (Upwork rate × 1.2) and create 3 project pricing templates", "apply_task": "Set your Contra pricing and add 'Let's discuss' option for complex projects", "video_title": "Contra Pricing — Keep 100% of What You Earn"},
            {"title": "Client Communication & Negotiation", "description": "Clients come to you on Contra. Professional communication and clear scope definition are key.", "practice_task": "Write response templates for: initial inquiry, scope discussion, negotiation, project start", "apply_task": "Apply templates to any pending Contra inquiries", "video_title": "Contra Communication — Turn Inquiries into Contracts"},
            {"title": "Building Long-Term Client Relationships", "description": "No commission means repeat clients are more profitable. Focus on relationship building.", "practice_task": "Create a client follow-up schedule for the next 3 months", "apply_task": "Send a value-add message to your past Contra clients", "video_title": "Contra Repeat Business — The Real Advantage"},
        ]
    }
}


def generate_curriculum(topic_name: str, total_days: int = 30, platforms: list = None) -> list[dict]:
    """
    Generate a full curriculum including skill training + platform application days.
    Returns list of dicts with day_number, title, description, practice_task, apply_task, video_title
    """
    # 1. Generate skill curriculum via LLM
    skill_days = _generate_skill_curriculum(topic_name, total_days)
    
    # 2. Append platform-specific days
    platform_days = _generate_platform_days(platforms)
    
    # 3. Combine and renumber
    all_days = skill_days + platform_days
    for i, day in enumerate(all_days, 1):
        day["day_number"] = i
    
    return all_days


def _generate_skill_curriculum(topic_name: str, total_days: int = 30) -> list[dict]:
    """Original LLM-based curriculum generator for the skill itself."""
    prompt = f"""You are a freelance education expert. Create a {total_days}-day curriculum for learning "{topic_name}" for freelancing.

Each day has:
- A specific, actionable topic (one concept per day)
- A 2-minute educational video title
- A practice task (25 minutes, hands-on)
- An apply task (10 minutes, real-world application)

The goal: After this curriculum, the student should be able to offer "{topic_name}" as a freelance service on Upwork or Fiverr.

Output ONLY valid JSON array (no markdown, no explanation):
[
  {{
    "day_number": 1,
    "title": "Day title here",
    "video_title": "SEO-friendly YouTube video title here",
    "description": "What the student will learn today (1-2 sentences)",
    "practice_task": "25-min hands-on task",
    "apply_task": "10-min real-world application"
  }},
  ...
]"""

    api_url = current_app.config.get("LLM_API_URL", "http://localhost:3002/v1/chat/completions")
    api_key = current_app.config.get("LLM_API_KEY", "")
    model = current_app.config.get("LLM_MODEL", "gpt-4o-mini")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a freelance curriculum designer. Output only valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 4096
    }

    try:
        timeout = current_app.config.get("LLM_TIMEOUT", 60)
        resp = httpx.post(api_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        
        curriculum = json.loads(content)
        return curriculum
    
    except Exception as e:
        return _fallback_curriculum(topic_name, total_days)


def _generate_platform_days(platforms: list) -> list[dict]:
    """Generate platform-specific application training days."""
    if not platforms:
        return []
    
    # Prioritize platforms: Upwork (most demand) → Fiverr → Contra
    priority = {"upwork": 1, "fiverr": 2, "contra": 3}
    ordered = sorted(platforms, key=lambda p: priority.get(p, 99))
    
    all_days = []
    for platform in ordered:
        module = PLATFORM_MODULES.get(platform)
        if not module:
            continue
        for day in module["days"]:
            all_days.append({
                "title": day["title"],
                "video_title": day["video_title"],
                "description": day["description"],
                "practice_task": day["practice_task"],
                "apply_task": day["apply_task"],
            })
    
    return all_days


def get_platform_day_count(platforms: list) -> int:
    """Get total number of platform application days."""
    if not platforms:
        return 0
    return sum(len(PLATFORM_MODULES[p]["days"]) for p in platforms if p in PLATFORM_MODULES)


def _fallback_curriculum(topic_name: str, total_days: int) -> list[dict]:
    """Generate a basic curriculum when LLM is unavailable."""
    days = []
    for i in range(1, total_days + 1):
        days.append({
            "day_number": i,
            "title": f"Day {i}: {topic_name} — Part {i}",
            "video_title": f"{topic_name} — Part {i}: Core Concepts Explained",
            "description": f"Learn advanced concepts in {topic_name}",
            "practice_task": f"Hands-on exercise related to today's {topic_name} topic",
            "apply_task": f"Apply what you learned — submit your work or research freelance opportunities"
        })
    return days
