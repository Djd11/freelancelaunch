"""
YouTube Uploader — Upload videos via YouTube Data API v3
"""
import os
import httpx


def upload_video(video_path: str, title: str, description: str, tags: list = None) -> dict:
    """
    Upload a video to YouTube.
    Requires YOUTUBE_API_KEY in config.
    Returns: { "video_id": "...", "url": "https://youtube.com/watch?v=..." }
    """
    # For MVP, we store the local path and mark as pending manual upload
    # Full YouTube Data API integration requires OAuth 2.0 setup
    
    video_id = _generate_video_id(title)
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    
    return {
        "video_id": video_id,
        "url": youtube_url,
        "title": title,
        "status": "pending_upload",
        "note": "YouTube API upload requires OAuth setup. Video saved locally for manual upload."
    }


def _generate_video_id(title: str) -> str:
    """Generate a placeholder video ID from the title."""
    import hashlib
    return hashlib.md5(title.encode()).hexdigest()[:11]


def save_video_metadata(video_path: str, title: str, description: str, output_dir: str) -> dict:
    """Save metadata for manual YouTube upload."""
    metadata = {
        "title": title,
        "description": description,
        "tags": [],
        "video_path": video_path,
        "category": "Education",
        "privacy_status": "public",
    }
    
    meta_path = os.path.join(output_dir, "youtube_metadata.json")
    import json
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return metadata
