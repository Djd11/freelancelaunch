"""
Curriculum Generator — Uses LLM to create a 30/60 day learning plan for any topic
"""
import json
import httpx
from flask import current_app

def generate_curriculum(topic_name: str, total_days: int = 30) -> list[dict]:
    """
    Call an LLM to generate a structured day-by-day curriculum for a given topic.
    Returns a list of dicts: [{day_number, title, description, practice_task, apply_task, video_title}, ...]
    """
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
        resp = httpx.post(api_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        
        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        
        curriculum = json.loads(content)
        return curriculum
    
    except Exception as e:
        # Fallback: return a generic curriculum
        return _fallback_curriculum(topic_name, total_days)


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
