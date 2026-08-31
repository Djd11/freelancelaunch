import { createRoot } from "react-dom/client";
import { Player } from "@remotion/player";
import { TwoPanelLesson } from "./TwoPanelLesson";

/**
 * Pre-built browser bundle (static/video/lesson-player.js) — mounted by the
 * Flask day view. The template sets window.__LESSON_PROPS__ with the day's
 * lesson (title/script/key_points/voiceover) and this root renders the
 * @remotion/player <Player> around the TwoPanelLesson composition. Pure
 * JS playback — no MP4 (docs/decisions.md D8).
 */

type LessonProps = {
  title?: string;
  script?: string;
  key_points?: string[];
  voiceover?: { url?: string; duration_seconds?: number };
  /* Redesign (Trades Desk 4-scene): engagement fields already passed by the
     day view; now consumed by HOOK/LESSON scenes. All optional — old payloads
     keep working through the composition's per-scene fallbacks. */
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

function mount() {
  const el = document.getElementById("lesson-player");
  if (!el) return;
  // Hide loading skeleton — player is about to render
  const skeleton = el.querySelector(".player-skeleton") as HTMLElement | null;
  if (skeleton) skeleton.style.display = "none";
  const props: LessonProps = (window as any).__LESSON_PROPS__ || {};
  const duration = Math.max(10, props.voiceover?.duration_seconds || 20);
  const root = createRoot(el);
  root.render(
    <Player
      component={TwoPanelLesson}
      inputProps={props as any}
      durationInFrames={Math.round(duration * 30)}
      compositionWidth={1920}
      compositionHeight={1080}
      fps={30}
      controls
      autoPlay
      loop
      style={{ width: "100%", height: "100%" }}
    />
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
