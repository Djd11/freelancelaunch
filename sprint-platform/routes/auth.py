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


@auth_bp.route("/auth/signup", methods=["GET", "POST"])
def signup():
    """Self-serve first-run signup: create the account and drop the learner
    straight into the sprint picker. v1 uses email + display name only (no
    password) to keep the first run frictionless — the upgrade path before a
    public launch is Supabase magic-link / password verification.
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("display_name") or "").strip()
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            flash("Enter a valid email address.")
            return render_template("signup.html", email=email, display_name=name), 200
        sb = obtain_supabase()
        existing = _find_user_by_email(sb, email)
        if existing:
            session["user_id"] = existing
            return redirect(url_for("main.sprints"))
        display = name or email.split("@")[0]
        import secrets
        try:
            res = sb.auth.admin.create_user({
                "email": email,
                "password": secrets.token_urlsafe(16),
                "email_confirm": True,
                "data": {"display_name": display},
            })
            user = getattr(res, "user", res)
            uid = getattr(user, "id", None)
        except Exception:
            uid = None
        if not uid:
            flash("Could not create your account — please try a different email.")
            return render_template("signup.html", email=email, display_name=name), 200
        try:
            sb.table("user_profiles").upsert(
                {"user_id": uid, "display_name": display, "is_public": False},
                on_conflict="user_id",
            ).execute()
        except Exception:
            pass
        session["user_id"] = uid
        flash("Welcome! Pick a skill to see live demand and start Day 1 free.")
        return redirect(url_for("main.sprints"))
    return render_template("signup.html")


@auth_bp.route("/auth/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
