import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { PANELS, PHASES, TOTAL_FRAMES, getCurrentPhase } from "./PanelContent.js";
import { FilmGrain } from "./components/FilmGrain.jsx";
import { Particles } from "./components/Particles.jsx";
import { Subtitles } from "./components/Subtitles.jsx";

// Layout - Full screen kinetic text
const TEXT_W = 1500;
const TEXT_CENTER_Y = 430;

// ── Main ──
export function TwoPanelStack() {
  const frame = useCurrentFrame();
  const { phase: curPhase, index: idx } = getCurrentPhase(frame);
  const panel = PANELS[idx];

  // ── Enhanced camera zoom with drift ──
  const zoomPulse = useMemo(() => {
    let pulse = 1;
    let driftX = 0;
    let driftY = 0;
    for (const p of PHASES) {
      if (frame >= p.start - 10 && frame < p.start + 20) {
        const t = (frame - (p.start - 10)) / 30;
        pulse = 1 + Math.sin(t * Math.PI) * 0.04 * (1 - t);
        driftX = Math.sin(t * Math.PI) * 3;
        driftY = Math.cos(t * Math.PI) * 2;
        break;
      }
    }
    const cinematicZoom = 1 + frame * 0.00003;
    return { scale: pulse * cinematicZoom, driftX, driftY };
  }, [frame]);

  // ── Subtitle segments from current panel ──
  const subtitleSegments = useMemo(() => {
    if (!panel.words) return [];
    const words = panel.words.split(" ");
    const segs = [];
    const segSize = 8; // words per subtitle segment
    const totalTokens = words.length;
    const perWord = Math.max(3, Math.floor((curPhase.duration - 15) / totalTokens));
    const capStart = curPhase.start + 15;
    for (let i = 0; i < words.length; i += segSize) {
      const chunk = words.slice(i, i + segSize).join(" ");
      const startFrame = capStart + i * perWord;
      const endFrame = capStart + Math.min(i + segSize, words.length) * perWord;
      segs.push({ text: chunk, startFrame, endFrame });
    }
    return segs;
  }, [panel, curPhase]);

  return (
    <AbsoluteFill style={{ backgroundColor: "#0B0F19", fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Drifting grid */}
      <svg width="100%" height="100%" style={{ position: "absolute", opacity: 0.03 }}>
        <defs>
          <pattern id="dg" width={60} height={60} patternUnits="userSpaceOnUse"
            patternTransform={`translate(${(frame * 0.05) % 60}, ${(frame * 0.05) % 60})`}>
            <line x1={60} y1={0} x2={60} y2={60} stroke="#fff" strokeWidth={0.5} />
            <line x1={0} y1={60} x2={60} y2={60} stroke="#fff" strokeWidth={0.5} />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dg)" />
      </svg>

      {/* Light leaks */}
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <radialGradient id="lk1" cx="30%" cy="30%" r="60%">
            <stop offset="0%" stopColor={panel.color} stopOpacity={0.09} />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <radialGradient id="lk2" cx="70%" cy="70%" r="50%">
            <stop offset="0%" stopColor="#6c5ce7" stopOpacity={0.06} />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#lk1)" />
        <rect width="100%" height="100%" fill="url(#lk2)" />
      </svg>

      {/* Floating particles for depth */}
      <Particles count={35} color={panel.color} opacity={0.07} />

      {/* Voice over audio */}
      <Audio src={staticFile("audio/narration.mp3")} volume={0.9} />

      {/* Kinetic text centered */}
      <AbsoluteFill style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        transform: `scale(${zoomPulse.scale}) translate(${zoomPulse.driftX}px, ${zoomPulse.driftY}px)`,
      }}>
        <Subtitles segments={subtitleSegments} color={panel.color} />
      </AbsoluteFill>

      <FilmGrain />
    </AbsoluteFill>
  );
}
