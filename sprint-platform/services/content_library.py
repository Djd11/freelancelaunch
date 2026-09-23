"""
content_library — the cluster-amortized course content store (arch §2 P3).

The 14-day course content (14 lessons + 3 copy-work project anatomies) is
provisioned ONCE per job cluster, under admin control, and stored in
cluster_content_library. Every learner enrolling in the cluster consumes
those rows instantly — ZERO per-user LLM calls. Individual users were
failing with "generation failed" because the free-tier LLM chain could not
absorb ~31 LLM calls on every enrollment; amortizing the work across the
cluster fixes the failure mode at its root (architecture.md §2 principle 3:
"Generate one sprint plan per cluster; users in a cohort share content,
each keeps their own day counter").

Sources of library content:
  1. Admin clicks "Generate" on /admin/content/<cluster> → the LLM worker
     runs ONCE for the whole cluster (admin-scoped, so rate limits bite one
     admin run instead of every learner).
  2. Admin edits a day's content directly (origin='edited') — regeneration
     never silently clobbers edited rows.

The lesson JSON stored per day is exactly the shape the old per-sprint
worker wrote into sprint_days.action_payload.lesson, so the day view,
TwoPanel player, quiz, and engagement preview all render unchanged.
"""
import logging
import threading

from services.llm import call_llm, LLMGenerationError

logger = logging.getLogger(__name__)

DAY_RANGE = range(1, 15)        # 14 course days
PROJECT_RANGE = range(1, 4)     # 3 copy-work projects


# ─── Reads ────────────────────────────────────────────────────────────

def library_days(sb, cluster_key):
    """{day_no: lesson_dict} for every populated library day of the cluster."""
    rows = sb.table("cluster_content_library").select("day_no,content") \
        .eq("cluster_key", cluster_key).eq("kind", "day") \
        .order("day_no").execute().data or []
    return {r["day_no"]: (r.get("content") or {}) for r in rows if r.get("content")}


def library_projects(sb, cluster_key):
    """{project_index: anatomy_dict} for every populated library project."""
    rows = sb.table("cluster_content_library").select("project_index,content") \
        .eq("cluster_key", cluster_key).eq("kind", "project") \
        .order("project_index").execute().data or []
    return {r["project_index"]: (r.get("content") or {}) for r in rows if r.get("content")}


def library_day_rows(sb, cluster_key):
    """{day_no: full row (content + origin + updated_at)} — admin detail view."""
    rows = sb.table("cluster_content_library").select("*") \
        .eq("cluster_key", cluster_key).eq("kind", "day") \
        .order("day_no").execute().data or []
    return {r["day_no"]: r for r in rows}


def library_status(sb, cluster_key):
    """{days: <populated count>, projects: <populated count>, ready: bool}."""
    days = library_days(sb, cluster_key)
    projects = library_projects(sb, cluster_key)
    return {
        "cluster_key": cluster_key,
        "days": len(days),
        "projects": len(projects),
        "ready": len(days) >= 14 and len(projects) >= 3,
    }


def is_ready(sb, cluster_key):
    """True when the cluster's library can provision a full 14-day sprint."""
    return library_status(sb, cluster_key)["ready"]


# ─── Learner-side application (zero LLM) ──────────────────────────────

def apply_library_to_sprint(sb, sprint_id, cluster_key):
    """Copy the cluster library into a sprint's sprint_days + copywork_projects.

    Zero LLM calls — this is a pure DB-to-DB copy of admin-provisioned
    content. Only fills EMPTY payloads (idempotent: re-runs never clobber
    learner progress or already-written rows).

    Returns the number of days populated.
    """
    days = library_days(sb, cluster_key)
    projects = library_projects(sb, cluster_key)

    # 1. Project anatomy → copywork_projects rows.
    for index, anatomy in projects.items():
        fields = {}
        if anatomy.get("title"):
            fields["title"] = anatomy["title"]
        if anatomy.get("clone_steps"):
            fields["clone_steps"] = anatomy["clone_steps"]
        if anatomy.get("rubric"):
            fields["rubric"] = anatomy["rubric"]
        if anatomy.get("reference_spec"):
            fields["reference_spec"] = anatomy["reference_spec"]
        if anatomy.get("gap_fill_topic"):
            fields["gap_fill_topic"] = anatomy["gap_fill_topic"]
        if fields:
            sb.table("copywork_projects").update(fields) \
                .eq("sprint_id", sprint_id).eq("project_index", index).execute()

    # 2. Lessons → sprint_days.action_payload (empty ones only).
    rows = sb.table("sprint_days").select("day_no,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data or []
    populated = 0
    for d in rows:
        day_no = d.get("day_no")
        lesson = days.get(day_no)
        if not lesson:
            continue
        payload = d.get("action_payload") or {}
        if payload.get("lesson"):
            populated += 1
            continue  # never clobber an already-populated day
        payload["lesson"] = lesson
        sb.table("sprint_days").update({"action_payload": payload}) \
            .eq("sprint_id", sprint_id).eq("day_no", day_no).execute()
        populated += 1
    return populated


def try_fill_from_library(sb, sprint_id):
    """Repair an EXISTING sprint from its cluster's library — zero LLM calls.

    The cohort-amortization gap this closes: a sprint created BEFORE the
    library was provisioned (enrollment fell back to per-user LLM generation,
    which failed on free-tier rate limits) stays empty forever — "generating"
    or "generation failed" on every day view. When the admin later provisions
    the library, this heals the sprint from the same rows new enrollments get.

    Returns True when content was (partially) applied, False when there was
    nothing to do (no library, or no empty days left). Never raises on a
    missing table — callers use it on hot request paths.
    """
    try:
        sprint = sb.table("sprints").select("cluster_key") \
            .eq("id", sprint_id).limit(1).execute().data
        if not sprint:
            return False
        cluster_key = sprint[0].get("cluster_key")
        if not cluster_key:
            return False
        if not is_ready(sb, cluster_key):
            return False
        # Only act when there is something to heal: apply_library_to_sprint
        # skips non-empty days, so an already-full sprint is a no-op.
        days = sb.table("sprint_days").select("day_no,action_payload") \
            .eq("sprint_id", sprint_id).execute().data or []
        if not any(not (d.get("action_payload") or {}).get("lesson") for d in days):
            return False
        apply_library_to_sprint(sb, sprint_id, cluster_key)
        return True
    except Exception:
        logger.exception("try_fill_from_library failed for %s", sprint_id)
        return False


# ─── Admin-side generation (LLM, once per cluster) ────────────────────

def generate_for_cluster(sb, cluster_key, client_factory=None):
    """Generate the FULL 14-day library for one cluster via the LLM chain.

    Admin-scoped: called from the admin routes, never on a learner path.
    Reuses lesson_engine's job-grounded prompts + parsers verbatim, so the
    library content is byte-shape compatible with the old per-sprint output.

    Skipping rules:
      - days/projects that already carry content are left alone;
      - rows with origin='edited' (admin overrides) are NEVER regenerated.

    Concurrency mirrors lesson_engine.generate_sprint_content: bounded thread
    pool, one Supabase client per task via client_factory.

    Returns {"days": n, "projects": n} of newly generated rows.
    """
    from services.lesson_engine import (
        lesson_for_day, project_anatomy, _store_reference_spec, _close_client,
    )
    from routes import DAY_TO_PROJECT

    def _sb():
        return client_factory() if client_factory else sb

    def _release(c):
        if client_factory is not None and c is not sb:
            _close_client(c)

    # Sprint-shaped stand-ins: lesson_engine's generators read
    # sprint["cluster_key"] / sprint["id"].
    sprint_stub = {"id": None, "cluster_key": cluster_key}
    existing_days = set(library_days(sb, cluster_key).keys())
    existing_projects = set(library_projects(sb, cluster_key).keys())

    generated = {"days": 0, "projects": 0}

    # ── 1. Project anatomies (parallel) ──────────────────────────────
    def _gen_project(index):
        if index in existing_projects:
            return
        c = _sb()
        try:
            anatomy = project_anatomy(c, sprint_stub, index)
            if not (anatomy.get("clone_steps") and anatomy.get("rubric")):
                return
            c.table("cluster_content_library").upsert({
                "cluster_key": cluster_key, "kind": "project",
                "day_no": 0, "project_index": index,
                "content": anatomy, "origin": "generated",
            }, on_conflict="cluster_key,kind,day_no,project_index").execute()
            generated["projects"] += 1
        finally:
            _release(c)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(_gen_project, PROJECT_RANGE))

    # Refresh after the parallel pass.
    projects = library_projects(sb, cluster_key)

    # ── 2. Lessons (parallel, Phase A days first) ────────────────────
    day_rows = [{"day_no": d,
                 "action_type": _action_for(d),
                 "title": f"Day {d}",
                 "action_payload": {}} for d in DAY_RANGE]
    ordered = sorted(day_rows, key=lambda d: (0 if d["day_no"] <= 5 else 1, d["day_no"]))

    def _gen_day(day_row):
        day_no = day_row["day_no"]
        if day_no in existing_days:
            return
        c = _sb()
        try:
            project_index = DAY_TO_PROJECT.get(day_no)
            project = projects.get(project_index) if project_index else None
            project = {"project_index": project_index, **project} if project else None
            try:
                lesson = lesson_for_day(c, sprint_stub, day_row, project)
            except Exception as exc:
                logger.warning("library day %s generation failed for %s: %s",
                               day_no, cluster_key, exc)
                return
            c.table("cluster_content_library").upsert({
                "cluster_key": cluster_key, "kind": "day",
                "day_no": day_no, "project_index": 0,
                "content": lesson, "origin": "generated",
            }, on_conflict="cluster_key,kind,day_no,project_index").execute()
            generated["days"] += 1
        finally:
            _release(c)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(_gen_day, ordered))

    return generated


def _action_for(day_no):
    """Same day→action map as sprint_planner.action_for (prompt branch keyed
    on day_row['action_type'])."""
    if day_no == 1:
        return "setup"
    if day_no < 6:
        return "copywork"
    if day_no <= 8:
        return "contract"
    if day_no <= 10:
        return "case-study"
    return "proposal"


def regenerate_day(sb, cluster_key, day_no):
    """Force-regenerate ONE day's lesson via the LLM (admin retry path)."""
    from services.lesson_engine import lesson_for_day, _close_client
    sprint_stub = {"id": None, "cluster_key": cluster_key}
    day_row = {"day_no": int(day_no), "action_type": _action_for(int(day_no)),
               "title": f"Day {day_no}", "action_payload": {}}
    lesson = lesson_for_day(sb, sprint_stub, day_row, None)
    if not lesson:
        raise LLMGenerationError("No LLM provider answered for the library day")
    sb.table("cluster_content_library").upsert({
        "cluster_key": cluster_key, "kind": "day",
        "day_no": int(day_no), "project_index": 0,
        "content": lesson, "origin": "generated",
    }, on_conflict="cluster_key,kind,day_no,project_index").execute()
    return lesson


# ─── Seed an existing sprint's content INTO the library (admin bootstrap) ──

def seed_from_sprint(sb, cluster_key, sprint_id, overwrite=False):
    """Copy a sprint's already-generated content into the cluster library.

    One-off bootstrap: the admin picks their best-generated sprint and
    publishes its content to every future learner of the cluster. Skips
    days without a lesson; refuses to overwrite existing library rows
    unless overwrite=True.

    Returns {"days": n, "projects": n} of copied rows.
    """
    copied = {"days": 0, "projects": 0}
    existing_days = set(library_days(sb, cluster_key).keys())
    existing_projects = set(library_projects(sb, cluster_key).keys())

    rows = sb.table("sprint_days").select("day_no,action_payload") \
        .eq("sprint_id", sprint_id).order("day_no").execute().data or []
    for d in rows:
        day_no = d.get("day_no")
        lesson = (d.get("action_payload") or {}).get("lesson")
        if not lesson or not (lesson.get("script") or lesson.get("title")):
            continue
        if day_no in existing_days and not overwrite:
            continue
        sb.table("cluster_content_library").upsert({
            "cluster_key": cluster_key, "kind": "day",
            "day_no": day_no, "project_index": 0,
            "content": lesson, "origin": "edited",
        }, on_conflict="cluster_key,kind,day_no,project_index").execute()
        copied["days"] += 1

    projects = sb.table("copywork_projects").select("project_index,title,clone_steps,"
                                                    "rubric,reference_spec,gap_fill_topic") \
        .eq("sprint_id", sprint_id).order("project_index").execute().data or []
    for p in projects:
        index = p.get("project_index")
        if not (p.get("clone_steps") and p.get("rubric")):
            continue
        if index in existing_projects and not overwrite:
            continue
        sb.table("cluster_content_library").upsert({
            "cluster_key": cluster_key, "kind": "project",
            "day_no": 0, "project_index": index,
            "content": {k: p.get(k) for k in
                        ("title", "clone_steps", "rubric", "reference_spec", "gap_fill_topic")},
            "origin": "edited",
        }, on_conflict="cluster_key,kind,day_no,project_index").execute()
        copied["projects"] += 1
    return copied


def update_day(sb, cluster_key, day_no, fields):
    """Admin edit of one library day (origin='edited' — never auto-clobbered).

    Accepts partial fields (title/script/objective/key_points/...); merges
    into the existing content when a row already exists.
    """
    clean = {k: v for k, v in (fields or {}).items()
             if k in ("title", "objective", "script", "key_points", "pitfalls",
                      "quiz", "quiz_answers", "hook", "day_overview",
                      "usefulness_context", "pre_quiz", "voiceover")}
    if not clean:
        return None
    rows = sb.table("cluster_content_library").select("*") \
        .eq("cluster_key", cluster_key).eq("kind", "day").eq("day_no", int(day_no)) \
        .limit(1).execute().data
    if rows:
        content = dict(rows[0].get("content") or {})
        content.update(clean)
        # Natural-key update (not id): one row per (cluster, kind, day_no).
        sb.table("cluster_content_library").update(
            {"content": content, "origin": "edited"},
        ).eq("cluster_key", cluster_key).eq("kind", "day") \
         .eq("day_no", int(day_no)).execute()
        return content
    content = {"title": "", "objective": "", "script": "",
               "key_points": [], "pitfalls": [], "quiz": [], "quiz_answers": [],
               "hook": "", "day_overview": [], "usefulness_context": "", "pre_quiz": []}
    content.update(clean)
    sb.table("cluster_content_library").insert({
        "cluster_key": cluster_key, "kind": "day",
        "day_no": int(day_no), "project_index": 0,
        "content": content, "origin": "edited",
    }).execute()
    return content


# ─── Active-generation tracking (mirrors lesson_engine) ───────────────

_active_generations: set = set()
_lock = threading.Lock()


def start_generation(cluster_key: str) -> None:
    with _lock:
        _active_generations.add(cluster_key)


def stop_generation(cluster_key: str) -> None:
    with _lock:
        _active_generations.discard(cluster_key)


def is_generating(cluster_key: str) -> bool:
    with _lock:
        return cluster_key in _active_generations
