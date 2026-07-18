import React from "react";
import { useCurrentFrame } from "remotion";

// ── Layout ──
const DX = 100, DY = 200, DW = 780, DH = 310;
const CX = DX + DW / 2, CY = DY + DH / 2;

// ── ByteByteGo Palette ──
const PALETTE = [
  "#2563eb", "#7c3aed", "#059669", "#d97706",
  "#dc2626", "#0891b2", "#ca8a04", "#9333ea",
];

// ── Arrow Defs ──
function ArrowDef() {
  return (
    <defs>
      <marker id="arr" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
      </marker>
      <marker id="arr-col" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
      </marker>
      <filter id="node-glow-dia">
        <feGaussianBlur stdDeviation="4" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
  );
}

// ── Animated Arrow: dashes march + traveling dot ──
function AnimatedArrow({ x1, y1, x2, y2, color = "#94a3b8", frame, delay = 0, speed = 3, dashed = false }) {
  const t = ((frame + delay) * speed) % 40;
  const offset = -t;
  const progress = ((frame + delay) % 36) / 36;
  const dx = x2 - x1, dy = y2 - y1;
  const dotX = x1 + dx * progress;
  const dotY = y1 + dy * progress;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={color} strokeWidth={2}
        strokeDasharray={dashed ? "6 4" : "6 6"}
        strokeDashoffset={offset}
        opacity={0.7}
        markerEnd="url(#arr)"
      />
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={color} strokeWidth={0.5} opacity={0.2}
      />
      <circle cx={dotX} cy={dotY} r={3.5} fill={color} opacity={0.9} />
      <circle cx={dotX} cy={dotY} r={6} fill={color} opacity={0.2} />
    </g>
  );
}

// ── Solid colored node with pulse animation ──
function BBGNode({ x, y, w, h, fillColor, label, sub, frame, idx, startFrame = 0 }) {
  const local = frame - startFrame;
  const flash = local < 8 ? 1 + 0.08 * (8 - local) * Math.sin(local * 1.5) : 1;
  // Continuous subtle pulse
  const pulse = 1 + Math.sin(frame * 0.04 + idx * 1.5) * 0.008;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={6}
        fill={fillColor} stroke="rgba(0,0,0,0.15)" strokeWidth={1}
        filter="url(#node-glow-dia)"
        style={{ transform: `scale(${flash * pulse})`, transformOrigin: `${x + w / 2}px ${y + h / 2}px` }}
      />
      <text x={x + w / 2} y={y + h / 2 + 4} textAnchor="middle" dominantBaseline="central"
        fill="#ffffff" fontSize={13} fontWeight={700}
      >{label}</text>
      {sub && (
        <text x={x + w / 2} y={y + h - 8} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={9}>{sub}</text>
      )}
    </g>
  );
}

function NumberCircle({ x, y, num, color }) {
  return (
    <g>
      <circle cx={x} cy={y} r={14} fill={color} stroke="rgba(0,0,0,0.1)" strokeWidth={1} />
      <text x={x} y={y + 5} textAnchor="middle" fill="#ffffff" fontSize={12} fontWeight={800}>{num}</text>
    </g>
  );
}

function Footer({ text }) {
  return (
    <text x={CX} y={DY + DH - 25} textAnchor="middle" fill="#64748b" fontSize={13} fontWeight={600}
      fontFamily="'JetBrains Mono', monospace" letterSpacing={1}
    >{text}</text>
  );
}

function SectionTitle({ text }) {
  return (
    <text x={CX} y={DY + 22} textAnchor="middle" fill="#475569" fontSize={11} fontWeight={700}
      fontFamily="'JetBrains Mono', monospace" letterSpacing={2}
    >{text}</text>
  );
}

// ── Floating particles for diagrams ──
function DiagramParticles({ color, frame, count = 12 }) {
  const particles = [];
  for (let i = 0; i < count; i++) {
    const seed = (i * 7919 + 104729) % 100000;
    const x = DX + (seed % DW);
    const y = DY + ((seed * 3) % DH);
    const size = 0.5 + (seed % 100) / 200;
    const speed = 0.05 + (seed % 50) / 300;
    const cx = x + Math.sin(frame * 0.008 + i) * 15;
    const cy = ((y - frame * speed) % DH + DH) % DH + DY;
    particles.push(
      <circle key={i} cx={cx} cy={cy} r={size} fill={color} opacity={0.12 + (i % 3) * 0.04} />
    );
  }
  return <>{particles}</>;
}

// ── 1. Chain Failure ──
function ChainFailure({ color, frame }) {
  const svcs = [
    { name: "Client",    color: "#2563eb" },
    { name: "Auth",      color: "#7c3aed" },
    { name: "Payment",   color: "#d97706" },
    { name: "Inventory", color: "#0891b2" },
    { name: "Email",     color: "#ca8a04" },
  ];
  const spacing = 120;
  const startX = CX - (svcs.length - 1) * spacing / 2;
  const failIdx = Math.floor((frame % 90) / 18) % svcs.length;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} />
      <SectionTitle text="TIGHT COUPLING" />
      <NumberCircle x={startX} y={CY - 45} num="1" color="#2563eb" />
      {svcs.map((s, i) => {
        const bx = startX + i * spacing;
        const failed = i >= failIdx && i > 0;
        return (
          <g key={i}>
            {i > 0 && (
              <AnimatedArrow
                x1={startX + (i - 1) * spacing + 50} y1={CY - 5}
                x2={bx - 50} y2={CY - 5}
                color={failed ? color : "#94a3b8"}
                frame={frame} delay={i * 5} speed={2}
              />
            )}
            <rect x={bx - 45} y={CY - 30} width={90} height={50} rx={6}
              fill={failed ? `${color}30` : s.color}
              stroke={failed ? color : "none"}
              strokeWidth={failed ? 2 : 0}
              opacity={failed && i > failIdx ? 0.5 : 1}
            />
            <text x={bx} y={CY - 8} textAnchor="middle" fill="#fff" fontSize={13} fontWeight={700}>{s.name}</text>
            <text x={bx} y={CY + 12} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={11} fontWeight={600}>Service</text>
            {failed && (
              <text x={bx} y={CY - 16} textAnchor="middle" fill={color} fontSize={16}>❌</text>
            )}
          </g>
        );
      })}
      <Footer text="ONE FAILURE CASCADES — TIGHT COUPLING TAKES DOWN THE CHAIN" />
    </svg>
  );
}

// ── 2. Producer → Queue → Consumer ──
function ProducerQueueConsumer({ color, frame }) {
  const flash = frame < 60 ? 1 + 0.06 * Math.sin(frame * 0.3) * Math.max(0, 1 - frame / 60) : 1;
  const active = Math.floor(frame / 60) % 3;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} />
      <SectionTitle text="MESSAGE QUEUE ARCHITECTURE" />
      <NumberCircle x={CX - 180} y={CY - 70} num="1" color="#2563eb" />
      <NumberCircle x={CX} y={CY - 70} num="2" color="#059669" />
      <NumberCircle x={CX + 180} y={CY - 70} num="3" color="#d97706" />

      <rect x={CX - 240} y={CY - 32} width={130} height={56} rx={8}
        fill="#2563eb" opacity={active === 0 ? 1 : 0.6} />
      <text x={CX - 175} y={CY - 8} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>Producer</text>
      <text x={CX - 175} y={CY + 14} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={12} fontWeight={600}>Publishes messages</text>

      <AnimatedArrow x1={CX - 110} y1={CY - 5} x2={CX - 70} y2={CY - 5}
        color={active >= 0 ? "#2563eb" : "#94a3b8"} frame={frame} delay={0} speed={2} />

      <rect x={CX - 65} y={CY - 40} width={130} height={72} rx={8}
        fill="#059669"
        transform={`scale(${flash})`} transformOrigin={`${CX}px ${CY}px`}
      />
      <text x={CX} y={CY - 5} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={800}>MESSAGE</text>
      <text x={CX} y={CY + 12} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={800}>QUEUE</text>
      <text x={CX} y={CY + 28} textAnchor="middle" fill="rgba(255,255,255,0.6)" fontSize={12} fontWeight={600}>Persistent buffer</text>

      <AnimatedArrow x1={CX + 65} y1={CY - 5} x2={CX + 110} y2={CY - 5}
        color={active >= 1 ? "#059669" : "#94a3b8"} frame={frame} delay={8} speed={2} />

      <rect x={CX + 115} y={CY - 32} width={130} height={56} rx={8}
        fill="#d97706" opacity={active === 2 ? 1 : 0.6} />
      <text x={CX + 180} y={CY - 8} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>Consumer</text>
      <text x={CX + 180} y={CY + 14} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={12} fontWeight={600}>Processes when ready</text>

      <Footer text="PRODUCERS SEND WITHOUT WAITING — CONSUMERS READ AT THEIR PACE" />
    </svg>
  );
}

// ── 3. Before / After ──
function BeforeAfter({ color, frame, phaseStart = 0 }) {
  const relFrame = frame - phaseStart;
  const items = [
    { text: "⚡ No buffer — spike hits all",   col: "#dc2626", side: 0 },
    { text: "🔥 One fail = all fail",           col: "#dc2626", side: 0 },
    { text: "🐢 2500ms response time",          col: "#dc2626", side: 0 },
    { text: "🧊 Queue absorbs spikes",          col: "#059669", side: 1 },
    { text: "✅ Independent scaling",            col: "#059669", side: 1 },
    { text: "⚡ 45ms response time",             col: "#059669", side: 1 },
  ];
  const stagger = 45;
  const dropLen = 30;

  function getRowY(itemIdx) {
    const f = relFrame - itemIdx * stagger;
    if (f < 0) return -60;
    if (f < dropLen) {
      const t = f / dropLen;
      return -60 * (1 - Math.pow(1 - t, 3));
    }
    return 0;
  }

  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={8} />
      <SectionTitle text="WITHOUT vs WITH QUEUE" />

      <text x={CX - 190} y={DY + 55} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>❌ Without Queue</text>
      <rect x={CX - 310} y={DY + 65} width={220} height={170} rx={8} fill="#dc2626" opacity={0.12} stroke="#dc2626" strokeWidth={1.5} />
      <rect x={CX - 310} y={DY + 65} width={220} height={36} rx={8} fill="#dc2626" />
      <text x={CX - 200} y={DY + 88} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={700}>Direct Coupling</text>

      <text x={CX + 190} y={DY + 55} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>✅ With Queue</text>
      <rect x={CX + 90} y={DY + 65} width={220} height={170} rx={8} fill="#059669" opacity={0.12} stroke="#059669" strokeWidth={1.5} />
      <rect x={CX + 90} y={DY + 65} width={220} height={36} rx={8} fill="#059669" />
      <text x={CX + 200} y={DY + 88} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={700}>Decoupled Services</text>

      {items.map((item, i) => {
        const ry = getRowY(i);
        const isLeft = item.side === 0;
        const rx = isLeft ? CX - 200 : CX + 200;
        const rbx = isLeft ? CX - 290 : CX + 110;
        return (
          <g key={i} transform={`translate(0, ${ry})`}>
            <rect x={rbx} y={DY + 115 + (i % 3) * 34} width={180} height={28} rx={4}
              fill={item.col} opacity={0.2} />
            <text x={rx} y={DY + 134 + (i % 3) * 34} textAnchor="middle"
              fill={isLeft ? "#fca5a5" : "#86efac"}
              fontSize={13} fontWeight={700}
            >{item.text}</text>
          </g>
        );
      })}

      <text x={CX} y={CY + 5} textAnchor="middle" fill="#475569" fontSize={32}>→</text>
      <text x={CX} y={CY + 40} textAnchor="middle" fill="#22c55e" fontSize={18} fontWeight={800}>-98%</text>

      <Footer text="98% LATENCY REDUCTION — QUEUES DECOUPLE YOUR SYSTEM" />
    </svg>
  );
}

// ── 4. AMQP Architecture ──
function AMQPArchitecture({ color, frame }) {
  const phase = Math.floor(frame / 55) % 4;
  const STEP = 170;
  const NODE_W = 120;
  const START_X = CX - (3 * STEP + NODE_W) / 2;
  const nodes = [
    { label: "Producer", sub: "Sends messages",         c: "#2563eb" },
    { label: "Exchange", sub: "Routes by routing key",  c: "#7c3aed" },
    { label: "Queue",    sub: "Persistent buffer",      c: "#059669" },
    { label: "Consumer", sub: "Receives & processes",   c: "#d97706" },
  ];
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} />
      <SectionTitle text="AMQP COMPONENTS" />
      {nodes.map((n, i) => {
        const bx = START_X + i * STEP;
        const by = CY - 28;
        const isActive = phase === i;
        return (
          <g key={i}>
            <rect x={bx} y={by} width={NODE_W} height={46} rx={6}
              fill={n.c} opacity={isActive ? 1 : 0.6}
              filter="url(#node-glow-dia)"
            />
            <text x={bx + NODE_W / 2} y={by + 18} textAnchor="middle" fill="#fff" fontSize={13} fontWeight={700}>{n.label}</text>
            <text x={bx + NODE_W / 2} y={by + 36} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={11} fontWeight={600}>{n.sub}</text>
            {isActive && <rect x={bx} y={by} width={NODE_W} height={46} rx={6} fill="none" stroke="#fff" strokeWidth={2} opacity={0.4} />}
          </g>
        );
      })}
      {nodes.slice(0, -1).map((_, i) => {
        const x1 = START_X + (i + 1) * STEP - NODE_W;
        const x2 = START_X + (i + 1) * STEP;
        return (
          <AnimatedArrow key={i}
            x1={x1} y1={CY - 5} x2={x2} y2={CY - 5}
            color={phase >= i ? nodes[i].c : "#94a3b8"}
            frame={frame} delay={i * 6} speed={2}
          />
        );
      })}
      <Footer text="ROUTE → BUFFER → DELIVER — EACH LAYER HAS A SPECIFIC JOB" />
    </svg>
  );
}

// ── 5. Pub-Sub / Work Queue ──
function PubSubWorkQueue({ color, frame }) {
  const focus = Math.floor(frame / 90) % 2;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={8} />
      <SectionTitle text="MESSAGING PATTERNS" />

      <text x={CX - 185} y={DY + 50} textAnchor="middle" fill="#fff" fontSize={13} fontWeight={700}>📢 Pub-Sub</text>
      <rect x={CX - 280} y={DY + 58} width={130} height={44} rx={8} fill="#7c3aed" opacity={focus === 0 ? 1 : 0.5} />
      <text x={CX - 215} y={DY + 85} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={700}>Publisher</text>

      <AnimatedArrow x1={CX - 150} y1={DY + 72} x2={CX - 115} y2={DY + 56}
        color={focus === 0 ? "#7c3aed" : "#475569"} frame={frame} delay={0} speed={2} />
      <AnimatedArrow x1={CX - 150} y1={DY + 80} x2={CX - 115} y2={DY + 80}
        color={focus === 0 ? "#7c3aed" : "#475569"} frame={frame} delay={3} speed={2} />
      <AnimatedArrow x1={CX - 150} y1={DY + 88} x2={CX - 115} y2={DY + 104}
        color={focus === 0 ? "#7c3aed" : "#475569"} frame={frame} delay={6} speed={2} />

      {["Sub A", "Sub B", "Sub C"].map((s, i) => (
        <rect key={i} x={CX - 115} y={DY + 50 + i * 28} width={100} height={26} rx={4}
          fill={focus === 0 ? "#059669" : "#1e293b"} opacity={focus === 0 ? 1 : 0.4} />
      ))}
      {["Sub A", "Sub B", "Sub C"].map((s, i) => (
        <text key={i} x={CX - 65} y={DY + 68 + i * 28} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={600}>{s}</text>
      ))}

      <text x={CX + 185} y={DY + 50} textAnchor="middle" fill="#fff" fontSize={13} fontWeight={700}>⚖️ Work Queue</text>
      <rect x={CX + 150} y={DY + 58} width={130} height={44} rx={8} fill="#2563eb" opacity={focus === 1 ? 1 : 0.5} />
      <text x={CX + 215} y={DY + 85} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={700}>Dispatcher</text>

      <AnimatedArrow x1={CX + 150} y1={DY + 72} x2={CX + 115} y2={DY + 56}
        color={focus === 1 ? "#2563eb" : "#475569"} frame={frame} delay={0} speed={2} />
      <AnimatedArrow x1={CX + 150} y1={DY + 80} x2={CX + 115} y2={DY + 80}
        color={focus === 1 ? "#2563eb" : "#475569"} frame={frame} delay={3} speed={2} />
      <AnimatedArrow x1={CX + 150} y1={DY + 88} x2={CX + 115} y2={DY + 104}
        color={focus === 1 ? "#2563eb" : "#475569"} frame={frame} delay={6} speed={2} />

      {["Wkr 1", "Wkr 2", "Wkr 3"].map((s, i) => (
        <rect key={i} x={CX + 15} y={DY + 50 + i * 28} width={100} height={26} rx={4}
          fill={focus === 1 ? "#d97706" : "#1e293b"} opacity={focus === 1 ? 1 : 0.4} />
      ))}
      {["Wkr 1", "Wkr 2", "Wkr 3"].map((s, i) => (
        <text key={i} x={CX + 65} y={DY + 68 + i * 28} textAnchor="middle" fill="#fff" fontSize={12} fontWeight={600}>{s}</text>
      ))}

      <Footer text="1→N BROADCAST vs N→1 COMPETING CONSUMERS" />
    </svg>
  );
}

// ── 6. Delivery Modes ──
function DeliveryModes({ color, frame }) {
  const modes = [
    { label: "At Most Once", speed: "⚡ Fastest", rel: "❌ Lossy", detail: "No retries", c: "#dc2626" },
    { label: "At Least Once", speed: "⚡ Fast", rel: "⚠️ Duplicates", detail: "Auto retry", c: "#d97706" },
    { label: "Exactly Once", speed: "🐢 Slow", rel: "✅ Perfect", detail: "Transactions", c: "#059669" },
  ];
  const active = Math.floor(frame / 65) % 3;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={8} />
      <SectionTitle text="DELIVERY GUARANTEES" />
      {modes.map((m, i) => {
        const mx = CX + (i - 1) * 230;
        const isActive = active === i;
        return (
          <g key={i}>
            <rect x={mx - 100} y={CY - 65} width={200} height={120} rx={10}
              fill={isActive ? "#1e293b" : "#0f172a"}
              stroke={isActive ? m.c : "#1e293b"} strokeWidth={isActive ? 2 : 1}
              filter={isActive ? "url(#node-glow-dia)" : undefined}
            />
            <rect x={mx - 100} y={CY - 65} width={200} height={42} rx={10} fill={m.c} opacity={isActive ? 1 : 0.6} />
            <text x={mx} y={CY - 42} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>{m.label}</text>
            <text x={mx} y={CY - 5} textAnchor="middle" fill={isActive ? "#e2e8f0" : "#64748b"} fontSize={12} fontWeight={600}>{m.speed}</text>
            <text x={mx} y={CY + 18} textAnchor="middle" fill={isActive ? m.c : "#475569"} fontSize={12} fontWeight={600}>{m.rel}</text>
            <text x={mx} y={CY + 38} textAnchor="middle" fill="#64748b" fontSize={12} fontWeight={600}>{m.detail}</text>
          </g>
        );
      })}
      <Footer text="TRADE: SPEED vs RELIABILITY vs COMPLEXITY" />
    </svg>
  );
}

// ── 7. Protocol Comparison (with real logos) ──
function ProtocolCompare({ color, frame }) {
  const protos = [
    { name: "AMQP", icon: "🔧", features: ["Exchanges + Binding", "ACK / NACK", "Complex routing"], best: "Enterprise", c: "#7c3aed", logo: "amqp" },
    { name: "MQTT", icon: "📡", features: ["Lightweight binary", "QoS levels 0-2", "Retain messages"], best: "IoT / Edge", c: "#0891b2", logo: "mqtt" },
    { name: "Kafka", icon: "📀", features: ["Log-based storage", "Partitions + Replay", "High throughput"], best: "Event Streaming", c: "#d97706", logo: "kafka" },
  ];
  const active = Math.floor(frame / 60) % 3;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={8} />
      <SectionTitle text="PROTOCOL COMPARISON" />
      {protos.map((p, i) => {
        const px = CX + (i - 1) * 240;
        const isActive = active === i;
        return (
          <g key={i}>
            <rect x={px - 105} y={CY - 72} width={210} height={150} rx={10}
              fill={isActive ? "#1e293b" : "#0f172a"}
              stroke={p.c} strokeWidth={isActive ? 2 : 1}
              filter={isActive ? "url(#node-glow-dia)" : undefined}
            />
            <rect x={px - 105} y={CY - 72} width={210} height={46} rx={10} fill={p.c} />
            <text x={px} y={CY - 52} textAnchor="middle" fontSize={14}>{p.icon}</text>
            <text x={px} y={CY - 32} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>{p.name}</text>
            <line x1={px - 80} y1={CY - 22} x2={px + 80} y2={CY - 22} stroke="#1e293b" strokeWidth={1} />
            {p.features.map((f, j) => (
              <text key={j} x={px} y={CY + 4 + j * 19} textAnchor="middle" fill="#94a3b8" fontSize={12} fontWeight={500}>• {f}</text>
            ))}
            <rect x={px - 52} y={CY + 56} width={104} height={22} rx={4} fill={p.c} opacity={0.15} stroke={p.c} strokeWidth={1} />
            <text x={px} y={CY + 71} textAnchor="middle" fill={p.c} fontSize={11} fontWeight={700}>Best: {p.best}</text>
          </g>
        );
      })}
      <Footer text="CHOOSE YOUR PROTOCOL — EACH EXCELS AT SOMETHING DIFFERENT" />
    </svg>
  );
}

// ── 8. Broker Landscape (with real logos) ──
function BrokerLandscape({ color, frame }) {
  const brokers = [
    { name: "RabbitMQ", tag: "Complex Routing", c: "#ff6600", logo: "rabbitmq" },
    { name: "Kafka", tag: "Event Streaming", c: "#d97706", logo: "kafka" },
    { name: "Amazon SQS", tag: "Fully Managed", c: "#2563eb", logo: "sqs" },
    { name: "Redis Streams", tag: "Low Latency", c: "#dc382d", logo: "redis" },
  ];
  const active = Math.floor(frame / 55) % 4;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={10} />
      <SectionTitle text="POPULAR BROKERS" />
      {brokers.map((b, i) => {
        const bx = CX + (i % 4 - 1.5) * 170;
        const by = CY - 30 + Math.floor(i / 4) * 90;
        const isActive = active === i;
        return (
          <g key={i}>
            <rect x={bx - 75} y={by - 36} width={150} height={72} rx={8}
              fill={b.c} opacity={isActive ? 1 : 0.6}
              filter={isActive ? "url(#node-glow-dia)" : undefined}
            />
            <text x={bx} y={by - 8} textAnchor="middle" fill="#fff" fontSize={14} fontWeight={700}>{b.name}</text>
            <text x={bx} y={by + 14} textAnchor="middle" fill="rgba(255,255,255,0.75)" fontSize={13} fontWeight={600}>{b.tag}</text>
          </g>
        );
      })}
      <Footer text="PICK THE RIGHT TOOL — KAFKA ISN'T ALWAYS THE ANSWER" />
    </svg>
  );
}

// ── 9. Risk Heatmap ──
function RiskHeatmap({ color, frame }) {
  const risks = [
    { label: "Ordering", score: 9, c: "#dc2626" },
    { label: "Exactly-Once", score: 8, c: "#dc2626" },
    { label: "Monitoring", score: 7, c: "#d97706" },
    { label: "Backpressure", score: 6, c: "#d97706" },
  ];
  const active = Math.floor(frame / 60) % 4;
  return (
    <svg width="100%" height="100%" style={{ position: "absolute", pointerEvents: "none" }}>
      <ArrowDef />
      <DiagramParticles color={color} frame={frame} count={6} />
      <SectionTitle text="COMPLEXITY SCORE" />
      {[0, 2, 4, 6, 8, 10].map((v, i) => {
        const gy = DY + 55 + (10 - v) * 28;
        return (
          <g key={i}>
            <line x1={DX + 60} y1={gy} x2={DX + DW - 60} y2={gy} stroke="#1e293b" strokeWidth={0.5} />
            <text x={DX + 50} y={gy + 4} textAnchor="end" fill="#475569" fontSize={10} fontWeight={600}>{v}</text>
          </g>
        );
      })}
      {risks.map((r, i) => {
        const barH = (r.score / 10) * 160;
        const bx = CX - 135 + i * 82;
        const isActive = active === i;
        const flashBar = isActive && frame < 70 ? 1 + 0.05 * Math.sin(frame * 0.4) * Math.max(0, 1 - frame / 70) : 1;
        return (
          <g key={i}>
            <rect x={bx - 20} y={DY + DH - 95 - barH} width={40} height={barH} rx={5}
              fill={r.c} opacity={isActive ? 1 : 0.5}
              filter={isActive ? "url(#node-glow-dia)" : undefined}
              transform={`scale(1,${flashBar})`} transformOrigin={`${bx}px ${DY + DH - 95}px`}
            />
            <text x={bx} y={DY + DH - 102 - barH} textAnchor="middle" fill={r.c} fontSize={16} fontWeight={800}>{r.score}</text>
            <text x={bx} y={DY + DH - 60} textAnchor="middle"
              fill={isActive ? "#e2e8f0" : "#94a3b8"} fontSize={13} fontWeight={700}
            >{r.label}</text>
          </g>
        );
      })}
      <Footer text="THE BIGGEST PAIN POINTS IN PRODUCTION QUEUES" />
    </svg>
  );
}

// ── Router ──
export function CustomDiagram({ diagramType, color, frame, phaseStart = 0 }) {
  switch (diagramType) {
    case "chain-failure": return <ChainFailure color={color} frame={frame} />;
    case "producer-queue-consumer": return <ProducerQueueConsumer color={color} frame={frame} />;
    case "before-after": return <BeforeAfter color={color} frame={frame} phaseStart={phaseStart} />;
    case "amqp-architecture": return <AMQPArchitecture color={color} frame={frame} />;
    case "pub-sub-workqueue": return <PubSubWorkQueue color={color} frame={frame} />;
    case "delivery-modes": return <DeliveryModes color={color} frame={frame} />;
    case "protocol-compare": return <ProtocolCompare color={color} frame={frame} />;
    case "broker-landscape": return <BrokerLandscape color={color} frame={frame} />;
    case "risk-heatmap": return <RiskHeatmap color={color} frame={frame} />;
    case "code-snippet": return null; // handled by CodeSnippet in TwoPanelStack
    default: return null;
  }
}
