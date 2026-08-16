import { useCurrentFrame, interpolate, Easing, Audio } from "remotion";

/**
 * TwoPanelLesson — data-driven "TwoPanel HTML preview — kinetic text + TTS"
 * composition (docs/decisions.md D8, engineering-spec §J4).
 *
 * Input props (set by the Flask day view from sprint_days.action_payload.lesson):
 *   { title, script, key_points: string[], voiceover: { url, duration_seconds } }
 *
 * The video is pure SVG + <Audio> — played in-browser by the pre-built
 * @remotion/player bundle (static/video/lesson-player.js). No MP4 is rendered;
 * duration = voiceover duration (frames at 30fps, min 300 so a missing audio
 * never renders a zero-length player).
 */

const FPS = 30;

export const TwoPanelLesson = ({
  title = "Lesson",
  script = "",
  key_points = [],
  voiceover = { url: null, duration_seconds: 20 },
}) => {
  const frame = useCurrentFrame();
  const durationFrames = Math.max(300, Math.round((voiceover?.duration_seconds || 20) * FPS));
  const progress = Math.min(1, frame / durationFrames);

  const sentences = String(script || "")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

  // Left panel: title + kinetic script words; right panel: key points.
  const words = String(title || "").split(" ");
  const scriptWords = sentences.length ? sentences.join(" ").split(" ") : [];

  // Reveal pacing across the whole duration.
  const titleDone = interpolate(frame, [0, 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scriptStart = 45;
  const scriptDur = Math.max(1, durationFrames * 0.55);
  const scriptVisible = Math.floor(((frame - scriptStart) / scriptDur) * scriptWords.length);
  const pointsStart = Math.floor(durationFrames * 0.5);
  const pointsDur = Math.max(1, durationFrames * 0.4);
  const pointsVisible = Math.floor(((frame - pointsStart) / pointsDur) * key_points.length);

  const activePoint = Math.min(key_points.length - 1, Math.max(0, pointsVisible - 1));

  const C = {
    bg: "#0f172a",
    panel: "#1e293b",
    text: "#e8e5de",
    muted: "#94a3b8",
    accent: "#f59e0b",
    ring: "#38bdf8",
  };

  return (
    <div style={{ width: 1920, height: 1080, background: C.bg, color: C.text, fontFamily: "system-ui, sans-serif", display: "flex", overflow: "hidden" }}>
      {voiceover?.url && <Audio src={voiceover.url} />}

      {/* Left panel — kinetic script */}
      <div style={{ flex: 1, padding: 80, display: "flex", flexDirection: "column", gap: 30 }}>
        <div style={{ fontSize: 58, fontWeight: 700, opacity: titleDone, transform: `translateY(${(1 - titleDone) * 24}px)` }}>
          {title}
        </div>
        <div style={{ fontSize: 34, lineHeight: 1.5, color: C.muted, flex: 1 }}>
          {scriptWords.slice(0, Math.max(0, scriptVisible)).join(" ")}
          {scriptVisible < scriptWords.length && <span style={{ opacity: 0.4 }}>▍</span>}
        </div>
      </div>

      {/* Right panel — key points with speaking ring */}
      <div style={{ width: 640, borderLeft: "1px solid rgba(255,255,255,0.08)", padding: 80, display: "flex", flexDirection: "column", gap: 22 }}>
        <div style={{ fontSize: 30, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>Key points</div>
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
            }}>
              <span style={{ color: speaking ? C.ring : C.accent, marginRight: 12 }}>{speaking ? "●" : dimmed ? "✓" : "○"}</span>
              {kp}
            </div>
          );
        })}
      </div>

      {/* Bottom progress bar */}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 8, background: "rgba(255,255,255,0.06)" }}>
        <div style={{ width: `${progress * 100}%`, height: 8, background: C.ring, transition: "none" }} />
      </div>
      <div style={{ position: "absolute", right: 40, bottom: 28, fontSize: 24, color: C.muted }}>
        {Math.round(progress * 100)}%
      </div>
    </div>
  );
};
