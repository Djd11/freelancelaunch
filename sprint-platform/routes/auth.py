"""auth blueprint — Supabase Auth surface (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash

auth_bp = Blueprint("auth", __name__)

DEMO_USER_ID = "demo-user"


def _find_user_by_email(sb, email):
    """Return the real auth.users id for an email, or None.

    Dev mode (FakeSupabase) has no auth surface — the AttributeError is
    caught and None returned, so the caller can fall back to the demo user.
    """
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
        from services.supabase_client import get_supabase, is_live_configured
        email = request.form.get("email", "").strip()
        sb = get_supabase()
        user_id = _find_user_by_email(sb, email) if email else None

        if user_id is None:
            if is_live_configured():
                # Live mode: the session MUST reference a real auth.users
                # UUID. Falling back to a fake id ("demo-user") crashes the
                # first uuid-FK write with Postgres 22P02 (e.g. starting a
                # sprint). Refuse the login instead.
                flash("No account found for that email on this project.")
                return render_template("login.html"), 200
            # Dev mode: one-click demo login.
            user_id = DEMO_USER_ID

        session["user_id"] = user_id
        return redirect(url_for("main.sprints"))
    return render_template("login.html")


@auth_bp.route("/auth/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
