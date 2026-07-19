"""
Platform Verification routes — link freelance marketplace accounts
"""
import os
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g
from services.supabase_client import get_supabase

platforms_bp = Blueprint("platforms", __name__, url_prefix="/platforms")
logger = logging.getLogger(__name__)

# ─── Known freelance platforms and their signup deep links ─────
PLATFORMS = {
    "upwork": {
        "name": "Upwork",
        "icon": "💼",
        "color": "#14a800",
        "signup_url": "https://www.upwork.com/signup/",
        "about": "The largest freelance marketplace. Create a profile, search jobs, submit proposals.",
        "steps": [
            "Click the link to open Upwork's signup page",
            "Sign up with your email or Google account",
            "Complete your freelancer profile (title, overview, skills)",
            "Set your hourly rate (start at $15-25/hr)",
            "Return here and click 'I've done this'"
        ]
    },
    "fiverr": {
        "name": "Fiverr",
        "icon": "🎯",
        "color": "#1dbf73",
        "signup_url": "https://www.fiverr.com/signup/",
        "about": "Gig-based marketplace. Create service listings and buyers come to you.",
        "steps": [
            "Click the link to open Fiverr's signup page",
            "Sign up as a seller (not buyer)",
            "Create your first 3 gigs (service listings)",
            "Add pricing packages: Basic, Standard, Premium",
            "Return here and click 'I've done this'"
        ]
    },
    "contra": {
        "name": "Contra",
        "icon": "⚡",
        "color": "#6366f1",
        "signup_url": "https://contra.com/signup/",
        "about": "Commission-free freelance platform. Portfolio-first, no fees.",
        "steps": [
            "Click the link to open Contra's signup page",
            "Sign up with your email",
            "Upload your portfolio samples",
            "Set your profile title and availability",
            "Return here and click 'I've done this'"
        ]
    }
}

DEFAULT_PLATFORMS = ["upwork", "fiverr", "contra"]


@platforms_bp.route("/setup")
def setup():
    """Platform verification onboarding page."""
    if not g.user:
        return redirect(url_for("auth.login"))
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Get existing platform links
    try:
        resp = sb.table("user_platforms").select("*") \
            .eq("user_id", user_id).execute()
        existing = resp.data or []
    except Exception:
        existing = []
    
    # Build platform status map
    platform_status = {}
    for p in existing:
        platform_status[p["platform"]] = p
    
    return render_template("platforms/setup.html",
        platforms=PLATFORMS,
        platform_status=platform_status,
    )


@platforms_bp.route("/api/select", methods=["POST"])
def select_platform():
    """User selects a platform to link."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    platform = data.get("platform", "").strip().lower()
    
    if platform not in PLATFORMS:
        return jsonify({"error": f"Invalid platform: {platform}"}), 400
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    # Check if already exists
    existing = sb.table("user_platforms").select("id") \
        .eq("user_id", user_id).eq("platform", platform).limit(1).execute()
    
    if existing.data:
        return jsonify({"status": "already_exists", "platform": platform})
    
    # Create new record
    try:
        sb.table("user_platforms").insert({
            "user_id": user_id,
            "platform": platform,
            "status": "pending",
        }).execute()
        return jsonify({"status": "created", "platform": platform, "signup_url": PLATFORMS[platform]["signup_url"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@platforms_bp.route("/api/verify", methods=["POST"])
def verify_platform():
    """User confirms they've created their account."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    platform = data.get("platform", "").strip().lower()
    
    if platform not in PLATFORMS:
        return jsonify({"error": "Invalid platform"}), 400
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    try:
        sb.table("user_platforms").update({
            "status": "verified",
            "verified_at": "now()",
        }).eq("user_id", user_id).eq("platform", platform).execute()
        return jsonify({"status": "verified", "platform": platform})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@platforms_bp.route("/api/skip", methods=["POST"])
def skip_platform():
    """User wants to skip a platform for now."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    platform = data.get("platform", "").strip().lower()
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    existing = sb.table("user_platforms").select("id") \
        .eq("user_id", user_id).eq("platform", platform).limit(1).execute()
    
    if existing.data:
        sb.table("user_platforms").update({"status": "skipped"}) \
            .eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("user_platforms").insert({
            "user_id": user_id,
            "platform": platform,
            "status": "skipped",
        }).execute()
    
    return jsonify({"status": "skipped", "platform": platform})


@platforms_bp.route("/api/remove", methods=["POST"])
def remove_platform():
    """User removes a platform from their list."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json() or {}
    platform = data.get("platform", "").strip().lower()
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    sb.table("user_platforms").delete() \
        .eq("user_id", user_id).eq("platform", platform).execute()
    
    return jsonify({"status": "removed", "platform": platform})


@platforms_bp.route("/api/status")
def platform_status():
    """Get current platform verification status."""
    if not g.user:
        return jsonify({"error": "Not logged in"}), 401
    
    sb = get_supabase()
    user_id = g.user["id"]
    
    try:
        resp = sb.table("user_platforms").select("*") \
            .eq("user_id", user_id).execute()
        platforms = resp.data or []
        
        has_verified = any(p["status"] == "verified" for p in platforms)
        pending = [p for p in platforms if p["status"] == "pending"]
        
        return jsonify({
            "platforms": platforms,
            "has_verified": has_verified,
            "pending_count": len(pending),
            "needs_setup": len(platforms) == 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
