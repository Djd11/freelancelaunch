"""
video_engine — two-panel lesson voiceover (engineering-spec §J4, decisions D8).

The day view's "TwoPanel HTML preview — kinetic text + TTS" plays a Remotion
composition (static/video/lesson-player.js) driven by the generated lesson.
This service produces the TTS half: edge-tts synthesizes the lesson script,
the duration is measured with ffprobe, and the MP3 is uploaded to the
dedicated Supabase Storage bucket (`voiceovers`) so the browser player can
fetch it by URL.

No-500: every step is best-effort. If edge-tts, ffprobe, or Storage is
unavailable, `voiceover_for_lesson` returns None and the day view keeps
rendering the kinetic-text fallback — the two-panel player is an enhancement,
never a hard dependency of the lesson.
"""
import io
import json
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

VOICEOVER_BUCKET = "voiceovers"
VOICE = "en-US-GuyNeural"
RATE = "-10%"


def _bucket_ready(sb):
    """Create the public `voiceovers` bucket on first use (idempotent)."""
    try:
        buckets = sb.storage.list_buckets()
        if not any(getattr(b, "name", None) == VOICEOVER_BUCKET for b in buckets):
            sb.storage.create_bucket(
                VOICEOVER_BUCKET, VOICEOVER_BUCKET, {"public": True}
            )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("video_engine: bucket check failed: %s", exc)
        return False


def _synthesize(text: str) -> bytes:
    """Synthesize the script with edge-tts and return raw MP3 bytes."""
    import asyncio

    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    return asyncio.run(_run())


def _duration_seconds(mp3_bytes: bytes) -> float:
    """Measure MP3 duration with ffprobe (seconds)."""
    with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
        tmp.write(mp3_bytes)
        tmp.flush()
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", tmp.name],
            capture_output=True, text=True, timeout=20,
        )
        return float(json.loads(out.stdout)["format"]["duration"])


def voiceover_for_lesson(sb, sprint_id: str, day_no: int, lesson) -> dict | None:
    """Generate + store the lesson's voiceover.

    Returns {"url": ..., "duration_seconds": ...} to store in
    sprint_days.action_payload.lesson["voiceover"], or None when the pipeline
    can't run (No-500 — the kinetic-text fallback stays).
    """
    if not lesson:
        return None
    script = str(lesson.get("script") or "").strip()
    title = str(lesson.get("title") or "").strip()
    text = f"{title}. {script}" if title else script
    if not text:
        return None

    try:
        mp3 = _synthesize(text)
        duration = _duration_seconds(mp3)
        if not duration or duration <= 0:
            return None
        if not _bucket_ready(sb):
            return None
        path = f"{sprint_id}/day-{day_no}.mp3"
        sb.storage.from_(VOICEOVER_BUCKET).upload(
            path, mp3, {"contentType": "audio/mpeg", "upsert": "true"},
        )
        base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
        url = f"{base}/storage/v1/object/public/{VOICEOVER_BUCKET}/{path}"
        return {"url": url, "duration_seconds": round(duration, 1)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("video_engine: voiceover failed for %s day %s: %s", sprint_id, day_no, exc)
        return None
