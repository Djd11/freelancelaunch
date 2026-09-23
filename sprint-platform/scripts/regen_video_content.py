#!/usr/bin/env python3
"""
regen_video_content — engagement-fields gap-fill for existing lessons.

Backfills ONLY the four engagement fields the new 4-scene lesson video
displays: hook, day_overview, usefulness_context, pre_quiz. Everything
else in the lesson payload stays byte-identical:
  - title, objective, script, key_points, pitfalls, quiz, quiz_answers
  - voiceover (MP3 url + duration — never touched, never re-synthesized)

Rationale (2026-08-31 decision): the redesigned Remotion player is a pure
presentation layer — existing lessons get the new look automatically. Days
generated before the engagement fields existed render with fallbacks
(HOOK shows the title, no stat panel, no pre-quiz). This script closes that
gap WITHOUT discarding any existing content: the fields simply don't
exist on those days, so this is a fill, not a rewrite.

Safety:
  --dry-run (default): prints per-day before/after diff, writes NOTHING.
  --apply: writes the merged payload back to sprint_days.action_payload.
  Payload merge is additive: only the 4 missing fields are set; the write
  is a full-row update of action_payload with all original keys intact.

Uses the platform's existing LLM infra (services.llm.call_llm) and the
same _ENGAGEMENT_INSTRUCTION contract the lesson engine itself uses, so
backfilled fields match what fresh sprints get.
"""
import argparse
import json
import sys

from app import create_app
from services.llm import call_llm


ENGAGEMENT_FIELDS = ("hook", "day_overview", "usefulness_context", "pre_quiz")

# Same contract the live lesson prompts embed for engagement fields.
_PROMPT = """You backfill engagement fields for an EXISTING freelance-sprint lesson.
Everything below already exists and must NOT be rewritten — you produce ONLY
the four engagement fields so the lesson's video preview is compelling.

Lesson context (do not rewrite any of this):
- Sprint niche / job cluster: {cluster}
- Day {day} of 14 (action: {action})
- Lesson title: "{title}"
- Lesson script (excerpt): {script}

Reply with JSON ONLY:
{{"hook": "...", "day_overview": ["...","..."], "usefulness_context": "...", "pre_quiz": [{{"q": "...", "options": ["...","..."], "answer": 0}}]}}

Field rules:
1. "hook": 1-2 sentences, punchy opener naming the learner's concrete
   freelance win for THIS niche (e.g. "Land your first Klaviyo automation
   gig faster"). Must read as a video title-card, not a summary.
2. "day_overview": 2-4 short strings, "what you will learn today".
3. "usefulness_context": ONE paragraph explaining WHY this skill wins
   freelance jobs in this niche — cite the kind of client work the
   script teaches. Include at least one concrete number or percentage
   when the script supports it (the video shows it as a big stat).
4. "pre_quiz": 1-2 objects testing PRIOR intuition BEFORE the lesson —
   each object MUST be {{"q": "...", "options": ["...","..."], "answer": <0-based index>}}.
"""


def _norm_pre_quiz(items):
    """Same normalization contract as lesson_engine._normalize_engagement:
    keep only well-formed items; drop malformed options/answers."""
    out = []
    if not isinstance(items, list):
        return out
    for it in items:
        if not isinstance(it, dict):
            continue
        q = str(it.get("q") or "").strip()
        opts = [str(o).strip() for o in (it.get("options") or []) if str(o).strip()]
        ans = it.get("answer")
        if not q or len(opts) < 2:
            continue
        try:
            ans_i = int(ans)
        except (TypeError, ValueError):
            ans_i = 0
        if not (0 <= ans_i < len(opts)):
            ans_i = 0
        out.append({"q": q, "options": opts, "answer": ans_i})
    return out[:2]


def _extract_json(text):
    import re
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError):
        return None


def _missing_fields(lesson):
    return [f for f in ENGAGEMENT_FIELDS
            if f == "pre_quiz"
            and not lesson.get("pre_quiz")
            or f != "pre_quiz" and not lesson.get(f)]


def _find_sprints(sb, sprint_filter):
    rows = sb.table("sprints").select("id,cluster_key,current_day").execute().data
    if sprint_filter:
        rows = [r for r in rows if r["id"].startswith(sprint_filter)]
    return rows


def process_day(sb, sprint, day_row, apply):
    """Returns (status, detail) — status in {skip, ok, fail}."""
    payload = day_row.get("action_payload") or {}
    lesson = payload.get("lesson")
    if not lesson:
        return "skip", "no lesson payload"
    missing = _missing_fields(lesson)
    if not missing:
        return "skip", "already complete"

    cluster = sprint.get("cluster_key") or "the target niche"
    day_no = day_row.get("day_no")
    action = (payload.get("action_type") or
              day_row.get("action_type") or "lesson")

    prompt = _PROMPT.format(
        cluster=cluster,
        day=day_no,
        action=action,
        title=str(lesson.get("title") or "")[:200],
        script=str(lesson.get("script") or "")[:1500],
    )

    raw = call_llm(prompt, timeout=90, max_retries=2, backoff_base=2)
    data = _extract_json(raw)
    if not data:
        return "fail", f"LLM returned no JSON (missing={missing})"

    patch = {}
    if not lesson.get("hook") and str(data.get("hook") or "").strip():
        patch["hook"] = str(data["hook"]).strip()
    if not lesson.get("day_overview") and isinstance(data.get("day_overview"), list):
        ov = [str(o).strip() for o in data["day_overview"] if str(o).strip()]
        if ov:
            patch["day_overview"] = ov[:4]
    if not lesson.get("usefulness_context") and str(data.get("usefulness_context") or "").strip():
        patch["usefulness_context"] = str(data["usefulness_context"]).strip()
    if not lesson.get("pre_quiz"):
        pq = _norm_pre_quiz(data.get("pre_quiz"))
        if pq:
            patch["pre_quiz"] = pq

    if not patch:
        return "fail", f"LLM JSON parsed but no usable fields (missing={missing})"

    # Additive merge — original keys (title/script/key_points/voiceover/…)
    # are carried through byte-identical.
    new_lesson = dict(lesson)
    new_lesson.update(patch)
    new_payload = dict(payload)
    new_payload["lesson"] = new_lesson

    if apply:
        sb.table("sprint_days").update(
            {"action_payload": new_payload}
        ).eq("sprint_id", sprint["id"]).eq("day_no", day_no).execute()

    detail = "; ".join(
        f"{k}={json.dumps(v, ensure_ascii=False)[:90]}" for k, v in patch.items()
    )
    return "ok", detail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write to DB (default: dry-run, no writes)")
    ap.add_argument("--sprint", default=None,
                    help="limit to one sprint id (prefix ok)")
    ap.add_argument("--day", type=int, default=None,
                    help="limit to one day number")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        from services.supabase_client import get_supabase
        sb = get_supabase()

        sprints = _find_sprints(sb, args.sprint)
        mode = "APPLY (writing)" if args.apply else "DRY RUN (no writes)"
        print(f"== regen_video_content — {mode} ==")
        print(f"   sprints in scope: {len(sprints)}")

        n_ok = n_skip = n_fail = 0
        for s in sprints:
            days = sb.table("sprint_days").select(
                "day_no,action_payload,action_type"
            ).eq("sprint_id", s["id"]).order("day_no").execute().data
            for d in days:
                if args.day is not None and d["day_no"] != args.day:
                    continue
                status, detail = process_day(sb, s, d, apply=args.apply)
                if status == "ok":
                    n_ok += 1
                elif status == "skip":
                    n_skip += 1
                else:
                    n_fail += 1
                print(f"[{status.upper():4s}] {s['id'][:8]}… day {d['day_no']:>2}: {detail}")
        print(f"== done: {n_ok} backfilled, {n_skip} skipped, {n_fail} failed ==")
        if not args.apply:
            print("   (dry run — re-run with --apply to write)")


if __name__ == "__main__":
    main()
