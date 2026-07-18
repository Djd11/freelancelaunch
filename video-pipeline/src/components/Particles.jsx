import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";

/**
 * Floating particle system for depth and life.
 * Particles drift slowly upward with subtle horizontal sway.
 */
export function Particles({ count = 40, color = "#ffffff", opacity: baseOpacity }) {
  const frame = useCurrentFrame();

  const particles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        // Deterministic "random" using index as seed
        const seed = (i * 7919 + 104729) % 100000;
        const rand = (offset) => ((seed + offset * 13) % 1000) / 1000;
        return {
          x: rand(0) * 1920,
          y: rand(1) * 1080,
          size: 0.6 + rand(2) * 1.8,
          speed: 0.08 + rand(3) * 0.25,
          swayAmp: 8 + rand(4) * 20,
          swayFreq: 0.003 + rand(5) * 0.006,
          opacity: (baseOpacity ?? (0.06 + rand(6) * 0.15)),
          phase: rand(7) * Math.PI * 2,
        };
      }),
    [count, baseOpacity],
  );

  return (
    <svg
      width="100%"
      height="100%"
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      {particles.map((p, i) => {
        const cx = p.x + Math.sin(frame * p.swayFreq + p.phase) * p.swayAmp;
        const cy = ((p.y - frame * p.speed) % (1080 + 20)) - 10;
        const wrapped = cy < -10 ? cy + 1080 + 20 : cy;
        return (
          <circle
            key={i}
            cx={cx}
            cy={wrapped}
            r={p.size}
            fill={color}
            opacity={p.opacity}
          />
        );
      })}
    </svg>
  );
}
