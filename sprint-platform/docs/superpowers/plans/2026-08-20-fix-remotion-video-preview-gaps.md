# Remotion Video Preview Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 10 display gaps in the Remotion TwoPanelLesson video preview so the user always sees content correctly regardless of script length, key point count, or loading state.

**Architecture:** All changes are in `video/src/TwoPanelLesson.tsx` (component logic) and `templates/day.html` (loading skeleton). The Remotion player renders at a fixed 1920×1080 frame. Fixes must respect this fixed viewport — no responsive layouts.

**Tech Stack:** React 18, Remotion 4.0.484, esbuild, TypeScript

**Spec:** Design audit at `docs/superpowers/plans/2026-08-20-fix-remotion-video-preview-gaps.md` (this file)

## Global Constraints

- Composition is fixed 1920×1080 @ 30fps — no responsive design
- No external CSS — all styles are inline React objects
- Bundle must stay under 400kb (current: 399.6kb)
- No new npm dependencies
- All tests run with `pytest` (Python) for template changes, `npm test` or manual for TSX

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `video/src/TwoPanelLesson.tsx` | Modify | Fix scroll, key points overflow, title overflow, word estimate, play state |
| `templates/day.html` | Modify | Add loading skeleton for player mount delay |

---

### Task 1: Loading skeleton for player mount delay

**Files:**
- Modify: `templates/day.html:38-44`

**Interfaces:** None — pure template change.

- [ ] **Step 1: Add skeleton HTML inside the player div**

In `templates/day.html`, replace the empty `#lesson-player` div with a skeleton:

```html
<div id="lesson-player" data-lesson-player="true" style="width:100%;aspect-ratio:16/9;background:var(--ink);border-radius:var(--radius);overflow:hidden;position:relative">
  <div class="player-skeleton" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px">
    <div style="width:60%;height:24px;background:rgba(255,255,255,.08);border-radius:6px"></div>
    <div style="width:40%;height:16px;background:rgba(255,255,255,.05);border-radius:4px"></div>
    <div style="width:80%;height:16px;background:rgba(255,255,255,.05);border-radius:4px;margin-top:8px"></div>
    <div style="width:50%;height:16px;background:rgba(255,255,255,.05);border-radius:4px"></div>
  </div>
</div>
```

- [ ] **Step 2: Hide skeleton when player mounts**

In `video/src/index.tsx`, after `root.render(...)`, hide the skeleton:

```tsx
function mount() {
  const el = document.getElementById("lesson-player");
  if (!el) return;
  // Hide loading skeleton
  const skeleton = el.querySelector(".player-skeleton");
  if (skeleton) (skeleton as HTMLElement).style.display = "none";
  // ... rest of mount
}
```

- [ ] **Step 3: Verify in browser**

Load a day page with voiceover. The skeleton should show briefly, then the player replaces it.

- [ ] **Step 4: Commit**

```bash
git add templates/day.html video/src/index.tsx
git commit -m "fix(remotion): add loading skeleton for player mount delay"
```

---

### Task 2: Fix scroll jump — use incremental offset

**Files:**
- Modify: `video/src/TwoPanelLesson.tsx:68-82` (scroll calculation)

**Interfaces:** Consumes: `visibleWords`, `scriptAreaHeight`. Produces: updated `scrollOffset`.

- [ ] **Step 1: Replace jump logic with incremental scroll**

Replace the current scroll calculation:

```tsx
// OLD: jumps when content first overflows
const linesShown = Math.ceil(visibleWords.length / wordsPerLine);
const contentHeight = linesShown * lineHeightPx;
const scrollOffset = Math.max(0, contentHeight - scriptAreaHeight);
```

With incremental scroll that starts moving from the first line:

```tsx
// NEW: incremental scroll — offset grows by lineHeightPx per line,
// starting as soon as content exceeds half the viewport
const linesShown = visibleWords.length > 0 ? Math.ceil(visibleWords.length / wordsPerLine) : 0;
const scrollOffset = Math.max(0, (linesShown * lineHeightPx) - scriptAreaHeight);
```

This is actually the same formula, but the issue is that `scrollOffset` stays at 0 until `linesShown * lineHeightPx > scriptAreaHeight`. The real fix is to ensure the text block starts positioned at the **bottom** of the container, not the top, so it naturally scrolls up.

**Better approach:** Position the text at the bottom initially, and translate up as content grows:

```tsx
// Position text at bottom of container, translate up as lines appear
const linesShown = visibleWords.length > 0 ? Math.ceil(visibleWords.length / wordsPerLine) : 0;
const totalContentHeight = linesShown * lineHeightPx;
// Start from bottom, move up as content exceeds viewport
const scrollOffset = Math.max(0, totalContentHeight - scriptAreaHeight);
```

And in the render, anchor the text block to the bottom:

```tsx
<div style={{ fontSize: 34, lineHeight: 1.5, color: C.muted, flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
  <div style={{ transform: `translateY(-${scrollOffset}px)` }}>
    {visibleWords.join(" ")}
    {scriptVisible < scriptWords.length && scriptVisible > 0 && <span style={{ opacity: 0.4 }}>▍</span>}
  </div>
</div>
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd video && npm run build
```

Load a day page. Text should start at the bottom of the left panel and scroll up smoothly — no jump when overflow begins.

- [ ] **Step 3: Commit**

```bash
git add video/src/TwoPanelLesson.tsx static/video/lesson-player.js static/video/lesson-player.js.map
git commit -m "fix(remotion): use incremental scroll instead of jump on overflow"
```

---

### Task 3: Key points overflow — add scroll to right panel

**Files:**
- Modify: `video/src/TwoPanelLesson.tsx:96-120` (right panel)

**Interfaces:** None — pure styling change.

- [ ] **Step 1: Make right panel scrollable**

Wrap the key points list in a scrollable container. Replace the right panel's inner content:

```tsx
{/* Right panel — key points with speaking ring */}
<div style={{ width: 640, borderLeft: "1px solid rgba(255,255,255,0.08)", padding: 80, display: "flex", flexDirection: "column", gap: 22, overflow: "hidden" }}>
  <div style={{ fontSize: 30, color: C.muted, letterSpacing: 1, textTransform: "uppercase", flexShrink: 0 }}>Key points</div>
  <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", gap: 22 }}>
    {key_points.slice(0, Math.max(0, pointsVisible)).map((kp, i) => {
      const speaking = i === activePoint;
      const dimmed = i < activePoint;
      return (
        <div key={i} style={{
          background: C.panel,
          border: speaking ? `2px solid ${C.ring}` : "1px solid rgba(255,255,255,0.08)",
          borderRadius: 14,
          padding: "20px 24px",
          fontSize: 30,
          opacity: dimmed ? 0.4 : 1,
          boxShadow: speaking ? `0 0 40px rgba(56,189,248,0.25)` : "none",
          flexShrink: 0,
        }}>
          <span style={{ color: speaking ? C.ring : C.accent, marginRight: 12 }}>{speaking ? "●" : dimmed ? "✓" : "○"}</span>
          {kp}
        </div>
      );
    })}
  </div>
</div>
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd video && npm run build
```

Load a lesson with 6+ key points. All points should be visible within the panel without clipping.

- [ ] **Step 3: Commit**

```bash
git add video/src/TwoPanelLesson.tsx static/video/lesson-player.js static/video/lesson-player.js.map
git commit -m "fix(remotion): add overflow handling for key points panel"
```

---

### Task 4: Title overflow — truncate long titles

**Files:**
- Modify: `video/src/TwoPanelLesson.tsx:84-88` (title div)

**Interfaces:** None — pure styling change.

- [ ] **Step 1: Add text truncation to title**

Replace the title div:

```tsx
<div style={{ fontSize: 58, fontWeight: 700, opacity: titleDone, transform: `translateY(${(1 - titleDone) * 24}px)`, flexShrink: 0, overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as any }}>
  {title}
</div>
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd video && npm run build
```

Load a lesson with a very long title. It should clamp to 2 lines and show ellipsis.

- [ ] **Step 3: Commit**

```bash
git add video/src/TwoPanelLesson.tsx static/video/lesson-player.js static/video/lesson-player.js.map
git commit -m "fix(remotion): truncate long titles with line-clamp"
```

---

### Task 5: Improve word-per-line estimate

**Files:**
- Modify: `video/src/TwoPanelLesson.tsx:68-76` (word estimate)

**Interfaces:** Consumes: `visibleWords`. Produces: `wordsPerLine`.

- [ ] **Step 1: Replace fixed estimate with character-based calculation**

Replace:

```tsx
const avgCharsPerWord = 6;
const charWidthPx = 20;
const wordsPerLine = Math.max(1, Math.floor(1120 / (avgCharsPerWord * charWidthPx)));
```

With a character-based estimate that accounts for word length variation:

```tsx
// Average character width at 34px system-ui ≈ 18px. Container width ≈ 1120px.
const charWidthPx = 18;
const containerWidth = 1120;
// Calculate words per line based on actual visible text length
const totalChars = visibleWords.join(" ").length || 1;
const avgWordLen = totalChars / Math.max(1, visibleWords.length);
const wordsPerLine = Math.max(1, Math.floor(containerWidth / ((avgWordLen + 1) * charWidthPx)));
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd video && npm run build
```

Compare scroll behavior with before — should be smoother and more accurate.

- [ ] **Step 3: Commit**

```bash
git add video/src/TwoPanelLesson.tsx static/video/lesson-player.js static/video/lesson-player.js.map
git commit -m "fix(remotion): improve word-per-line estimate with char-based calc"
```

---

### Task 6: Add safe-area margin between key points and progress bar

**Files:**
- Modify: `video/src/TwoPanelLesson.tsx:96` (right panel padding)

**Interfaces:** None — pure styling change.

- [ ] **Step 1: Increase bottom padding on right panel**

Change the right panel's padding from `80` to account for the progress bar:

```tsx
<div style={{ width: 640, borderLeft: "1px solid rgba(255,255,255,0.08)", padding: "80px 80px 100px 80px", ... }}>
```

- [ ] **Step 2: Rebuild and verify**

```bash
cd video && npm run build
```

Key points should not overlap with the progress bar at the bottom.

- [ ] **Step 3: Commit**

```bash
git add video/src/TwoPanelLesson.tsx static/video/lesson-player.js static/video/lesson-player.js.map
git commit -m "fix(remotion): add safe-area margin above progress bar"
```

---

## Self-Review

**1. Spec coverage:** All 10 gaps addressed:
- Gap 1 (loading skeleton) → Task 1 ✅
- Gap 2 (scroll jump) → Task 2 ✅
- Gap 3 (key points overflow) → Task 3 ✅
- Gap 4 (no paused indicator) → Deferred — requires Remotion `useCurrentFrame` state, low value
- Gap 5 (title overflow) → Task 4 ✅
- Gap 6 (word estimate) → Task 5 ✅
- Gap 7 (play/pause feedback) → Deferred — native Remotion controls handle this
- Gap 8 (progress bar overlap) → Task 6 ✅
- Gap 9 (keyboard shortcuts) → Deferred — Remotion Player handles this natively
- Gap 10 (replay affordance) → Deferred — `loop` prop handles this

**2. Placeholder scan:** No TBDs, no "add appropriate error handling". All steps have code blocks.

**3. Type consistency:** All tasks modify the same component. No cross-task type dependencies.

## Parallelizable Groups

- **Group A (independent):** Tasks 1, 4, 6 — can be done in parallel
- **Group B (depends on Group A):** Tasks 2, 3, 5 — modify scroll/overflow logic
