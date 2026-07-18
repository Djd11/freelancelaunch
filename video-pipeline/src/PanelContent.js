// ============================================================
// Panel Content — Message Queues (restored 9-panel sync with audio)
// ============================================================

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const PANELS = [
  {
    id: "hook",
    title: "The Async Crisis",
    caption: "When services call each other directly — a single spike crashes everything",
    color: "#eab308",
    accent: "rgba(234,179,8,0.12)",
    diagramType: "chain-failure",
    imgLabel: "Chain Reaction",
    words: "Every direct service call couples your systems together. When one service spikes, the whole chain fails — like dominoes. This tight coupling is why cascading failures bring down entire systems in seconds.",
    graph: {
      title: "Failure Cascade",
      type: "bar",
      labels: ["Payment", "Inventory", "Shipping", "Email"],
      data: [100, 85, 70, 50],
      unit: "%",
      barColor: "#eab308",
    },
  },
  {
    id: "what",
    title: "What Is a Message Queue?",
    caption: "A buffer between services — producers send, consumers receive asynchronously",
    color: "#4ECDC4",
    accent: "rgba(78,205,196,0.12)",
    diagramType: "producer-queue-consumer",
    imgLabel: "Queue Buffer",
    words: "A message queue is a buffer. Producers publish messages without waiting for consumers. Consumers poll or subscribe at their own pace. The queue persists messages until they are successfully processed.",
    graph: {
      title: "Message Queue Adoption",
      type: "line",
      labels: ["2018", "2019", "2020", "2021", "2022", "2024"],
      data: [35, 48, 62, 78, 85, 92],
      unit: "%",
      barColor: "#4ECDC4",
    },
  },
  {
    id: "why",
    title: "Why Queues Matter",
    caption: "Decoupling, load leveling, fault tolerance, and async processing",
    color: "#FFE66D",
    accent: "rgba(255,230,109,0.12)",
    diagramType: "before-after",
    imgLabel: "With vs Without",
    words: "Queues decouple services so each scales independently. They absorb traffic spikes like a shock absorber. Failed consumers don't lose messages. Asynchronous processing means your API responds in milliseconds, not seconds.",
    graph: {
      title: "Response Time",
      type: "compare",
      labels: ["Without Queue", "With Queue"],
      data: [2500, 45],
      unit: "ms",
      barColor: "#FFE66D",
    },
  },
  {
    id: "arch",
    title: "Queue Architecture",
    caption: "Producer → Broker → Exchange → Queue → Consumer — four core components",
    color: "#A8E6CF",
    accent: "rgba(168,230,207,0.12)",
    diagramType: "amqp-architecture",
    imgLabel: "AMQP Model",
    words: "The producer sends a message to the broker. The broker routes it via an exchange to the right queue based on routing rules. The consumer picks it up when ready. Each component can be clustered for high availability.",
    graph: {
      title: "Request Flow",
      type: "nodes",
      labels: ["Producer", "Broker", "Queue", "Consumer"],
      data: [4],
      unit: "",
      barColor: "#A8E6CF",
    },
  },
  {
    id: "patterns",
    title: "Messaging Patterns",
    caption: "Point-to-Point, Pub-Sub, Work Queues, Request-Reply — each solves a different problem",
    color: "#FF8B94",
    accent: "rgba(255,139,148,0.12)",
    diagramType: "pub-sub-workqueue",
    imgLabel: "Pattern Visual",
    words: "Point-to-point delivers one message to one consumer. Pub-sub broadcasts to all subscribers. Work queues distribute tasks across workers. Request-reply sends a response back through a reply queue. Pick the pattern that fits your use case.",
    graph: {
      title: "Pattern Usage",
      type: "hbar",
      labels: ["Work Queue", "Pub-Sub", "P2P", "Req-Reply"],
      data: [40, 30, 20, 10],
      unit: "%",
      barColor: "#FF8B94",
    },
  },
  {
    id: "delivery",
    title: "Delivery Guarantees",
    caption: "At-most-once, At-least-once, Exactly-once — each with a cost tradeoff",
    color: "#B8A9C9",
    accent: "rgba(184,169,201,0.12)",
    diagramType: "delivery-modes",
    imgLabel: "Delivery Levels",
    words: "At most once delivers messages with zero retries — fast but lossy. At least once guarantees delivery but may duplicate. Exactly once is the gold standard but requires distributed transactions and hurts throughput.",
    graph: {
      title: "Delivery Guarantees",
      type: "compare",
      labels: ["At-Most-Once", "Exactly-Once"],
      data: [1, 100],
      unit: "x cost",
      barColor: "#B8A9C9",
    },
  },
  {
    id: "protocols",
    title: "AMQP, MQTT & Kafka",
    caption: "AMQP for reliability, MQTT for IoT, Kafka for event streaming at scale",
    color: "#F7DC6F",
    accent: "rgba(247,220,111,0.12)",
    diagramType: "protocol-compare",
    imgLabel: "Protocol Matrix",
    words: "AMQP is feature-rich with exchanges, bindings, and acknowledgments. MQTT is lightweight for IoT devices with minimal bandwidth. Kafka uses a log-based model for high-throughput event streaming and replays.",
    graph: {
      title: "Throughput (msg/s)",
      type: "bar",
      labels: ["AMQP", "MQTT", "Kafka"],
      data: [50, 15, 1000],
      unit: "K",
      barColor: "#F7DC6F",
    },
  },
  {
    id: "providers",
    title: "Popular Brokers",
    caption: "RabbitMQ, Apache Kafka, Amazon SQS, Redis Streams — strengths and tradeoffs",
    color: "#85C1E9",
    accent: "rgba(133,193,233,0.12)",
    diagramType: "broker-landscape",
    imgLabel: "Broker Options",
    words: "RabbitMQ excels at complex routing with AMQP. Kafka dominates event streaming and data pipelines. SQS offers fully managed queues on AWS with no ops overhead. Redis Streams are fast but limited in persistence.",
    graph: {
      title: "Market Share",
      type: "hbar",
      labels: ["Kafka", "RabbitMQ", "SQS", "Redis"],
      data: [40, 30, 20, 10],
      unit: "%",
      barColor: "#85C1E9",
    },
  },
  {
    id: "tradeoffs",
    title: "Pitfalls & Tradeoffs",
    caption: "Message ordering, exactly-once cost, monitoring complexity, backpressure",
    color: "#F1948A",
    accent: "rgba(241,148,138,0.12)",
    diagramType: "risk-heatmap",
    imgLabel: "Risk Matrix",
    words: "Message ordering is hard across partitions. Exactly-once delivery adds significant latency. Queues are invisible — you need monitoring to detect backlogs. Without backpressure, a slow consumer can overflow the broker's memory.",
    graph: {
      title: "Complexity Score",
      type: "hbar",
      labels: ["Ordering", "Exactly-Once", "Monitoring", "Backpressure"],
      data: [9, 8, 7, 6],
      unit: "/10",
      barColor: "#F1948A",
    },
  },
];

// Auto-calculate balanced timing matching narration.mp3 (136.85s)
const WORD_COUNTS = PANELS.map(p => p.words.split(" ").length);
const TOTAL_WORDS = WORD_COUNTS.reduce((a, b) => a + b, 0);
const VIDEO_SECONDS = 136.85;
const TOTAL_FRAMES_AUDIO = Math.round(VIDEO_SECONDS * FPS);
const GAP_FRAMES = (PANELS.length - 1) * 10;
const CONTENT_FRAMES = TOTAL_FRAMES_AUDIO - GAP_FRAMES;
const RAW_DURATIONS = WORD_COUNTS.map(w => Math.max(30, Math.round(w / TOTAL_WORDS * CONTENT_FRAMES)));
const RAW_SUM = RAW_DURATIONS.reduce((a, b) => a + b, 0);
RAW_DURATIONS[RAW_DURATIONS.length - 1] += TOTAL_FRAMES_AUDIO - RAW_SUM - GAP_FRAMES;

export const PHASES = PANELS.map((_, i) => ({
  label: PANELS[i].id,
  start: i === 0 ? 0 : RAW_DURATIONS.slice(0, i).reduce((a, b) => a + b + 10, 0),
  duration: RAW_DURATIONS[i],
}));

export const TOTAL_FRAMES = PHASES[PHASES.length - 1].start + PHASES[PHASES.length - 1].duration;

export function getCurrentPhase(frame) {
  const clamped = Math.min(frame, TOTAL_FRAMES - 1);
  for (let i = PHASES.length - 1; i >= 0; i--) {
    if (clamped >= PHASES[i].start) return { phase: PHASES[i], index: i };
  }
  return { phase: PHASES[0], index: 0 };
}