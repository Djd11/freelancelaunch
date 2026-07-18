import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

/**
 * Scene transition effects — zoom, glitch, wipe, fade, slide.
 * Renders over the scene during transition frames.
 */
export function SceneTransition({ type = "zoom", duration = 12, color = "#0B0F19" }) {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Reverse: 1 at start, 0 at end
  const fade = 1 - progress;

  switch (type) {
    case "zoom":
      return (
        <AbsoluteFill
          style={{
            transform: `scale(${1 + progress * 3})`,
            opacity: fade,
            backgroundColor: color,
          }}
        />
      );

    case "glitch":
      const glitchX = Math.sin(frame * 2.5) * 15 * fade;
      const glitchX2 = Math.cos(frame * 3.1) * 10 * fade;
      return (
        <AbsoluteFill style={{ opacity: fade }}>
          {/* RGB split */}
          <AbsoluteFill
            style={{
              backgroundColor: "rgba(255,0,0,0.08)",
              mixBlendMode: "screen",
              transform: `translateX(${glitchX}px)`,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: "rgba(0,255,0,0.06)",
              mixBlendMode: "screen",
              transform: `translateX(${glitchX2}px)`,
            }}
          />
          <AbsoluteFill
            style={{
              backgroundColor: "rgba(0,100,255,0.06)",
              mixBlendMode: "screen",
              transform: `translateX(${-glitchX}px)`,
            }}
          />
          {/* Scan lines */}
          {frame % 3 === 0 && (
            <div
              style={{
                position: "absolute",
                top: `${(frame * 37) % 100}%`,
                left: 0,
                right: 0,
                height: 2,
                backgroundColor: "rgba(255,255,255,0.15)",
              }}
            />
          )}
        </AbsoluteFill>
      );

    case "wipe":
      return (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: color,
            clipPath: `inset(0 ${(1 - progress) * 100}% 0 0)`,
          }}
        />
      );

    case "slide":
      return (
        <AbsoluteFill
          style={{
            transform: `translateX(${(1 - progress) * 100}%)`,
            backgroundColor: color,
          }}
        />
      );

    case "fade":
    default:
      return (
        <AbsoluteFill
          style={{
            opacity: fade,
            backgroundColor: color,
          }}
        />
      );
  }
}
