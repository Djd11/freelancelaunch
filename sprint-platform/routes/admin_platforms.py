"""admin_platforms blueprint — platform connection management + manual refresh."""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, g, flash

admin_platforms_bp = Blueprint("admin_platforms", __name__)


def _require_admin():
    """Check admin — reuse admin_bp's _require_admin for consistency."""
    from routes import require_login
    gate = require_login()
    if gate:
        return gate
    from flask import session, current_app
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "login required"}), 401
    # Import and delegate to admin_bp's _require_admin
    from routes.admin import _require_admin as _admin_check
    if not _admin_check():
        return jsonify({"error": "admin only"}), 403
    return None


@admin_platforms_bp.route("/admin/platforms")
def list_platforms():
    """List all platform connections with status."""
    gate = _require_admin()
    if gate:
        return gate
    from services.supabase_client import get_supabase
    from services.platform_scheduler import get_scheduler_status
    sb = get_supabase()
    connections = sb.table("platform_connections").select("*").order("created_at").execute().data
    scheduler = get_scheduler_status()
    return render_template("admin/platforms.html",
                           connections=connections, scheduler=scheduler)


@admin_platforms_bp.route("/admin/platforms", methods=["POST"])
def add_platform():
    """Add a new platform connection."""
    gate = _require_admin()
    if gate:
        return gate
    from services.supabase_client import get_supabase
    sb = get_supabase()
    platform = request.form.get("platform", "").strip()
    display_name = request.form.get("display_name", "").strip()
    config = {}
    if request.form.get("feed_urls"):
        config["feed_urls"] = [u.strip() for u in request.form["feed_urls"].split("\n") if u.strip()]
    if request.form.get("api_key"):
        config["api_key"] = request.form["api_key"].strip()
    if request.form.get("search_query"):
        config["search_query"] = request.form["search_query"].strip()
    if request.form.get("cluster_key"):
        config["cluster_key"] = request.form["cluster_key"].strip()

    sb.table("platform_connections").insert({
        "platform": platform,
        "display_name": display_name or platform,
        "config": config,
        "is_active": True,
    }).execute()
    flash(f"Platform '{display_name or platform}' added.")
    return redirect(url_for("admin_platforms.list_platforms"))


@admin_platforms_bp.route("/admin/platforms/<platform_id>/refresh", methods=["POST"])
def refresh_platform(platform_id):
    """Trigger an immediate refresh for one platform."""
    gate = _require_admin()
    if gate:
        return gate
    from services.supabase_client import get_supabase
    from services.feed_ingest import ingest_jobs
    from services.platform_connector import get_connector
    sb = get_supabase()
    conn = sb.table("platform_connections").select("*").eq("id", platform_id).execute().data
    if not conn:
        return jsonify({"error": "not found"}), 404
    c = conn[0]
    config = c.get("config") or {}
    try:
        connector = get_connector(c["platform"], **config)
        cluster_key = config.get("cluster_key", "email-automation")
        query = config.get("search_query", "")
        new, skipped = ingest_jobs(sb, connector, cluster_key, query)
        return jsonify({"ok": True, "new": new, "skipped": skipped})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@admin_platforms_bp.route("/admin/platforms/refresh-all", methods=["POST"])
def refresh_all():
    """Trigger refresh for all active platforms."""
    gate = _require_admin()
    if gate:
        return gate
    from services.feed_ingest import refresh_all_platforms
    from services.supabase_client import get_supabase
    sb = get_supabase()
    results = refresh_all_platforms(sb)
    return jsonify(results)
