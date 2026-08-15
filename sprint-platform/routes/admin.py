"""
Admin blueprint — feed curation, cohort creation, platform admin.
Requires user with user_metadata.role == 'admin' in Supabase Auth.
"""
from flask import Blueprint, request, jsonify, session, g, current_app, render_template, redirect, url_for, flash

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
        from services.supabase_client import get_supabase
        sb = get_supabase()
        
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
        
        # Third check: if we're using live Supabase (has auth.admin)
        if hasattr(sb, 'auth') and hasattr(sb.auth, 'admin'):
            # Verify user exists in user_profiles
            resp = sb.table("user_profiles").select("user_id").eq("user_id", user_id).limit(1).execute()
            if not resp.data:
                return False
            # Check auth user metadata
            auth_resp = sb.auth.admin.get_user_by_id(user_id)
            user = auth_resp.user
            return user.user_metadata.get("role") == "admin" if user and user.user_metadata else False
        
        # For FakeSupabase (dev mode), check if user has admin flag in user_profiles
        profile_resp = sb.table("user_profiles").select("user_id").eq("user_id", user_id).limit(1).execute()
        if not profile_resp.data:
            return False
            
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
    from services.supabase_client import get_supabase
    sb = get_supabase()
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
    from services.supabase_client import get_supabase
    sb = get_supabase()
    # Use upsert to handle duplicates
    resp = sb.table("job_clusters").upsert(data, on_conflict="cluster_key").execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Cluster \"{resp.data[0].get('display_name')}\" saved.")
    return redirect(url_for("admin.list_clusters"))


@admin_bp.route("/feed")
def list_feed():
    from services.supabase_client import get_supabase
    sb = get_supabase()
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
    from services.supabase_client import get_supabase
    sb = get_supabase()
    resp = sb.table("job_feed").insert(data).execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Posting \"{resp.data[0].get('title')}\" added to the feed.")
    return redirect(url_for("admin.list_feed"))


@admin_bp.route("/cohorts")
def list_cohorts():
    from services.supabase_client import get_supabase
    sb = get_supabase()
    resp = sb.table("cohorts").select("*").order("start_date", desc=True).execute()
    cohorts = resp.data or []
    return render_template("admin/cohorts.html", cohorts=cohorts)


@admin_bp.route("/cohorts/create", methods=["GET", "POST"])
def create_cohort():
    if request.method == "GET":
        return render_template("admin/cohort_form.html")
    data = request.get_json(silent=True) or request.form.to_dict()
    from services.supabase_client import get_supabase
    sb = get_supabase()
    resp = sb.table("cohorts").insert(data).execute()
    if request.is_json:
        return jsonify(resp.data[0]), 201
    flash(f"Cohort \"{resp.data[0].get('name')}\" created.")
    return redirect(url_for("admin.list_cohorts"))
