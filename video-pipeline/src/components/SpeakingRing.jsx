import React from "react";
import { useCurrentFrame } from "remotion";

export function SpeakingRing({ color = "#00ff87" }) {
  const frame = useCurrentFrame();
  const c = 1880, r = 48, dashLen = 30, perimeter = 2 * Math.PI * r;
  const offset = -((frame * 8) % perimeter);
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <circle cx={c} cy={80} r={r} fill="none" stroke="#1e1e2e" strokeWidth={3} />
      <circle cx={c} cy={80} r={r} fill="none" stroke={color} strokeWidth={2}
        strokeDasharray={`${dashLen} ${perimeter - dashLen}`}
        strokeDashoffset={offset} strokeLinecap="round"
      />
    </svg>
  );
}
