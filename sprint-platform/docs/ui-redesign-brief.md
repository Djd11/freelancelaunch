# UI Redesign Brief — "The Trades Desk"

Single source of truth for the FreelanceLaunch UI/UX revamp.
Read this fully before touching any template. Also read
`.agents/skills/frontend-design/SKILL.md` (short — the design philosophy this
brief follows).

## 0. Context

- App: Flask + Jinja sprint platform ("FreelanceLaunch"). 14-day
  demand-validated freelance training sprints: phases A/B/C, gates,
  unlock meters, mock contracts, proposals, live job feed.
- Current design = warm cream + serif + terracotta — the generic
  "AI default" look. We are replacing it ENTIRELY, not adapting it.
- All UI lives in `templates/*.html` (22 files) + one shared
  `templates/styles.css` (Jinja-included into `base.html` as an inline
  `<style>` — KEEP that include mechanism).
- Backup of the old UI exists at /tmp/sprint-ui-backup — do not touch it.

## 1. Design concept

Subject: WORK. Sprints, shifts, gates, contracts, pay. The design borrows
the vernacular of skilled trades and jobsite signage:

- Signage typography: Barlow Condensed (literally derived from highway
  signage) for display.
- Punch-clock readouts: IBM Plex Mono for numbers, counters, labels.
- Cool concrete-sage canvas — NOT cream, NOT near-black.
- Safety orange used the way real signage uses it: black text on orange
  (hi-vis), not white-on-neon.
- **Signature element (spend the boldness here): the PUNCH-CARD day
  strip.** 14 numbered slots; completed days are literally punched out
  with a hole. Days are a real sequence, so numbering is semantic.
  Everything else stays quiet and disciplined.

## 2. Tokens — use EXACTLY these

```css
:root{
  /* ground */
  --canvas:#E8EAE6;        /* concrete sage-gray            */
  --surface:#FDFDFB;      /* paper white (cards)            */
  --surface-2:#F0F2EE;    /* shelf gray (inset panels)      */
  --ink:#20241F;           /* graphite text                  */
  --ink-2:#3C423B;
  --muted:#5D645C;
  --faint:#646B62;       /* darkened from #8A9188 for AA text contrast */
  --line:#B4BBB1;        /* alias — day.html references var(--line) */
  --hairline:#CDD2CB;
  --hairline-strong:#B4BBB1;
  /* hi-vis accent — the one brand color */
  --accent:#D95B08;  --accent-ink:#A84505;  --accent-soft:#FCEADB;
  /* semantics */
  --steel:#2E5E73;    --steel-soft:#E2EDF1;   /* info/links    */
  --green:#2E6B3A;    --green-ink:#20492A;    --green-soft:#E4EFE3;  /* pass/verified */
  --amber:#8F6400;    --amber-ink:#6B4B00;    --amber-soft:#F6EDD2;  /* waiting/locked */
  --red:#B3372B;      --red-ink:#8C2A20;      --red-soft:#F9E7E1;    /* error/urgent  */
  --radius:8px; --radius-lg:10px;
  --shadow:0 1px 2px rgba(32,36,31,.06),0 4px 14px rgba(32,36,31,.06);
  --font-display:"Barlow Condensed", "Arial Narrow", sans-serif;
  --font-body:"Barlow", -apple-system, "Segoe UI", sans-serif;
  --font-mono:"IBM Plex Mono", ui-monospace, "SF Mono", monospace;
}
```

## 2.1 Contrast rulings (pre-verified — do not deviate)

QA pre-computed these; all pass WCAG AA as specified:
- ink #20241F on canvas 13.0:1 · muted on surface 6.0:1 · on canvas 5.0:1
- accent-ink on surface 5.86:1 · steel on surface 6.95:1
- green-ink on green-soft 8.67:1 · amber-ink on amber-soft 6.8:1 ·
  red-ink on red-soft 7.1:1 · white on green 6.4:1 · paper on ink 15.5:1
- **faint #646B62**: canvas 4.54 · surface 5.40 · surface-2 4.88 ·
  green-soft 4.65 · accent-soft 4.69 (all ≥4.5 — the OLD #8A9188 is
  BANNED)
- **#000 on accent #D95B08 = 5.45:1; on hover #CC5407 = 4.84:1** —
  button text is pure #000, never var(--ink)
- Plain --accent #D95B08 is NOT used for text on light grounds (use
  --accent-ink); --green #2E6B3A as text on surface = 6.29:1 OK
- th mono 11px, chips mono ≥11px — nothing below 11px anywhere

Type roles:
- **Display** (h1/h2/h3, .stat numbers, logo): Barlow Condensed 600/700,
  tighter letter-spacing (-0.01em), sentence case (NOT all-caps headings).
- **Body**: Barlow 400/500/600/700, 15px, line-height 1.55.
- **Mono** (eyebrow labels, chips, badges, day numerals, counters,
  table headers, timestamps, ticker): IBM Plex Mono, 11–13px, uppercase,
  letter-spacing .06–.08em for eyebrows.
- Scale: h1 clamp(40px, 5vw, 56px)/1.05; h2 30px/1.15; h3 20px/1.3;
  small 13.5px; xs 12.5px.

Google Fonts link (put in base.html, replace the Fraunces one):
`https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap`

## 3. Core components (define in styles.css, use everywhere)

### Punch-card day strip — THE signature
```css
.punchcard{display:flex;gap:5px}
.punchcard .slot{
  flex:1;min-width:0;height:42px;border:1px solid var(--hairline-strong);
  border-radius:6px;background:var(--surface);position:relative;
  font-family:var(--font-mono);font-size:11px;font-weight:500;
  color:var(--faint);display:flex;align-items:flex-start;
  justify-content:center;padding-top:5px;text-decoration:none;
}
/* punched = done: number fades, hole punched through */
.punchcard .slot.done{color:var(--faint)}
.punchcard .slot.done::after{
  content:"";position:absolute;left:50%;top:55%;width:14px;height:14px;
  transform:translate(-50%,-50%);border-radius:50%;
  background:var(--canvas);border:2.5px solid var(--green);
  box-shadow:inset 0 1px 2px rgba(32,36,31,.35);
}
/* today: hi-vis ring + marker */
.punchcard .slot.today{border-color:var(--accent);color:var(--ink);
  box-shadow:0 0 0 3px var(--accent-soft)}
.punchcard .slot.today::before{content:"";position:absolute;left:50%;
  top:20%;width:8px;height:8px;transform:translateX(-50%);
  border-radius:50%;background:var(--accent);animation:pulse 1.6s infinite}
/* future: quiet, dashed guide */
.punchcard .slot.locked{background:var(--surface-2);border-style:dashed;color:var(--faint)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
```
Slots keep day numbers visible (mono). Slots that are links keep
`<a href>` + `title` tooltips. Any track-style bar elsewhere in the app
is replaced by a punchcard variant.

### Stamp (gate passed / issued badges only)
```css
.stamp{display:inline-flex;align-items:center;gap:6px;
  font-family:var(--font-mono);font-size:11px;font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--green-ink);
  border:1.5px solid currentColor;border-radius:4px;padding:3px 9px;
  transform:rotate(-1.5deg);background:var(--surface)}
.stamp.ok{color:var(--green-ink)} .stamp.wait{color:var(--amber-ink)}
.stamp.fail{color:var(--red-ink)}
```
Use rotation ONLY on "issued/passed" stamps (Gate A/B pass,
Demand-Validated badge). Status chips elsewhere stay unrotated.

### Buttons (44px hit targets; NO white-on-orange)
- `.btn` base: inline-flex, min-height 44px, padding 10px 20px,
  radius 8px, Barlow 600 14px, sentence case.
- `.btn-p` (primary): **background var(--accent); color #000 (pure
  black — signage-true and 5.45:1)**; hover: darken bg to #CC5407
  (4.84:1 with black), translateY(1px) on active. Black-on-orange is
  the signage look AND passes AA for normal text.
- `.btn-ink`: graphite bg, paper text. `.btn-o`: 1.5px outline on surface.
  `.btn-g`: green bg, white text. `.btn-white`: on dark bands, paper bg
  ink text. `.btn-sm` 38px.

### Cards, nav, misc
- `.card`: surface bg, 1px hairline, radius-lg, shadow, 22px padding.
  Optional `.card-flat` (no shadow).
- `.topnav`: flex, padding 18px 0, hairline bottom.
- `.logo`: Barlow Condensed 700 22px; `em` → color var(--accent).
  Prefix a brand mark: `.logo::before` = 14px orange square with a
  punched hole (8px canvas circle, centered), margin-right 10px,
  aria-hidden (put it on a wrapping span if ::before on .logo breaks
  inline flow — keep it simple and robust).
- `.chip` / `.badge`: mono 11px uppercase, bordered chips
  (1px hairline-strong) or soft-tinted (existing b-green/b-amber/b-accent/
  b-slate/b-red semantics keep working, remap colors to tokens).
- `.eyebrow`: mono 11px 600 uppercase tracking .08em color var(--muted)
  — replaces all the inline "text-transform:uppercase" label styles.
- Tables: mono uppercase 11px headers, hairline rows, hover surface-2.
- Inputs: 1.5px hairline-strong, radius 8px, focus ring
  (border accent + 3px accent-soft shadow). Focus-visible outline: 2px
  accent, offset 2px.
- `.check-item` status circles keep the dashed/solid behavior, remap to
  tokens (done = green solid ✓).
- `.flash`: green-soft band with mono "OK" prefix feel.
- Motion: one orchestrated landing sequence (punch slots animate in
  staggered via `.punchcard.animate .slot{animation:rise .25s both}` +
  per-slot delay); everything else static. MUST wrap all animation in
  `@media (prefers-reduced-motion: reduce){...}` kill switch (copy the
  existing pattern from old styles.css).
- Responsive: grids collapse to 1 col at 900px; punchcard stays usable at
  390px (slots may shrink to 24px height, hide slot numbers below 480px).

## 4. Rules of engagement (CRITICAL)

1. **Presentation-layer only.** Preserve every Jinja variable, filter,
   `{% if %}` branch, CSRF hidden input, form method/action, script,
   element id, data-*, onclick, route string. Zero behavior changes.
2. **Inline hex replacements** wherever they remain after restyling:
   `#3F7A4E`→`#2E6B3A`, `#B1574F`→`#B3372B`, `#A97B22`→`#8F6400`,
   `#C96442`→`#D95B08`, `#CBE0CB`→`#C6DBC5`, `#EBD5C9`→`#F2D9C2`,
   `#E3B7B0`→`#EBBFB6`, `#FBE9E7`→`#F9E7E1`, `#FAF9F5`→`#FDFDFB`,
   `#1A1917`→`#20241F`. Prefer tokens over raw hex in all new code.
   The generation banner script in sprint_dashboard.html hardcodes
   `#3F7A4E/#B1574F` in JS — update those three literals too.
3. **No new dependencies.** Pure CSS in styles.css; no CDN JS; keep the
   `{% include "styles.css" %}` mechanism; fonts via the single Google
   Fonts link.
4. **Don't touch** Python files (routes/, services/, app.py),
   static/js/*.js logic (visual hex literals inside templates' inline
   scripts ARE in scope), or /tmp/sprint-ui-backup.
5. **Emoji**: replace decorative ones with mono labels where trivial
   (🔒 → "LOCKED" chip text, 📡 → "RSS" chip). Keep 🎉-style functional
   marks minimal; never change meaning or remove information.
6. **Copy discipline** (per skill): active voice, same verb everywhere,
   sentence case, plain language. Do not rewrite product copy wholesale —
   adjust only where the new structure demands it (e.g. eyebrows like
   "SHIFT A · DAYS 01–05").
7. Accessibility floor: text contrast ≥ 4.5:1, visible keyboard focus,
   44px targets, reduced-motion respected, semantic HTML (keep existing
   roles/labels/aria).

## 5. Per-page treatment

| Template | Treatment |
|---|---|
| base.html | New fonts link, favicon (orange square + punched hole SVG data-URI), keep flash + block structure |
| landing.html | Hero: condensed display headline; hi-vis underline sweep on the key phrase; demand readout card as mono "instrument panel" (DEMAND · cluster; big mono numbers for jobs/rate/growth); punch-card strip animating days 1–14 below hero; 3 phases as hairline-divided columns with mono eyebrows "SHIFT A · DAYS 01–05 / SHIFT B · DAYS 06–10 / SHIFT C · DAYS 11–14"; CTA band = graphite block |
| sprint_picker.html | Cluster cards as work orders: icon + optional trending stamp; mono stat row "N JOBS OPEN · $R/HR · 14 DAYS"; primary button keeps "Start sprint" |
| sprint_dashboard.html | Header: shift chip + mono counter strip; generation banner restyled (updated JS hexes); phases-track = 3 shift cards each with its own punch mini-strip (A:5 slots, B:5, C:4) + stamps for gates; Sprint Content grid unchanged structurally; Job Unlock Meter = full 14-slot punchcard + mono "N/14 DAYS · J POSTINGS UNLOCKED"; Today/Momentum = instrument readouts (mono numbers); contracts + live feed tables in new style |
| day.html | Eyebrow "SHIFT {phase} · DAY {n} · {action}"; done banner = green panel + stamp "DAY COMPLETE — +N POSTINGS UNLOCKED" + mini progress punchcard; Lesson/Task sticky tab strip (ink active tab); engagement/quiz panels on tokens; player container graphite; "Mark lesson watched" button behavior unchanged |
| mock_contract.html | Brief as "WORK ORDER" document: mono eyebrow CLIENT BRIEF, requirements/constraints two-col, red "DUE IN N DAYS" stamp-style badge; verification gate check-items + stamps; case study form on tokens |
| proposals.html | "BID BOARD": 5-slot punchcard (submitted = punched); proposal text panel styled as drafted document (surface-2, serif-free); jobs table; diagnosis card amber-stamped |
| mentor.html | Dispatch-radio chat: mentor avatar = accent square with mono "M", user avatar = surface-2 square "Y"; chat input bar on tokens; JS unchanged |
| clients.html | Labor-board list: hairline rows, name left, mono stat rail right (jobs now / days ago / proposals·interviews·contracts), stamps for badges |
| profile.html | Demand-Validated badges = rotated green stamps; case-study list rows; keep all profile data bindings |
| login.html | Centered card, condensed heading, tokens |
| pricing.html | Quiet two-row hairline list, tokens |
| error.html | Standalone page: match system (condensed giant code, mono reference line) |
| admin/base.html + dashboard.html | Same topnav + tokens; admin badge = amber stamp "ADMIN" |
| admin/clusters.html feed.html cohorts.html | Mono-header tables, status badges on tokens |
| admin/cluster_form.html feed_form.html cohort_form.html | Cards + fields on tokens, mono eyebrows |
| admin/platforms.html | FULL REWRITE into the design system (currently orphan Tailwind classes that render unstyled): scheduler status card with stamp, connections table, add-connection form — preserve every form field name/action exactly |

## 6. QA checklist (reviewer)

1. Render check: `bash start_server.sh` in background (port 5000), then
   curl `/`, `/sprints`, `/pricing`, `/auth/login` and any route that
   renders without DB. DB-dependent pages may 503 if Supabase is down —
   for those, template-sanity-check the Jinja directly instead.
2. Integrity greps: `csrf_token` count unchanged per form file; no
   leftover old hexes (#C96442|#FAF9F5|#F7ECE6|#3F7A4E|#B1574F|#A97B22|
   #1A1917|#CBE0CB|#EBD5C9|#E3B7B0|#FBE9E7) anywhere in templates/;
   `id="gen-banner"`, `data-copy-proposal`, `showDayTab`, rubric
   `data-*` attributes all still present.
3. HTML parse: rendered pages parse with Python's html.parser without
   errors (quick script).
4. Responsive spot-check at 390/768/1280 via CSS review (no horizontal
   overflow: punchcard shrinks, grids collapse).
5. Accessibility: focus-visible present; black-on-orange buttons;
   reduced-motion kill switch; table headers mono but ≥11px.
6. Consistency: same radius/shadow/type everywhere; no mixed font stack;
   eyebrows uniform.
Report: findings list with file:line, severity, and concrete fix
suggestion. Fix nothing yourself — report only.
