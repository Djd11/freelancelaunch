# FreelanceLaunch — First-Run Dogfood Report

**Tester:** Dana (QE cum end-user agent) · **Date:** 2026-09-04 · **Method:** real Chromium (Playwright), fresh accounts, full journey signup → Day-1 tasks → locked surfaces, desktop + mobile 390×844. Artifacts: `docs/dogfood/` (journey scripts, logs, 77 screenshots in `shots/`).

## Market-readiness score: 6.5 / 10

The core loop is genuinely good and the funnel converts: signup → sprint start → content generation → Day-1 lesson → rubric → copywork submit all work end-to-end with zero 500s on the happy path. What drags the score: an account-takeover auth model, a mentor that is broken for exactly the new users the first run creates, and placeholder job data that undercuts the "demand-validated" promise.

## First-hand value narrative

I signed up as "Dana" with a throwaway email. One field, no password — I was on the sprint picker in seconds and the "Start free — create account" CTA actually worked (this was the old blocker; it's fixed). I started the Email Automation sprint. Content generation ran visibly with a spinner; the dashboard kept me informed. Day 1 opened with a real lesson about Klaviyo flows — specific, actionable, with a knowledge check. The task tab gave me a reference build spec, a 3-point rubric, and a link box. When I pasted "not-a-url" the app rejected it with a clear message. Completing Day 1 moved the Job Unlock Meter — that dopamine hit is real and it's the product's best moment.

Where the value broke: the Mentor. As a brand-new user I asked it about my target job and got "You have no live job post yet" — the job it referenced didn't exist. The dashboard's "Open posting →" links went to example.com. And my public profile URL was shared with another user.

## Issues

### BLOCKERS
| # | Issue | Evidence |
|---|-------|----------|
| B1 | **Email-only auth = account takeover.** Anyone can log in as anyone by typing their email. No password, no verification. | `/auth/login` accepts email alone; session set from `session["user_id"]`. |
| B2 | **Mentor broken for new users.** Intro references a target job whose description is the literal placeholder "Anonymized real job posting — …"; replies can take ~80 s with zero UI feedback, so the chat looks dead. | `shots/H1-mentor.png`, journeyH log (`delta 0`, 80.5 s). |
| B3 | *(reclassified by captain)* "Mark lesson watched" click-timeout was a test-script artifact — the button lives in the default Lesson tab and is visible; journeyE clicked it successfully. | `day.html` panel-lesson default-visible. |

### MAJOR
| # | Issue | Evidence |
|---|-------|----------|
| M1 | **Profile slug collision.** Two accounts named "Dana" both resolve to `/profile/dana` (oldest wins); the second user's public link is someone else's page. | journeyI log, I5/I6. |
| M2 | **example.com "Open posting" links + placeholder job descriptions** in the live job table — the demand-validated promise is seeded fake data. | journeyF2 log, dashboard HTML. |
| M3 | **Missing voiceover mp3s** (ERR_ABORTED on day-3.mp3 for one sprint). *(Captain re-check: all 221 stored voiceover URLs return 200 — ERR_ABORTED is the browser cancelling audio when the video layer starts; not a missing file.)* | journeyI errors. |
| M4 | **500s on sprint pages during testing.** *(Captain diagnosis: the dev server process died mid-run — environmental, not reproducible after restart; all routes now 200/302.)* | journeyJ jsonl. |
| M5 | **80 s mentor latency with no feedback.** | journeyH log. |

### MINOR
- `$0/hr` rendered on cluster cards where no rate data exists.
- Unknown profile slug returned 200 instead of 404.
- Clients-page filter is a `<select>`; automation-friendly labels would help (script friction only).

## What's genuinely good
- One-field signup, instant start — the frictionless first run the product wants.
- Generation progress is visible and honest; resume-after-restart works.
- Day-1 lesson quality is high and specific; knowledge checks reinforce.
- Junk-URL rejection with a clear, friendly message.
- Job Unlock Meter movement after completing a day is a real motivator.
- CSRF protection solid (400 without token); sprint/day routes all owner-checked (no IDOR found — captain verified every route checks `sprint.user_id == g.user["id"]`).
- Mobile 390×844 layout holds.

## Captain's fix log (same day)
1. **B2/M2 (data):** scraped 386 real live gigs from Freelancer.com skill pages (`scripts/seed_freelancer_jobs.py`), applied to `job_feed` (`scripts/apply_freelancer_seed.py`): 127 email-automation / 105 web-scraping / 50 ai-chatbots. The 5 FK-locked placeholder rows were updated in place with real gigs — no more example.com, mentor now quotes a real job description. Cluster counts recomputed honestly (was 450/322/268 fabricated).
2. **M5:** mentor chat now echoes the question, shows a "Thinking…" bubble, disables send, and renders the answer in place (no silent reload).
3. **M1:** unique public slugs — earliest account keeps the bare first-name slug, later same-name users get `name-<uid6>`; legacy links unchanged; unknown slug → 404 (`routes/profile.py`).
4. **Minor:** `$0/hr` guards in landing/picker/topics/topic-detail/dashboard templates.
5. **Verified:** `scripts/verify_dogfood_fixes.py` — 16/16 checks pass; pytest baseline unchanged (164 passed, 1 pre-existing failure).

## Still open before public launch
- **B1 auth** — needs a product decision (password or magic-link); deliberately not changed mid-flight.
- **Feed freshness** — the seeded gigs are real but will age; the scheduled RSS connector is misconfigured (backend feed → email-automation) and Freelancer.com search needs an API JWT. Wire a key or a working source before launch.
- **growth_score / "demand this quarter"** on landing/topic pages is still seed data.
