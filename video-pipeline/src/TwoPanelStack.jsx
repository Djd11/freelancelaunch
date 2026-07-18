import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { PANELS, PHASES, TOTAL_FRAMES, getCurrentPhase } from "./PanelContent.js";
import { FilmGrain } from "./components/FilmGrain.jsx";
import { CustomDiagram } from "./components/CustomDiagram.jsx";
import { Particles } from "./components/Particles.jsx";
import { MemeInsert } from "./components/MemeInsert.jsx";
import { CodeSnippet } from "./components/CodeSnippet.jsx";
import { Subtitles } from "./components/Subtitles.jsx";

// Layout
const L = { X: 100, LW: 780, GAP: 40, RW: 900, H: 620, Y: 200, TOP: 310, BOT: 310 };
const RX = L.X + L.LW + L.GAP;

// Keywords to highlight in phase color
const KEYWORDS = new Set([
  "queue", "Queue", "Queues", "queues", "producer", "Producer", "consumer", "Consumer",
  "broker", "Broker", "AMQP", "MQTT", "Kafka", "pub", "sub", "Pub-Sub",
  "throughput", "latency", "async", "decouple", "partition", "Partition",
  "durable", "persistent", "work", "Work", "exchange", "Exchange",
  "routing", "binding", "acknowledgment", "backpressure", "at-least-once",
  "exactly-once", "at-most-once", "RabbitMQ", "SQS", "Redis",
  "pika", "channel", "connection", "callback",
]);

function wrap(text, max = 44) {
  const words = text.split(" ");
  const lines = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > max && cur.length > 0) {
      lines.push(cur.trim());
      cur = w;
    } else cur += (cur ? " " : "") + w;
  }
  if (cur.trim()) lines.push(cur.trim());
  return lines;
}

function buildLines(words, max = 44) {
  const tokens = words.split(" ");
  const lines = [];
  let cur = [],
    curLen = 0;
  for (const w of tokens) {
    if (curLen + w.length + (curLen ? 1 : 0) > max && cur.length) {
      lines.push(cur.slice());
      cur = [w];
      curLen = w.length;
    } else {
      cur.push(w);
      curLen += (curLen ? 1 : 0) + w.length;
    }
  }
  if (cur.length) lines.push(cur);
  let idx = 0;
  return lines.map((l) => {
    const s = idx;
    idx += l.length;
    return { words: l, start: s, end: idx };
  });
}

// ── Animated Graph (enhanced with glow effects) ──
function AnimatedGraph({ graph, frame, startFrame, duration }) {
  const localFrame = frame - startFrame;
  const progress = Math.min(1, localFrame / (duration * 0.65));
  const eased = 1 - Math.pow(1 - progress, 2);

  if (!graph) return null;

  const { title, type, labels, data, unit, barColor } = graph;
  const gx = L.X + 30,
    gy = L.Y + L.TOP + 25,
    gw = L.LW - 60,
    gh = L.BOT - 45;
  const maxVal = Math.max(...data, 1);

  if (type === "line") {
    const pts = data.map((v, i) => ({
      x: gx + (i / (data.length - 1 || 1)) * gw,
      y: gy + gh - 30 - (v / maxVal) * (gh - 60),
    }));
    const n = Math.max(2, Math.floor(eased * data.length));
    return (
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <filter id="line-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id={`grad-${barColor.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={barColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={barColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Area fill under line */}
        {n >= 2 && (
          <polygon
            points={pts
              .slice(0, n)
              .map((p) => `${p.x},${p.y}`)
              .join(" ") + ` ${pts[n - 1].x},${gy + gh - 30} ${pts[0].x},${gy + gh - 30}`}
            fill={`url(#grad-${barColor.replace("#", "")})`}
            opacity={0.4}
          />
        )}
        <line x1={gx} y1={gy + gh - 30} x2={gx + gw} y2={gy + gh - 30} stroke="#1e293b" strokeWidth={1} />
        <text x={gx} y={gy - 8} fill="#64748b" fontSize={13} fontWeight={600}
          fontFamily="'JetBrains Mono', monospace" letterSpacing={1.5}>{title}</text>
        {data.slice(0, n).map((v, i) => {
          const p = pts[i];
          return (
            <g key={i}>
              {i > 0 && (
                <line x1={pts[i - 1].x} y1={pts[i - 1].y} x2={p.x} y2={p.y}
                  stroke={barColor} strokeWidth={2.5} strokeLinecap="round" filter="url(#line-glow)" />
              )}
              <circle cx={p.x} cy={p.y} r={5} fill={barColor} />
              <circle cx={p.x} cy={p.y} r={8} fill="none" stroke={barColor} strokeWidth={1.5} opacity={0.4} />
              <text x={p.x} y={gy + gh - 12} textAnchor="middle" fill="#94a3b8" fontSize={10}
                fontFamily="'JetBrains Mono', monospace">{labels[i]}</text>
              <text x={p.x} y={p.y - 12} textAnchor="middle" fill="#e2e8f0" fontSize={11} fontWeight={700}>
                {v}{unit}</text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (type === "nodes") {
    const cx = gx + gw / 2,
      cy = gy + gh / 2;
    const pts = [
      { x: gx + 40, y: cy - 10 },
      { x: gx + gw / 2 - 10, y: gy + 20 },
      { x: gx + gw / 2 + 10, y: gy + gh - 20 },
      { x: gx + gw - 40, y: cy + 10 },
    ];
    const n = Math.max(2, Math.floor(eased * labels.length));
    return (
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <filter id="node-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <text x={gx} y={gy - 8} fill="#64748b" fontSize={13} fontWeight={600}
          fontFamily="'JetBrains Mono', monospace" letterSpacing={1.5}>{title}</text>
        {pts.slice(0, n).map((p, i) => (
          <g key={i}>
            {i > 0 && (
              <>
                <line x1={pts[i - 1].x} y1={pts[i - 1].y} x2={p.x} y2={p.y}
                  stroke={barColor} strokeWidth={2.5} opacity={0.5}
                  strokeDasharray={eased > 0.85 ? "none" : "6 4"} />
                <polygon
                  points={`${(pts[i - 1].x + p.x) / 2 + 5},${(pts[i - 1].y + p.y) / 2 - 5} ${(pts[i - 1].x + p.x) / 2 - 5},${(pts[i - 1].y + p.y) / 2 + 5} ${(pts[i - 1].x + p.x) / 2 + 14},${(pts[i - 1].y + p.y) / 2}`}
                  fill={barColor} opacity={0.6} />
              </>
            )}
            <circle cx={p.x} cy={p.y} r={18} fill="#111827" stroke={barColor} strokeWidth={2} filter="url(#node-glow)" />
            <circle cx={p.x} cy={p.y} r={5} fill={barColor} opacity={0.8 + 0.2 * Math.sin(frame * 0.08 + i)} />
            <text x={p.x} y={p.y + 34} textAnchor="middle" fill="#94a3b8" fontSize={11}
              fontFamily="'JetBrains Mono', monospace">{labels[i]}</text>
          </g>
        ))}
      </svg>
    );
  }

  if (type === "bar") {
    const count = data.length;
    const gap = 14;
    const barW = Math.min(90, (gw - gap * (count - 1)) / count);
    const totalW = count * barW + (count - 1) * gap;
    const startX = gx + (gw - totalW) / 2;
    return (
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <filter id="bar-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <text x={gx} y={gy - 8} fill="#64748b" fontSize={13} fontWeight={600}
          fontFamily="'JetBrains Mono', monospace" letterSpacing={1.5}>{title}</text>
        {data.map((v, i) => {
          const vi = Math.min(1, Math.max(0, eased * data.length - i));
          const bh = (v / maxVal) * (gh - 50) * vi;
          const bx = startX + i * (barW + gap);
          return (
            <g key={i}>
              {bh > 0 && (
                <rect x={bx} y={gy + gh - 40 - bh} width={barW} height={bh} rx={4}
                  fill={barColor} opacity={0.8} filter="url(#bar-glow)" />
              )}
              {bh > 20 && (
                <text x={bx + barW / 2} y={gy + gh - 40 - bh + 18}
                  textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>{v}{unit}</text>
              )}
              <text x={bx + barW / 2} y={gy + gh - 20}
                textAnchor="middle" fill="#94a3b8" fontSize={11}
                fontFamily="'JetBrains Mono', monospace">{labels[i]}</text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (type === "hbar") {
    const count = data.length;
    const gap = 8;
    const barH = Math.min(30, (gh - 50 - gap * (count - 1)) / count);
    const labelW = 85;
    return (
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <text x={gx} y={gy - 8} fill="#64748b" fontSize={13} fontWeight={600}
          fontFamily="'JetBrains Mono', monospace" letterSpacing={1.5}>{title}</text>
        {data.map((v, i) => {
          const vi = Math.min(1, Math.max(0, eased * data.length - i));
          const bw = (v / maxVal) * (gw - labelW - 30) * vi;
          const by = gy + i * (barH + gap);
          return (
            <g key={i}>
              <text x={gx + labelW - 8} y={by + barH / 2 + 4} textAnchor="end" fill="#94a3b8" fontSize={11}
                fontFamily="'JetBrains Mono', monospace">{labels[i]}</text>
              <rect x={gx + labelW} y={by} width={Math.max(2, bw)} height={barH} rx={4} fill={barColor} opacity={0.75} />
              {bw > 35 && (
                <text x={gx + labelW + 8} y={by + barH / 2 + 4}
                  fill="#e2e8f0" fontSize={12} fontWeight={700}>{v}{unit}</text>
              )}
            </g>
          );
        })}
      </svg>
    );
  }

  if (type === "compare") {
    const barW = 130;
    const gap = 50;
    const totalW = 2 * barW + gap;
    const startX = gx + (gw - totalW) / 2;
    const pct = Math.round((1 - data[1] / data[0]) * 100);
    const showPct = pct > 0 && pct < 999; // only show meaningful reductions
    return (
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <linearGradient id="compare-green" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00ff87" stopOpacity="1" />
            <stop offset="100%" stopColor="#00cc6a" stopOpacity="0.8" />
          </linearGradient>
        </defs>
        <text x={gx} y={gy - 8} fill="#64748b" fontSize={13} fontWeight={600}
          fontFamily="'JetBrains Mono', monospace" letterSpacing={1.5}>{title}</text>
        {data.map((v, i) => {
          const vi = Math.min(1, Math.max(0, (eased - i * 0.35) * 3));
          const bh = (v / maxVal) * (gh - 60) * Math.min(1, vi * 1.3);
          const bx = startX + i * (barW + gap);
          return (
            <g key={i}>
              <rect x={bx} y={gy + gh - 40 - bh} width={barW} height={Math.max(1, bh)} rx={6}
                fill={i === 1 ? "url(#compare-green)" : barColor} opacity={0.85} />
              {bh > 25 && (
                <text x={bx + barW / 2} y={gy + gh - 40 - bh + 20}
                  textAnchor="middle" fill="#fff" fontSize={18} fontWeight={700}>{v}{unit}</text>
              )}
              {showPct && eased > 0.7 && (
                <text x={bx + barW / 2} y={gy + gh - 40 - bh - 14}
                  textAnchor="middle" fill="#00ff87" fontSize={24} fontWeight={700}>-{pct}%</text>
              )}
              <text x={bx + barW / 2} y={gy + gh - 20}
                textAnchor="middle" fill="#94a3b8" fontSize={13}>{labels[i]}</text>
            </g>
          );
        })}
      </svg>
    );
  }

  return null;
}

// ── Main ──
export function TwoPanelStack() {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const { phase: curPhase, index: idx } = getCurrentPhase(frame);
  const panel = PANELS[idx];

  // Check if this is a meme panel
  const isMeme = false;
  // Check if this is a code panel
  const isCode = false;

  const pop = 1; // instant — no scale-in lag so visual matches audio
  const lines = isCode ? [] : buildLines(panel.words, 44);
  const totalTokens = panel.words.split(" ").length;
  const perWord = Math.max(3, Math.floor((curPhase.duration - 15) / totalTokens));
  const capStart = curPhase.start + 15;

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
    // Very slow continuous zoom for cinematic feel
    const cinematicZoom = 1 + frame * 0.00003;
    return { scale: pulse * cinematicZoom, driftX, driftY };
  }, [frame]);

  const localStart = frame - curPhase.start;
  const burstIntensity = Math.max(0, 1 - localStart / 10);
  const burstR = 4 + burstIntensity * 12;
  const leakX = 30 + 20 * Math.sin(frame * 0.008);
  const leakY = 60 + 15 * Math.cos(frame * 0.012);

  // ── Subtitle segments from current panel ──
  const subtitleSegments = useMemo(() => {
    if (!panel.words) return [];
    const words = panel.words.split(" ");
    const segs = [];
    const segSize = 8; // words per subtitle segment
    for (let i = 0; i < words.length; i += segSize) {
      const chunk = words.slice(i, i + segSize).join(" ");
      const startFrame = curPhase.start + 15 + i * perWord;
      const endFrame = curPhase.start + 15 + Math.min(i + segSize, words.length) * perWord;
      segs.push({ text: chunk, startFrame, endFrame });
    }
    return segs;
  }, [panel, curPhase, perWord]);

  // ── Transition type cycles ──
  const transitionTypes = ["zoom", "glitch", "wipe", "slide", "fade"];

  if (isMeme) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#0B0F19" }}>
        <Audio src={staticFile("audio/narration.mp3")} volume={0.9} />
        <MemeInsert memeId={panel.memeId} duration={curPhase.duration} />
        <Particles count={25} color={panel.color || "#38bdf8"} opacity={0.08} />
        <FilmGrain />
        <ProgressArc totalFrames={TOTAL_FRAMES} currentPhase={{ emoji: panel.emoji || "😂", color: panel.color || "#38bdf8" }} />
      </AbsoluteFill>
    );
  }

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

      {/* Light leaks — enhanced with more movement */}
      <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
        <defs>
          <radialGradient id="lk1" cx={`${leakX}%`} cy={`${leakY}%`} r="60%">
            <stop offset="0%" stopColor={panel.color} stopOpacity={0.09} />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <radialGradient id="lk2" cx={`${100 - leakX}%`} cy={`${100 - leakY}%`} r="50%">
            <stop offset="0%" stopColor="#6c5ce7" stopOpacity={0.06} />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#lk1)" />
        <rect width="100%" height="100%" fill="url(#lk2)" />
      </svg>

      {/* Floating particles for depth */}
      <Particles count={35} color={panel.color} opacity={0.07} />

      {/* Background music — ducked during speech */}
      {/* <Audio src={staticFile("music/ambient-tech.mp3")} volume={0.15} /> */}
      <Audio src={staticFile("audio/narration.mp3")} volume={0.9} />

      {/* Scene counter */}
      <div style={{
        position: "absolute", top: 30, left: 50, zIndex: 10,
        fontSize: 13, fontWeight: 600, color: "#475569",
        fontFamily: "'JetBrains Mono', monospace", letterSpacing: 1.5,
        border: "1px solid #1e293b", borderRadius: 6,
        padding: "6px 14px", background: "rgba(0,0,0,0.4)",
      }}>
        {String(idx + 1).padStart(2, "0")}/{String(PANELS.length).padStart(2, "0")}
      </div>

      {/* Previous cards (dimmed) */}
      {PANELS.slice(0, idx)
        .filter((p) => p.type !== "meme")
        .map((p, i) => {
          const pEnd = PHASES[i].start + PHASES[i].duration;
          const fade = Math.max(0.3, 1 - Math.max(0, Math.min(1, (frame - pEnd - 10) / 20)) * 0.65);
          return (
            <g key={`prev-${p.id}`} opacity={fade}>
              <DimLeftCard p={p} />
              <DimTextCard p={p} />
            </g>
          );
        })}

      {/* Main content with camera zoom + drift */}
      <AbsoluteFill style={{
        transform: `scale(${zoomPulse.scale}) translate(${zoomPulse.driftX}px, ${zoomPulse.driftY}px)`,
      }}>
        <g transform={`scale(${pop})`} style={{ transformOrigin: `${width / 2}px ${L.Y + L.H / 2}px` }}>

          {/* LEFT CARD: image + graph OR code snippet */}
          {isCode ? (
            <CodeSnippet
              code={panel.code}
              language={panel.language || "python"}
              frame={frame}
              phaseStart={curPhase.start}
              color={panel.color}
            />
          ) : (
            <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
              <defs>
                <radialGradient id="ig" cx="40%" cy="40%" r="70%">
                  <stop offset="0%" stopColor={panel.accent} />
                  <stop offset="100%" stopColor="transparent" />
                </radialGradient>
                <filter id="ng">
                  <feGaussianBlur stdDeviation="8" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="transparent" />
                  <stop offset="100%" stopColor="rgba(0,0,0,0.7)" />
                </linearGradient>
                <clipPath id="ic">
                  <rect x={L.X} y={L.Y} width={L.LW} height={L.TOP} rx={16} />
                </clipPath>
              </defs>
              <rect x={L.X} y={L.Y} width={L.LW} height={L.H} rx={16} fill="#111827" />
              <rect x={L.X} y={L.Y} width={L.LW} height={L.H} rx={16}
                fill="none" stroke={panel.color} strokeWidth={2} filter="url(#ng)" opacity={0.5} />
              <CustomDiagram diagramType={panel.diagramType} color={panel.color} frame={frame} phaseStart={curPhase.start} />
              <line x1={L.X + 20} y1={L.Y + L.TOP} x2={L.X + L.LW - 20} y2={L.Y + L.TOP}
                stroke={panel.color} strokeWidth={1} opacity={0.3} />
              {/* Burst effect on scene enter */}
              {burstIntensity > 0 && (
                <g opacity={burstIntensity * 0.4}>
                  <circle cx={L.X + L.LW / 2} cy={L.Y + L.H / 2} r={burstR} fill="none" stroke={panel.color} strokeWidth={2} />
                  <circle cx={L.X + L.LW / 2 + 40} cy={L.Y + L.H / 2 - 30} r={burstR * 0.4} fill={panel.color} opacity={0.3} />
                </g>
              )}
            </svg>
          )}

          {!isCode && <AnimatedGraph graph={panel.graph} frame={frame} startFrame={curPhase.start + 15} duration={curPhase.duration} />}

          {/* RIGHT: text card */}
          <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
            <rect x={RX} y={L.Y} width={L.RW} height={L.H} rx={16} fill="#111827" />
            <rect x={RX} y={L.Y} width={5} height={L.H} rx={2} fill={panel.color} />
            <text x={RX + 40} y={L.Y + 65} fill="#f1f5f9" fontSize={32} fontWeight={700}>{panel.title}</text>
            <text x={RX + 40} y={L.Y + 108} fill="#94a3b8" fontSize={17}>{panel.caption}</text>
            <line x1={RX + 40} y1={L.Y + 135} x2={RX + L.RW - 40} y2={L.Y + 135} stroke="#1e293b" strokeWidth={1} />
            {lines.map((line, li) => (
              <text key={li} x={RX + 40} y={L.Y + 175 + li * 38}
                fontFamily="'Inter', 'Segoe UI', sans-serif" fontSize={22}>
                {line.words.map((word, wi) => {
                  const globalIdx = line.start + wi;
                  const wordFrame = capStart + globalIdx * perWord;
                  const show = frame >= wordFrame;
                  const clean = word.replace(/[^a-zA-Z0-9]/g, "");
                  const isKey = KEYWORDS.has(clean) || KEYWORDS.has(word);
                  // Smooth fade-in for each word
                  const wordAge = Math.max(0, frame - wordFrame);
                  const wordOpacity = show ? Math.min(1, wordAge / 4) : 0;
                  return (
                    <tspan key={wi}
                      fill={!show ? "#1e293b" : isKey ? panel.color : "#e2e8f0"}
                      fontWeight={show ? (isKey ? 700 : 500) : 400}
                      opacity={show ? wordOpacity : 0}
                    >{word} </tspan>
                  );
                })}
              </text>
            ))}
            {/* Burst ring on right card */}
            {burstIntensity > 0 && (
              <g opacity={burstIntensity * 0.3}>
                <circle cx={RX + L.RW / 2} cy={L.Y + L.H / 2} r={burstR * 0.7} fill="none" stroke={panel.color} strokeWidth={1.5} />
              </g>
            )}
          </svg>
        </g>
      </AbsoluteFill>

      {/* Subtitles */}
      {!isCode && <Subtitles segments={subtitleSegments} color={panel.color} />}

      <FilmGrain />
    </AbsoluteFill>
  );
}

function DimLeftCard({ p }) {
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <rect x={L.X} y={L.Y} width={L.LW} height={L.H} rx={16} fill="#111827" />
      <rect x={L.X} y={L.Y} width={L.LW} height={L.H} rx={16} fill="none" stroke="#1e293b" strokeWidth={1.5} />
      <text x={L.X + L.LW / 2} y={L.Y + L.TOP / 2} textAnchor="middle" dominantBaseline="central" fontSize={36} opacity={0.25}>🖼️</text>
      <line x1={L.X + 20} y1={L.Y + L.TOP} x2={L.X + L.LW - 20} y2={L.Y + L.TOP} stroke="#1e293b" strokeWidth={1} opacity={0.3} />
      <text x={L.X + L.LW / 2} y={L.Y + L.TOP + L.BOT / 2} textAnchor="middle" dominantBaseline="central"
        fill="#475569" fontSize={14} fontWeight={600} opacity={0.4}
        fontFamily="'JetBrains Mono', monospace"
      >📊 {p.graph?.title || p.id}</text>
    </svg>
  );
}

function DimTextCard({ p }) {
  const lines = wrap(p.words, 44).slice(0, 4);
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <rect x={RX} y={L.Y} width={L.RW} height={L.H} rx={16} fill="#111827" />
      <rect x={RX} y={L.Y} width={5} height={L.H} rx={2} fill="#1e293b" />
      <text x={RX + 40} y={L.Y + 65} fill="#94a3b8" fontSize={28} fontWeight={600}>{p.title}</text>
      {lines.map((line, i) => (
        <text key={i} x={RX + 40} y={L.Y + 150 + i * 30} fill="#475569" fontSize={18}>{line}</text>
      ))}
    </svg>
  );
}
