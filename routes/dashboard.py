"""
Dashboard routes — main user experience
"""
import logging
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, g, request
from services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _get_user_topic_progress(sb, user_id, profile, cohort_id, selected_topic_id):
    """Build progress state for every topic the user is engaged with.

    Drives the dashboard's horizontal topic tabs — each tab shows that
    topic's real learning stage (day number, days done, %, status), scoped
    to that topic only (no cross-topic contamination).

    Returns a list of dicts, ordered: primary topic first, then in-progress,
    then not-started, then completed (alphabetical within each group):
      {id, slug, name, icon, color, tagline, cohort, cohort_id, max_days,
       days_completed, last_completed_day, current_day, pct, status,
       is_primary, is_started, progress_rows}
    """
    from routes.topics import CURATED_TOPICS
    curated = {t["slug"]: t for t in CURATED_TOPICS}

    # 1) All of the user's progress rows (spans every topic — no filtering yet)
    prog_rows = []
    try:
        resp = sb.table("user_progress").select(
            "cohort_video_id,day_number,video_watched,practice_completed,apply_completed,updated_at"
        ).eq("user_id", user_id).limit(500).execute()
        prog_rows = resp.data or []
    except Exception as e:
        logger.warning(f"user_progress fetch failed: {e}")

    # 2) Map cohort_video_id → cohort_id + day_number
    video_map = {}
    video_ids = [p["cohort_video_id"] for p in prog_rows if p.get("cohort_video_id")]
    if video_ids:
        try:
            vids = sb.table("cohort_videos").select("id,cohort_id,day_number,curriculum_day_id") \
                .in_("id", video_ids[:200]).limit(200).execute()
            for v in (vids.data or []):
                video_map[v["id"]] = v
        except Exception as e:
            logger.warning(f"cohort_videos lookup failed: {e}")

    # 3) Load every cohort involved (user's + any touched via progress)
    cohort_ids = {cohort_id} if cohort_id else set()
    cohort_ids.update(v.get("cohort_id") for v in video_map.values() if v.get("cohort_id"))
    cohort_map = {}
    for cid in list(cohort_ids)[:50]:
        try:
            cresp = sb.table("cohorts").select("id,topic_id,current_day,max_days,name") \
                .eq("id", cid).limit(1).execute()
            if cresp.data:
                cohort_map[cid] = cresp.data[0]
        except Exception:
            pass
    topic_by_cohort = {cid: c["topic_id"] for cid, c in cohort_map.items() if c.get("topic_id")}

    # 4) Topic ids to show: cohort topics + selected topic + any with progress
    topic_ids = set(topic_by_cohort.values())
    if selected_topic_id:
        topic_ids.add(selected_topic_id)
    if not topic_ids:
        return []

    topic_map = {}
    for tid in list(topic_ids)[:50]:
        try:
            tresp = sb.table("topics").select("id,slug,name").eq("id", tid).limit(1).execute()
            if tresp.data:
                topic_map[tid] = tresp.data[0]
        except Exception:
            pass

    # 5) Group progress rows by topic (isolated — a Shopify row never counts
    #    toward Web Scraping)
    by_topic = {}
    for p in prog_rows:
        v = video_map.get(p.get("cohort_video_id")) or {}
        tid = topic_by_cohort.get(v.get("cohort_id"))
        if not tid:
            continue
        by_topic.setdefault(tid, []).append(p)

    # 6) Aggregate per-topic stage
    status_order = {"in_progress": 0, "not_started": 1, "completed": 2}
    results = []
    for tid, t in topic_map.items():
        slug = t.get("slug")
        ct = curated.get(slug, {})
        cohort = next((c for c in cohort_map.values() if c.get("topic_id") == tid), None)

        rows = by_topic.get(tid, [])
        completed_days = set()
        last_completed = 0
        for p in rows:
            dn = p.get("day_number")
            if not dn:
                continue
            if p.get("video_watched"):
                completed_days.add(dn)
                if dn > last_completed:
                    last_completed = dn

        max_days = (cohort or {}).get("max_days") or 30
        cohort_day = (cohort or {}).get("current_day") or 0

        # Meaningful "current day": never 0, never a placeholder. If the
        # cohort hasn't advanced, resume where the user left off + 1.
        if cohort_day > 0:
            current_day = max(cohort_day, last_completed + 1)
        else:
            current_day = last_completed + 1
        if current_day < 1:
            current_day = 1
        if current_day > max_days:
            current_day = max_days

        days_completed = len(completed_days)
        pct = round(days_completed / max_days * 100) if max_days else 0

        if days_completed >= max_days and max_days > 0:
            status = "completed"
        elif days_completed > 0 or (cohort and cohort_day > 0):
            status = "in_progress"
        else:
            status = "not_started"

        results.append({
            "id": tid,
            "slug": slug,
            "name": t.get("name"),
            "icon": ct.get("icon", "📘"),
            "color": ct.get("color", "#6366f1"),
            "tagline": ct.get("tagline", ""),
            "cohort": cohort,
            "cohort_id": cohort["id"] if cohort else None,
            "max_days": max_days,
            "days_completed": days_completed,
            "last_completed_day": last_completed,
            "current_day": current_day,
            "pct": pct,
            "status": status,
            "is_primary": tid == selected_topic_id,
            "is_started": days_completed > 0 or current_day > 1,
            "progress_rows": rows,
        })

    results.sort(key=lambda t: (0 if t["is_primary"] else 1,
                                status_order.get(t["status"], 1),
                                (t["name"] or "").lower()))
    return results


def _cohort_for_topic(sb, topic_id):
    """Any cohort whose topic matches (used when the user has no direct
    cohort row for a topic but does have progress against its videos)."""
    try:
        rows = sb.table("cohorts").select("*").eq("topic_id", topic_id).limit(1).execute()
        return rows.data[0] if rows.data else None
    except Exception:
        return None


@dashboard_bp.route("/")
def home():
    if not g.user:
        return redirect(url_for("auth.login", next=url_for("dashboard.home")))

    sb = get_supabase()
    user_id = g.user["id"]
    topic_param = (request.args.get("topic") or "").strip() or None

    # Get user profile
    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}

    cohort_id = profile.get("cohort_id")
    selected_topic_id = profile.get("selected_topic_id")
    if not cohort_id and not selected_topic_id:
        # No cohort or topic assigned — redirect to topic selection
        return redirect(url_for("topics.explore"))

    # ── Build per-topic progress → drives the horizontal tab view ──────────
    topics = _get_user_topic_progress(sb, user_id, profile, cohort_id, selected_topic_id)
    if not topics:
        flash("No topics found — pick a skill to get started", "error")
        return redirect(url_for("topics.explore"))

    # ── Resolve the active topic: ?topic= slug > selected_topic_id > first ──
    if topic_param:
        active = next((t for t in topics if t["slug"] == topic_param), None)
    else:
        active = next((t for t in topics if t["is_primary"]), None)
    if not active:
        active = topics[0]

    active_topic_slug = active["slug"]
    active_topic_name = active["name"]
    active_cohort = active.get("cohort") or {}
    current_day = active["current_day"]
    max_days = active["max_days"]
    total_done = active["days_completed"]
    cohort_id_for_topic = active.get("cohort_id")

    # ── Resolve today's video for the ACTIVE topic only ────────────────────
    today_video = None
    if cohort_id_for_topic:
        try:
            video_resp = sb.table("cohort_videos").select("*") \
                .eq("cohort_id", cohort_id_for_topic) \
                .eq("day_number", current_day) \
                .limit(1) \
                .execute()
            today_video = video_resp.data[0] if video_resp.data else None
        except Exception:
            today_video = None
    if not today_video and active.get("id"):
        # No direct cohort — fall back to any cohort that teaches this topic
        try:
            alt_cohort = _cohort_for_topic(sb, active["id"])
            if alt_cohort:
                video_resp = sb.table("cohort_videos").select("*") \
                    .eq("cohort_id", alt_cohort["id"]) \
                    .eq("day_number", current_day) \
                    .limit(1) \
                    .execute()
                today_video = video_resp.data[0] if video_resp.data else None
        except Exception:
            pass

    # ── Resolve today's curriculum day from the ACTIVE topic ───────────────
    curriculum_day = None
    if today_video and today_video.get("curriculum_day_id"):
        try:
            cd_resp = sb.table("curriculum_days").select("*") \
                .eq("id", today_video["curriculum_day_id"]) \
                .limit(1) \
                .execute()
            curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception:
            pass

    if not curriculum_day and active_topic_slug:
        try:
            tdb = sb.table("topics").select("id").eq("slug", active_topic_slug).limit(1).execute()
            if tdb.data:
                cur = sb.table("curricula").select("id").eq("topic_id", tdb.data[0]["id"]).limit(1).execute()
                if cur.data:
                    cd_resp = sb.table("curriculum_days").select("*") \
                        .eq("curriculum_id", cur.data[0]["id"]) \
                        .eq("day_number", current_day) \
                        .limit(1) \
                        .execute()
                    curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception as e:
            logger.warning(f"Dashboard curriculum lookup error: {e}")

    # ── User's progress for today's video (active topic only) ─────────────
    progress = None
    if today_video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", today_video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None

    # ─── CONFIDENCE ENGINE — scoped to the active topic ────────────────────
    streak, nudges, confidence, milestone = 0, [], {"score": 0, "level": "Day One", "message": ""}, None
    welcome_back, day_celebrated = None, False
    try:
        from services.nudge_engine import (
            compute_streak, get_nudges, compute_confidence,
            get_milestone, get_welcome_back
        )

        completed_dates = []
        progress_days = {}
        last_completed_day = active.get("last_completed_day", 0)
        for row in active.get("progress_rows", []):
            day_num = row.get("day_number")
            progress_days[day_num] = row
            if row.get("video_watched") or row.get("practice_completed"):
                if row.get("updated_at"):
                    try:
                        completed_dates.append(datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")).date())
                    except Exception:
                        pass

        streak = compute_streak(completed_dates)
        nudges = get_nudges(progress_days, last_completed_day, current_day)
        confidence = compute_confidence(total_done, streak, max_days)
        milestone = get_milestone(current_day, streak)

        # Welcome-back nudge for inactive users
        if last_completed_day > 0 and last_completed_day < current_day - 1:
            welcome_back = get_welcome_back(current_day - last_completed_day, current_day)

        # Today's celebration if all 3 done
        if progress and progress.get("video_watched") and progress.get("practice_completed") and progress.get("apply_completed"):
            day_celebrated = True
    except Exception as e:
        logger.error(f"Nudge engine error: {e}")

    return render_template("dashboard/home.html",
        profile=profile,
        cohort=active_cohort,
        current_day=current_day,
        max_days=max_days,
        today_video=today_video,
        curriculum_day=curriculum_day,
        progress=progress,
        total_done=total_done,
        streak=streak,
        nudges=nudges,
        confidence=confidence,
        milestone=milestone,
        welcome_back=welcome_back,
        day_celebrated=day_celebrated,
        active_topic_slug=active_topic_slug,
        active_topic_name=active_topic_name,
        active_topic=active,
        topics=topics,
    )


@dashboard_bp.route("/day/<int:day_number>")
def day_detail(day_number):
    """View a specific day's content. Auto-generates curriculum if missing (never 500).

    Supports ?topic=<slug> for TOPIC-SCOPED day views (used by the /topics/<slug>
    detail page day links). When present, the lesson resolves from THAT topic's
    curriculum — never from the user's cohort — so browsing n8n day 1 can never
    show a Shopify lesson even if the user's enrolled cohort is Shopify.
    Progress checkboxes only appear when the user's cohort topic matches.
    """
    if not g.user:
        return redirect(url_for("auth.login"))

    sb = get_supabase()
    user_id = g.user["id"]
    topic_param = (request.args.get("topic") or "").strip() or None

    profile_resp = sb.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}
    cohort_id = profile.get("cohort_id")

    if not cohort_id and not topic_param:
        return redirect(url_for("topics.explore"))

    # ── Cohort context (may be absent for topic-scoped browsing) ──────────
    cohort = {}
    cohort_topic_slug = None
    if cohort_id:
        cohort_resp = sb.table("cohorts").select("*,topics(slug,name)").eq("id", cohort_id).limit(1).execute()
        cohort = cohort_resp.data[0] if cohort_resp.data else {}
        if cohort.get("topics"):
            cohort_topic_slug = cohort["topics"].get("slug")
        elif cohort.get("topic_id"):
            try:
                tdb = sb.table("topics").select("slug,name").eq("id", cohort["topic_id"]).limit(1).execute()
                if tdb.data:
                    cohort_topic_slug = tdb.data[0].get("slug")
            except Exception as e:
                print(f"Topic fallback lookup error: {e}")

    # ── Which topic does this day belong to? ───────────────────────────────
    is_topic_scoped = bool(topic_param)
    topic_slug = topic_param or cohort_topic_slug
    topic_name = None
    if topic_slug:
        try:
            tdb = sb.table("topics").select("name").eq("slug", topic_slug).limit(1).execute()
            if tdb.data:
                topic_name = tdb.data[0].get("name")
        except Exception as e:
            print(f"Topic name lookup error: {e}")

    # ── Cohort video only when the cohort topic matches the viewed topic ───
    video = None
    if cohort_id and cohort_topic_slug == topic_slug:
        video_resp = sb.table("cohort_videos").select("*") \
            .eq("cohort_id", cohort_id) \
            .eq("day_number", day_number) \
            .limit(1) \
            .execute()
        video = video_resp.data[0] if video_resp.data else None

    # ── Curriculum day (from the topic's curriculum, cohort-agnostic) ──────
    curriculum_day = None
    if video and video.get("curriculum_day_id"):
        cd_resp = sb.table("curriculum_days").select("*") \
            .eq("id", video["curriculum_day_id"]) \
            .limit(1) \
            .execute()
        curriculum_day = cd_resp.data[0] if cd_resp.data else None

    if not curriculum_day and topic_slug:
        try:
            tdb = sb.table("topics").select("id").eq("slug", topic_slug).limit(1).execute()
            if tdb.data:
                cur = sb.table("curricula").select("id") \
                    .eq("topic_id", tdb.data[0]["id"]).limit(1).execute()
                if cur.data:
                    cd_resp = sb.table("curriculum_days").select("*") \
                        .eq("curriculum_id", cur.data[0]["id"]) \
                        .eq("day_number", day_number) \
                        .limit(1) \
                        .execute()
                    curriculum_day = cd_resp.data[0] if cd_resp.data else None
        except Exception as e:
            print(f"Curriculum day fallback-2 error: {e}")

    # ── User progress ───────────────────────────────────────────────────────
    progress = None
    if video:
        prog_resp = sb.table("user_progress").select("*") \
            .eq("user_id", user_id) \
            .eq("cohort_video_id", video["id"]) \
            .limit(1) \
            .execute()
        progress = prog_resp.data[0] if prog_resp.data else None

    # NEEDS GENERATION: curriculum missing — show loading state, auto-trigger generation
    needs_generation = curriculum_day is None
    if needs_generation and not topic_slug:
        # No topic context — fail gracefully, not 500
        flash("No curriculum available for this topic yet", "error")
        return redirect(url_for("dashboard.home"))

    # Check if content is fallback-quality (for "Regenerate" button)
    is_fallback = False
    if curriculum_day:
        from services.curriculum_generator import is_fallback_content
        is_fallback = is_fallback_content(curriculum_day)

    return render_template("dashboard/day.html",
        day_number=day_number,
        video=video,
        curriculum_day=curriculum_day,
        progress=progress,
        needs_generation=needs_generation,
        topic_slug=topic_slug,
        topic_name=topic_name,
        cohort=cohort,
        is_topic_scoped=is_topic_scoped,
        is_fallback_content=is_fallback
    )
