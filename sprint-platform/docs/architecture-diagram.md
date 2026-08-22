# Sprint Platform — Architecture Diagram

**Generated:** 2026-08-20 · **Source:** codebase analysis + `architecture.md` + `engineering-spec.md`

---

## 1. High-Level System Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER'S BROWSER                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Server-Rendered Jinja2 Templates (Tailwind CDN + Alpine.js)       │    │
│  │                                                                     │    │
│  │  landing · login · sprint_picker · sprint_dashboard · day           │    │
│  │  proposals · mock_contract · profile · mentor · clients · admin     │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                       │
│  ┌──────────────────────────────────▼──────────────────────────────────┐    │
│  │  Remotion Player Bundle (static/video/lesson-player.js · 400kb)    │    │
│  │                                                                     │    │
│  │  TwoPanelLesson.tsx → kinetic text + edge-tts voiceover             │    │
│  │  Mounted by: templates/day.html (window.__LESSON_PROPS__)           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Client-Side JS (vanilla + Alpine.js)                               │    │
│  │                                                                     │    │
│  │  CSRF token injection (X-CSRFToken header)                         │    │
│  │  Polling: GET /sprints/<id>/generation (content progress)          │    │
│  │  Forms: POST day/complete, copywork, contract, proposals, mentor   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTPS
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RENDER (FREE TIER) — DEPLOYMENT                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  gunicorn (2 workers, 120s timeout)                                │    │
│  │  wsgi.py → create_app()                                            │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLASK APPLICATION LAYER                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  app.py — Application Factory (create_app)                        │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐      │    │
│  │  │  Security Layer                                           │      │    │
│  │  │  • CSRFProtect (flask-wtf) — all POST routes              │      │    │
│  │  │  • Session cookie (user_id = auth.users UUID)            │      │    │
│  │  │  • before_request: load_user() + UUID validation         │      │    │
│  │  └──────────────────────────────────────────────────────────┘      │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐      │    │
│  │  │  Template Filters                                         │      │    │
│  │  │  • format_script  — markdown → semantic HTML              │      │    │
│  │  │  • strip_markdown — markdown → clean plain text           │      │    │
│  │  │  • money          — decimal → "$N"                        │      │    │
│  │  │  • dt             — timestamp → "YYYY-MM-DD"              │      │    │
│  │  └──────────────────────────────────────────────────────────┘      │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                       │
│  ┌──────────────────────────────────▼──────────────────────────────────┐    │
│  │  BLUEPRINTS (Routes Layer)                                          │    │
│  │                                                                     │    │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐               │    │
│  │  │ auth_bp     │ │ main_bp      │ │ sprints_bp    │               │    │
│  │  │ /auth/login │ │ /            │ │ /sprints/<id> │               │    │
│  │  │ /auth/logout│ │ /sprints     │ │ /day/<n>      │               │    │
│  │  │             │ │ /topics      │ │ /generation   │               │    │
│  │  │             │ │ /pricing     │ │ /day/<n>/     │               │    │
│  │  │             │ │ /sprints/    │ │   complete    │               │    │
│  │  │             │ │   request    │ │ /day/<n>/     │               │    │
│  │  │             │ │ /sprints/    │ │   copywork    │               │    │
│  │  │             │ │   <key>/start│ │ /complete     │               │    │
│  │  │             │ │              │ │ /badge        │               │    │
│  │  └─────────────┘ └──────────────┘ └───────────────┘               │    │
│  │                                                                     │    │
│  │  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐             │    │
│  │  │ contract_bp   │ │ proposals_bp  │ │ profile_bp   │             │    │
│  │  │ /sprints/     │ │ /sprints/     │ │ /profile/<s> │             │    │
│  │  │   <id>/contract│ │   <id>/      │ │ /profile/me  │             │    │
│  │  │ /contract/    │ │   proposals   │ │              │             │    │
│  │  │   submit      │ │ /proposals/   │ └──────────────┘             │    │
│  │  │ /contract/    │ │   <pid>/      │                              │    │
│  │  │   add         │ │   submit      │ ┌──────────────┐             │    │
│  │  │ /contract/    │ │ /proposals/   │ │ mentor_bp    │             │    │
│  │  │   <id>/complete│ │   <pid>/     │ │ /mentor      │             │    │
│  │  │ /case-study   │ │   respond     │ │ /mentor/turn │             │    │
│  │  └───────────────┘ └───────────────┘ └──────────────┘             │    │
│  │                                                                     │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │    │
│  │  │ clients_bp   │ │ admin_bp     │ │ (pricing_bp) │               │    │
│  │  │ /clients/    │ │ /admin/*     │ │ (deferred)   │               │    │
│  │  │  freelancers │ │ clusters     │ │              │               │    │
│  │  │              │ │ cohorts      │ └──────────────┘               │    │
│  │  │              │ │ feed         │                                │    │
│  │  │              │ │ /admin/      │                                │    │
│  │  │              │ │  clusters/   │                                │    │
│  │  │              │ │  <key>/refresh│                               │    │
│  │  └──────────────┘ └──────────────┘                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SERVICE LAYER (Workers)                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  DEMAND INTELLIGENCE                  │ SPRINT ENGINES              │    │
│  │                                        │                             │    │
│  │  demand_intelligence.py                │ sprint_planner.py           │    │
│  │  • feed ingest + normalize             │ • 14-day skeleton (sync)    │    │
│  │  • cluster + score                     │                             │    │
│  │  • unlock_day quantile buckets         │ lesson_engine.py            │    │
│  │  • live counters + snapshots           │ • per-day lesson (LLM-only)│    │
│  │                                        │ • project anatomy (LLM)     │    │
│  │  unlock_engine.py                      │ • generate_sprint_content   │    │
│  │  • meter recompute on day completion   │   (background thread)       │    │
│  │  • snapshot write                      │ • day_status_map()          │    │
│  │                                        │ • generation_error stamping │    │
│  │                                        │                             │    │
│  │                                        │ copywork_engine.py          │    │
│  │                                        │ • project skeleton seed     │    │
│  │                                        │ • gap_fill_topic assignment │    │
│  │                                        │                             │    │
│  │                                        │ mock_contract_engine.py     │    │
│  │                                        │ • brief synthesis (anonymized)│   │
│  │                                        │ • No-500 default            │    │
│  │                                        │                             │    │
│  │                                        │ proposal_engine.py          │    │
│  │                                        │ • LLM-engineered drafts     │    │
│  │                                        │ • async fill (score=-1 fail)│    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SUPPORT ENGINES                                                   │    │
│  │                                                                     │    │
│  │  video_engine.py                   verification_service.py          │    │
│  │  • edge-tts voiceover synthesis    • auto_check_gate_a (3 projects) │    │
│  │  • ffprobe duration measurement    • auto_check_gate_b (contract)   │    │
│  │  • MP3 → Storage bucket            • record() (peer pass)          │    │
│  │                                                                     │    │
│  │  badge_engine.py                   outcome_service.py               │    │
│  │  • demand-validated badge issuance • contract add/complete (RPC)    │    │
│  │  • idempotent (gate B + sprint)    • total_earned / avg rollup     │    │
│  │                                                                     │    │
│  │  iteration_engine.py               nudge_engine.py                  │    │
│  │  • diagnosis (price/portfolio/niche)• streak + confidence recompute │    │
│  │  • remedial micro-course            • encouragement messages         │    │
│  │                                                                     │    │
│  │  mentor_agent.py                   schemas.py                       │    │
│  │  • Socratic chat (LLM-only)        • Pydantic validation models    │    │
│  │  • job-grounded + conversation     • ProposalPayload               │    │
│  │    memory + grounding gate          • MentorTurnPayload             │    │
│  │  • visible 503 on failure          • ContractAddPayload            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  LLM PROVIDER CHAIN (services/llm.py — call_llm)                   │    │
│  │                                                                     │    │
│  │  ┌─────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐  │    │
│  │  │ 1. ENV  │───▶│ 2. OpenRtr │───▶│ 3. Omnirte │───▶│ 4. None  │  │    │
│  │  │ endpoint│    │ cloud      │    │ localhost  │    │ → LLM-   │  │    │
│  │  │ (config)│    │ (API key)  │    │ :20128     │    │ Generation│  │    │
│  │  └─────────┘    └────────────┘    └────────────┘    │ Error    │  │    │
│  │                                                     └──────────┘  │    │
│  │  Retry: max_retries with exponential backoff                      │    │
│  │  Content is LLM-only — no deterministic fallback                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SUPABASE CLIENT (services/supabase_client.py)                     │    │
│  │                                                                     │    │
│  │  ┌──────────────────────┐  ┌──────────────────────┐               │    │
│  │  │ get_client_supabase()│  │ get_supabase()        │               │    │
│  │  │ ANON KEY             │  │ SERVICE ROLE KEY      │               │    │
│  │  │ (routes only)        │  │ (admin workers)       │               │    │
│  │  │ RLS enforced         │  │ Bypasses RLS          │               │    │
│  │  └──────────┬───────────┘  └──────────┬───────────┘               │    │
│  └─────────────┼──────────────────────────┼───────────────────────────┘    │
│                │                          │                                 │
└────────────────┼──────────────────────────┼─────────────────────────────────┘
                 │                          │
                 ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SUPABASE (CLOUD) — DATA LAYER                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL Database (schema.sql)                                    │    │
│  │                                                                     │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                 │    │
│  │  │ DEMAND TABLES       │  │ USER/COHORT TABLES  │                 │    │
│  │  │                     │  │                     │                 │    │
│  │  │ job_clusters        │  │ user_profiles       │                 │    │
│  │  │ job_feed            │  │ user_platforms      │                 │    │
│  │  │ demand_snapshots    │  │ cohorts             │                 │    │
│  │  └─────────────────────┘  └─────────────────────┘                 │    │
│  │                                                                     │    │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                 │    │
│  │  │ SPRINT TABLES       │  │ VERIFICATION TABLES  │                │    │
│  │  │                     │  │                     │                 │    │
│  │  │ sprints             │  │ verification_reviews│                 │    │
│  │  │ sprint_days         │  │ (gate A + gate B)   │                 │    │
│  │  │ sprint_unlock_      │  └─────────────────────┘                 │    │
│  │  │   snapshots         │                                          │    │
│  │  └─────────────────────┘  ┌─────────────────────┐                 │    │
│  │                           │ PHASE A TABLES      │                 │    │
│  │  ┌─────────────────────┐  │                     │                 │    │
│  │  │ PHASE B TABLES      │  │ copywork_projects   │                 │    │
│  │  │                     │  └─────────────────────┘                 │    │
│  │  │ capstone_briefs     │                                          │    │
│  │  │ case_studies        │  ┌─────────────────────┐                 │    │
│  │  └─────────────────────┘  │ PHASE C TABLES      │                 │    │
│  │                           │                     │                 │    │
│  │  ┌─────────────────────┐  │ proposals           │                 │    │
│  │  │ OUTCOME TABLES      │  │ contracts           │                 │    │
│  │  │                     │  └─────────────────────┘                 │    │
│  │  │ badges              │                                          │    │
│  │  │ user_momentum       │  ┌─────────────────────┐                 │    │
│  │  └─────────────────────┘  │ MENTOR TABLE        │                 │    │
│  │                           │                     │                 │    │
│  │  ┌─────────────────────┐  │ mentor_sessions     │                 │    │
│  │  │ PUBLIC VIEW         │  └─────────────────────┘                 │    │
│  │  │                     │                                          │    │
│  │  │ public_freelancers  │  ┌─────────────────────┐                 │    │
│  │  │ (client filter)     │  │ RPC FUNCTIONS       │                 │    │
│  │  └─────────────────────┘  │                     │                 │    │
│  │                           │ add_contract_atomic │                 │    │
│  │                           │ complete_contract_  │                 │    │
│  │                           │   atomic            │                 │    │
│  │                           │ idx_cohorts_active_ │                 │    │
│  │                           │   per_cluster       │                 │    │
│  │                           └─────────────────────┘                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Supabase Auth (session cookie → auth.users UUID)                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Supabase Storage (voiceovers bucket)                               │    │
│  │  • MP3 files from edge-tts → served to Remotion <Audio>            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SERVICES                                    │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ LLM Providers    │  │ edge-tts         │  │ Supabase Cloud           │  │
│  │                  │  │                  │  │                          │  │
│  │ • OpenRouter     │  │ • TTS synthesis  │  │ • Postgres               │  │
│  │ • Omniroute      │  │ • Local binary   │  │ • Auth                   │  │
│  │ • Custom endpoint│  │ • MP3 output     │  │ • Storage (voiceovers)   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Render (deployment host)                                           │    │
│  │  • gunicorn → wsgi.py → create_app()                               │    │
│  │  • Free tier: 512 MB RAM, 2 workers, 120s timeout                  │    │
│  │  • Env vars: SECRET_KEY, SUPABASE_*, LLM_*, ADMIN_EMAIL            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Developer Machine (cron + local dev)                               │    │
│  │  • run.py → localhost:5000 (debug mode)                             │    │
│  │  • Nightly crons: feed refresh, demand snapshots                   │    │
│  │  • .env file (local secrets)                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow: Enrollment → Content Generation → Day Completion

```
 User clicks "Start Sprint"
         │
         ▼
 ┌─── POST /sprints/<cluster_key>/start ───────────────────────────────────┐
 │                                                                          │
 │  1. Resolve cluster (job_clusters)                                      │
 │  2. _open_cohort() → join latest active cohort OR create Cohort #N     │
 │  3. Create sprints row + sprint_unlock_snapshots                       │
 │  4. sprint_planner.create_plan() → 14 sprint_days (sync, idempotent)   │
 │  5. copywork_engine.create_projects() → 3 skeleton projects (sync)     │
 │  6. Background thread: lesson_engine.generate_sprint_content()          │
 │     │                                                                    │
 │     │  ┌──────────────────────────────────────────────────────┐        │
 │     │  │ For each day 1..14:                                  │        │
 │     │  │   • lesson_engine.lesson_for_day() → call_llm()     │        │
 │     │  │     → title, script, key_points, pitfalls            │        │
 │     │  │   • video_engine → edge-tts → MP3 → Storage         │        │
 │     │  │   • lesson_engine.project_anatomy() → call_llm()    │        │
 │     │  │     → clone_steps, rubric per project                │        │
 │     │  │   • On failure: stamp generation_error on day payload│        │
 │     │  │   • day_status_map() → {day_no: ok|error|pending}   │        │
 │     │  └──────────────────────────────────────────────────────┘        │
 │                                                                          │
 │  7. Dashboard polls GET /sprints/<id>/generation                        │
 │     → {status: "partial", generated: 12, total: 14,                    │
 │        day_status: {1:"ok", 2:"ok", ..., 7:"error", ...}}             │
 │                                                                          │
 │  8. Banner: "⚡ 12 of 14 days generated" + color-coded day track        │
 └──────────────────────────────────────────────────────────────────────────┘

 User clicks "Open Day 4"
         │
         ▼
 ┌─── GET /sprints/<id>/day/4 ─────────────────────────────────────────────┐
 │                                                                          │
 │  1. load_day() → sprint_days row with action_payload.lesson             │
 │  2. Render day.html:                                                    │
 │     ├── Remotion Player (window.__LESSON_PROPS__ = lesson|strip_markdown)│
 │     │   ├── Kinetic text: title + script words revealed frame-by-frame  │
 │     │   ├── Key points: blue ring on active, ✓ on past                  │
 │     │   ├── Voiceover: <Audio src="voiceovers/...mp3">                  │
 │     │   └── Auto-scroll: incremental translateY when content overflows  │
 │     ├── Copy-Work Task (clone_steps + rubric from project_anatomy)      │
 │     └── Gap-Fill preview (copywork_project.gap_fill_topic)              │
 └──────────────────────────────────────────────────────────────────────────┘

 User clicks "Complete Day"
         │
         ▼
 ┌─── POST /sprints/<id>/day/4/complete ───────────────────────────────────┐
 │                                                                          │
 │  1. _complete_day_if_not_done() → idempotency guard                    │
 │     │                                                                    │
 │     │  a. Check sprint_days.is_done → if already done, skip            │
 │     │  b. Mark is_done + completed_at                                   │
 │     │  c. Advance sprints.current_day / phase                           │
 │     │                                                                    │
 │  2. unlock_engine.recompute()                                           │
 │     → sprint_unlock_snapshots {newly: +38, total: 186, cluster: 450}   │
 │                                                                          │
 │  3. nudge_engine recompute (streak, confidence)                         │
 │                                                                          │
 │  4. Return JSON {ok, next_day, meter, momentum}                         │
 │                                                                          │
 │  5. UI: celebratory uptick banner "+38 postings unlocked"               │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Verification Gates Flow

```
 ┌─── GATE A: Phase A → Phase B ───────────────────────────────────────────┐
 │                                                                          │
 │  Trigger: POST /sprints/<id>/day/<n>/copywork {rubric_url}              │
 │                                                                          │
 │  1. Validate rubric_url is valid http(s) link                           │
 │  2. Mark copywork_project.done + submitted_url                           │
 │  3. auto_check_gate_a():                                                │
 │     ├── All 3 projects done?  ─── No → "Phase B locked"                │
 │     ├── Each has valid URL?   ─── No → "Phase B locked"                │
 │     └── All pass? ─── Yes → verification_reviews(gate='A') = pass      │
 │                                                                          │
 │  Result: Phase B unlocks → Mock Contract available                      │
 └──────────────────────────────────────────────────────────────────────────┘

 ┌─── GATE B: Phase B → Phase C ───────────────────────────────────────────┐
 │                                                                          │
 │  Trigger: POST /sprints/<id>/contract/submit {submission_url}           │
 │                                                                          │
 │  1. Validate submission_url is valid http(s) link                       │
 │  2. Create verification_reviews row (pending)                            │
 │  3. auto_check_gate_b():                                                │
 │     ├── Valid deliverable URL?  ─── No → pending                       │
 │     ├── Case study saved?       ─── No → pending                       │
 │     └── Both pass? ─── Yes → verification_reviews(gate='B') = pass     │
 │                                                                          │
 │  Result: Phase C unlocks → Job feed + proposals available               │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Contract + Earnings Flow (Atomic RPC)

```
 ┌─── POST /sprints/<id>/contract/add ─────────────────────────────────────┐
 │                                                                          │
 │  1. Validate inputs (Pydantic: ContractAddPayload)                     │
 │  2. CSRF check                                                          │
 │  3. RPC: add_contract_atomic(sprint_id, client, value, hours, platform)│
 │     ├── BEGIN TRANSACTION                                              │
 │     │   INSERT INTO contracts (sprint_id, user_id, ...)                │
 │     │   SELECT → increment contracts_won, total_earned, first_contract │
 │     │   UPDATE sprints SET contracts_won += 1,                         │
 │     │     total_earned += value,                                       │
 │     │     avg_contract_value = total_earned / contracts_won,           │
 │     │     first_contract_at = COALESCE(first_contract_at, now())       │
 │     │   RETURNING *                                                    │
 │     └── COMMIT                                                         │
 │                                                                          │
 │  4. Fallback: if RPC unavailable → multi-step Python (outcome_service) │
 └──────────────────────────────────────────────────────────────────────────┘

 ┌─── POST /sprints/<id>/contract/<id>/complete ───────────────────────────┐
 │                                                                          │
 │  1. RPC: complete_contract_atomic(contract_id, sprint_id)              │
 │     ├── BEGIN TRANSACTION                                              │
 │     │   UPDATE contracts SET status = 'completed'                      │
 │     │   UPDATE sprints SET contracts_completed += 1                    │
 │     │   RETURNING *                                                    │
 │     └── COMMIT                                                         │
 │                                                                          │
 │  2. Fallback: multi-step Python (outcome_service)                      │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Security Layer Stack

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  LAYER 1: CSRF Protection (flask-wtf CSRFProtect)                      │
 │  • Every POST route requires csrf_token in form body or X-CSRFToken   │
 │  • Token stored in signed session cookie                              │
 │  • JS fetch calls: X-CSRFToken header from meta tag                   │
 └────────────────────────────────┬────────────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────────────┐
 │  LAYER 2: Session Auth                                                 │
 │  • cookie user_id must be valid auth.users UUID (22P02 guard)         │
 │  • before_request: load_user() → g.user populated                     │
 │  • require_login() guard on protected routes                           │
 └────────────────────────────────┬────────────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────────────┐
 │  LAYER 3: Route Ownership                                              │
 │  • All /sprints/* state changes gated to sprint owner                  │
 │  • _is_uuid() prevents malformed IDs from hitting DB                  │
 └────────────────────────────────┬────────────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────────────┐
 │  LAYER 4: Supabase RLS (anon key via get_client_supabase)             │
 │  • Routes use anon key → RLS policies enforced                        │
 │  • Admin workers use service key → bypasses RLS                       │
 └────────────────────────────────┬────────────────────────────────────────┘
                                  │
 ┌────────────────────────────────▼────────────────────────────────────────┐
 │  LAYER 5: Input Validation (Pydantic schemas.py)                       │
 │  • ContractAddPayload: client (2-200), value (0.01-10M), hours (1-10K)│
 │  • MentorTurnPayload: sprint_id (UUID), message (1-2000 chars)        │
 │  • ProposalPayload: proposal_id (UUID), platform (allowlist)          │
 └─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Template → Component → Data Source Mapping

```
┌────────────────────┬──────────────────────────┬────────────────────────────┐
│ Template           │ Component                │ Data Source                 │
├────────────────────┼──────────────────────────┼────────────────────────────┤
│ landing.html       │ Hero + demand counter    │ job_clusters (public read) │
│ login.html         │ Auth form                │ Supabase Auth              │
│ sprint_picker.html │ Cluster cards + badges   │ job_clusters + job_feed    │
│ sprint_dashboard   │ Phase track + meter +    │ sprints + sprint_days +    │
│                    │ generation progress +    │ sprint_unlock_snapshots +  │
│                    │ contracts card + day track│ day_status_map()           │
│ day.html           │ Remotion Player +        │ sprint_days.action_payload │
│                    │ copy-work + gap-fill     │ .lesson + copywork_projects│
│ mock_contract.html │ Brief + Gate B submit    │ capstone_briefs +          │
│                    │                          │ verification_reviews       │
│ proposals.html     │ First-Bid + iteration    │ proposals + job_feed +     │
│                    │ diagnosis                │ iteration_engine           │
│ profile.html       │ Public badges + portfolio│ user_profiles + badges +   │
│                    │                          │ job_clusters               │
│ mentor.html        │ AI mentor chat           │ mentor_sessions +          │
│                    │                          │ mentor_agent (LLM)         │
│ clients.html       │ Freelancer filter        │ public_freelancers view    │
│ admin/*.html       │ Cluster/cohort/feed mgmt │ job_clusters + cohorts +   │
│                    │                          │ job_feed                   │
└────────────────────┴──────────────────────────┴────────────────────────────┘
```

---

## 7. Async Background Jobs

```
┌─────────────────────────────┬────────────────────┬────────────────────────┐
│ Job                         │ Trigger            │ Mechanism              │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Sprint content generation   │ POST /start        │ background thread      │
│ (14 lessons + voiceovers)   │                    │ + DB polling           │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Proposal draft fill         │ GET /proposals     │ background thread      │
│ (5 LLM-engineered drafts)   │                    │ + page status          │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Feed refresh + snapshots    │ admin POST /refresh│ inline (admin action)  │
│                             │ or nightly cron    │                        │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Badge issuance              │ GET /badge         │ inline (idempotent)    │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Verification auto-check     │ POST copywork/     │ inline (auto)          │
│ (Gate A + Gate B)           │ POST contract/     │                        │
├─────────────────────────────┼────────────────────┼────────────────────────┤
│ Mentor turn                 │ POST /mentor/turn  │ request-scoped (~30s)  │
└─────────────────────────────┴────────────────────┴────────────────────────┘
```

---

## 8. File Structure

```
sprint-platform/
├── app.py                          # Flask factory (create_app)
├── config.py                       # Config class (env vars)
├── wsgi.py                         # WSGI entry (Render/gunicorn)
├── run.py                          # Local dev server
├── requirements.txt                # Python deps
├── render.yaml                     # Render deployment config
│
├── routes/                         # Flask blueprints (HTTP layer)
│   ├── __init__.py                 # Shared helpers + DAY_TO_PROJECT
│   ├── main.py                     # Landing, enrollment, content gen
│   ├── sprints.py                  # Dashboard, day views, completion
│   ├── contract.py                 # Mock contract + Gate B
│   ├── proposals.py                # First-Bid + proposals
│   ├── profile.py                  # Public profile
│   ├── mentor.py                   # AI mentor chat
│   ├── clients.py                  # Freelancer filter
│   ├── admin.py                    # Admin CRUD
│   └── auth.py                     # Login/logout
│
├── services/                       # Business logic (workers)
│   ├── llm.py                      # LLM provider chain (call_llm)
│   ├── supabase_client.py          # Dual-key client (anon + service)
│   ├── demand_intelligence.py      # Feed, clustering, scoring
│   ├── sprint_planner.py           # 14-day skeleton
│   ├── lesson_engine.py            # Lessons + async generation
│   ├── video_engine.py             # edge-tts voiceover
│   ├── copywork_engine.py          # Project skeleton
│   ├── mock_contract_engine.py     # Brief synthesis
│   ├── proposal_engine.py          # LLM proposal drafts
│   ├── verification_service.py     # Gate A + B auto-check
│   ├── badge_engine.py             # Badge issuance
│   ├── outcome_service.py          # Contract + earnings (RPC)
│   ├── unlock_engine.py            # Meter recompute
│   ├── nudge_engine.py             # Streak + confidence
│   ├── iteration_engine.py         # Diagnosis + remedial
│   ├── mentor_agent.py             # Socratic chat (LLM)
│   └── schemas.py                  # Pydantic validation
│
├── templates/                      # Jinja2 HTML
│   ├── base.html                   # Shared layout (nav, CSRF meta)
│   ├── styles.css                  # Global styles
│   ├── landing.html                # Marketing page
│   ├── login.html                  # Auth form
│   ├── sprint_picker.html          # Cluster cards
│   ├── sprint_dashboard.html       # Dashboard + meter + tracks
│   ├── day.html                    # Day view + Remotion player
│   ├── mock_contract.html          # Brief + Gate B
│   ├── proposals.html              # First-Bid challenge
│   ├── profile.html                # Public profile
│   ├── mentor.html                 # AI mentor chat
│   ├── clients.html                # Freelancer search
│   └── admin/                      # Admin CRUD forms
│
├── static/
│   ├── video/lesson-player.js      # Remotion bundle (400kb)
│   └── favicon.ico
│
├── video/                          # Remotion source
│   ├── src/
│   │   ├── index.tsx               # Player mount + skeleton hide
│   │   └── TwoPanelLesson.tsx      # Two-panel composition
│   ├── package.json
│   └── package-lock.json
│
├── db/
│   ├── schema.sql                  # Full Postgres schema
│   └── rpc.sql                     # Atomic RPC functions + index
│
├── tests/                          # Test suite
│   ├── test_supabase_client.py     # Task 1: anon/service split
│   ├── test_contract_validation.py # Task 3: input validation
│   ├── test_background_error.py    # Task 4: error stamping
│   ├── test_cohort_race.py         # Task 5: race condition
│   ├── test_day_complete.py        # Task 6: idempotency
│   ├── test_day_to_project.py      # Task 7: dedup mapping
│   ├── test_mentor_grounding.py    # Task 8: grounding gate
│   ├── test_proposal_thread.py     # Task 9: thread dedup
│   ├── test_llm_retry.py           # Task 10: retry/backoff
│   ├── test_schemas.py             # Task 11: Pydantic models
│   ├── test_atomic_rpc.py          # Task 12: RPC functions
│   ├── test_csrf.py                # Task 2: CSRF protection
│   ├── test_strip_markdown.py      # Markdown stripping
│   ├── test_remotion_preview.py    # Video preview gaps
│   ├── features/                   # BDD behave scenarios
│   └── steps/                      # BDD step implementations
│
├── docs/
│   ├── architecture.md             # Architecture document
│   ├── architecture-diagram.md     # This file
│   ├── engineering-spec.md         # Engineering spec
│   ├── api.md                      # API reference
│   ├── decisions.md                # Design decisions
│   └── superpowers/plans/          # Implementation plans
│
└── scripts/
    └── full_journey.py             # Visual journey script
```

---

*Source: codebase analysis + `docs/architecture.md` + `docs/engineering-spec.md` + `db/schema.sql`*
