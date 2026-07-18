import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

/**
 * Subtitle track — shows word-by-word synced text at bottom of screen.
 * Accepts an array of { text, startFrame, endFrame } segments.
 */
export function Subtitles({ segments = [], color = "#4ECDC4" }) {
  const frame = useCurrentFrame();

  const current = segments.find(
    (s) => frame >= s.startFrame && frame < s.endFrame,
  );

  if (!current) return null;

  // Fade in/out
  const fadeIn = interpolate(
    frame,
    [current.startFrame, current.startFrame + 4],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const fadeOut = interpolate(
    frame,
    [current.endFrame - 4, current.endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 50,
        left: "50%",
        transform: "translateX(-50%)",
        opacity,
        zIndex: 50,
      }}
    >
      <div
        style={{
          background: "rgba(0,0,0,0.75)",
          backdropFilter: "blur(8px)",
          padding: "10px 28px",
          borderRadius: 10,
          border: `1px solid ${color}33`,
          maxWidth: "75%",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: 26,
            fontWeight: 600,
            color: "#f1f5f9",
            fontFamily: "'Inter', 'Segoe UI', sans-serif",
            lineHeight: 1.4,
            letterSpacing: "-0.01em",
          }}
        >
          {current.text}
        </span>
      </div>
    </div>
  );
}
