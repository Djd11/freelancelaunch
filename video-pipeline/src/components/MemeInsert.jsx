import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Quick meme / reaction insert between scenes.
 * Scales in with spring physics, holds, then scales out.
 */
export function MemeInsert({ memeId, duration = 75 }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const memes = {
    "database-down":  "memes/database-down.svg",
    "its-fine":       "memes/its-fine.svg",
    "stonks":         "memes/stonks.svg",
    "this-fine":      "memes/this-fine.svg",
    "mind-blown":     "memes/mind-blown.svg",
    "surprised":      "memes/surprised.svg",
    "confused":       "memes/confused.svg",
    "nod":            "memes/nod.svg",
  };

  const src = memes[memeId] || memes["nod"];

  // Spring in
  const scaleIn = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 180 },
  });

  // Fade out in last 10 frames
  const fadeOut = interpolate(frame, [duration - 10, duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Subtle float
  const floatY = Math.sin(frame * 0.08) * 3;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0B0F19",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      {/* Glow behind image */}
      <div
        style={{
          position: "absolute",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(56,189,248,0.12) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />
      <Img
        src={staticFile(src)}
        style={{
          maxWidth: "55%",
          maxHeight: "55%",
          transform: `scale(${scaleIn}) translateY(${floatY}px)`,
          opacity: fadeOut,
          borderRadius: 16,
          boxShadow: "0 12px 48px rgba(0,0,0,0.6)",
          border: "2px solid rgba(255,255,255,0.08)",
        }}
      />
    </AbsoluteFill>
  );
}
