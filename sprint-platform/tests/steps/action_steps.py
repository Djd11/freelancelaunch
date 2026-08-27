"""Action + verify steps — form submissions, DB-state assertions, iteration diagnosis."""
import json

from behave import given, when, then

from tests.live_db_adapter import get_live_adapter, TEST_USER_ID, get_static_job_id
from tests.steps.common_steps import _post
from services.iteration_engine import diagnose


# ── When: form submissions ─────────────────────────────────────────
@when('I POST to "{path}"')
def step_post_plain(context, path):
    _post(context, path, data={})


@when('I POST the login form with email "{email}"')
def step_login_form(context, email):
    _post(context, "/auth/login", data={"email": email})


@when('I submit a request-a-sprint form for skill "{skill}"')
def step_request_sprint(context, skill):
    _post(context, "/sprints/request", data={"skill": skill})


@when('I mark the lesson watched for day {day} of sprint "{sid}"')
def step_mark_watched(context, day, sid):
    """Browser-form POST to the /watched toggle (plain, urlencoded — never JSON),
    mirroring day.html's plain-form pattern; the route redirects back to the day view."""
    _post(context, f"/sprints/{sid}/day/{day}/watched", data={})


@when('I submit the copy-work task for day {day} of sprint "{sid}" with rubric_url "{url}"')
def step_copywork_submit(context, day, sid, url):
    _post(context, f"/sprints/{sid}/day/{day}/copywork", data={"rubric_url": url})


@when('I check the first rubric checkbox for project {project} of sprint "{sid}"')
def step_check_first_rubric(context, project, sid):
    """User checks the first rubric item for a project."""
    _post(context, f"/sprints/{sid}/day/4/rubric-check", data={"project_index": project, "rubric_index": 0, "checked": "true"})


@when('I check the second rubric checkbox for project {project} of sprint "{sid}"')
def step_check_second_rubric(context, project, sid):
    """User checks the second rubric item for a project."""
    _post(context, f"/sprints/{sid}/day/4/rubric-check", data={"project_index": project, "rubric_index": 1, "checked": "true"})


@when('I mark the gap-fill addressed for day {day} of sprint "{sid}"')
def step_mark_gapfill(context, day, sid):
    """User marks the gap-fill as addressed."""
    _post(context, f"/sprints/{sid}/day/{day}/gapfill-check", data={"checked": "true"})


def _fake_generation_llm(prompt, **kwargs):
    """Deterministic stand-in for the LLM in worker tests — returns the same
    job-grounded JSON shape the real model produces (content is LLM-only in the
    app; the stub keeps assertions stable without a live provider). **kwargs:
    call_llm forwards timeout/max_retries/backoff_base, which are irrelevant
    to a stub."""
    import json
    import re
    # Match various prompt formats for extracting the job title
    m = (re.search(r'Cluster job posting: "([^"]+)"', prompt or "")
          or re.search(r'The sprint is for: "([^"]+)"', prompt or "")
          or re.search(r'The job title is: "([^"]+)"', prompt or "")
          or re.search(r'The job posting says: "([^"]+)"', prompt or ""))
    job_title = m.group(1) if m else "the target job"
    # Project anatomy requests (contain 'project N of 3')
    im = re.search(r"project (\d) of 3", prompt or "")
    if im:
        index = int(im.group(1))
        # Fixed email-flow titles ONLY for the canonical email-automation feed
        # postings; every other cluster's project title is DERIVED from the
        # job title so grounding gates (e.g. web-scraping titles must mention
        # the scraped-job posting) stay honest for all clusters.
        email_feed_titles = {
            "Klaviyo flow setup for store",
            "Email automation revamp",
            "Abandoned cart series",
            "Segment + campaign build",
            "Post-purchase upsell flow",
        }
        if job_title in email_feed_titles:
            title = {
                1: "Rebuild the Checkout Welcome Flow",
                2: "Rebuild the Abandoned-Cart Flow",
                3: "Rebuild the Post-Purchase Upsell Flow",
            }.get(index, f"Rebuild the core flow for {job_title}")
        else:
            title = f"Rebuild the core flow for {job_title}"
        clone_steps_map = {
            1: ["Trigger on Checkout Started",
                 "Add welcome email with dynamic order summary",
                 "Configure mobile-responsive template"],
            2: ["Trigger on Checkout Abandoned",
                 "Add 30-minute delay email with cart summary",
                 "Add 24-hour follow-up with coupon"],
            3: ["Trigger on Purchase Completed",
                 "Add upsell block for complementary product",
                 "Configure 30-day winback sequence"],
        }
        rubric_map = {
            1: ["Welcome email sends within 1 hour of checkout",
                "Dynamic cart summary present in the email",
                "Email renders correctly on mobile"],
            2: ["Recovery flow triggers when a cart is abandoned",
                "Dynamic cart summary present",
                "Coupon step included"],
            3: ["Post-purchase trigger fires on completion",
                "Upsell block renders with the product",
                "Winback sequence is scheduled"],
        }
        gap_fill_map = {1: None, 2: "mobile responsiveness", 3: None}
        reference_spec_map = {
            1: ("Screen 1: Flow list — create the automation from a blank account.\n"
                "Screen 2: Trigger settings — pick the start event from the posting.\n"
                "Screen 3: Message step — paste the sample subject line.\n"
                "Screen 4: Settings — set the delay and switch the flow on."),
            2: ("Screen 1: Flow list — create the recovery automation from scratch.\n"
                "Screen 2: Trigger settings — start on the abandonment event.\n"
                "Screen 3: First message — cart summary, 30-minute delay.\n"
                "Screen 4: Second message — coupon at 24 hours."),
            3: ("Screen 1: Flow list — create the post-purchase automation.\n"
                "Screen 2: Trigger settings — fire on order completion.\n"
                "Screen 3: Upsell block — complementary product.\n"
                "Screen 4: Winback schedule — 30-day cadence."),
        }

        return json.dumps({
            "title": title,
            "clone_steps": clone_steps_map.get(index, ["Step 1", "Step 2", "Step 3"]),
            "rubric": rubric_map.get(index, ["Criterion 1", "Criterion 2", "Criterion 3"]),
            "gap_fill_topic": gap_fill_map.get(index),
            "reference_spec": reference_spec_map.get(index, "Screen 1: build it."),
        })
    # Gap-fill micro-lesson (day 5 with a flagged nuance)
    if "Gap-fill focus" in (prompt or ""):
        fm = re.search(r"Gap-fill focus: ([^.]+)\.", prompt or "")
        focus = fm.group(1).strip() if fm else None
        if focus:
            script = (f"Today's micro-lesson fixes {focus} for {job_title}: rebuild the piece "
                      f"with {focus} done properly, then re-check it against the posting.")
        else:
            script = (f"Your target job is {job_title}. Today you rebuild the smallest real "
                      "version of exactly what the posting asks for — matching its wording.")
        return json.dumps({
            "title": f"{job_title}: how to copy it",
            "objective": f"Rebuild the smallest real version of what the posting asks for.",
            "script": script,
            "key_points": [f"What the posting literally asks for in {job_title}",
                            focus or "The smallest reproducible piece you can build today"],
            "pitfalls": ["Copying a generic template instead of the posting's exact flow",
                          "Skipping the dynamic cart block the client names"],
            "quiz": [f"What trigger fires this {job_title} flow?",
                      "Which block carries the dynamic content?"],
            "quiz_answers": ["The start event named in the posting.",
                              "The dynamic summary block configured per the posting."],
        })
    # Quiz verification pass (content-quality P1-3): confirm answers are specific.
    if "verify" in (prompt or "").lower() and "quiz" in (prompt or "").lower():
        return json.dumps({"ok": True})
    # Regular day lesson (setup, copywork, contract, case-study, proposals)
    # The script uses markdown-style numbered steps and bold emphasis so the
    # format_script Jinja2 filter converts them to <ol>/<b> HTML for readability.
    return json.dumps({
        "title": f"Day lesson for {job_title}",
        "objective": f"Complete the day's task for {job_title}.",
        "script": (
            f"In this lesson you will learn how to handle **{job_title}**.\n"
            "1. **Open the tool** and navigate to the flow builder.\n"
            "2. **Set the trigger** using the metric from the posting.\n"
            "3. **Add the email step** and configure dynamic content.\n"
            "4. **Test with a sample** before going live."),
        "key_points": ["Use the exact trigger from the job posting",
                        "Follow the step-by-step build sequence",
                        "Test before publishing"],
        "pitfalls": ["Skipping the test step",
                      "Using the wrong trigger for this flow type"],
        "quiz": ["What trigger starts the flow in this niche's tool?",
                   "Which variable holds the dynamic content?",
                   "How do you test the flow before going live?"],
        "quiz_answers": ["The start event named in the job posting (e.g. Checkout Started).",
                           "The dynamic summary block bound to the order/cart object.",
                           "Send a test event and confirm the email renders correctly."],
    })


# P1-1: a fake that returns a REPAIRED quiz/answer pair when the engine sends
# the verification prompt (services.lesson_engine._quiz_verify_prompt emits
# "LESSON:" + the lesson JSON). This exercises the repair path of
# _verify_lesson_quiz instead of the dead `{"ok": true}` branch, so the test
# can assert the stored answers are the specific, repaired ones.
_REPAIRED_QUIZ = [
    "What trigger starts the flow in this niche's tool?",
    "Which variable holds the dynamic content?",
    "How do you test the flow before going live?",
]
_REPAIRED_ANSWERS = [
    "The Checkout Started start event fires the flow in this niche's tool.",
    "The dynamic order-summary block bound to the cart object holds the content.",
    "Send a test event and confirm the email renders correctly in a live inbox.",
]


def _fake_repairing_llm(prompt, **kwargs):
    """Like _fake_generation_llm, but the quiz-verify pass returns a repaired,
    specific answer key (length-matched to the quiz) so _verify_lesson_quiz
    actually replaces the original pair."""
    if "LESSON:" in (prompt or ""):
        return json.dumps({"quiz": _REPAIRED_QUIZ, "quiz_answers": _REPAIRED_ANSWERS})
    return _fake_generation_llm(prompt, **kwargs)


@given('I check all rubric items for project {project} of sprint "{sid}"')
@when('I check all rubric items for project {project} of sprint "{sid}"')
def step_check_all_rubric(context, project, sid):
    """The real checkbox flow: the learner ticks every rubric item for a
    project BEFORE submitting — a submission only counts done when all
    self-checks were ticked first (content-quality P0-3)."""
    for rubric_index in range(3):
        _post(context, f"/sprints/{sid}/day/2/rubric-check",
              data={"project_index": project, "rubric_index": rubric_index,
                    "checked": "true"})
        assert context.response.status_code == 200, \
            f"rubric-check POST failed: {context.response.status_code}"


@when('the copy-work projects are created for sprint "{sid}"')
def step_create_projects(context, sid):
    """Run the REAL seeding path (services.copywork_engine.create_projects) so
    gates can assert what production ships — not what the fixture helper seeds
    (content-quality P0-2)."""
    from services.copywork_engine import create_projects
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    create_projects(adapter.sb, real_sprint_id)


@when('the content generation worker runs for sprint "{sid}"')
def step_worker_run(context, sid):
    """Run the async content worker synchronously with a stubbed LLM returning
    job-grounded JSON (no real LLM/TTS in tests) so assertions are stable.
    Every prompt sent to the stub is captured on context.captured_prompts so
    gates can assert what the engine ASKED the model (e.g. no hard-coded
    foreign-niche tool names), not just what the stub answered."""
    import services.lesson_engine as le
    import services.video_engine as ve
    captured: list = []

    def _capturing_llm(prompt, **kwargs):
        captured.append(prompt or "")
        return _fake_generation_llm(prompt, **kwargs)

    le.call_llm = _capturing_llm
    context.captured_prompts = captured
    ve.voiceover_for_lesson = lambda *a, **k: None
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    le.generate_sprint_content(adapter.sb, real_sprint_id)


@when('the content generation worker runs for sprint "{sid}" and the LLM omits '
      'the gap-fill topic')
def step_worker_run_null_gapfill(context, sid):
    """Same worker run, but the LLM's anatomy answers carry gap_fill_topic=null
    — the seeded flagged focus must survive (content-quality P1-4: an LLM null
    never overwrites an existing gap_fill_topic)."""
    import services.lesson_engine as le
    import services.video_engine as ve

    def _null_gapfill_llm(prompt, **kwargs):
        return _fake_generation_llm(prompt, **kwargs).replace(
            '"gap_fill_topic": "mobile responsiveness"',
            '"gap_fill_topic": null')

    le.call_llm = _null_gapfill_llm
    ve.voiceover_for_lesson = lambda *a, **k: None
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    le.generate_sprint_content(adapter.sb, real_sprint_id)


@when('the content generation worker runs for sprint "{sid}" with no LLM')
def step_worker_run_no_llm(context, sid):
    """Run the worker with the LLM unavailable — generation must fail visibly
    (generation_error stamp), never fall back to template content."""
    import services.lesson_engine as le
    import services.video_engine as ve
    from services.llm import LLMGenerationError
    le.call_llm = lambda *a, **k: None
    ve.voiceover_for_lesson = lambda *a, **k: None
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    try:
        le.generate_sprint_content(adapter.sb, real_sprint_id)
    except LLMGenerationError:
        pass  # expected — the failure is recorded on the day payload


@when('the content generation worker runs for sprint "{sid}" and the quiz '
      'verify repairs generic answers')
def step_worker_run_quiz_repair(context, sid):
    """Run the worker with a fake whose quiz-verify pass returns a REPAIRED,
    specific answer key (content-quality P1-1) — exercises _verify_lesson_quiz's
    repair path so the stored quiz_answers become the repaired ones."""
    import services.lesson_engine as le
    import services.video_engine as ve
    le.call_llm = _fake_repairing_llm
    ve.voiceover_for_lesson = lambda *a, **k: None
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    le.generate_sprint_content(adapter.sb, real_sprint_id)


def _fake_proposals_llm(prompt, **kwargs):
    """Deterministic stand-in for the LLM in proposal-fill tests — returns the
    batched JSON array of engineered drafts the real model produces. Echoes any
    learner-submitted URLs found in the prompt into the proof so the P1-2
    grounding (cite the real deliverable, not an abstract Mock Contract) is
    observable in assertions."""
    import json
    import re
    titles = re.findall(r'- "([^"]+)"', prompt or "")
    urls = re.findall(r'https?://[^\s")]+', prompt or "")
    url_text = (" See my build at " + ", ".join(urls)) if urls else ""
    out = []
    for t in titles:
        out.append({
            "job_title": t,
            "hook": f"I see you need {t} handled — I just rebuilt a matching flow for a Mock Contract.",
            "proof": "I completed a Mock Contract brief in this niche and passed a 3-point checklist." + url_text,
            "cta": "Happy to run a quick scope call this week.",
            "score": 85,
        })
    return json.dumps(out)


def _seed_and_fill_proposals(adapter, sid, llm):
    """Seed the skeleton drafts (as the proposals route does), then run the
    fill worker synchronously so state is deterministic before assertions —
    avoids racing the route's background fill thread."""
    import services.proposal_engine as pe
    real_sprint_id = adapter.resolve_sprint_id(sid)
    sprint_rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).limit(1).execute().data
    sprint = sprint_rows[0]
    pe.call_llm = llm
    pe.generate_drafts(adapter.sb, sprint, sprint.get("cluster_key"), sprint.get("user_id"))
    return pe, real_sprint_id


@when('the proposal drafts are generated for sprint "{sid}"')
def step_proposal_fill(context, sid):
    """Synchronously run the proposal fill worker with a stubbed LLM so the
    engineered drafts are ready before assertions (LLM-only, no templates)."""
    pe, real_sprint_id = _seed_and_fill_proposals(get_live_adapter(), sid, _fake_proposals_llm)
    pe.fill_drafts(get_live_adapter().sb, real_sprint_id)


@when('the proposal drafts are generated for sprint "{sid}" with no LLM')
def step_proposal_fill_no_llm(context, sid):
    """Run the proposal fill with the LLM unavailable — drafts must be marked
    failed (score=-1) and the page must surface the error, never a template."""
    from services.llm import LLMGenerationError
    pe, real_sprint_id = _seed_and_fill_proposals(get_live_adapter(), sid, lambda *a, **k: None)
    try:
        pe.fill_drafts(get_live_adapter().sb, real_sprint_id)
    except LLMGenerationError:
        pass  # expected — drafts are marked score=-1 for the page to surface


@when('I submit the contract form to "{path}" with no data')
def step_contract_no_data(context, path):
    _post(context, path, data={})


@when('I submit the contract form to "{path}" with submission_url "{url}"')
def step_contract_submit(context, path, url):
    _post(context, path, data={"submission_url": url})


@when('I submit the proposal form to "{path}"')
def step_proposal_submit(context, path):
    _post(context, path, data={})


@when('I choose platform "{platform}" and submit the proposal form to "{path}"')
def step_proposal_platform(context, platform, path):
    _post(context, path, data={"platform": platform})


@when('I add a contract of value {value:d} with {hours:d} hours on platform "{platform}" for sprint "{sid}"')
def step_add_contract(context, value, hours, platform, sid):
    _post(context, f"/sprints/{sid}/contract/add", data={
        "client_name": "Demo Client",
        "project_title": "Email automation setup",
        "contract_value": value,
        "hours_worked": hours,
        "platform": platform,
    })


@when('I log outcome "{outcome}" for proposal "{pid}" on sprint "{sid}"')
def step_log_outcome(context, outcome, pid, sid):
    _post(context, f"/sprints/{sid}/proposals/{pid}/respond", data={"outcome": outcome})


@when('I mark the most recent contract complete for sprint "{sid}"')
def step_contract_complete(context, sid):
    """POST to /sprints/<id>/contract/<cid>/complete for the sprint's newest
    contract (the dashboard "Mark complete" CTA on each active contract row)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("contracts").select("id") \
        .eq("sprint_id", real_sprint_id).order("created_at", desc=True).limit(1).execute().data
    assert rows, f"no contracts for sprint {sid} to mark complete"
    _post(context, f"/sprints/{sid}/contract/{rows[0]['id']}/complete", data={})


@when('I save the case study "{title}" for sprint "{sid}"')
def step_save_case_study(context, title, sid):
    _post(context, f"/sprints/{sid}/case-study", data={
        "title": title,
        "problem": "Store lost checkouts to cart abandonment.",
        "solution": "Built a 2-step recovery flow with a dynamic cart summary.",
        "result": "Recovered 12% of abandoned carts in 4 weeks.",
    })


@then('gate "{gate}" has passed verification for sprint "{sid}"')
def step_gate_passed(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*") \
        .eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert rows and rows[0].get("status") == "pass", \
        f"gate {gate} not passed for sprint {sid}: {rows}"


@then('gate "{gate}" has not passed verification for sprint "{sid}"')
def step_gate_not_passed(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*") \
        .eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert not rows or rows[0].get("status") != "pass", \
        f"gate {gate} unexpectedly passed for sprint {sid}: {rows}"


@given('copy-work project {n} for sprint "{sid}" has rubric "{rubric}"')
def step_project_has_rubric(context, n, sid, rubric):
    """Set a single explicit rubric item on a copy-work project so Gate B's
    content check has a concrete observable artifact to look for (P0-2)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("copywork_projects").update({
        "rubric": [rubric],
    }).eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute()


@given('the mock contract brief for sprint "{sid}" requires "{req}"')
def step_brief_requires(context, sid, req):
    """Seed the capstone brief's acceptance criteria so Gate B's content check
    validates the deliverable against the brief's OWN requirements (critique I2),
    not the copy-work rubric."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("capstone_briefs").select("id") \
        .eq("sprint_id", real_sprint_id).limit(1).execute().data
    if rows:
        adapter.sb.table("capstone_briefs").update({"requirements": req}) \
            .eq("id", rows[0]["id"]).execute()
    else:
        # job_feed_id is NOT NULL — reuse the cluster's first feed row.
        feed = adapter.sb.table("job_feed").select("id") \
            .eq("status", "active").limit(1).execute().data
        adapter.sb.table("capstone_briefs").insert({
            "sprint_id": real_sprint_id, "title": "Mock Brief", "requirements": req,
            "job_feed_id": feed[0]["id"] if feed else None,
        }).execute()


@when('I submit the mock contract for sprint "{sid}" with deliverable_url "{url}" missing that requirement')
def step_submit_contract_missing(context, sid, url):
    """Submit a Mock Contract deliverable whose content does NOT meet the brief's
    acceptance criterion → Gate B must NOT pass (P0-2)."""
    _post(context, f"/sprints/{sid}/contract/submit", data={
        "submission_url": url,
        "deliverable_text": "I rebuilt a generic checkout flow and tested it end to end.",
    })


@when('I resubmit with a deliverable containing the dynamic summary block')
def step_resubmit_contract_with_artifact(context):
    """Resubmit the Mock Contract with deliverable content that DOES contain the
    rubric-named artifact → Gate B must pass (P0-2)."""
    _post(context, "/sprints/s1/contract/submit", data={
        "submission_url": "https://me.dev/flow-with-artifact",
        "deliverable_text": "Here is my finished deliverable. Message contains the dynamic summary block.",
    })


@then('copy-work project {n} for sprint "{sid}" is not marked done')
def step_project_not_done(context, n, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("done") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows and not rows[0].get("done"), \
        f"copy-work project {n} unexpectedly done for sprint {sid}: {rows}"


@then('copy-work project {n} for sprint "{sid}" has submitted_url "{url}"')
def step_project_has_url(context, n, sid, url):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("submitted_url") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows and rows[0].get("submitted_url") == url, \
        f"copy-work project {n} submitted_url={rows[0].get('submitted_url') if rows else None!r}, expected {url!r}"


@then('copy-work project {n} for sprint "{sid}" has a title mentioning "{text}"')
def step_project_title_mentions(context, n, sid, text):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("title") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows, f"no copy-work project {n} for sprint {sid}"
    assert text in rows[0].get("title", ""), \
        f"project {n} title {rows[0].get('title')!r} does not mention {text!r}"


@then('day {n} of sprint "{sid}" has a lesson mentioning "{text}"')
def step_day_lesson_mentions(context, n, sid, text):
    """Assert the worker stored a lesson whose content mentions the text —
    e.g. the Day 5 gap-fill micro-lesson targeting the flagged nuance."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprint_days").select("action_payload") \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute().data
    assert rows, f"no day {n} row for sprint {sid}"
    lesson = (rows[0].get("action_payload") or {}).get("lesson") or {}
    blob = json.dumps(lesson)
    assert text in blob, f"day {n} lesson missing {text!r}: {blob}"


@then('day {n} of sprint "{sid}" has a lesson not mentioning "{banned}"')
def step_day_lesson_not_mentions(context, n, sid, banned):
    """The inverse grounding gate: a generated lesson must never name a tool
    from an unrelated niche (content-quality P0-1)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprint_days").select("action_payload") \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute().data
    assert rows, f"no day {n} row for sprint {sid}"
    blob = json.dumps((rows[0].get("action_payload") or {}).get("lesson") or {})
    assert banned.lower() not in blob.lower(), \
        f"day {n} lesson mentions {banned!r}: {blob[:400]}"


@then('no generation prompt for sprint "{sid}" mentions "{first}" or "{second}"')
def step_prompts_clean(context, sid, first, second):
    """Every prompt the engine sent for this sprint must be free of literal
    foreign-niche tool names — tool vocabulary is derived from the cluster,
    never hard-coded (content-quality P0-1)."""
    prompts = getattr(context, "captured_prompts", None)
    assert prompts is not None, "worker did not run — no prompts captured"
    bad = [p for p in prompts
           if first.lower() in p.lower() or second.lower() in p.lower()]
    assert not bad, \
        f"{len(bad)} prompt(s) mention {first!r}/{second!r}; first offender: {bad[0][:300]}"


@then('a content generation prompt contains the quiz instruction')
def step_prompt_quiz_instruction(context):
    """P0-1: prove the generated LLM prompt actually carried _QUIZ_INSTRUCTION
    (which contains both 'quiz' and 'quiz_answers'). The fake always returns a
    quiz, so without this check a DEV edit that dropped the instruction would
    still leave the BDD suite green (false-green gap)."""
    from services.lesson_engine import _QUIZ_INSTRUCTION
    prompts = getattr(context, "captured_prompts", None)
    assert prompts is not None, "worker did not run — no prompts captured"
    assert any(_QUIZ_INSTRUCTION in (p or "") for p in prompts), \
        "no captured generation prompt contains _QUIZ_INSTRUCTION; quiz prompt wiring may be broken"


@then('days 6 to 14 draw from more than one distinct job posting')
def step_prompts_rotate(context):
    """Phase B/C lessons must rotate across the ranked feed instead of every
    prompt quoting feed[0] (content-quality P1-2)."""
    import re as _re
    prompts = getattr(context, "captured_prompts", None)
    assert prompts is not None, "worker did not run — no prompts captured"
    titles_by_day = {}
    for p in prompts:
        dm = _re.search(r"Day (\d+)[,.]", p)
        tm = _re.search(r'The job title is: "([^"]+)"', p)
        if dm and tm and int(dm.group(1)) >= 6:
            titles_by_day[int(dm.group(1))] = tm.group(1)
    assert titles_by_day, "no Phase B/C day prompts were captured"
    distinct = set(titles_by_day.values())
    assert len(distinct) > 1, \
        f"days {sorted(titles_by_day)} all drew from one posting: {distinct}"


@then('copy-work project {n} for sprint "{sid}" ships no reachable source URL')
def step_no_reachable_source_url(context, n, sid):
    """Seeded projects must not carry reachable placeholder URLs (e.g.
    example.com) into prod paths — content-quality P0-2."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("source_url") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows, f"no copy-work project {n} for sprint {sid}"
    url = rows[0].get("source_url")
    assert not url or not str(url).lower().startswith(("http://", "https://")), \
        f"project {n} ships a reachable placeholder URL: {url!r}"


@then('copy-work project {n} for sprint "{sid}" still has gap-fill topic "{topic}"')
def step_gapfill_topic_survives(context, n, sid, topic):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("gap_fill_topic") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute().data
    assert rows, f"no copy-work project {n} for sprint {sid}"
    actual = rows[0].get("gap_fill_topic")
    assert actual == topic, \
        f"project {n} gap_fill_topic={actual!r}, expected {topic!r} to survive"


def _day_lesson(adapter, sid, n):
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprint_days").select("action_payload") \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute().data
    assert rows, f"no day {n} row for sprint {sid}"
    lesson = (rows[0].get("action_payload") or {}).get("lesson") or {}
    assert lesson, f"day {n} has no generated lesson for sprint {sid}"
    return lesson


@then('day {n} of sprint "{sid}" has a lesson with at least {k} key points')
def step_day_lesson_key_points(context, n, sid, k):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    kps = lesson.get("key_points") or []
    assert len(kps) >= int(k), f"day {n} lesson has {len(kps)} key points, expected >= {k}"


@then('day {n} of sprint "{sid}" has a lesson with a script longer than {m} characters')
def step_day_lesson_script_len(context, n, sid, m):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    assert len(lesson.get("script") or "") > int(m), f"day {n} lesson script too short"


@then('day {n} of sprint "{sid}" has a lesson with an objective')
def step_day_lesson_objective(context, n, sid):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    assert (lesson.get("objective") or "").strip(), f"day {n} lesson has no objective"


@then('day {n} of sprint "{sid}" has a lesson mentioning a pitfall')
def step_day_lesson_pitfall(context, n, sid):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    assert (lesson.get("pitfalls") or []), f"day {n} lesson has no pitfalls"


@then('day {n} of sprint "{sid}" has a lesson with at least {k} quiz questions')
def step_day_lesson_quiz_count(context, n, sid, k):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    quiz = lesson.get("quiz") or []
    assert len(quiz) >= int(k), f"day {n} lesson has {len(quiz)} quiz questions, expected >= {k}"


@then('day {n} of sprint "{sid}" has a lesson with quiz_answers for every question')
def step_day_lesson_quiz_answers(context, n, sid):
    lesson = _day_lesson(get_live_adapter(), sid, n)
    quiz = lesson.get("quiz") or []
    answers = lesson.get("quiz_answers") or []
    assert quiz, f"day {n} lesson has no quiz to answer"
    assert len(answers) == len(quiz), \
        f"day {n} lesson has {len(answers)} answers for {len(quiz)} questions"
    # M1: answer key must be specific, not a generic placeholder — each answer
    # carries real content (the P1-3 fix claims non-generic answers).
    for a in answers:
        assert isinstance(a, str) and len(a.strip()) >= 5, \
            f"day {n} quiz answer is too short/generic: {a!r}"


@then('day {n} of sprint "{sid}" has the repaired quiz answers')
def step_day_lesson_repaired_answers(context, n, sid):
    """P1-1: the stored quiz_answers are the SPECIFIC repaired pair returned by
    the verify pass (not the generic original) — proves _verify_lesson_quiz's
    repair path ran and replaced the answers."""
    lesson = _day_lesson(get_live_adapter(), sid, n)
    answers = lesson.get("quiz_answers") or []
    assert answers == _REPAIRED_ANSWERS, \
        f"day {n} quiz_answers={answers!r}, expected repaired {_REPAIRED_ANSWERS!r}"


@given('day {n} of sprint "{sid}" has a lesson without quiz data')
def step_seed_lesson_no_quiz(context, n, sid):
    """P1-5: seed a LEGACY lesson (pre-feature) that has NO quiz/quiz_answers
    so we can assert the day page still renders and hides the Knowledge Check
    section gracefully (no 500, no broken toggle)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprint_days").select("action_payload") \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).limit(1).execute().data
    assert rows, f"no day {n} row for sprint {sid}"
    payload = dict(rows[0].get("action_payload") or {})
    payload["lesson"] = {
        "title": "Legacy lesson with no quiz",
        "objective": "Do the thing the posting asks for.",
        "script": "Rebuild the smallest real version of exactly what the posting asks for.",
        "key_points": ["Use the exact trigger from the job posting",
                       "Follow the step-by-step build sequence"],
        "pitfalls": ["Skipping the test step",
                     "Using the wrong trigger for this flow type"],
    }
    payload["lesson"].pop("quiz", None)
    payload["lesson"].pop("quiz_answers", None)
    adapter.sb.table("sprint_days").update({"action_payload": payload}) \
        .eq("sprint_id", real_sprint_id).eq("day_no", int(n)).execute()


@then('copy-work project {p} for sprint "{sid}" has between {lo} and {hi} clone steps')
def step_project_clone_count(context, p, sid, lo, hi):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("clone_steps") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(p)).execute().data
    assert rows, f"no copy-work project {p} for sprint {sid}"
    steps = rows[0].get("clone_steps") or []
    assert int(lo) <= len(steps) <= int(hi), \
        f"project {p} has {len(steps)} clone steps, expected {lo}-{hi}"


@then('copy-work project {p} for sprint "{sid}" has exactly {n} rubric items')
def step_project_rubric_count(context, p, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("rubric") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(p)).execute().data
    assert rows, f"no copy-work project {p} for sprint {sid}"
    rubric = rows[0].get("rubric") or []
    assert len(rubric) == int(n), f"project {p} has {len(rubric)} rubric items, expected {n}"


def _sprint_row(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    return rows[0]


@then('sprint "{sid}" has contracts_won equal to {n:d}')
def step_contracts_won(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("contracts_won") or 0) == n, \
        f"contracts_won={row.get('contracts_won')}, expected {n}"


@then('sprint "{sid}" has contracts_completed equal to {n:d}')
def step_contracts_completed(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("contracts_completed") or 0) == n, \
        f"contracts_completed={row.get('contracts_completed')}, expected {n}"


@then('sprint "{sid}" has total_earned equal to {n:d}')
def step_total_earned(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("total_earned") or 0) == n, \
        f"total_earned={row.get('total_earned')}, expected {n}"


@then('sprint "{sid}" has avg_contract_value equal to {n:d}')
def step_avg_contract_value(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("avg_contract_value") or 0) == n, \
        f"avg_contract_value={row.get('avg_contract_value')}, expected {n}"


@then('sprint "{sid}" has a first_contract_at timestamp')
def step_first_contract_at(context, sid):
    row = _sprint_row(context, sid)
    assert row.get("first_contract_at"), f"first_contract_at missing: {row.get('first_contract_at')!r}"


@then('sprint "{sid}" is completed')
def step_sprint_completed(context, sid):
    row = _sprint_row(context, sid)
    assert row.get("status") == "completed", \
        f"sprint {sid} status={row.get('status')}, expected completed"


@then('sprint "{sid}" has responses_received equal to {n:d}')
def step_responses_received(context, sid, n):
    row = _sprint_row(context, sid)
    assert int(row.get("responses_received") or 0) == n, \
        f"responses_received={row.get('responses_received')}, expected {n}"


@then('a case study titled "{title}" exists for sprint "{sid}"')
def step_case_study_exists(context, title, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("case_studies").select("*") \
        .eq("sprint_id", real_sprint_id).eq("title", title).execute().data
    assert rows, f"no case study {title!r} for sprint {sid}"


@when('the sprint reaches day {n}')
def step_sprint_reaches_day(context, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id("s1")
    adapter.sb.table("sprints").update({
        "current_day": int(n),
        "phase": "C" if int(n) >= 11 else "A",
    }).eq("id", real_sprint_id).execute()
    # Get the updated sprint for diagnosis
    sprint = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).limit(1).execute().data[0]
    context.diagnosis = diagnose(sprint)


# ── Then: DB-state assertions ──────────────────────────────────────
@then('a verification review for gate "{gate}" is recorded for sprint "{sid}"')
def step_review_recorded(context, gate, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("verification_reviews").select("*").eq("sprint_id", real_sprint_id).eq("gate", gate).execute().data
    assert rows, f"no verification_reviews row for ({sid}, gate {gate})"


@then('a job cluster "{key}" is recorded as requested')
def step_cluster_requested(context, key):
    adapter = get_live_adapter()
    rows = adapter.sb.table("job_clusters").select("*").eq("cluster_key", key).eq("status", "requested").execute().data
    assert rows, f"cluster {key} not recorded as requested"


@then('a badge is issued for sprint "{sid}"')
def step_badge_issued(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("badges").select("*").eq("sprint_id", real_sprint_id).execute().data
    assert rows, f"no badge row for sprint {sid}"


@then('no badge is issued for sprint "{sid}"')
def step_badge_not_issued(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("badges").select("*").eq("sprint_id", real_sprint_id).execute().data
    assert not rows, f"unexpected badge row for sprint {sid}: {rows}"


@then('draft proposals exist for sprint "{sid}"')
def step_drafts_exist(context, sid):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("proposals").select("*").eq("sprint_id", real_sprint_id).eq("status", "draft").execute().data
    assert rows, f"no draft proposals for sprint {sid}"


@then('the proposal "{pid}" is marked submitted')
def step_proposal_submitted(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "submitted", f"proposal {pid} not submitted: {rows}"


@given('copy-work project {n} for sprint "{sid}" has submitted_url "{url}" and rubric_checked all true')
def step_project_submitted_url_checked(context, n, sid, url):
    """Seed a Gate-A-passed project: a valid submitted URL plus every rubric item
    self-checked (content-quality P1-2 needs this to ground the proposal proof in
    the learner's real deliverable)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    adapter.sb.table("copywork_projects").update({
        "submitted_url": url,
        "rubric_checked": [True, True, True],
    }).eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute()


@then('the proposal for the live job mentions "{text}"')
def step_proposal_mentions(context, text):
    """Assert at least one generated proposal body cites the learner's real
    submitted deliverable URL (content-quality P1-2 grounding)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id("s1")
    rows = adapter.sb.table("proposals").select("template_body") \
        .eq("sprint_id", real_sprint_id).execute().data
    bodies = [r.get("template_body") or "" for r in rows]
    assert any(text in b for b in bodies), \
        f"no proposal mentions {text!r}; bodies={bodies!r}"


@then('the proposal "{pid}" is submitted on platform "{platform}"')
def step_proposal_platform_status(context, pid, platform):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows, f"no proposal {pid}"
    assert rows[0].get("status") == "submitted", f"proposal {pid} not submitted"
    assert rows[0].get("platform") == platform, \
        f"proposal {pid} platform={rows[0].get('platform')}, expected {platform}"


@then('sprint "{sid}" has proposals_sent equal to {n}')
def step_sprint_sent(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    assert rows[0].get("proposals_sent") == int(n), \
        f"proposals_sent={rows[0].get('proposals_sent')}, expected {n}"


@then('the proposal "{pid}" remains a draft until the user confirms submission')
def step_proposal_draft_confirm(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "draft", f"proposal {pid} not draft"


@then('the proposal "{pid}" remains a draft')
def step_proposal_draft(context, pid):
    adapter = get_live_adapter()
    real_pid = adapter.get_proposal_real_id(pid)
    rows = adapter.sb.table("proposals").select("*").eq("id", real_pid).execute().data
    assert rows and rows[0].get("status") == "draft", f"proposal {pid} not draft"


@then('the sprint "{sid}" is now on day {n}')
def step_sprint_now_day(context, sid, n):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("sprints").select("*").eq("id", real_sprint_id).execute().data
    assert rows, f"no sprint {sid}"
    assert rows[0].get("current_day") == int(n), \
        f"current_day={rows[0].get('current_day')}, expected {n}"


@then('the iteration engine returns a diagnosis of price, portfolio, or niche')
def step_diagnosis(context):
    assert context.diagnosis in ("price", "portfolio", "niche"), \
        f"diagnosis={context.diagnosis!r}"


@then('the page does not contain any client name')
def step_no_client_name(context):
    html = getattr(context, "page_html", "") or ""
    for bad in ("Acme", "Client Name", "Jordan Lee", "Wayne", "Doe"):
        assert bad not in html, f"page unexpectedly contains client name {bad!r}"


@then('the page does not contain any badge')
def step_no_badge(context):
    html = getattr(context, "page_html", "") or ""
    assert "����" not in html, "page unexpectedly contains a badge"


@then('a mentor session exists for sprint "{sid}" and job "{job}"')
def step_mentor_session(context, sid, job):
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    # Map fixture job ID to real UUID using module-level storage
    real_job_id = get_static_job_id(job)
    rows = adapter.sb.table("mentor_sessions").select("*").eq("sprint_id", real_sprint_id).eq("job_feed_id", real_job_id).execute().data
    assert rows, f"no mentor session for ({sid}, {job})"


@given('sprint "{sid}" stored clone step "{step}" for project {n}')
def step_stored_clone_step(context, sid, step, n):
    """Seed a clone step on a copy-work project so the mentor RAG contradiction
    check has stored build content to compare against (content-quality P1-1)."""
    adapter = get_live_adapter()
    real_sprint_id = adapter.resolve_sprint_id(sid)
    rows = adapter.sb.table("copywork_projects").select("clone_steps") \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).limit(1).execute().data
    existing = (rows[0].get("clone_steps") or []) if rows else []
    if step not in existing:
        existing = existing + [step]
    adapter.sb.table("copywork_projects").update({"clone_steps": existing}) \
        .eq("sprint_id", real_sprint_id).eq("project_index", int(n)).execute()


@when('the learner asks the mentor "{question}"')
def step_learner_asks_mentor(context, question):
    """Drive the mentor agent directly with a stubbed LLM that returns an answer
    advising a trigger. Asserts the returned answer (if any) does not contradict
    the stored clone steps (content-quality P1-1)."""
    import services.mentor_agent as ma
    from services.llm import LLMGenerationError
    # Stub returns an answer that mentions a contradicting trigger and contains
    # two job-description terms ("checkout", "flow") so it clears the term bar
    # and reaches the contradiction check.
    ma.call_llm = lambda prompt, **k: \
        "You should use the Purchase Completed trigger for this checkout flow."
    job_description = "Build a checkout flow with dynamic content."
    real_sprint_id = get_live_adapter().resolve_sprint_id("s1")
    try:
        context.mentor_result = ma.answer(
            question, job_description, sprint_id=real_sprint_id,
            sb=get_live_adapter().sb)
        context.mentor_error = None
    except LLMGenerationError as exc:
        context.mentor_error = str(exc)
        context.mentor_result = None


@then('the mentor answer does not advise a trigger contradicting the stored clone steps')
def step_mentor_no_contradiction(context):
    if context.mentor_error:
        # Rejected for contradicting stored clone steps — acceptable outcome.
        return
    answer = (context.mentor_result or {}).get("answer", "")
    assert "purchase completed" not in answer.lower(), \
        f"mentor answer advises a contradicting trigger: {answer!r}"