"""
HTML Video Preview Generator
Creates a TwoPanel (ByteByteGo-style) HTML preview with voiceover for any curriculum day.
No MP4 rendering — pure HTML/CSS/JS + TTS audio, plays in the browser.

Layout mirrors the educational-vid-gen skill:
  Left:  SVG diagram (animated, meaningfully labeled) + stat bars
  Right: Kinetic word-by-word text reveal synced to audio
  Bottom: Audio player controls
"""
import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)

VOICE = "en-US-ChristopherNeural"


def build_voiceover_text(curriculum_day: dict) -> str:
    """Build the narration script from a curriculum day's content.
    Deduplicates overlapping fields (e.g. learning_objectives == description)
    to prevent the voiceover repeating the same sentences."""
    def clean(text):
        text = re.sub(r"^##?\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def word_set(text):
        return set(re.findall(r"[a-z]+", text.lower()))

    def overlap_pct(a, b):
        sa, sb = word_set(a), word_set(b)
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / min(len(sa), len(sb))

    hook_raw = clean(curriculum_day.get("learning_objectives") or curriculum_day.get("hook") or "")
    desc_raw = clean(curriculum_day.get("description") or curriculum_day.get("concept") or "")
    practice_raw = clean(curriculum_day.get("practice_task") or "")

    # ── De-duplicate: if hook and description share >50% words, keep only the longer ──
    if hook_raw and desc_raw and overlap_pct(hook_raw, desc_raw) > 0.5:
        if len(hook_raw) >= len(desc_raw):
            desc_raw = ""  # keep hook, drop description
        else:
            hook_raw = ""  # keep description, drop hook

    # ── Assemble: up to 3 non-overlapping parts ──
    parts = []
    if hook_raw:
        parts.append(hook_raw[:200])
    if desc_raw:
        parts.append(desc_raw[:300])
    if practice_raw:
        parts.append("Your practice task: " + practice_raw[:120])

    if parts:
        script = " ".join(parts)
    else:
        topic = curriculum_day.get("title", "web development")
        script = f"Welcome to today's lesson on {topic}. Let us learn and practice to grow your freelance skills."
    return script[:600]


async def _generate_tts_async(text: str, output_path: str) -> bool:
    """Generate TTS audio using edge-tts."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return False


def generate_tts(text: str, output_path: str) -> bool:
    """Synchronous wrapper for TTS generation."""
    return asyncio.run(_generate_tts_async(text, output_path))


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds."""
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 30.0


def extract_keywords(text: str, count: int = 5) -> list:
    """Extract important keywords for highlighting."""
    stopwords = {"the", "a", "an", "and", "or", "but", "you", "your", "will",
                 "this", "that", "with", "from", "for", "are", "was", "have",
                 "has", "can", "not", "into", "what", "how", "why", "when",
                 "about", "learn", "today", "let", "get", "client", "also"}
    words = re.findall(r"[A-Za-z][A-Za-z\'\-]{4,}", text.lower())
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:count]]


def _extract_step_label(text: str, max_len: int = 34) -> str:
    """Extract a concise, meaningful label from curriculum text.
    Strips markdown bold/italic, headers, and newlines before taking the first sentence."""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # bold **x**
    text = re.sub(r"\*([^*]+)\*", r"\1", text)        # italic *x*
    text = re.sub(r"__([^_]+)__", r"\1", text)         # bold __x__
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # headers
    text = re.sub(r"\*Goal:?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    # Get first sentence or clause
    parts = re.split(r"[.!?;]\s+", text)
    label = parts[0].strip() if parts else text.strip()
    # Truncate if too long
    if len(label) > max_len:
        label = label[:max_len - 1].rstrip() + "\u2026"
    return label

def build_svg_diagram(day_number: int, title: str, keywords: list, color: str,
                       description: str = "", practice_task: str = "", apply_task: str = "") -> str:
    """ByteByteGo-style animated flow diagram with 3 lesson-specific steps.
    Each step gets a <g class="step-box step-N"> for JS-driven animation in sync
    with audio progress. Labels are extracted from actual curriculum content."""

    learn_label  = _extract_step_label(description) or _extract_step_label(title, 34)
    practice_label = _extract_step_label(practice_task) or "Hands-on exercise"
    apply_label  = _extract_step_label(apply_task) or "Real client work"

    steps = [
        ("01", "LEARN",  learn_label,    color, "step-box step-0"),
        ("02", "PRACTICE", practice_label, "#22c55e", "step-box step-1"),
        ("03", "APPLY",  apply_label,    "#eab308", "step-box step-2"),
    ]

    # ── Centered layout (no overflow) ──
    box_w, gap, box_h = 170, 40, 88
    total_w = 3 * box_w + 2 * gap
    start_x = (780 - total_w) / 2  # truly centered in 780px viewBox
    y = 60

    svg = ['<svg width="100%" height="100%" viewBox="0 0 780 340" preserveAspectRatio="xMidYMid meet" '
           'xmlns="http://www.w3.org/2000/svg" style="font-family:Inter,system-ui,sans-serif">']
    svg.append("<defs>"
               f'<linearGradient id="boxg1" x1="0" y1="0" x2="0" y2="1">'
               f'<stop offset="0%" stop-color="{color}"/><stop offset="100%" stop-color="{color}99"/></linearGradient>'
               '<linearGradient id="boxg2" x1="0" y1="0" x2="0" y2="1">'
               '<stop offset="0%" stop-color="#22c55e"/><stop offset="100%" stop-color="#22c55e99"/></linearGradient>'
               '<linearGradient id="boxg3" x1="0" y1="0" x2="0" y2="1">'
               '<stop offset="0%" stop-color="#eab308"/><stop offset="100%" stop-color="#eab30899"/></linearGradient>'
               '</defs>')

    # ── Diagram title ──
    title_text = title[:42].upper() if title else f"DAY {day_number}"
    svg.append(f'<text x="390" y="30" text-anchor="middle" fill="#94a3b8" font-size="12" '
               f'font-weight="700" letter-spacing="1.5">{title_text}</text>')
    svg.append(f'<line x1="60" y1="40" x2="720" y2="40" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>')

    # ── Step boxes with animation groups ──
    for i, (num, step_label, sub_label, c, css_class) in enumerate(steps):
        x = start_x + i * (box_w + gap)
        grad = f"boxg{i + 1}"
        svg.append(f'<g class="{css_class}">')
        svg.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="14" fill="url(#{grad})"/>')
        svg.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="14" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>')
        # Number badge
        svg.append(f'<circle cx="{x + 24}" cy="{y + 22}" r="12" fill="rgba(255,255,255,0.18)"/>')
        svg.append(f'<text x="{x + 24}" y="{y + 27}" text-anchor="middle" fill="#fff" font-size="11" font-weight="800">{num}</text>')
        # Step title
        svg.append(f'<text x="{x + 44}" y="{y + 30}" fill="#fff" font-size="16" font-weight="800" letter-spacing="0.5">{step_label}</text>')
        # Sublabel (clipped to fit)
        svg.append(f'<text x="{x + box_w / 2}" y="{y + 62}" text-anchor="middle" fill="rgba(255,255,255,0.75)" '
                   f'font-size="11" font-weight="600">'
                   f'<tspan>{sub_label}</tspan></text>')
        svg.append("</g>")

        # Arrow between blocks
        if i < 2:
            ax1 = x + box_w + 4
            ax2 = x + box_w + gap - 4
            ay = y + box_h / 2
            svg.append(f'<line class="flow-arrow" x1="{ax1}" y1="{ay}" x2="{ax2}" y2="{ay}" stroke="{c}" stroke-width="3" stroke-dasharray="8 7"/>')
            svg.append(f'<path d="M {ax2} {ay} l -8 -5 v 10 z" fill="{c}"/>')
            svg.append(f'<circle class="flow-dot" cx="{ax1}" cy="{ay}" r="4" fill="#fff">'
                       f'<animateMotion dur="1.6s" repeatCount="indefinite" '
                       f'path="M 0 0 L {ax2 - ax1} 0"/></circle>')

    # ── Bottom row: keyword chips + goal ──
    ky = y + box_h + 28
    # Keyword chips (centered)
    kw_widths = [max(60, len(kw) * 8 + 20) for kw in keywords[:3]]
    kw_total = sum(kw_widths) + 10 * (len(keywords[:3]) - 1)
    kx = (780 - kw_total) / 2
    for kw in keywords[:3]:
        w = max(60, len(kw) * 8 + 20)
        svg.append(f'<rect x="{kx}" y="{ky}" width="{w}" height="28" rx="14" fill="{color}14" stroke="{color}" stroke-width="1.2"/>')
        svg.append(f'<text x="{kx + w / 2}" y="{ky + 18}" text-anchor="middle" fill="{color}" font-size="11" font-weight="700">{kw.upper()}</text>')
        kx += w + 10

    # Goal pill (right side, below APPLY)
    goal_x = start_x + 2 * (box_w + gap) + box_w / 2 - 72
    goal_y = ky + 40
    svg.append(f'<line x1="{start_x + 2 * (box_w + gap) + box_w / 2}" y1="{y + box_h}" '
               f'x2="{start_x + 2 * (box_w + gap) + box_w / 2}" y2="{goal_y - 6}" stroke="#eab308" stroke-width="2" stroke-dasharray="6 5"/>')
    svg.append(f'<path d="M {start_x + 2 * (box_w + gap) + box_w / 2} {goal_y - 6} l -4 -7 h 8 z" fill="#eab308"/>')
    svg.append(f'<rect x="{goal_x}" y="{goal_y}" width="144" height="30" rx="15" fill="rgba(234,179,8,0.12)" stroke="#eab308" stroke-width="1.5"/>')
    svg.append(f'<text x="{goal_x + 72}" y="{goal_y + 20}" text-anchor="middle" fill="#eab308" font-size="12" font-weight="800">💼 FIRST CLIENT</text>')

    # ── Section progress timeline (fills dead space at bottom) ──
    pt_y = goal_y + 72  # timeline center
    pt_x_start, pt_x_end = 160, 620
    svg.append(f'<line x1="{pt_x_start}" y1="{pt_y}" x2="{pt_x_end}" y2="{pt_y}" stroke="rgba(255,255,255,0.1)" stroke-width="2"/>')
    for si, (sx, slbl) in enumerate([
        (pt_x_start + (pt_x_end - pt_x_start) * i / 2, l)
        for i, l in enumerate(["LEARN", "PRACTICE", "APPLY"])
    ]):
        dc = [color, "#22c55e", "#eab308"][si]
        svg.append(f'<circle class="step-dot step-dot-{si}" cx="{sx}" cy="{pt_y}" r="8" fill="{dc}" opacity="0.4"/>')
        svg.append(f'<text x="{sx}" y="{pt_y + 22}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="10" font-weight="600">{slbl}</text>')

    svg.append('<style>'
               '.flow-arrow { stroke-dasharray: 8 7; animation: dash 0.9s linear infinite; }'
               '@keyframes dash { to { stroke-dashoffset: -15; } }'
               '.step-box { opacity: 0.55; transition: opacity 0.5s ease; }'
               '.step-box.active { opacity: 1; }'
               '@keyframes pulseStep { 0%,100% { opacity: 1; } 50% { opacity: 0.82; } }'
               '.step-box.active { animation: pulseStep 1.8s ease-in-out infinite; }'
               '.step-dot { opacity: 0.3; transition: opacity 0.4s ease; }'
               '.step-dot.active { opacity: 1; }'
               '</style>')
    svg.append("</svg>")
    return "".join(svg)

def build_preview_html(day_number: int, title: str, script: str, audio_url: str,
                       color: str = "#6366f1", keywords: list = None,
                       audio_duration: float = 30.0, embed: bool = False,
                       description: str = "", practice_task: str = "", apply_task: str = "") -> str:
    """Build the complete TwoPanel HTML preview page.

    embed=True: strips the topbar chrome so the page can sit inside the day-page
    iframe as a self-contained player (no page-within-a-page look).
    """
    keywords = list(keywords or []) or extract_keywords(script)
    diagram_svg = build_svg_diagram(day_number, title, keywords, color,
                                    description=description, practice_task=practice_task,
                                    apply_task=apply_task)
    words = script.split()
    word_count = len(words)

    kw_lower = {k.lower() for k in keywords}
    word_spans = []
    for i, w in enumerate(words):
        clean_w = re.sub(r"[^A-Za-z0-9'-]", "", w)
        cls = "kw" if clean_w.lower() in kw_lower else ""
        word_spans.append(f'<span id="w{i}" class="word {cls}">{w}</span>')
    words_html = " ".join(word_spans)

    topbar_html = ""
    if not embed:
        topbar_html = f"""
  <div class="topbar">
    <a class="back" href="/dashboard/day/{day_number}">\u2190 Back to Day {day_number}</a>
    <div class="title">\u25b6 Day {day_number} Video Preview</div>
    <div class="chip">HTML Preview \u00b7 No render needed</div>
  </div>"""

    body_class = "embed" if embed else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Day {day_number}: {title} \u2014 Preview</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{ background: #0B0F19; color: #e2e8f0; font-family: Inter, system-ui, -apple-system, sans-serif;
         display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}

  .topbar {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 24px;
             border-bottom: 1px solid rgba(255,255,255,0.08); background: rgba(11,15,25,0.95); }}
  .topbar .title {{ font-size: 16px; font-weight: 700; color: #f1f5f9; }}
  .topbar .chip {{ font-size: 12px; color: #94a3b8; background: rgba(255,255,255,0.06);
                  padding: 4px 12px; border-radius: 999px; }}
  .topbar .back {{ color: #94a3b8; text-decoration: none; font-size: 13px; }}
  .topbar .back:hover {{ color: #fff; }}

  .panels {{ display: flex; flex: 1; gap: 20px; padding: 20px; min-height: 0; }}
  .panel {{ background: #111827; border: 1px solid rgba(99,102,241,0.3); border-radius: 16px;
           box-shadow: 0 0 24px rgba(99,102,241,0.08); position: relative; overflow: hidden; }}
  .left {{ flex: 0 0 42%; display: flex; flex-direction: column; padding: 16px; }}
  .right {{ flex: 1; display: flex; flex-direction: column; padding: 28px 32px; overflow: hidden; }}

  .diagram-wrap {{ display: flex; flex-direction: column; align-items: stretch; padding: 0 0 8px 0; }}
  .diagram-wrap svg {{ width: 100%; height: auto; max-height: 100%; flex-shrink: 0; }}

  .section-progress {{ display: flex; align-items: center; justify-content: center; gap: 14px;
                     padding: 14px 0; flex-shrink: 0; }}
  .section-progress .sp-dot {{ width: 10px; height: 10px; border-radius: 50%; background: rgba(255,255,255,0.15);
                              transition: background 0.4s ease, box-shadow 0.4s ease; }}
  .section-progress .sp-dot.active {{ background: {color}; box-shadow: 0 0 12px {color}; }}
  .section-progress .sp-line {{ flex: 1; height: 2px; background: rgba(255,255,255,0.08); }}
  .section-progress .sp-label {{ font-size: 10px; color: rgba(255,255,255,0.35); text-align: center; margin-top: 2px; }}

  .stat-bars {{ padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08); flex-shrink: 0; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }}
  .bar-label {{ font-size: 11px; color: #94a3b8; width: 60px; text-align: right; }}
  .bar-track {{ flex: 1; height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ height: 100%; background: {color}; border-radius: 4px; width: 0; transition: width 1.2s ease; }}

  .right h1 {{ font-size: 22px; font-weight: 800; color: #f1f5f9; letter-spacing: -0.02em; margin-bottom: 4px; }}
  .right .caption {{ font-size: 13px; color: #94a3b8; margin-bottom: 12px; }}
  .right .divider {{ height: 1px; background: rgba(255,255,255,0.08); margin-bottom: 12px; }}
  .kinetic {{ font-size: 18px; line-height: 1.65; color: #64748b; overflow-y: auto; flex: 1; min-height: 0; }}
  .word {{ opacity: 0; transition: opacity 0.25s ease, color 0.25s ease; }}
  .word.on {{ opacity: 1; color: #e2e8f0; }}
  .word.kw.on {{ color: {color}; font-weight: 700; }}
  .note {{ font-size: 11px; color: rgba(148,163,184,0.4); text-align: center; margin-top: 8px; flex-shrink: 0; }}

  body.embed .panels {{ gap: 12px; padding: 12px; }}
  body.embed .left {{ padding: 10px; }}
  body.embed .right {{ padding: 14px 18px; }}
  body.embed .controls {{ padding: 8px 14px; }}
  body.embed .note {{ display: none; }}
  body.embed .scene-chip {{ display: none; }}

  .controls {{ padding: 14px 24px; border-top: 1px solid rgba(255,255,255,0.08);
              background: rgba(11,15,25,0.95); display: flex; align-items: center; gap: 16px; flex-shrink: 0; }}
  .play-btn {{ width: 48px; height: 48px; border-radius: 50%; border: none; cursor: pointer;
              background: {color}; color: #fff; font-size: 18px; display: flex; align-items: center;
              justify-content: center; transition: transform 0.15s ease; flex-shrink: 0; }}
  .play-btn:hover {{ transform: scale(1.06); }}
  .play-btn:active {{ transform: scale(0.95); }}
  .progress-track {{ flex: 1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; cursor: pointer; }}
  .progress-fill {{ height: 100%; background: {color}; border-radius: 3px; width: 0%; transition: width 0.2s linear; }}
  .time {{ font-size: 12px; color: #94a3b8; font-variant-numeric: tabular-nums; min-width: 90px; text-align: center; }}

  .scene-chip {{ position: absolute; top: 12px; left: 12px; font-size: 11px; color: #94a3b8;
               background: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 999px; z-index: 1; }}
</style>
</head>
<body class="{body_class}">
  {topbar_html}

  <div class="panels">
    <div class="panel left">
      <div class="scene-chip">01 / 03 \u00b7 {title[:26]}</div>
      <div class="diagram-wrap">{diagram_svg}</div>
      <div class="section-progress">
        <div>
          <div class="sp-dot sp-dot-0" id="sp0"></div>
          <div class="sp-label">Learn</div>
        </div>
        <div class="sp-line"></div>
        <div>
          <div class="sp-dot sp-dot-1" id="sp1"></div>
          <div class="sp-label">Practice</div>
        </div>
        <div class="sp-line"></div>
        <div>
          <div class="sp-dot sp-dot-2" id="sp2"></div>
          <div class="sp-label">Apply</div>
        </div>
      </div>
    </div>
    <div class="panel right">
      <h1>{title}</h1>
      <div class="caption">Day {day_number} \u00b7 Voiceover lesson</div>
      <div class="divider"></div>
      <div class="kinetic" id="kinetic">{words_html}</div>
      <div class="note">Word-by-word reveal synced to voiceover \u00b7 {word_count} words</div>
    </div>
  </div>

  <div class="controls">
    <button class="play-btn" id="playBtn">\u25b6</button>
    <div class="progress-track" id="progressTrack">
      <div class="progress-fill" id="progressFill"></div>
    </div>
    <div class="time" id="timeDisplay">0:00 / 0:00</div>
  </div>
  <audio id="audio" src="{audio_url}" preload="auto"></audio>
<script>
const audio = document.getElementById('audio');
const playBtn = document.getElementById('playBtn');
const progressFill = document.getElementById('progressFill');
const progressTrack = document.getElementById('progressTrack');
const timeDisplay = document.getElementById('timeDisplay');
const totalWords = {word_count};
let currentWord = -1;
let duration = {audio_duration};

function formatTime(s) {{ if (isNaN(s)) s = 0; const m = Math.floor(s / 60), sec = Math.floor(s % 60); return m + ':' + (sec < 10 ? '0' : '') + sec; }}

audio.addEventListener('loadedmetadata', () => {{ duration = audio.duration || duration; timeDisplay.textContent = '0:00 / ' + formatTime(duration); }});

function syncWords() {{
  if (!audio.duration) return;
  const progress = audio.currentTime / audio.duration;
  const idx = Math.floor(progress * totalWords);
  for (let i = currentWord + 1; i <= idx && i < totalWords; i++) {{
    const el = document.getElementById('w' + i);
    if (el) el.classList.add('on');
  }}
  currentWord = Math.max(currentWord, idx);
  // Scroll the active word into view
  const activeEl = document.getElementById('w' + currentWord);
  if (activeEl) activeEl.scrollIntoView({{ block: 'center', behavior: 'smooth' }});

  // ── Step animation: highlight each step-box during its 1/3 of the audio ──
  document.querySelectorAll('.step-box').forEach((box, i) => {{
    const start = i / 3, end = (i + 1) / 3;
    box.classList.toggle('active', progress >= start && progress <= end);
  }});

  // ── Section progress dots + SVG timeline dots ──
  for (let i = 0; i < 3; i++) {{
    const active = progress >= i / 3;
    const sp = document.getElementById('sp' + i);
    if (sp) sp.classList.toggle('active', active);
    const sd = document.querySelector('.step-dot-' + i);
    if (sd) sd.classList.toggle('active', active);
  }}
}}

audio.addEventListener('timeupdate', syncWords);
audio.addEventListener('play', () => {{ playBtn.textContent = '\u23f8'; syncWords(); }});
audio.addEventListener('pause', () => {{ playBtn.textContent = '\u25b6'; }});
audio.addEventListener('ended', () => {{
  playBtn.textContent = '\u25b6';
  document.querySelectorAll('.step-box').forEach(b => b.classList.remove('active'));
  for (let i = 0; i < 3; i++) {{
    const sp = document.getElementById('sp' + i);
    if (sp) sp.classList.remove('active');
    const sd = document.querySelector('.step-dot-' + i);
    if (sd) sd.classList.remove('active');
  }}
}});

playBtn.addEventListener('click', () => {{ if (audio.paused) audio.play(); else audio.pause(); }});

progressTrack.addEventListener('click', (e) => {{
  const rect = progressTrack.getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  audio.currentTime = pct * audio.duration;
  syncWords();
}});

setInterval(() => {{
  if (!audio.paused) {{
    const pct = (audio.currentTime / (audio.duration || duration)) * 100;
    progressFill.style.width = pct + '%';
    timeDisplay.textContent = formatTime(audio.currentTime) + ' / ' + formatTime(audio.duration || duration);
  }}
}}, 200);
</script>
</body>
</html>"""
    return html

