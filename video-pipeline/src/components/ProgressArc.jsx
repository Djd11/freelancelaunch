import React from "react";
import { useCurrentFrame } from "remotion";

export function ProgressArc({ totalFrames = 3924, currentPhase = { emoji: "📡", color: "#00ff87" } }) {
  const frame = useCurrentFrame();
  const pct = Math.round((frame / totalFrames) * 100);
  const cx = 1880, cy = 1030, r = 38, circ = 2 * Math.PI * r;

  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e1e2e" strokeWidth={5} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={currentPhase.color} strokeWidth={5}
        strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - frame / totalFrames)}
        transform={`rotate(-90 ${cx} ${cy})`}
      />
      <text x={cx} y={cy - 8} textAnchor="middle" dominantBaseline="central" fontSize={16}>
        {currentPhase.emoji}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" dominantBaseline="central"
        fill="#888" fontSize={11} fontWeight={600} fontFamily="'Segoe UI', sans-serif"
      >{pct}%</text>
    </g>
  );
}
