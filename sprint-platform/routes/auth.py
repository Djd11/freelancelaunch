"""auth blueprint — Supabase Auth surface (arch §4.2)."""
from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash

from supabase_auth.errors import AuthError

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
        password = request.form.get("password", "") or ""

        if not email:
            # BUG-3: an empty email must ask for the email — never masquerade
            # as "No account found" (which implies the account lookup ran).
            flash("Enter your email address to sign in.")
            return render_template("login.html"), 200

        if not password:
            flash("Invalid email or password.")
            return render_template("login.html"), 200

        # BUG-1: validate the password against auth.users — the session is
        # only issued after Supabase confirms the credentials.
        sb = obtain_supabase()
        try:
            res = sb.auth.sign_in_with_password({"email": email, "password": password})
        except AuthError:
            res = None
        user = getattr(res, "user", None) if res is not None else None
        uid = getattr(user, "id", None)
        if not uid:
            # One generic message for wrong password AND nonexistent email —
            # never reveal which part failed.
            flash("Invalid email or password.")
            return render_template("login.html"), 200

        session["user_id"] = uid
        return redirect(url_for("main.sprints"))
    return render_template("login.html")


@auth_bp.route("/login")
def login_alias():
    """BUG-2: /login is what humans type — forward to the real login surface."""
    return redirect(url_for("auth.login"))


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
