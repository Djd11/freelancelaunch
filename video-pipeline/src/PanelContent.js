// ============================================================
// Panel Content — Single Panel Kinetic Text with Voice Over
// ============================================================

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// Single panel with the full script for kinetic text
export const PANELS = [
  {
    id: "kinetic-text",
    title: "Message Queues Explained",
    color: "#4ECDC4",
    accent: "rgba(78,205,196,0.12)",
    // Full narration text - will be animated word by word
    words: "Every direct service call couples your systems together. When one service spikes, the whole chain fails like dominoes. This tight coupling is why cascading failures bring down entire systems in seconds. A message queue is a buffer. Producers publish messages without waiting for consumers. Consumers poll or subscribe at their own pace. The queue persists messages until they are successfully processed. Queues decouple services so each scales independently. They absorb traffic spikes like a shock absorber. Failed consumers do not lose messages. Asynchronous processing means your API responds in milliseconds not seconds. The producer sends a message to the broker. The broker routes it via an exchange to the right queue based on routing rules. The consumer picks it up when ready. Each component can be clustered for high availability. Point to point delivers one message to one consumer. Pub sub broadcasts to all subscribers. Work queues distribute tasks across workers. Request reply sends a response back through a reply queue. Pick the pattern that fits your use case. At most once delivers messages with zero retries fast but lossy. At least once guarantees delivery but may duplicate. Exactly once is the gold standard but requires distributed transactions and hurts throughput. AMQP is feature rich with exchanges bindings and acknowledgments. MQTT is lightweight for IoT devices with minimal bandwidth. Kafka uses a log based model for high throughput event streaming and replays. RabbitMQ excels at complex routing with AMQP. Kafka dominates event streaming and data pipelines. SQS offers fully managed queues on AWS with no ops overhead. Redis Streams are fast but limited in persistence. Message ordering is hard across partitions. Exactly once delivery adds significant latency. Queues are invisible you need monitoring to detect backlogs. Without backpressure a slow consumer can overflow the broker memory.",
    graph: null,
  },
];

// Calculate timing based on word count and audio duration
const WORD_COUNTS = PANELS.map(p => p.words.split(" ").length);
const TOTAL_WORDS = WORD_COUNTS.reduce((a, b) => a + b, 0);
const VIDEO_SECONDS = 136.85; // matches narration.mp3 duration
const TOTAL_FRAMES_AUDIO = Math.round(VIDEO_SECONDS * FPS);

export const PHASES = PANELS.map((_, i) => ({
  label: PANELS[i].id,
  start: 0,
  duration: TOTAL_FRAMES_AUDIO,
}));

export const TOTAL_FRAMES = TOTAL_FRAMES_AUDIO;

export function getCurrentPhase(frame) {
  const clamped = Math.min(frame, TOTAL_FRAMES - 1);
  return { phase: PHASES[0], index: 0 };
}