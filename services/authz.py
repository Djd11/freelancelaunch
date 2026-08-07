"""
Authorization helpers — shared admin checks across blueprints.

The app has no roles table (MVP); an admin is any logged-in user whose email
matches the ADMIN_EMAIL env var (stored on user_profiles.avatar_url, which the
auth routes use to persist the signup email).
"""
from functools import wraps

from flask import current_app, flash, g, redirect, request, url_for


def is_admin_user(user=None):
    """True if the given user (defaults to g.user) is the configured admin."""
    user = user if user is not None else g.get("user")
    if not user:
        return False
    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    user_email = user.get("avatar_url", "")
    return bool(admin_email and user_email == admin_email)


def require_admin(f):
    """Route decorator: login + admin-email gate. Non-admins are bounced to the dashboard."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        if not is_admin_user():
            flash("You don't have permission to access that page.", "error")
            return redirect(url_for("dashboard.home"))
        return f(*args, **kwargs)
    return wrapper
