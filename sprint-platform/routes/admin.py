"""
Admin blueprint — feed curation, cohort creation, platform admin.
Requires user with user_metadata.role == 'admin' in Supabase Auth.
"""
from flask import Blueprint, request, jsonify, session, g, current_app, render_template, redirect, url_for, flash
from . import obtain_supabase

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _get_admin_user_id():
    """Get the admin user ID from config or environment."""
    return current_app.config.get("ADMIN_USER_ID")


def load_cluster_row(sb, cluster_key):
    """One job_clusters row by key, or None."""
    rows = sb.table("job_clusters").select("*").eq("cluster_key", cluster_key) \
        .limit(1).execute().data
    return rows[0] if rows else None


def _require_admin():
    """Check if current user is admin."""
    user_id = session.get("user_id")
    if not user_id:
        return False
    try:
        sb = obtain_supabase()
        
        # First check: try to get admin user ID from config (set in tests)
        admin_id = current_app.config.get("ADMIN_USER_ID")
        if admin_id and user_id == admin_id:
            return True
        
        # Second check: look up admin user by email in Supabase Auth
        try:
            users = sb.auth.admin.list_users()
            for u in users:
                if u.email == "admin@sprint-platform.local" and u.id == user_id:
                    # Found admin user by email
                    if u.user_metadata.get("role") == "admin":
                        return True
        except Exception:
            pass
        
        # Live Supabase: verify the user exists and carries role=admin metadata.
        if hasattr(sb, 'auth') and hasattr(sb.auth, 'admin'):
            # Verify user exists in user_profiles
            resp = sb.table("user_profiles").select("user_id").eq("user_id", user_id).limit(1).execute()
            if not resp.data:
                return False
            # Check auth user metadata
            auth_resp = sb.auth.admin.get_user_by_id(user_id)
            user = auth_resp.user
            return user.user_metadata.get("role") == "admin" if user and user.user_metadata else False

        return False
    except Exception as e:
        current_app.logger.warning(f"Admin check failed: {e}")
        return False


@admin_bp.before_request
def require_admin():
    if not _require_admin():
        # For API requests, return 403
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": "Admin access required"}), 403
        # For browser requests, redirect to login if not logged in, else 403
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return jsonify({"error": "Admin access required"}), 403


@admin_bp.route("/")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/clusters")
def list_clusters():
    sb = obtain_supabase()
    resp = sb.table("job_clusters").select("*").order("cluster_key").execute()
    clusters = resp.data or []
    return render_template("admin/clusters.html", clusters=clusters)


@admin_bp.route("/clusters/create", methods=["GET", "POST"])
def create_cluster():
    if request.method == "GET":
        return render_template("admin/cluster_form.html")
    data = request.get_json(silent=True) or request.form.to_dict()
    # Ensure keywords is an array
    if "keywords" not in data:
        data["keywords"] = []
    sb = obtain_supabase()
    # Use upsert to handle duplicates
    resp = sb.table("job_clusters").upsert(data, on_conflict="cluster_key").execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Cluster \"{resp.data[0].get('display_name')}\" saved.")
    return redirect(url_for("admin.list_clusters"))


@admin_bp.route("/feed")
def list_feed():
    sb = obtain_supabase()
    resp = sb.table("job_feed").select("*").order("cluster_key,unlock_day").execute()
    jobs = resp.data or []
    return render_template("admin/feed.html", jobs=jobs)


@admin_bp.route("/feed/create", methods=["GET", "POST"])
def create_feed():
    if request.method == "GET":
        return render_template("admin/feed_form.html")
    data = request.get_json(silent=True) or request.form.to_dict()
    # Parse skills
    if "skills" in data and isinstance(data["skills"], str):
        data["skills"] = [s.strip() for s in data["skills"].split(",") if s.strip()]
    sb = obtain_supabase()
    resp = sb.table("job_feed").insert(data).execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Posting \"{resp.data[0].get('title')}\" added to the feed.")
    return redirect(url_for("admin.list_feed"))


@admin_bp.route("/cohorts")
def list_cohorts():
    sb = obtain_supabase()
    resp = sb.table("cohorts").select("*").order("start_date", desc=True).execute()
    cohorts = resp.data or []
    return render_template("admin/cohorts.html", cohorts=cohorts)


@admin_bp.route("/cohorts/create", methods=["GET", "POST"])
def create_cohort():
    if request.method == "GET":
        return render_template("admin/cohort_form.html")
    data = request.get_json(silent=True) or request.form.to_dict()
    sb = obtain_supabase()
    resp = sb.table("cohorts").insert(data).execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Cohort \"{resp.data[0].get('name')}\" created.")
    return redirect(url_for("admin.list_cohorts"))


# ─── CLUSTER CONTENT LIBRARY (arch §2 P3 — provision once, every learner
# ─── consumes; zero per-user LLM calls) ──────────────────────────────

@admin_bp.route("/content")
def content_library_home():
    """List every active cluster with its library status."""
    from services import content_library
    sb = obtain_supabase()
    clusters = sb.table("job_clusters").select("cluster_key,display_name,status") \
        .eq("status", "active").order("cluster_key").execute().data or []
    rows = [{**c, "library": content_library.library_status(sb, c["cluster_key"])}
            for c in clusters]
    return render_template("admin/content_library.html", clusters=rows)


@admin_bp.route("/content/<cluster_key>")
def content_library_detail(cluster_key):
    """Per-cluster library status + the day/day content preview + controls."""
    from services import content_library
    sb = obtain_supabase()
    cluster = load_cluster_row(sb, cluster_key)
    if not cluster:
        flash("Unknown cluster.")
        return redirect(url_for("admin.content_library_home"))
    days = content_library.library_day_rows(sb, cluster_key)
    projects = content_library.library_projects(sb, cluster_key)
    status = content_library.library_status(sb, cluster_key)
    return render_template(
        "admin/content_library_detail.html",
        cluster=cluster, days=days, projects=projects, status=status,
        generating=content_library.is_generating(cluster_key),
    )


@admin_bp.route("/content/<cluster_key>/generate", methods=["POST"])
def content_library_generate(cluster_key):
    """Generate the FULL cluster library via the LLM — admin-scoped, so the
    provider's rate limits bite one admin run instead of every learner.
    Runs synchronously under the admin's request; the admin sees the result."""
    from services import content_library
    sb = obtain_supabase()
    if not load_cluster_row(sb, cluster_key):
        return jsonify({"error": "unknown cluster"}), 404
    content_library.start_generation(cluster_key)
    try:
        result = content_library.generate_for_cluster(sb, cluster_key)
    except Exception as exc:
        current_app.logger.exception("library generation failed for %s", cluster_key)
        if request.is_json or request.headers.get("Accept") == "application/json":
            return jsonify({"error": f"generation failed: {exc}",
                            "status": "error"}), 503
        flash(f"Generation failed: {exc}")
        return redirect(url_for("admin.content_library_detail", cluster_key=cluster_key))
    finally:
        content_library.stop_generation(cluster_key)
    if request.is_json or request.headers.get("Accept") == "application/json":
        status = content_library.library_status(sb, cluster_key)
        return jsonify({"status": "ready" if status["ready"] else "partial",
                        **result, **status}), 200
    flash(f"Content library updated: {result['days']} days, {result['projects']} "
          "projects generated.")
    return redirect(url_for("admin.content_library_detail", cluster_key=cluster_key))


@admin_bp.route("/content/<cluster_key>/day/<int:day_no>", methods=["GET", "POST"])
def content_library_day_edit(cluster_key, day_no):
    """View + edit one library day's lesson JSON (admin upload/override)."""
    import json as _json
    from services import content_library
    sb = obtain_supabase()
    if request.method == "GET":
        days = content_library.library_days(sb, cluster_key)
        lesson = days.get(day_no) or {}
        return render_template("admin/content_day_form.html",
                               cluster_key=cluster_key, day_no=day_no, lesson=lesson)
    try:
        fields = _json.loads(request.form.get("content_json") or "{}")
    except ValueError:
        flash("Content must be valid JSON.")
        return redirect(url_for("admin.content_library_day_edit",
                                cluster_key=cluster_key, day_no=day_no))
    content_library.update_day(sb, cluster_key, day_no, fields)
    flash(f"Day {day_no} content saved (edited content is never auto-regenerated).")
    return redirect(url_for("admin.content_library_detail", cluster_key=cluster_key))


@admin_bp.route("/content/<cluster_key>/seed-from-sprint", methods=["POST"])
def content_library_seed(cluster_key):
    """Bootstrap: publish an existing sprint's generated content into the
    library so every future learner of the cluster consumes it."""
    from services import content_library
    sb = obtain_supabase()
    sprint_id = request.form.get("sprint_id") or (request.get_json(silent=True) or {}).get("sprint_id")
    overwrite = (request.form.get("overwrite") == "true")
    if not sprint_id:
        return jsonify({"error": "sprint_id required"}), 400
    sprint = sb.table("sprints").select("id,cluster_key") \
        .eq("id", sprint_id).limit(1).execute().data
    if not sprint:
        return jsonify({"error": "sprint not found"}), 404
    copied = content_library.seed_from_sprint(sb, sprint[0]["cluster_key"], sprint_id,
                                              overwrite=overwrite)
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"status": "seeded", **copied}), 200
    flash(f"Library seeded from sprint: {copied['days']} days, "
          f"{copied['projects']} projects copied.")
    return redirect(url_for("admin.content_library_detail", cluster_key=cluster_key))


@admin_bp.route("/clusters/<cluster_key>/refresh", methods=["POST"])
def refresh_cluster(cluster_key):
    """Recompute the cluster's live counters from its feed + write a demand
    snapshot (eng-spec §4.5). Explicit admin action — never an implicit read."""
    from services.demand_intelligence import refresh_cluster as refresh, assign_unlock_days
    sb = obtain_supabase()
    assigned = assign_unlock_days(sb, cluster_key)
    result = refresh(sb, cluster_key, snapshot=True)
    result["unlock_days_assigned"] = assigned
    if request.is_json:
        return jsonify(result), 200
    flash(f"Demand refreshed: {result['job_count']} active postings, {assigned} unlock days assigned.")
    return redirect(url_for("admin.list_clusters"))
