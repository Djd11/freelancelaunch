import React from "react";
import { useCurrentFrame } from "remotion";

const DX = 100, DY = 200, DW = 780, DH = 620;

// Simple syntax highlighting via regex
function colorize(line) {
  const parts = [];
  let remaining = line;
  let key = 0;

  const patterns = [
    { regex: /^(#.*$)/m, color: "#6a737d" },                    // comments
    { regex: /^(\s*"""[\s\S]*?"""|"""[\s\S]*?""")/m, color: "#9ecbff" }, // docstrings
    { regex: /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/, color: "#9ecbff" }, // strings
    { regex: /\b(import|from|def|class|return|if|else|elif|for|while|with|as|try|except|finally|raise|yield|lambda|async|await|pass|break|continue|in|not|and|or|is|None|True|False)\b/, color: "#c678dd" }, // keywords
    { regex: /\b(print|len|range|str|int|float|list|dict|set|tuple|type|isinstance|hasattr|getattr|setattr|super|self|cls)\b/, color: "#e5c07b" }, // builtins
    { regex: /\b([A-Z][a-zA-Z0-9_]*)\b/, color: "#e5c07b" },  // classes
    { regex: /\b(\d+(?:\.\d+)?)\b/, color: "#d19a66" },        // numbers
    { regex: /(def\s+)(\w+)/, color: "#61afef" },               // function names
    { regex: /(@\w+)/, color: "#e06c75" },                       // decorators
  ];

  // Just return colored spans for common patterns
  // For simplicity, we'll do keyword + string + comment highlighting
  let result = remaining;

  // Tokenize roughly
  const tokens = [];
  let pos = 0;

  // Simple approach: split by words and colorize
  const words = remaining.split(/(\s+|[(),:{}.=\[\]!<>+\-*/#@])/);
  for (const word of words) {
    if (!word) continue;
    let color = "#abb2bf"; // default

    if (word.startsWith('#')) color = "#5c6370";
    else if (/^["']/.test(word)) color = "#98c379";
    else if (/^(import|from|def|class|return|if|else|elif|for|while|with|as|try|except|finally|raise|yield|lambda|async|await|pass|break|continue|in|not|and|or|is|None|True|False|self|cls)$/.test(word)) color = "#c678dd";
    else if (/^(print|len|range|str|int|float|list|dict|set|tuple|type|isinstance|hasattr|getattr|setattr|super|connect|channel|queue_declare|basic_consume|basic_publish|basic_ack|start_consuming|BlockingConnection|ConnectionParameters|callback|dec)$/.test(word)) color = "#61afef";
    else if (/^[A-Z]/.test(word)) color = "#e5c07b";
    else if (/^\d+$/.test(word)) color = "#d19a66";
    else if (/^[(){}\[\]:,=./+\-*#@!]$/.test(word)) color = "#636d83";

    tokens.push({ text: word, color });
  }

  return tokens;
}

/**
 * Code snippet panel — terminal-style code block with line-by-line reveal.
 */
export function CodeSnippet({ code, language = "python", frame, phaseStart = 0, color = "#4ECDC4" }) {
  const localFrame = frame - phaseStart;
  const lines = (code || "").split("\n");
  const linesPerTick = 0.12; // frames per line reveal
  const visibleCount = Math.min(lines.length, Math.floor(localFrame * linesPerTick) + 1);
  const startDelay = 8; // frames before first line appears

  return (
    <svg
      width="100%"
      height="100%"
      style={{ position: "absolute", pointerEvents: "none" }}
    >
      {/* Terminal window */}
      <rect x={DX} y={DY} width={DW} height={DH} rx={12} fill="#0d1117" />
      <rect x={DX} y={DY} width={DW} height={DH} rx={12}
        fill="none" stroke={color} strokeWidth={1.5} opacity={0.3} />

      {/* Title bar */}
      <rect x={DX} y={DY} width={DW} height={36} rx={12} fill="#161b22" />
      <rect x={DX} y={DY + 24} width={DW} height={12} fill="#161b22" />

      {/* Traffic lights */}
      <circle cx={DX + 20} cy={DY + 18} r={6} fill="#ff5f57" />
      <circle cx={DX + 40} cy={DY + 18} r={6} fill="#febc2e" />
      <circle cx={DX + 60} cy={DY + 18} r={6} fill="#28c840" />

      {/* Language badge */}
      <rect x={DX + DW - 80} y={DY + 8} width={64} height={20} rx={4} fill={color} opacity={0.2} />
      <text x={DX + DW - 48} y={DY + 22} textAnchor="middle" fill={color}
        fontSize={11} fontWeight={700} fontFamily="'JetBrains Mono', monospace"
      >{language}</text>

      {/* Code lines */}
      {lines.slice(0, visibleCount).map((line, i) => {
        const lineFrame = startDelay + i / linesPerTick;
        const opacity = localFrame > lineFrame ? 1 : 0;
        const highlight = i === visibleCount - 1 && localFrame > lineFrame;
        const y = DY + 60 + i * 26;

        if (y > DY + DH - 20) return null; // overflow guard

        return (
          <g key={i} opacity={opacity}>
            {/* Active line highlight */}
            {highlight && (
              <rect x={DX} y={y - 14} width={DW} height={24} fill={color} opacity={0.06} />
            )}
            {/* Line number */}
            <text x={DX + 16} y={y} fill="#484f58" fontSize={12}
              fontFamily="'JetBrains Mono', monospace" textAnchor="end"
            >{String(i + 1).padStart(2, " ")}</text>
            {/* Separator */}
            <line x1={DX + 24} y1={y - 10} x2={DX + 24} y2={y + 4} stroke="#21262d" strokeWidth={1} />
            {/* Code text */}
            <text x={DX + 36} y={y} fill="#c9d1d9" fontSize={13}
              fontFamily="'JetBrains Mono', monospace"
            >
              {colorize(line).map((token, ti) => (
                <tspan key={ti} fill={token.color}>{token.text}</tspan>
              ))}
            </text>
          </g>
        );
      })}

      {/* Cursor blink at last visible line */}
      {visibleCount > 0 && visibleCount <= lines.length && (
        <rect
          x={DX + 36 + (lines[visibleCount - 1] || "").length * 7.8}
          y={DY + 60 + (visibleCount - 1) * 26 - 12}
          width={8} height={16}
          fill={color}
          opacity={Math.sin(frame * 0.15) > 0 ? 0.9 : 0}
        />
      )}
    </svg>
  );
}
