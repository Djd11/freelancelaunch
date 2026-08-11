"""
Auth routes — login, signup, logout, profile
"""
from urllib.parse import urlsplit

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from services.supabase_client import get_supabase

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("auth/signup.html")
    
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip()
    topic_slug = request.form.get("topic", "")
    
    if not email or not password:
        flash("Email and password are required", "error")
        return render_template("auth/signup.html")
    
    sb = get_supabase()
    try:
        # Create user in Supabase Auth
        resp = sb.auth.sign_up({"email": email, "password": password})
        user_id = resp.user.id

        # Create user profile
        profile = sb.table("user_profiles").insert({
            "user_id": user_id,
            "display_name": name or email.split("@")[0],
            "avatar_url": email,  # store email here for display
        }).execute()

        # Track acquisition
        source = request.args.get("source", "direct")
        source_detail = request.args.get("ref", "")
        landing_topic = topic_slug or request.args.get("topic", "")

        sb.table("user_acquisition").insert({
            "user_id": user_id,
            "source": source,
            "source_detail": source_detail,
            "landing_topic": landing_topic,
            "signed_up_at": "now()",
        }).execute()

        flash("Account created! Check your email to confirm.", "success")
        return redirect(url_for("auth.login"))

    except Exception as e:
        error_msg = str(e)
        # Supabase returns the SAME user object (auto-login) for an existing
        # email in some SDK versions — the duplicate surfaces as a 23505
        # (duplicate key) on the auth user, or a 23503 FK failure when the
        # profile insert references an already-existing auth user.
        low = error_msg.lower()
        if ("already registered" in low or "23505" in error_msg
                or "duplicate" in low or "23503" in error_msg
                or "already exists" in low):
            flash("This email is already registered. Try logging in.", "error")
        else:
            flash(f"Signup failed: {error_msg}", "error")
        return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")
    
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    
    if not email or not password:
        flash("Email and password are required", "error")
        return render_template("auth/login.html")
    
    sb = get_supabase()
    try:
        resp = sb.auth.sign_in_with_password({"email": email, "password": password})
        session["user_id"] = resp.user.id
        session["access_token"] = resp.session.access_token
        
        flash("Welcome back!", "success")
        # Only allow internal/relative redirects — blocks open-redirect phishing
        # via ?next=https://evil.com (scheme) or ?next=//evil.com (netloc).
        next_url = request.args.get("next", url_for("dashboard.home"))
        parsed = urlsplit(next_url)
        if parsed.scheme or parsed.netloc:
            next_url = url_for("dashboard.home")
        return redirect(next_url)
    
    except Exception as e:
        flash(f"Login failed: Invalid email or password", "error")
        return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("topics.explore"))


@auth_bp.route("/profile", methods=["GET", "POST"])
def profile():
    if not g.user:
        return redirect(url_for("auth.login", next=url_for("auth.profile")))
    
    sb = get_supabase()
    
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()
        sb.table("user_profiles").update({
            "display_name": name
        }).eq("user_id", g.user["id"]).execute()
        flash("Profile updated!", "success")
        return redirect(url_for("auth.profile"))
    
    # Get profile
    profile_resp = sb.table("user_profiles").select("*").eq("user_id", g.user["id"]).limit(1).execute()
    profile = profile_resp.data[0] if profile_resp.data else {}

    return render_template("auth/profile.html", profile=profile)
