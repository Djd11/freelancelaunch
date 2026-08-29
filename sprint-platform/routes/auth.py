"""auth blueprint — Supabase Auth surface (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash
from . import obtain_supabase

auth_bp = Blueprint("auth", __name__)


def _find_user_by_email(sb, email):
    """Return the real auth.users id for an email, or None."""
    try:
        users = sb.auth.admin.list_users()
    except Exception:
        return None
    for u in users:
        if u.email == email:
            return u.id
    return None


@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        sb = obtain_supabase()
        user_id = _find_user_by_email(sb, email) if email else None

        if user_id is None:
            # The session MUST reference a real auth.users UUID. A made-up id
            # crashes the first uuid-FK write with Postgres 22P02 (e.g.
            # starting a sprint). Refuse the login instead.
            flash("No account found for that email on this project.")
            return render_template("login.html"), 200

        session["user_id"] = user_id
        return redirect(url_for("main.sprints"))
    return render_template("login.html")


@auth_bp.route("/auth/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
