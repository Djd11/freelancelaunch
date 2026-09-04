"""auth blueprint — verified-email sign-in: Google OAuth + email magic link.

Replaces the old email-only login (dogfood blocker B1: anyone could assume
anyone's identity by typing their email). Both flows here prove the user
controls the mailbox before a session is created:

  * Google OAuth  — one tap, email verified by Google, display name + photo
    come back in user_metadata.
  * Magic link    — Supabase emails a signed link; clicking it proves mailbox
    control. Works for any trusted provider (Gmail, Outlook, iCloud…).

Both use the PKCE flow against GoTrue directly (authorize → /auth/callback
?code= → /token?grant_type=pkce), with the code verifier + state held in the
Flask session, so no client secret ever sits in the browser and callback CSRF
is rejected. Verified emails live in Supabase auth.users — the outreach list.

Google requires the provider enabled in Supabase Dashboard → Auth → OAuth
(Google Client ID/secret + redirect URI https://<project>/auth/v1/callback).
If it isn't configured, GoTrue shows its own error page; magic link always
works with the built-in SMTP (rate-limited — move to custom SMTP for launch).
"""
import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from . import obtain_supabase

auth_bp = Blueprint("auth", __name__)

_FLOW_KEY = "auth_flow"  # session: {"verifier":…, "state":…, "kind": "google"|"magic"}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _pkce_pair():
    verifier = _b64url(secrets.token_bytes(32))  # 43 chars, RFC 7636 charset
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def _sb_url():
    return (current_app.config.get("SUPABASE_URL") or "").rstrip("/")


def _anon_key():
    return (current_app.config.get("SUPABASE_KEY") or "").strip()


def _public_base():
    return (os.getenv("PUBLIC_BASE_URL") or request.url_root).rstrip("/")


def _gotrue_headers():
    key = _anon_key()
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"}


def _start_flow(kind, extra_params=None):
    """Store a fresh PKCE verifier + state and return the GoTrue authorize URL."""
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(12)
    session[_FLOW_KEY] = {"verifier": verifier, "state": state, "kind": kind}
    params = {
        "redirect_to": f"{_public_base()}/auth/callback",
        "code_challenge": challenge,
        "code_challenge_method": "s256",
        "state": state,
    }
    if extra_params:
        params.update(extra_params)
    return params


@auth_bp.route("/auth/login")
def login():
    return render_template("login.html")


@auth_bp.route("/auth/signup")
def signup():
    return render_template("signup.html")


@auth_bp.route("/auth/google")
def google():
    base = _sb_url()
    if not base:
        flash("Auth is not configured on this server.")
        return redirect(url_for("auth.login"))
    params = _start_flow("google")
    params["provider"] = "google"
    return redirect(f"{base}/auth/v1/authorize?" + urllib.parse.urlencode(params))


@auth_bp.route("/auth/magic", methods=["POST"])
def magic():
    """Send a PKCE magic-link email. Creates the account on first use if the
    project allows signup (Supabase default), so one endpoint covers
    sign-in AND sign-up — zero passwords, verified email either way."""
    email = (request.form.get("email") or "").strip().lower()
    display = (request.form.get("display_name") or "").strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        flash("Enter a valid email address.")
        return render_template("signup.html" if display else "login.html",
                               email=email, display_name=display), 200
    base = _sb_url()
    params = _start_flow("magic")
    body = {
        "email": email,
        "code_challenge": params["code_challenge"],
        "code_challenge_method": "s256",
        "options": {
            "email_redirect_to": params["redirect_to"],
            "data": {"display_name": display or email.split("@")[0]},
        },
    }
    req = urllib.request.Request(
        f"{base}/auth/v1/otp", data=json.dumps(body).encode(),
        headers=_gotrue_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = json.loads(exc.read().decode())
            # GoTrue uses different keys by error class: error_description for
            # OAuth, msg for rate-limit/validation. Read both so the useful
            # text isn't dropped (dogfood: 429 showed a bare "400").
            detail = (body.get("error_description") or body.get("msg")
                      or body.get("error") or "")
        except Exception:
            pass
        if exc.code == 429:
            flash("Too many link requests — wait a minute and try again, "
                  "or use Google sign-in.")
        else:
            flash(f"Couldn't send the sign-in link. {detail}".strip() + " Try again.")
        return render_template("login.html", email=email), 200
    except Exception:
        flash("Couldn't reach the auth service — try again in a moment.")
        return render_template("login.html", email=email), 200
    if payload.get("security_item_id"):  # captcha configured — not used here
        flash("Extra verification required — use Google sign-in instead.")
        return render_template("login.html", email=email), 200
    return render_template("magic_sent.html", email=email)


@auth_bp.route("/auth/callback")
def callback():
    err = request.args.get("error_description") or request.args.get("error")
    code = request.args.get("code")
    flow = session.pop(_FLOW_KEY, None)
    if err or not code or not flow:
        flash("Sign-in didn't complete — please try again.")
        return redirect(url_for("auth.login"))
    if request.args.get("state") and request.args.get("state") != flow.get("state"):
        flash("Sign-in link didn't match this browser — start again.")
        return redirect(url_for("auth.login"))
    base = _sb_url()
    body = {"auth_code": code, "code_verifier": flow["verifier"]}
    req = urllib.request.Request(
        f"{base}/auth/v1/token?grant_type=pkce", data=json.dumps(body).encode(),
        headers=_gotrue_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        flash("Sign-in link expired — request a fresh one.")
        return redirect(url_for("auth.login"))
    user = data.get("user") or {}
    uid = user.get("id")
    if not uid:
        flash("Sign-in failed — no user returned.")
        return redirect(url_for("auth.login"))
    email = (user.get("email") or "").lower()
    meta = user.get("user_metadata") or {}
    display = (meta.get("full_name") or meta.get("name")
               or (email.split("@")[0] if email else "Learner"))
    session["user_id"] = uid
    # Ensure a profile row exists (magic-link-created users have none yet).
    try:
        sb = obtain_supabase()
        existing = sb.table("user_profiles").select("user_id").eq("user_id", uid).limit(1).execute().data
        if not existing:
            sb.table("user_profiles").upsert(
                {"user_id": uid, "display_name": display[:80], "is_public": False},
                on_conflict="user_id").execute()
            flash("Welcome! Pick a skill to see live demand and start Day 1 free.")
        else:
            flash("Welcome back — your sprint is waiting.")
    except Exception:
        flash("Welcome! Pick a skill to see live demand and start Day 1 free.")
    return redirect(url_for("main.sprints"))


@auth_bp.route("/auth/logout")
def logout():
    session.pop("user_id", None)
    session.pop(_FLOW_KEY, None)
    return redirect(url_for("main.index"))
