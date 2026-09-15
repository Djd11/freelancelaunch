"""auth blueprint — passwordless email OTP + Google/Facebook, via Supabase Auth
(design §4/§5.2; spikes/2026-09-15-t1-pkce-otp-spike.md for the measured client
contract).

The session contract is unchanged: ``session["user_id"]`` holds an ``auth.users``
UUID and is consumed by ``app.load_user`` / ``require_login``. Every path below
either sets that key or leaves it untouched — there is deliberately no
intermediate "half-authenticated" state, and the OTP step is therefore not a
login until the code verifies.

Three entry points funnel into one post-auth step (``_complete_auth``): OTP
verify, OAuth callback, and — unchanged, for accounts that already have a real
password — ``POST /auth/login``.
"""
import time

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from supabase_auth.errors import AuthError

from . import obtain_supabase
from services.supabase_client import get_auth_supabase

auth_bp = Blueprint("auth", __name__)

# Session keys owned by this module.
_OTP_EMAIL = "otp_email"              # address the last code was sent to
_OTP_SENT_AT = "otp_last_sent_at"     # epoch of the last accepted send
_OTP_NAME = "otp_pending_name"        # display name captured at signup funnel

# `verify_otp` type literal. Measured on the live project: "email" verifies an
# email-OTP code; "magiclink" is REJECTED even with a fresh, unused token, so
# this is load-bearing — do not "try another literal" when a verify fails.
_OTP_TYPE = "email"


def _auth_client():
    """Anon + PKCE client for OTP/OAuth (T1). 503 rather than a crash if the
    project is unconfigured, matching obtain_supabase()."""
    try:
        return get_auth_supabase()
    except Exception as exc:
        current_app.logger.error("auth client unavailable: %s", exc)
        abort(503)


def _email_is_wellformed(email):
    """Syntax only. Never an existence check — that is the whole point of the
    unified, always-generic OTP response."""
    return bool(email) and "@" in email and "." in (email.split("@")[-1] or "")


def _mask_email(email):
    """`maya@corp.io` → `ma…@corp.io` — enough to recognise the address without
    re-echoing it wholesale into the code-entry step."""
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    keep = local[:2] if len(local) > 3 else local[:1]
    return f"{keep}…@{domain}"


def _cooldown_left(email=None):
    """Seconds still blocked by the resend throttle (design §5.2). Authoritative:
    the UI countdown is cosmetic, this gate is the rule.

    Keyed **per address** (`{"someone@x.io": 1757…}`) rather than one global
    timestamp: with a global gate, mistyping your email once locks the correct
    address out for 60s and the only "fix" is to wait. Total send volume is
    still bounded by Supabase's dashboard rate limits and the SMTP free tier
    (design §5.2), which is what the throttle was never meant to replace.
    """
    email = (email or session.get(_OTP_EMAIL) or "").strip().lower()
    sent = session.get(_OTP_SENT_AT)
    if not email or not isinstance(sent, dict):
        return 0
    last = sent.get(email)
    if not last:
        return 0
    span = int(current_app.config.get("OTP_RESEND_COOLDOWN_SECONDS", 60))
    return max(0, span - int(time.time() - float(last)))


def _clear_otp_state():
    session.pop(_OTP_EMAIL, None)
    session.pop(_OTP_SENT_AT, None)
    session.pop(_OTP_NAME, None)


def _complete_auth(uid, email=None, name_hint=None, welcome=None):
    """The single post-auth step for OTP + OAuth (design §4).

    Sets the session, then creates a ``user_profiles`` row **only when none
    exists** — `ignore_duplicates=True` is INSERT … ON CONFLICT DO NOTHING, so a
    returning user's edited display_name is never clobbered by a later social
    login for the same address. Provisioning lives here rather than in each
    caller so all entry paths behave identically (and so the admin@-style
    missing-profile rows can't recur for new signups).

    A profile-insert failure must NOT log anyone out: auth is already verified,
    and load_user() tolerates a missing row. So it is logged and swallowed.
    """
    session["user_id"] = uid
    display = (name_hint or "").strip()
    if not display and email:
        display = email.split("@")[0]

    provisioned = False
    try:
        sb = obtain_supabase()
        existing = sb.table("user_profiles").select("user_id") \
            .eq("user_id", uid).limit(1).execute().data
        if not existing:
            sb.table("user_profiles").upsert(
                {"user_id": uid, "display_name": display or uid, "is_public": False},
                on_conflict="user_id",
                ignore_duplicates=True,
            ).execute()
            provisioned = True
    except Exception as exc:
        current_app.logger.warning("user_profiles provisioning failed for %s: %s",
                                   uid, exc)

    _clear_otp_state()
    if welcome is not None:
        flash(welcome)
    elif provisioned:
        flash("Welcome! Pick a skill to see live demand and start Day 1 free.")
    else:
        flash("Welcome back — pick a sprint to continue.")
    return redirect(url_for("main.sprints"))


def _render_login(mode="signin", step=None, status=200, email=None,
                  show_sent=False):
    """login.html is the one surface for sign-in, create-account and code entry.

    /auth/signup renders signup.html — a thin shell around the same
    ``_auth_panel.html`` — so every existing link to it stays valid while there
    remains only one form implementation to change. `creating` is passed in
    rather than derived in the template: Jinja discards a top-level {% set %} in
    a child template, so it would never reach the title block.
    """
    creating = mode == "signup"
    template = "signup.html" if creating and step != "code" else "login.html"
    return render_template(
        template,
        mode=mode,
        creating=creating,
        step=step,
        email=email or "",
        masked_email=_mask_email(email or session.get(_OTP_EMAIL) or ""),
        otp_enabled=bool(current_app.config.get("OTP_EMAIL_ENABLED", True)),
        providers=sorted(current_app.config.get("OAUTH_PROVIDERS", set())),
        cooldown_left=_cooldown_left(email or session.get(_OTP_EMAIL)),
        otp_length=int(current_app.config.get("OTP_CODE_LENGTH", 8)),
        show_sent=show_sent,
    ), status


# ── sign-in / create-account surface ─────────────────────────────────────────

@auth_bp.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "") or ""

        if not email:
            # BUG-3: an empty email must ask for the email — never masquerade
            # as "No account found" (which implies the account lookup ran).
            flash("Enter your email address to sign in.")
            return _render_login(status=200, email=email)

        if not password:
            flash("Invalid email or password.")
            return _render_login(status=200, email=email)

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
            return _render_login(status=200, email=email)

        session["user_id"] = uid
        return redirect(url_for("main.sprints"))

    # GET. ?step=code is only honoured when a send actually happened, so the
    # code step can't be conjured by typing a URL (it would be a dead end).
    if request.args.get("step") == "code" and session.get(_OTP_EMAIL):
        return _render_login(step="code", email=session[_OTP_EMAIL])
    return _render_login(mode="signup" if request.args.get("mode") == "signup"
                         else "signin")


@auth_bp.route("/login")
def login_alias():
    """BUG-2: /login is what humans type — forward to the real login surface."""
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/signup", methods=["GET", "POST"])
def signup():
    """Create-account funnel. There is no password to set any more: the account
    springs into existence inside Supabase on the first verified OTP, so this
    route collects the name, remembers it, and asks for a code.

    Design §5.2 deletes the old collision auto-login that sat here — signing up
    with someone's existing address used to drop you straight into their session
    (account and, for admin@, admin takeover).
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("display_name") or "").strip()
        if not _email_is_wellformed(email):
            flash("Enter a valid email address.")
            return _render_login(mode="signup", status=200, email=email)
        if name:
            session[_OTP_NAME] = name
        return _send_code(email)

    # Single surface: /auth/signup shows the login page in create-account mode
    # so existing links and anchors keep working.
    return _render_login(mode="signup")


# ── email OTP ────────────────────────────────────────────────────────────────

def _send_code(email):
    """Ask GoTrue for a code, then show the code step unconditionally.

    The response is deliberately identical whether or not the address is
    registered: `should_create_user=True` means an unknown address gets an
    account, and a known one gets a code — so this endpoint cannot be used to
    enumerate users (design §5.2).
    """
    if not current_app.config.get("OTP_EMAIL_ENABLED", True):
        flash("Sign-in by email code is unavailable right now — use your password.")
        return _render_login(status=200, email=email)

    left = _cooldown_left(email)
    if left:
        # Refuse before sending anything. Same page, no new information.
        flash(f"Please wait {left}s before requesting another code.")
        return _render_login(step="code", status=200, email=email)

    pending_name = session.get(_OTP_NAME)
    try:
        # `data` is applied by GoTrue only when it creates the user, so the
        # signup name lands in user_metadata without a second write.
        options = {"should_create_user": True}
        if pending_name:
            options["data"] = {"display_name": pending_name}
        _auth_client().auth.sign_in_with_otp({"email": email, "options": options})
    except AuthError as exc:
        # Supabase-side failures here are never account-specific (bad syntax,
        # rate limit, SMTP down, signup disabled), so a generic transport error
        # leaks nothing — and telling the truth beats a fake "code sent" that
        # leaves the user staring at an empty inbox. (Deviation from the
        # literal wording of design §5.2; same privacy property.)
        current_app.logger.warning("otp send failed for %s: %s",
                                   _mask_email(email), exc)
        flash("We couldn't send a code just now — please try again in a minute.")
        return _render_login(status=200, email=email)

    session[_OTP_EMAIL] = email
    # Throttle map lives in a signed cookie, so bound it: ~4KB is the browser
    # limit for the whole session, and an unbounded dict would let a spammer
    # POST their way out of their own login state. Keep the recent entries.
    sent = session.get(_OTP_SENT_AT)
    sent = dict(sent) if isinstance(sent, dict) else {}
    sent[email] = int(time.time())
    if len(sent) > 10:
        sent = {k: v for k, v in sorted(sent.items(), key=lambda kv: kv[1])[-10:]}
    session[_OTP_SENT_AT] = sent
    return _render_login(step="code", email=email, show_sent=True)


@auth_bp.route("/auth/otp/send", methods=["POST"])
def otp_send():
    email = (request.form.get("email") or session.get(_OTP_EMAIL) or "").strip().lower()
    # In create-account mode the same form carries the first name; hold it for
    # _complete_auth (and for the metadata of the account GoTrue is about to
    # create) instead of round-tripping it through a hidden field.
    name = (request.form.get("display_name") or "").strip()
    if name:
        session[_OTP_NAME] = name
    if not _email_is_wellformed(email):
        flash("Enter a valid email address.")
        return _render_login(mode="signup" if session.get(_OTP_NAME) else None,
                             status=200, email=session.get(_OTP_EMAIL))
    return _send_code(email)


@auth_bp.route("/auth/otp/verify", methods=["POST"])
def otp_verify():
    if not current_app.config.get("OTP_EMAIL_ENABLED", True):
        # The send path refuses when OTP is off; verify must too, or a bookmarked
        # code step would still be a live login route.
        flash("Sign-in by email code is unavailable right now — use your password.")
        return _render_login(status=200)
    token = (request.form.get("token") or "").strip()
    # The session address is authoritative: it is the one we actually sent to.
    email = session.get(_OTP_EMAIL) or (request.form.get("email") or "").strip().lower()

    if not _email_is_wellformed(email):
        _clear_otp_state()
        return _render_login(status=200)
    if not token:
        flash("Enter the code we sent you.")
        return _render_login(step="code", status=200, email=email)

    try:
        res = _auth_client().auth.verify_otp(
            {"email": email, "token": token, "type": _OTP_TYPE})
    except AuthError:
        # Wrong, expired or already-used code. No session is set, nothing is
        # half-provisioned: the user stays on the code step and may resend.
        flash("That code didn't work — request a new one.")
        return _render_login(step="code", status=200, email=email)

    user = getattr(res, "user", None)
    uid = getattr(user, "id", None)
    if not uid:
        flash("That code didn't work — request a new one.")
        return _render_login(step="code", status=200, email=email)

    meta = getattr(user, "user_metadata", None) or {}
    name = meta.get("display_name") or session.get(_OTP_NAME)
    return _complete_auth(uid, email=getattr(user, "email", None) or email,
                          name_hint=name)


# ── social OAuth (PKCE) ──────────────────────────────────────────────────────

@auth_bp.route("/auth/oauth/<provider>")
def oauth_start(provider):
    """Begin the provider redirect. GET + CSRF-exempt by design: PKCE's code
    verifier, held in this browser's own session cookie, is the CSRF state."""
    provider = (provider or "").strip().lower()
    if provider not in current_app.config.get("OAUTH_PROVIDERS", set()):
        # Not enabled here — same 404 whether the name is nonsense or just off.
        abort(404)
    try:
        res = _auth_client().auth.sign_in_with_oauth({
            "provider": provider,
            "options": {"redirect_to": _callback_url()},
        })
    except AuthError as exc:
        current_app.logger.warning("oauth start failed (%s): %s", provider, exc)
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))
    return redirect(res.url)


def _callback_url():
    return (current_app.config.get("OAUTH_REDIRECT_BASE")
            or request.url_root.rstrip("/")) + \
        current_app.config.get("OAUTH_CALLBACK_PATH", "/auth/oauth/callback")


@auth_bp.route("/auth/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        # Covers user-cancel, provider denial and a stripped query alike.
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))

    try:
        res = _auth_client().auth.exchange_code_for_session({
            "auth_code": code,
            # Empty string is falsy, so the client reads the verifier from
            # FlaskSessionStorage itself (gotrue_client.py:1186). Passing None
            # would do the same but breaks CodeExchangeParams' str annotation.
            "code_verifier": "",
            "redirect_to": _callback_url(),
        })
    except AuthError as exc:
        current_app.logger.warning("oauth exchange failed: %s", exc)
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))

    user = getattr(res, "user", None)
    uid = getattr(user, "id", None)
    if not uid:
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))

    # Same-email linking is Supabase's job, not ours: legacy accounts are
    # email-confirmed, so the provider attaches to the existing user and no
    # duplicate row is created (design §8). Do not add custom link logic.
    meta = getattr(user, "user_metadata", None) or {}
    name = meta.get("full_name") or meta.get("name") or meta.get("display_name")
    return _complete_auth(uid, email=getattr(user, "email", None),
                          name_hint=name or session.get(_OTP_NAME))


@auth_bp.route("/auth/logout")
def logout():
    _clear_otp_state()
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
