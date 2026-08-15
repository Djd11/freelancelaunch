"""auth blueprint — Supabase Auth surface (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, session, g

auth_bp = Blueprint("auth", __name__)

DEMO_USER_ID = "demo-user"


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        user_id = DEMO_USER_ID
        if email:
            from services.supabase_client import get_supabase
            sb = get_supabase()
            # Look up user by email in auth.users
            try:
                # Try to get user from Supabase Auth
                users = sb.auth.admin.list_users()
                for u in users:
                    if u.email == email:
                        user_id = u.id
                        break
            except Exception:
                # Fallback: check if it's the demo user
                if email == "demo@sprint-platform.local":
                    user_id = DEMO_USER_ID
        session["user_id"] = user_id
        return redirect(url_for("main.sprints"))
    return render_template("login.html")


@auth_bp.route("/auth/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
