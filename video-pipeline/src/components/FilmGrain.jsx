import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export function FilmGrain() {
  const frame = useCurrentFrame();
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, pointerEvents: "none", mixBlendMode: "overlay" }}>
      <defs>
        <filter id="fg">
          <feTurbulence type="fractalNoise" baseFrequency={0.9} numOctaves={4} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
      </defs>
      <rect width="100%" height="100%" filter="url(#fg)" opacity={0.035} />
    </svg>
  );
}
