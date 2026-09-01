import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
  Audio,
  AbsoluteFill,
} from "remotion";

/**
 * TwoPanelLesson — the 4-scene "Trades Desk" lesson video.
 * (docs/decisions.md D8, engineering-spec §J4; redesign per the approved
 *  mock docs/mockups/video-preview-redesign-mock.html — all five ★ choices:
 *  Light variant, karaoke transcript, hand-drawn underlines, live waveform,
 *  punch-card outro.)
 *
 * Input props (set by the Flask day view from sprint_days.action_payload.lesson
 * via window.__LESSON_PROPS__):
 *   { title, script, key_points: string[], voiceover: {url, duration_seconds},
 *     hook?, day_overview?, usefulness_context?, pre_quiz?,
 *     day_no?, phase?, action?, days_done?, total_days? }
 *
 * Pure SVG + <Audio>, played in-browser by the pre-built @remotion/player
 * bundle (static/video/lesson-player.js). No MP4; duration = voiceover
 * duration at 30fps, min 300 frames. Older payloads without hook/day_overview
 * still render: every scene has a fallback, and no empty placeholder blocks
 * are ever shown.
 *
 * FONTS: Barlow / Barlow Condensed / IBM Plex Mono are loaded by the host
 * day page (templates/base.html) — referenced via font-family stack only.
 *
 * WAVEFORM: the bottom strip is DECORATIVE — a deterministic sine/noise mix
 * driven by frame (matches the approved mock). No audio decoding.
 */

const FPS = 30;
const MIN_FRAMES = 300;

/** Strip markdown formatting from script text for clean video rendering. */
function stripMarkdown(text: string): string {
  if (!text) return "";
  let t = text
    .replace(/\*\*(.+?)\*\*/g, "$1") // **bold** → bold
    .replace(/^\d+\.\s+/gm, "") // 1. Step → Step
    .replace(/^[-*]\s+/gm, "") // - item → item
    .replace(/\n{3,}/g, "\n\n") // collapse blank lines
    .trim();
  return t;
}

const firstSentence = (text: string): string => {
  const clean = stripMarkdown(text || "");
  if (!clean) return "";
  const m = clean.match(/^[^.!?]*[.!?]/);
  return (m ? m[0] : clean).trim();
};

/** "The Trades Desk" light tokens — mirror of the mock :root (exact hexes). */
const C = {
  /* ByteMonk dark studio (2026-09-01): near-black ground measured from their
     thumbnails (#050505–#14091A, ~75% dark); one saturated accent — their
     #E65509 is a near-twin of our safety orange, so the orange stays. */
  bg: "#0A0A0B",
  surface: "#16181C",
  surface2: "#1E2126",
  ink: "#F2F4F1",
  ink2: "#D7DCD8",
  muted: "#9BA39C",
  hairline: "#39424A",
  hairline2: "#4A545D",
  accent: "#D95B08",
  accentInk: "#F08A47",
  accentSoft: "#2A170B",
  green: "#4C9A5E",
  greenInk: "#7FCB90",
  greenSoft: "#1B2E20",
};

const FONT = {
  cond: '"Barlow Condensed","Arial Narrow",sans-serif',
  body: '"Barlow",-apple-system,"Segoe UI",sans-serif',
  mono: '"IBM Plex Mono",ui-monospace,"SF Mono",monospace',
};

type LessonProps = {
  title?: string;
  script?: string;
  key_points?: string[];
  voiceover?: { url?: string; duration_seconds?: number };
  hook?: string;
  day_overview?: string[];
  usefulness_context?: string;
  pre_quiz?: unknown;
  day_no?: number;
  phase?: string;
  action?: string;
  days_done?: number;
  total_days?: number;
};

const mono = (size: number, weight = 500): React.CSSProperties => ({
  fontFamily: FONT.mono,
  fontSize: size,
  fontWeight: weight,
});

const pad2 = (n: number) => String(n).padStart(2, "0");

/** t4 blocker #2: length-based headline clamp. ≤10 words (mock demo) → 88px;
 *  real 15-22-word hooks scale down to fit the scene, floor 52px. */
const clampHeadline = (wordCount: number): number => {
  if (wordCount <= 10) return 88;
  if (wordCount <= 14) return 74;
  if (wordCount <= 18) return 64;
  return 56;
};

/** Spring entrance (overshoot via damping 12) — never linear-only. */
const springIn = (frame: number, from: number) =>
  spring({ frame: frame - from, fps: FPS, config: { damping: 12, mass: 1 } });

/** Hand-drawn marker underline: wavy SVG path drawn on via dashoffset.
 *  Path coordinates live in a 0–100 viewBox space; preserveAspectRatio
 *  stretches it to the element width. */
const Underline: React.FC<{
  progress: number;
  width?: number;
  color?: string;
  thickness?: number;
  seed?: number;
}> = ({ progress, width = 120, color = C.accent, thickness = 5, seed = 1 }) => {
  const wob = (i: number) => Math.sin(seed * 7.3 + i * 1.7) * 2.2;
  const d = `M 0 ${9 + wob(0)}` +
    ` C 18 ${6 + wob(1)}, 34 ${12 + wob(2)}, 52 ${9 + wob(3)}` +
    ` S 80 ${5 + wob(4)}, 100 ${8 + wob(5)}`;
  return (
    <svg
      width={width}
      height={18}
      viewBox="0 0 100 18"
      preserveAspectRatio="none"
      style={{ display: "block", overflow: "visible" }}
    >
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth={thickness}
        strokeLinecap="round"
        pathLength={100}
        strokeDasharray={100}
        strokeDashoffset={100 - Math.max(0, Math.min(1, progress)) * 100}
      />
    </svg>
  );
};

export const TwoPanelLesson: React.FC<LessonProps> = (props) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const {
    title = "Lesson",
    script = "",
    key_points = [],
    voiceover = { url: null, duration_seconds: 20 },
    hook,
    day_overview,
    usefulness_context,
    day_no,
    phase,
    action,
    days_done,
    total_days = 14,
  } = props;

  const D = Math.max(MIN_FRAMES, durationInFrames);

  // ── Scene split: proportional to duration (never hardcoded seconds) ──
  const hookEnd = Math.max(30, Math.floor(D * 0.125));
  const lessonEnd = Math.floor(D * 0.56);
  const pointsEnd = Math.floor(D * 0.87);

  // ── Text prep ──
  const cleanScript = stripMarkdown(String(script || ""));
  const sentences = cleanScript
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const scriptWords = sentences.length
    ? sentences.join(" ").split(" ").filter(Boolean)
    : [];

  // Karaoke: char-proportional word pacing across the LESSON scene (★2).
  const lessonDur = Math.max(1, lessonEnd - hookEnd);
  const totalChars = scriptWords.join(" ").length || 1;
  const wordStartFrames = (() => {
    let acc = 0;
    return scriptWords.map((w) => {
      const startFrame = Math.floor((acc / totalChars) * lessonDur);
      acc += w.length + 1;
      return startFrame;
    });
  })();

  // ── Captions: sentence-level, only during the LESSON scene ──
  const capForFrame = (() => {
    const rel = frame - hookEnd;
    if (rel < 0 || rel >= lessonDur) return "";
    let acc = 0;
    for (const s of sentences) {
      const startFrame = Math.floor((acc / totalChars) * lessonDur);
      acc += s.length + 1;
      const endFrame = Math.floor((acc / totalChars) * lessonDur);
      if (rel >= startFrame && rel < endFrame) return s;
    }
    return "";
  })();

  // ── OUTRO punch-card facts (★5 — real progress, never faked) ──
  const dayNo = typeof day_no === "number" ? dayNoGuard(day_no) : 1;
  const done =
    typeof days_done === "number"
      ? Math.max(0, Math.min(total_days, days_done))
      : Math.max(0, dayNo - 1);
  const daysToGo = Math.max(0, total_days - dayNo);

  const mm = String(Math.floor(frame / FPS / 60)).padStart(2, "0");
  const ss = String(Math.floor(frame / FPS) % 60).padStart(2, "0");
  const chapterBounds: [number, number][] = [
    [0, hookEnd],
    [hookEnd, lessonEnd],
    [lessonEnd, pointsEnd],
    [pointsEnd, D],
  ];

  return (
    <AbsoluteFill
      style={{ background: C.bg, color: C.ink, fontFamily: FONT.body }}
    >
      {voiceover?.url && <Audio src={voiceover.url} />}

      {/* ══════════ TOP CHROME ══════════ */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "20px 30px",
        }}
      >
        <span
          style={{
            ...mono(12, 600),
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: C.greenInk,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: C.green,
              display: "inline-block",
              opacity: interpolate(frame % 48, [0, 24, 48], [1, 0.35, 1]),
            }}
          />
          Voiceover live
        </span>
        <span style={{ ...mono(12, 500), color: C.muted }}>
          {mm}:{ss}
        </span>
      </div>

      {/* ══════════ SCENE 1 · HOOK ══════════ */}
      <Sequence from={0} durationInFrames={hookEnd}>
        <HookScene
          hook={firstSentence(String(hook || title))}
          eyebrow={
            [
              `Day ${pad2(dayNo)}`,
              phase ? `Shift ${phase}` : "",
              action ? String(action) : "",
            ]
              .filter(Boolean)
              .join(" · ")
          }
          keyPointCount={key_points.length}
          hasVoiceover={Boolean(voiceover?.url)}
          voiceoverDur={voiceover?.duration_seconds}
        />
      </Sequence>

      {/* ══════════ SCENE 2 · LESSON — ByteMonk roadmap (map-not-detail) ══════════ */}
      <Sequence from={hookEnd} durationInFrames={lessonEnd - hookEnd}>
        <LessonScene
          title={String(title)}
          words={scriptWords}
          wordStartFrames={wordStartFrames}
          statSource={String(usefulness_context || "")}
          dayOverview={Array.isArray(day_overview) ? day_overview : []}
        />
      </Sequence>

      {/* ══════════ SCENE 3 · KEY POINTS ══════════ */}
      <Sequence from={lessonEnd} durationInFrames={pointsEnd - lessonEnd}>
        <PointsScene key_points={key_points} />
      </Sequence>

      {/* ══════════ SCENE 4 · OUTRO — punch-card ══════════ */}
      <Sequence from={pointsEnd}>
        <OutroScene dayNo={dayNo} done={done} totalDays={total_days} daysToGo={daysToGo} />
      </Sequence>

      {/* ══════════ BOTTOM CHROME ══════════ */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          padding: "0 30px 18px",
          background: `linear-gradient(transparent, ${C.bg}dd 55%)`,
        }}
      >
        {/* Decorative waveform (deterministic; see file NOTE). Bars grow
            bottom-aligned via scaleY + transformOrigin, so the container
            centers with alignItems:center — no flex-end needed. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 3,
            height: 26,
            marginBottom: 10,
          }}
        >
          {Array.from({ length: 48 }).map((_, i) => {
            const energy = Math.max(
              0.08,
              0.25 +
                0.75 *
                  Math.abs(
                    Math.sin((frame / FPS) * 7 + i * 0.55) *
                      (0.5 + 0.5 * Math.sin((frame / FPS) * 2.1 + i * 0.21))
                  )
              );
            return (
              <div
                key={i}
                style={{
                  flex: 1,
                  maxWidth: 7,
                  height: "100%",
                  background: C.accent,
                  opacity: 0.85,
                  borderRadius: 2,
                  transform: `scaleY(${energy})`,
                  transformOrigin: "bottom",
                }}
              />
            );
          })}
        </div>

        {/* Chapter bar — 4 scenes */}
        <div
          style={{
            display: "flex",
            gap: 4,
            height: 6,
            borderRadius: 3,
            overflow: "hidden",
            background: C.hairline,
            marginBottom: 12,
          }}
        >
          {chapterBounds.map(([a, b], i) => {
            const state = frame >= b ? "done" : frame >= a ? "now" : "future";
            return (
              <div key={i} style={{ flex: 1, position: "relative" }}>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: 3,
                    background:
                      state === "done"
                        ? C.green
                        : state === "now"
                        ? C.accent
                        : "transparent",
                    opacity:
                      state === "now"
                        ? interpolate(frame % 48, [0, 24, 48], [1, 0.5, 1])
                        : 1,
                  }}
                />
              </div>
            );
          })}
        </div>

        {/* Caption chip */}
        <div
          style={{
            minHeight: 44,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          {capForFrame ? (
            <div
              style={{
                fontSize: 19,
                fontWeight: 600,
                color: C.ink,
                background: C.surface,
                border: `1px solid ${C.hairline2}`,
                borderRadius: 8,
                padding: "7px 16px",
                maxWidth: "80%",
                overflow: "hidden",
              }}
            >
              {capForFrame}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const dayNoGuard = (n: number) =>
  Number.isFinite(n) && n > 0 ? Math.min(99, Math.round(n)) : 1;

/* ═══════════════ SCENES ═══════════════ */

/* ── HOOK (★ springs, ★ hand-drawn underline) ── */
const HookScene: React.FC<{
  hook: string;
  eyebrow: string;
  keyPointCount: number;
  hasVoiceover: boolean;
  voiceoverDur?: number;
}> = ({ hook, eyebrow, keyPointCount, hasVoiceover, voiceoverDur }) => {
  const f = useCurrentFrame();
  const words = (hook || "Lesson").split(" ").filter(Boolean);
  const hlIndex = words.length > 2 ? Math.floor(words.length * 0.66) : -1;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 8%",
      }}
    >
      <div
        style={{
          ...mono(14, 600),
          letterSpacing: ".1em",
          textTransform: "uppercase",
          color: C.accentInk,
          marginBottom: 18,
          opacity: springIn(f, 2),
          transform: `translateY(${(1 - springIn(f, 2)) * 12}px)`,
        }}
      >
        {eyebrow}
      </div>
      {/* Length-based font clamp (t4 blocker #2): real hooks run 20+ words —
          88px clips them. Scale down so the longest realistic hook still
          fits the 640px scene area, floor at a still-bold 52px. */}
      <h2
        style={{
          fontFamily: FONT.cond,
          fontSize: clampHeadline(hook ? (hook || "").split(" ").length : 0),
          fontWeight: 700,
          lineHeight: 1.02,
          letterSpacing: "-.01em",
          color: C.ink,
          maxWidth: "15ch",
          margin: 0,
          overflow: "hidden",
        }}
      >
        {words.map((w, i) => {
          const s = springIn(f, 6 + i * 4);
          const isHl = i === hlIndex;
          /* t4 #1: the highlight wrapper CONTAINS the word itself, so the
             underline anchors to the word's own box - left edge under the
             word's first glyph, below the baseline. */
          if (isHl) {
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  position: "relative",
                  opacity: s,
                  transform: `translateY(${(1 - s) * 30}px) scale(${0.96 + s * 0.04})`,
                }}
              >
                {w}
                <span
                  style={{
                    position: "absolute",
                    left: 0,
                    bottom: -8,
                  }}
                >
                  <Underline
                    progress={interpolate(s, [0.4, 1], [0, 1], {
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                    })}
                    width={Math.min(200, Math.max(90, w.length * 16))}
                    thickness={6}
                  />
                </span>
              </span>
            );
          }
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                opacity: s,
                transform: `translateY(${(1 - s) * 30}px) scale(${0.96 + s * 0.04})`,
              }}
            >
              {w}
            </span>
          );
        })}
      </h2>
      <div
        style={{
          marginTop: 26,
          display: "flex",
          gap: 10,
          opacity: springIn(f, 40),
          transform: `translateY(${(1 - springIn(f, 40)) * 10}px)`,
        }}
      >
        {[
          // t4 #7: real estimate from duration (5 min was hardcoded) —
          // shown only when we actually know the length.
          ...(voiceoverDur
            ? [`≈ ${Math.max(1, Math.round(voiceoverDur / 60))} min`]
            : []),
          hasVoiceover ? "Voiceover + transcript" : "Transcript",
          `${keyPointCount} key points`,
        ].map((chip) => (
          <span
            key={chip}
            style={{
              ...mono(12, 600),
              textTransform: "uppercase",
              letterSpacing: ".05em",
              color: C.ink2,
              border: `1px solid ${C.hairline2}`,
              borderRadius: 4,
              padding: "6px 12px",
              background: C.surface,
            }}
          >
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
};

/* ── LESSON — ByteMonk roadmap (map-not-detail, 2026-09-01) ──
   The channel formula: never wall-of-text the content. The middle scene
   shows WHAT you'll learn — day_overview items as numbered journey stops,
   one active at a time, karaoke-synced by stop. The full script stays
   readable on the page below the player (data-lesson-content). */
const LessonScene: React.FC<{
  title: string;
  words: string[];
  wordStartFrames: number[];
  statSource: string;
  dayOverview: string[];
}> = ({ title, words, wordStartFrames, statSource, dayOverview }) => {
  const f = useCurrentFrame(); // scene-relative (Sequence wraps us)

  // Roadmap stops: day_overview when present; fallback = first sentences of
  // the script (2-4 short stops) so legacy payloads still render a map.
  const stops: string[] = (dayOverview && dayOverview.length
    ? dayOverview
    : (() => {
        const clean = words.join(" ");
        const sentences = clean.split(/(?<=[.!?])\s+/).filter(Boolean);
        return sentences.slice(0, 4);
      })()
  )
    .map((s) => String(s).replace(/\*\*/g, "").trim())
    .filter((s) => s.length > 3)
    .slice(0, 6);

  // Stop-sync (char-proportional like the karaoke pacing it replaces):
  const totalChars = stops.join(" ").length || 1;
  const sceneLen = Math.max(1, stops.length * 90 + 30); // approx frames; caller pace
  const visibleStops = (() => {
    let acc = 0; let vis = 0;
    for (const s of stops) {
      const startFrame = Math.floor((acc / totalChars) * (stops.length * 90));
      acc += s.length + 1;
      if (f >= startFrame) vis += 1;
    }
    return vis;
  })();
  const activeStop = Math.max(0, visibleStops - 1);

  // Pinned scroll math (kept from the transcript era): charWidthPx=18 /
  // containerWidth=1120 -> lines -> translateY(-scrollOffset) — now guards
  // the STOPS container when a sprint carries many stops.
  const charWidthPx = 18;
  const containerWidth = 1120;
  const visibleStopText = stops.slice(0, Math.max(1, visibleStops));
  const avgWordLen =
    visibleStopText.length > 0
      ? visibleStopText.join(" ").length /
        visibleStopText.join(" ").split(" ").length
      : 6;
  const wordsPerLine = Math.max(
    1,
    Math.floor(containerWidth / ((avgWordLen + 1) * charWidthPx))
  );
  const lineHeightPx = 96; // stop row height (title 34px + spacing)
  const totalStopWords = visibleStopText.join(" ").split(" ").length;
  const linesShown =
    totalStopWords > 0 ? Math.ceil(totalStopWords / wordsPerLine) : 0;
  const scriptAreaHeight = 1080 - 120 - 90 - 40 - 120;
  const scrollThreshold = scriptAreaHeight * 0.7;
  const scrollOffset = Math.max(0, linesShown * lineHeightPx - scrollThreshold);

  // Stat panel (no fake data): only when usefulness_context carries a number.
  const statLine = firstSentence(statSource);
  const statTokens = statLine
    ? (statLine.match(/[$+≈≈]?\s?\d[\d.,%]*[a-zA-Z+%]?/g) || []).map((s) =>
        s.replace(/\s+/g, "")
      )
    : [];
  const statNum = statTokens.sort((a, b) => b.length - a.length)[0];
  const showStat = Boolean(statLine && statNum);

  if (stops.length === 0) return null; // no empty placeholder blocks

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 8%",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 16,
          marginBottom: 40,
        }}
      >
        <div
          style={{
            fontFamily: FONT.cond,
            fontSize: 34,
            fontWeight: 600,
            color: C.ink,
          }}
        >
          {title}
        </div>
        <span
          style={{
            ...mono(11, 600),
            textTransform: "uppercase",
            letterSpacing: ".07em",
            color: "#5FA5C2",
            border: `1px solid ${C.hairline2}`,
            padding: "3px 9px",
            borderRadius: 4,
            background: C.surface,
          }}
        >
          Today's roadmap
        </span>
      </div>

      {/* The map: numbered stops, one active at a time (ByteMonk formula). */}
      <div
        style={{
          position: "relative",
          maxWidth: "62ch",
          height: 640,
          overflow: "hidden",
        }}
      >
        <div style={{ transform: `translateY(-${scrollOffset}px)` }}>
          {stops.map((stop, i) => {
            const s = springIn(f, 8 + i * 22);
            const isActive = i === activeStop;
            const isDone = i < activeStop;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 26,
                  opacity: s,
                  transform: `translateY(${(1 - s) * 26}px)`,
                  marginBottom: 34,
                }}
              >
                <div
                  style={{
                    ...mono(26, 600),
                    color: isActive ? C.accent : isDone ? C.green : C.muted,
                    minWidth: 64,
                    paddingTop: 2,
                    textShadow: isActive
                      ? `0 0 24px ${C.accent}66`
                      : "none",
                  }}
                >
                  {isDone ? "✓" : pad2(i + 1)}
                </div>
                <div
                  style={{
                    fontFamily: FONT.cond,
                    fontSize: 38,
                    fontWeight: 600,
                    lineHeight: 1.18,
                    color: isActive ? C.ink : isDone ? C.ink2 : C.muted,
                    maxWidth: "48ch",
                  }}
                >
                  {stop}
                  {isActive ? (
                    <span
                      style={{
                        display: "inline-block",
                        marginLeft: 14,
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: C.accent,
                        animation: "none",
                        opacity: interpolate(f % 48, [0, 24, 48], [1, 0.35, 1]),
                      }}
                    />
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {showStat ? (
        <div
          style={{
            position: "absolute",
            right: "7%",
            top: "50%",
            transform: `translateY(-50%) scale(${0.9 + springIn(f, 48) * 0.1})`,
            textAlign: "right",
            opacity: springIn(f, 48),
          }}
        >
          <div
            style={{
              fontFamily: FONT.cond,
              fontSize: 120,
              fontWeight: 700,
              lineHeight: 1,
              color: C.accent,
            }}
          >
            {statNum}
          </div>
          <div
            style={{
              ...mono(12, 500),
              letterSpacing: ".08em",
              textTransform: "uppercase",
              color: C.muted,
              marginTop: 6,
              maxWidth: 260,
            }}
          >
            {statLine}
          </div>
        </div>
      ) : null}
    </div>
  );
};


/* ── KEY POINTS (★ springs stagger, ★ underline draw-on, ✓ punch) ── */
const PointsScene: React.FC<{ key_points: string[] }> = ({ key_points }) => {
  const f = useCurrentFrame(); // scene-relative
  const points = key_points.slice(0, 4);
  const per = 57; // frames between card entrances (≈1.9s)

  if (points.length === 0) return null; // no empty placeholder blocks

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 8%",
      }}
    >
      <div
        style={{
          fontFamily: FONT.cond,
          fontSize: 34,
          fontWeight: 600,
          color: C.ink,
          marginBottom: 8,
          opacity: springIn(f, 3),
          transform: `translateY(${(1 - springIn(f, 3)) * 14}px)`,
        }}
      >
        What separates pros from tinkerers
      </div>
      <div
        style={{
          ...mono(12, 600),
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: C.muted,
          marginBottom: 30,
          opacity: springIn(f, 9),
        }}
      >
        Key points · verified at Gate A
      </div>
      <div style={{ display: "flex", gap: 26 }}>
        {points.map((kp, i) => {
          const s = springIn(f, 16 + i * per);
          const drawn = interpolate(s, [0.5, 1], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const checked = springIn(f, 16 + i * per + 45);
          return (
            <div
              key={i}
              style={{
                flex: 1,
                background: C.surface,
                border: `1.5px solid ${checked > 0.5 ? C.green : C.hairline2}`,
                borderRadius: 14,
                padding: 26,
                position: "relative",
                opacity: s,
                transform: `translateY(${(1 - s) * 44}px) scale(${0.97 + s * 0.03})`,
              }}
            >
              <div
                style={{
                  ...mono(12, 600),
                  color: C.accentInk,
                  letterSpacing: ".08em",
                  marginBottom: 12,
                }}
              >
                KP {pad2(i + 1)}
              </div>
              <div
                style={{
                  fontFamily: FONT.cond,
                  fontSize: 27,
                  fontWeight: 600,
                  color: C.ink,
                  lineHeight: 1.15,
                  display: "inline-block",
                  position: "relative",
                  paddingBottom: 10,
                }}
              >
              {/* t4 #5: strip any residual **bold** markdown from KP titles */}
                {String(kp).replace(/\*\*(.+?)\*\*/g, "$1")}
                <div style={{ position: "absolute", left: 0, bottom: 0 }}>
                  <Underline progress={drawn} width={140} thickness={4.5} seed={i + 2} />
                </div>
              </div>
              <div
                style={{
                  position: "absolute",
                  top: -14,
                  right: -14,
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: C.green,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  fontWeight: 700,
                  opacity: checked,
                  transform: `scale(${0.4 + checked * 0.6}) rotate(${(1 - checked) * -30}deg)`,
                }}
              >
                ✓
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

/* ── OUTRO — stamp + punch-card (★5) ── */
const OutroScene: React.FC<{
  dayNo: number;
  done: number;
  totalDays: number;
  daysToGo: number;
}> = ({ dayNo, done, totalDays, daysToGo }) => {
  const f = useCurrentFrame(); // scene-relative
  const stampS = springIn(f, 3);
  const headS = springIn(f, 12);
  const punchS = springIn(f, 21);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
      }}
    >
      <div
        style={{
          ...mono(13, 600),
          letterSpacing: ".09em",
          textTransform: "uppercase",
          color: C.greenInk,
          border: "2px solid currentColor",
          borderRadius: 5,
          padding: "6px 14px",
          background: C.surface,
          marginBottom: 26,
          opacity: stampS,
          transform: `rotate(-2deg) scale(${0.7 + stampS * 0.3})`,
        }}
      >
        Lesson complete
      </div>
      <h2
        style={{
          fontFamily: FONT.cond,
          fontSize: 56,
          fontWeight: 700,
          color: C.ink,
          margin: 0,
          lineHeight: 1.05,
          opacity: headS,
          transform: `translateY(${(1 - headS) * 18}px)`,
        }}
      >
        Now replicate the flow yourself.
      </h2>
      <div
        style={{
          display: "flex",
          gap: 6,
          marginTop: 34,
          opacity: punchS,
          transform: `translateY(${(1 - punchS) * 14}px)`,
        }}
      >
        {Array.from({ length: totalDays }).map((_, i) => {
          const dayNum = i + 1;
          const isPunched = dayNum <= done;
          const isToday = dayNum === dayNo;
          return (
            <div
              key={i}
              style={{
                width: 46,
                height: 46,
                border: `1.5px ${isPunched || isToday ? "solid" : "dashed"} ${
                  isPunched ? C.green : isToday ? C.accent : C.hairline2
                }`,
                borderRadius: 7,
                position: "relative",
                background: isPunched || isToday ? C.surface : C.surface2,
                fontFamily: FONT.mono,
                fontSize: 12,
                color: isToday ? C.ink : C.muted,
                display: "flex",
                justifyContent: "center",
                paddingTop: 5,
                boxShadow: isToday ? `0 0 0 3px ${C.accentSoft}` : "none",
              }}
            >
              {pad2(dayNum)}
              {isPunched ? (
                <div
                  style={{
                    position: "absolute",
                    left: "50%",
                    top: "60%",
                    width: 15,
                    height: 15,
                    transform: "translate(-50%,-50%)",
                    borderRadius: "50%",
                    background: C.bg,
                    border: `2.5px solid ${C.green}`,
                    boxShadow: "inset 0 1px 2px rgba(0,0,0,.28)",
                  }}
                />
              ) : null}
            </div>
          );
        })}
      </div>
      <div
        style={{
          ...mono(12, 500),
          letterSpacing: ".06em",
          textTransform: "uppercase",
          color: C.muted,
          marginTop: 22,
          opacity: springIn(f, 30),
        }}
      >
        Day {pad2(dayNo)} punched · {daysToGo} days to go
      </div>
    </div>
  );
};
