import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

/**
 * Kinetic Text - Word-by-word animated text synced with voice over.
 * Accepts an array of { text, startFrame, endFrame } segments.
 */
export function Subtitles({ segments = [], color = "#4ECDC4" }) {
  const frame = useCurrentFrame();

  // Find the current segment
  const current = segments.find(
    (s) => frame >= s.startFrame && frame < s.endFrame,
  );

  if (!current) return null;

  // Split text into individual words
  const words = current.text.split(" ");
  const totalWords = words.length;
  const segmentDuration = current.endFrame - current.startFrame;
  const framesPerWord = Math.max(2, segmentDuration / totalWords);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 150,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        textAlign: "center",
        maxWidth: "85%",
      }}
    >
      <div
        style={{
          background: "rgba(0,0,0,0.75)",
          backdropFilter: "blur(8px)",
          padding: "24px 48px",
          borderRadius: 16,
          border: `1px solid ${color}33`,
        }}
      >
        <div style={{ 
          display: "flex", 
          flexWrap: "wrap", 
          justifyContent: "center", 
          gap: "8px",
          lineHeight: 1.6,
        }}>
          {words.map((word, i) => {
            const wordStartFrame = current.startFrame + Math.floor(i * framesPerWord);
            const wordEndFrame = wordStartFrame + Math.ceil(framesPerWord * 1.5);
            
            // Animation progress for this word
            const progress = interpolate(
              frame,
              [wordStartFrame, wordStartFrame + 6],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            
            // Fade out
            const fadeOut = interpolate(
              frame,
              [current.endFrame - 8, current.endFrame],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );
            
            const opacity = Math.min(progress, fadeOut);
            const scale = 0.8 + progress * 0.2;
            const yOffset = (1 - progress) * 20;

            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity,
                  transform: `translateY(${yOffset}px) scale(${scale})`,
                  transition: "transform 0.1s ease-out, opacity 0.1s ease-out",
                  fontSize: 32,
                  fontWeight: 700,
                  color: "#f1f5f9",
                  fontFamily: "'Inter', 'Segoe UI', sans-serif",
                  letterSpacing: "-0.02em",
                  textShadow: `0 0 30px ${color}80, 0 4px 20px rgba(0,0,0,0.5)`,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
