"""
User Confidence & Nudge Engine
Computes streaks, encouragement messages, milestones, and confidence scores.
"""
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


def compute_streak(completed_dates: list) -> int:
    """Compute current streak from list of completion dates (date objects).
    Streak = consecutive days ending today or yesterday (grace for today)."""
    if not completed_dates:
        return 0
    
    unique_dates = sorted(set(completed_dates), reverse=True)
    today = date.today()
    
    # If most recent completion is today, streak counts from today
    # If most recent is yesterday, streak still counts (they can complete today)
    if unique_dates[0] != today and unique_dates[0] != today - timedelta(days=1):
        return 0
    
    streak = 1
    expected = unique_dates[0] - timedelta(days=1)
    for d in unique_dates[1:]:
        if d == expected:
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak


def get_encouragement(field: str) -> str:
    """Return a positive feedback message for a completed task."""
    messages = {
        "video_watched": [
            "✅ Watched! Your brain is building the foundation.",
            "📺 Lesson watched — knowledge acquired!",
            "👏 Nice! One step closer to your first client.",
        ],
        "practice_completed": [
            "💪 Practice done! This is where skills are built.",
            "🎯 Excellent! You're not just learning — you're DOING.",
            "🔥 Practice complete. Freelancers who practice daily win daily.",
        ],
        "apply_completed": [
            "🚀 Applied! That's real progress toward client work.",
            "🏆 Apply task done — you're building your portfolio!",
            "✨ Outstanding! Every apply task is a step to income.",
        ],
        "day_complete": [
            "🎉 Day complete! You're on your way to freelance freedom.",
            "🏅 Day finished — consistency beats intensity!",
            "🌟 Full day done. Your future clients will thank you.",
        ],
    }
    import random
    return random.choice(messages.get(field, ["Great work!"]))


def get_milestone(day_number: int, streak: int) -> dict:
    """Return milestone celebration if applicable."""
    if day_number == 7:
        return {"icon": "🏆", "title": "Week 1 Complete!", 
                "message": "You've finished the Foundation week. Keep building!"}
    if day_number == 14:
        return {"icon": "🚀", "title": "Halfway There!",
                "message": "14 days in — you're officially consistent. Momentum is real."}
    if day_number == 21:
        return {"icon": "🎖️", "title": "Week 3 Complete!",
                "message": "Application week done. You're client-ready soon."}
    if day_number == 28:
        return {"icon": "👑", "title": "Almost Graduated!",
                "message": "4 weeks of daily practice. Incredible discipline."}
    if day_number == 30:
        return {"icon": "🎓", "title": "Graduation Day!",
                "message": "You completed the full 30-day journey. Now go win clients!"}
    if streak in (3, 5, 10, 15, 21, 30):
        return {"icon": "🔥", "title": f"{streak}-Day Streak!",
                "message": f"You've practiced {streak} days in a row. That's real commitment."}
    return None


def get_nudges(progress_days: dict, last_completed_day: int, today_number: int) -> list:
    """Generate contextual nudges based on user's progress.
    progress_days: {day_number: {'practice_completed': bool, ...}}
    Returns list of {type, message, icon} dicts."""
    nudges = []
    
    # Nudge 1: Incomplete previous day practice
    if last_completed_day and last_completed_day < today_number:
        prev = progress_days.get(last_completed_day, {})
        if not prev.get("practice_completed"):
            nudges.append({
                "type": "incomplete_practice",
                "icon": "📝",
                "message": f"Don't forget Day {last_completed_day}'s practice — you're so close to a full streak!"
            })
    
    # Nudge 2: Streak encouragement
    if last_completed_day >= 3:
        nudges.append({
            "type": "streak",
            "icon": "🔥",
            "message": f"{last_completed_day}-day streak! Keep the momentum going today."
        })
    
    # Nudge 3: Today's task reminder
    nudges.append({
        "type": "today",
        "icon": "🎯",
        "message": f"Day {today_number} awaits — 20 focused minutes today compounds into a career."
    })
    
    return nudges


def compute_confidence(days_completed: int, streak: int, total_days: int = 30) -> dict:
    """Compute a confidence/momentum score (0-100). Generous curve to keep users motivated."""
    completion = days_completed / max(total_days, 1)
    completion_bonus = completion * 70  # up to 70 points from completion
    streak_bonus = min(streak / 7, 1) * 30  # up to 30 points from 7-day streak
    
    score = round(completion_bonus + streak_bonus)
    
    if score >= 80:
        level = "Unstoppable"
        message = "You're on fire. Clients are within reach — keep going!"
    elif score >= 55:
        level = "Building Momentum"
        message = "Solid progress! Consistency is your superpower."
    elif score >= 30:
        level = "Getting Started"
        message = "Good start! Each day adds up — don't stop now."
    elif score >= 10:
        level = "Day One"
        message = "Every expert was once a beginner. Day by day!"
    else:
        level = "Just Beginning"
        message = "Take it one day at a time — you've got this!"
    
    return {"score": score, "level": level, "message": message}


def get_welcome_back(days_away: int, next_day: int) -> str:
    """Welcome-back nudge for returning users."""
    if days_away >= 2:
        return f"👋 Welcome back! Day {next_day} awaits you — pick up right where you left off."
    return None
