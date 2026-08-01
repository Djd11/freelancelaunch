"""
HTML Video Preview Generator
Creates a TwoPanel (ByteByteGo-style) HTML preview with voiceover for any curriculum day.
No MP4 rendering — pure HTML/CSS/JS + TTS audio, plays in the browser.

Layout mirrors the educational-vid-gen skill:
  Left:  SVG diagram (animated flow) + stat bars
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
    """Build the narration script from a curriculum day's content."""
    hook = curriculum_day.get("learning_objectives") or curriculum_day.get("hook") or ""
    concept = curriculum_day.get("description") or curriculum_day.get("concept") or ""
    practice = curriculum_day.get("practice_task") or ""
    
    # Clean markdown/headers
    def clean(text):
        text = re.sub(r"^##?\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    
    parts = []
    if hook:
        parts.append(clean(hook))
    if concept:
        parts.append(clean(concept)[:400])
    if practice:
        parts.append(f"Your practice task: {clean(practice)[:150]}")
    
    script = " ".join(parts) if parts else f"Welcome to today's lesson. Let's learn and practice to grow your freelance skills."
    return script[:800]


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
        return 30.0  # fallback


def extract_keywords(text: str, count: int = 5) -> list:
    """Extract important keywords for highlighting."""
    stopwords = {"the", "a", "an", "and", "or", "but", "you", "your", "will",
                 "this", "that", "with", "from", "for", "are", "was", "have",
                 "has", "can", "not", "into", "what", "how", "why", "when",
                 "about", "learn", "today", "let's", "get", "client"}
    words = re.findall(r"[A-Za-z][A-Za-z'-]{4,}", text.lower())
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:count]]


def build_svg_diagram(day_number: int, title: str, keywords: list, color: str) -> str:
    """Build a simple animated 3-step flow diagram (Learn → Practice → Apply)."""
    steps = ["LEARN", "PRACTICE", "APPLY"]
    subs = [
        f"Day {day_number} concept",
        "Hands-on exercise",
        "Real client work",
    ]
    
    # 3 boxes horizontally centered at 780px wide card
    box_w, gap, start_x = 180, 70, 100 + (780 - (3 * 180 + 2 * 70)) // 2
    y = 120
    
    svg = [f'<svg width="780" height="310" viewBox="0 0 780 310" xmlns="http://www.w3.org/2000/svg" style="font-family:Inter,system-ui,sans-serif">']
    svg.append(f'<defs><linearGradient id="boxg" x1="0" y1="0" x2="1" y2="1">'
               f'<stop offset="0%" stop-color="{color}"/><stop offset="100%" stop-color="{color}88"/></linearGradient></defs>')
    
    for i, (step, sub) in enumerate(zip(steps, subs)):
        x = start_x + i * (box_w + gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="70" rx="12" fill="url(#boxg)"/>')
        svg.append(f'<text x="{x + box_w/2}" y="{y + 32}" text-anchor="middle" fill="#fff" font-size="17" font-weight="700">{step}</text>')
        svg.append(f'<text x="{x + box_w/2}" y="{y + 52}" text-anchor="middle" fill="rgba(255,255,255,0.75)" font-size="12" font-weight="600">{sub}</text>')
        if i < 2:
            ax = x + box_w + 8
            svg.append(f'<line x1="{ax}" y1="{y + 35}" x2="{ax + gap - 16}" y2="{y + 35}" stroke="{color}" stroke-width="2.5" stroke-dasharray="6 6"/>')
            svg.append(f'<path d="M {ax + gap - 16} {y + 35} l -8 -5 v 10 z" fill="{color}"/>')
    
    # Keyword chips at bottom
    ky = y + 100
    kw_x = 100
    for kw in keywords[:4]:
        w = max(70, len(kw) * 9 + 20)
        svg.append(f'<rect x="{kw_x}" y="{ky}" width="{w}" height="28" rx="14" fill="{color}22" stroke="{color}" stroke-width="1.5"/>')
        svg.append(f'<text x="{kw_x + w/2}" y="{ky + 19}" text-anchor="middle" fill="{color}" font-size="12" font-weight="600">{kw.upper()}</text>')
        kw_x += w + 12
    
    svg.append('</svg>')
    return "".join(svg)


def build_preview_html(day_number: int, title: str, script: str, audio_url: str,
                       color: str = "#6366f1", keywords: list = None, audio_duration: float = 30.0) -> str:
    """Build the complete TwoPanel HTML preview page."""
    keywords = list(keywords or []) or extract_keywords(script)
    diagram_svg = build_svg_diagram(day_number, title, keywords, color)
    words = script.split()
    word_count = len(words)
    
    # Build keyword highlight map
    kw_lower = {k.lower() for k in keywords}
    
    # Word spans with keyword highlighting
    word_spans = []
    for i, w in enumerate(words):
        clean_w = re.sub(r"[^A-Za-z0-9'-]", "", w)
        cls = "kw" if clean_w.lower() in kw_lower else ""
        word_spans.append(f'<span id="w{i}" class="word {cls}">{w}</span>')
    words_html = " ".join(word_spans)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Day {day_number}: {title} — Preview</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0B0F19; color: #e2e8f0; font-family: Inter, system-ui, -apple-system, sans-serif;
         display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
  
  /* ── TOP BAR ── */
  .topbar {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 24px;
             border-bottom: 1px solid rgba(255,255,255,0.08); background: rgba(11,15,25,0.95); }}
  .topbar .title {{ font-size: 16px; font-weight: 700; color: #f1f5f9; }}
  .topbar .chip {{ font-size: 12px; color: #94a3b8; background: rgba(255,255,255,0.06);
                  padding: 4px 12px; border-radius: 999px; }}
  .topbar .back {{ color: #94a3b8; text-decoration: none; font-size: 13px; }}
  .topbar .back:hover {{ color: #fff; }}
  
  /* ── TWO PANEL LAYOUT ── */
  .panels {{ display: flex; flex: 1; gap: 24px; padding: 24px; min-height: 0; }}
  .panel {{ background: #111827; border: 1px solid rgba(99,102,241,0.3); border-radius: 16px;
           box-shadow: 0 0 24px rgba(99,102,241,0.08); position: relative; }}
  .left {{ flex: 0 0 40%; display: flex; flex-direction: column; padding: 20px; }}
  .right {{ flex: 1; display: flex; flex-direction: column; padding: 32px 36px; overflow: hidden; }}
  
  /* ── LEFT: DIAGRAM ── */
  .diagram-wrap {{ flex: 1; display: flex; align-items: center; justify-content: center; }}
  .diagram-wrap svg {{ max-width: 100%; }}
  
  /* ── LEFT: STAT BARS ── */
  .stat-bars {{ margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); }}
  .stat-bars .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
  .stat-bars .bar-label {{ font-size: 11px; color: #94a3b8; width: 72px; text-align: right; }}
  .stat-bars .bar-track {{ flex: 1; height: 10px; background: rgba(255,255,255,0.06); border-radius: 5px; overflow: hidden; }}
  .stat-bars .bar-fill {{ height: 100%; background: {color}; border-radius: 5px; width: 0;
                        transition: width 1.2s ease; }}
  
  /* ── RIGHT: KINETIC TEXT ── */
  .right h1 {{ font-size: 28px; font-weight: 800; color: #f1f5f9; letter-spacing: -0.02em; margin-bottom: 6px; }}
  .right .caption {{ font-size: 15px; color: #94a3b8; margin-bottom: 24px; }}
  .right .divider {{ height: 1px; background: rgba(255,255,255,0.08); margin-bottom: 24px; }}
  .kinetic {{ font-size: 22px; line-height: 1.7; color: #64748b; }}
  .word {{ opacity: 0; transition: opacity 0.25s ease, color 0.25s ease; }}
  .word.on {{ opacity: 1; color: #e2e8f0; }}
  .word.kw.on {{ color: {color}; font-weight: 700; }}
  
  /* ── CONTROLS ── */
  .controls {{ padding: 16px 24px; border-top: 1px solid rgba(255,255,255,0.08);
              background: rgba(11,15,25,0.95); display: flex; align-items: center; gap: 16px; }}
  .play-btn {{ width: 52px; height: 52px; border-radius: 50%; border: none; cursor: pointer;
              background: {color}; color: #fff; font-size: 20px; display: flex; align-items: center;
              justify-content: center; transition: transform 0.15s ease, opacity 0.15s ease; }}
  .play-btn:hover {{ transform: scale(1.06); }}
  .play-btn:active {{ transform: scale(0.95); }}
  .progress-track {{ flex: 1; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; cursor: pointer; position: relative; }}
  .progress-fill {{ height: 100%; background: {color}; border-radius: 3px; width: 0%; }}
  .time {{ font-size: 12px; color: #94a3b8; font-variant-numeric: tabular-nums; min-width: 90px; text-align: center; }}
  
  .scene-chip {{ position: absolute; top: 14px; left: 14px; font-size: 11px; color: #94a3b8;
               background: rgba(255,255,255,0.06); padding: 3px 10px; border-radius: 999px; }}
  .pulse {{ position: absolute; width: 8px; height: 8px; border-radius: 50%; background: {color};
          top: 18px; right: 18px; box-shadow: 0 0 12px {color}; }}
  
  .note {{ position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%);
          font-size: 11px; color: rgba(148,163,184,0.5); white-space: nowrap; }}
</style>
</head>
<body>
  <div class="topbar">
    <a class="back" href="/dashboard/day/{day_number}">← Back to Day {day_number}</a>
    <div class="title">▶ Day {day_number} Video Preview</div>
    <div class="chip">HTML Preview · No render needed</div>
  </div>
  
  <div class="panels">
    <!-- LEFT PANEL: Diagram + Stats -->
    <div class="panel left">
      <div class="scene-chip">01 / 03 · {title[:28]}</div>
      <div class="pulse"></div>
      <div class="diagram-wrap">{diagram_svg}</div>
      <div class="stat-bars">
        <div class="bar-row"><div class="bar-label">Concept</div><div class="bar-track"><div class="bar-fill" data-w="85"></div></div></div>
        <div class="bar-row"><div class="bar-label">Practice</div><div class="bar-track"><div class="bar-fill" data-w="60"></div></div></div>
        <div class="bar-row"><div class="bar-label">Apply</div><div class="bar-track"><div class="bar-fill" data-w="40"></div></div></div>
      </div>
    </div>
    
    <!-- RIGHT PANEL: Kinetic Text -->
    <div class="panel right">
      <h1>{title}</h1>
      <div class="caption">Day {day_number} · Voiceover lesson</div>
      <div class="divider"></div>
      <div class="kinetic" id="kinetic">{words_html}</div>
      <div class="note">Word-by-word reveal synced to voiceover · {word_count} words</div>
    </div>
  </div>
  
  <!-- CONTROLS -->
  <div class="controls">
    <button class="play-btn" id="playBtn">▶</button>
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

function formatTime(s) {{
  if (isNaN(s)) s = 0;
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return m + ':' + (sec < 10 ? '0' : '') + sec;
}}

audio.addEventListener('loadedmetadata', () => {{
  duration = audio.duration || duration;
  timeDisplay.textContent = '0:00 / ' + formatTime(duration);
}});

function syncWords() {{
  if (!audio.duration) return;
  const idx = Math.floor((audio.currentTime / audio.duration) * totalWords);
  for (let i = currentWord + 1; i <= idx && i < totalWords; i++) {{
    const el = document.getElementById('w' + i);
    if (el) el.classList.add('on');
  }}
  currentWord = Math.max(currentWord, idx);
  // Start stat bars after first word
  if (currentWord === 0) {{
    document.querySelectorAll('.bar-fill').forEach(b => b.style.width = b.dataset.w + '%');
  }}
}}

audio.addEventListener('timeupdate', syncWords);
audio.addEventListener('play', () => {{ playBtn.textContent = '⏸'; syncWords(); }});
audio.addEventListener('pause', () => {{ playBtn.textContent = '▶'; }});
audio.addEventListener('ended', () => {{ playBtn.textContent = '▶'; }});

playBtn.addEventListener('click', () => {{
  if (audio.paused) audio.play(); else audio.pause();
}});

progressTrack.addEventListener('click', (e) => {{
  const rect = progressTrack.getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  audio.currentTime = pct * audio.duration;
  progressFill.style.width = (pct * 100) + '%';
}});

setInterval(() => {{
  if (!audio.paused) {{
    const pct = (audio.currentTime / (audio.duration || duration)) * 100;
    progressFill.style.width = pct + '%';
    timeDisplay.textContent = formatTime(audio.currentTime) + ' / ' + formatTime(audio.duration || duration);
  }}
}}, 250);
</script>
</body>
</html>"""
    return html
