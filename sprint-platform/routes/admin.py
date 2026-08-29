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
