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
import re
import time

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, session, url_for)

from supabase_auth.errors import AuthError

from . import obtain_supabase
from services.supabase_client import get_auth_supabase, PKCE_SESSION_KEY

auth_bp = Blueprint("auth", __name__)

# Session keys owned by this module.
_OTP_EMAIL = "otp_email"              # address the last code was sent to
_OTP_SENT_AT = "otp_last_sent_at"     # {address: epoch} of accepted sends (see _cooldown_left)
_OTP_NAME = "otp_pending_name"        # display name captured at the signup funnel
_OTP_NAME_FOR = "otp_pending_name_for"   # the address that name was captured for

# The name is free text that is echoed back into the page and written to
# user_profiles, and the whole session is a signed cookie under a ~4KB browser
# cap — so bound it rather than trusting the input field's maxlength.
_MAX_NAME_LEN = 80

# `verify_otp` type literal, pinned. Measured against real issued codes:
# "email" redeems BOTH token families — a brand-new address gets a
# signup-family token, an existing confirmed account a magiclink-family one.
# The narrower literals are family-specific and mutually exclusive ("signup"
# 403s every legacy login, which spec §8 promises must work; "magiclink" 403s
# every new signup), and GoTrue replies to a valid token of the wrong type with
# the SAME 403 it gives a wrong code — so a typo here is a silent,
# undiagnosable "Invalid code" for 100% of one population. Do not experiment.
#
# PROOF, measured on the live project with one FRESH TOKEN PER LITERAL (so a
# prior success cannot consume the token and fake a later rejection) — see
# docs/superpowers/spikes/spike_verify_type_matrix.py: the minted token really
# IS account-state dependent (first-ever mint for an unknown address =>
# verification_type 'signup'; any mint for an address that already exists =>
# 'magiclink'), and the redeeming literals differ by family — 'signup' redeems
# only the signup family, 'magiclink'/'recovery' only the existing-address
# family, and 'email' redeems BOTH. A single pinned literal is therefore correct
# precisely because this is the one umbrella value; pinning any other would
# break exactly one half of the population with an error byte-identical to a typo.
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


def _token_is_plausible(token):
    """Numeric and exactly ``OTP_CODE_LENGTH`` characters — checked here so junk
    never reaches GoTrue.

    This is abuse-surface, not an auth bypass: a wrong code is still rejected
    upstream. But every attempt that reaches GoTrue spends the project's verify
    rate limit, which on the free tier is shared with real logins, so an
    unbounded string field is a cheap way to lock everyone out. (MAJOR-1, t4.)

    ``[0-9]`` and not ``\\d``: Python's ``\\d`` is Unicode-aware, so look-alikes
    pasted from rich text ("²⁰²⁴") pass it — and ``.isdigit()``/``.isnumeric()``
    have the same hole. ``fullmatch`` also pins the length, which is what makes
    the 4000-char probe impossible.

    Crucially the token is never converted to a number anywhere: about 1 code in
    10 starts with a zero (measured: ``07368987``), and ``int()`` would shave it
    to 7 characters and hard-fail that user's login forever.
    """
    n = int(current_app.config.get("OTP_CODE_LENGTH", 8))
    return bool(re.fullmatch(f"[0-9]{{{n}}}", token or ""))


def _remember_name(raw_name, email):
    """Store the signup name, bounded and tagged with its address.

    The tag matters: without it, a visitor who starts signing up as "Mallory",
    abandons the code step, and later signs in as a different address on the
    same browser would stamp "Mallory" onto that account's profile.
    """
    name = (raw_name or "").strip()[:_MAX_NAME_LEN]
    if name:
        session[_OTP_NAME] = name
        session[_OTP_NAME_FOR] = (email or "").strip().lower()
    return name


def _pending_name(email):
    """The stored name, but only if it was captured for *this* address."""
    name = session.get(_OTP_NAME)
    if not name:
        return None
    return name if session.get(_OTP_NAME_FOR) == (email or "").strip().lower() else None


def _clear_otp_state():
    session.pop(_OTP_EMAIL, None)
    session.pop(_OTP_SENT_AT, None)
    session.pop(_OTP_NAME, None)
    session.pop(_OTP_NAME_FOR, None)


def _clear_pkce_verifier():
    """Drop the PKCE code verifier from the session.

    ``exchange_code_for_session`` only calls ``remove_item`` when the token
    request did *not* raise (gotrue_client.py:1200), so a denied or failed
    exchange otherwise leaves the verifier sitting in the cookie from a flow
    that has already ended — which makes "was the PKCE state consumed?"
    unanswerable from the session later on. (t4 §8.1 / MINOR follow-up.)
    """
    bucket = session.get(PKCE_SESSION_KEY)
    if not isinstance(bucket, dict):
        return
    for key in [k for k in bucket if k.endswith("-code-verifier")]:
        bucket.pop(key, None)
    if bucket:
        session[PKCE_SESSION_KEY] = bucket
    else:
        session.pop(PKCE_SESSION_KEY, None)   # leave no empty dict behind
    session.modified = True


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
        # Password logins must not inherit OTP leftovers either (INFO-3): the
        # pending name and address state belong to a flow this request skipped.
        _clear_otp_state()
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
        if not _email_is_wellformed(email):
            flash("Enter a valid email address.")
            return _render_login(mode="signup", status=200, email=email)
        _remember_name(request.form.get("display_name"), email)
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

    pending_name = _pending_name(email)
    try:
        # `data` is applied by GoTrue only when it creates the user, so the
        # signup name lands in user_metadata without a second write.
        options = {"should_create_user": True}
        if pending_name:
            options["data"] = {"display_name": pending_name}
        _auth_client().auth.sign_in_with_otp({"email": email, "options": options})
    except AuthError as exc:
        # Generic transport error instead of a fake "code sent". ⚠️ READ THE
        # COUPLING BEFORE CHANGING THE DASHBOARD (t4 INFO-1): this branch is
        # enumeration-safe only because every GoTrue failure on /otp is
        # currently address-independent (bad syntax, rate limit, SMTP down).
        # If an operator ever sets disable_signup=true, an UNREGISTERED address
        # starts failing with `otp_disabled` while a registered one still
        # succeeds — and this honest branch becomes a live user-enumeration
        # oracle. The spec's "always show the code step" is the config-proof
        # alternative; switching to it means flipping a T3 assertion that
        # currently pins this message, so it is the captain's call, not mine.
        # Documented for operators in docs/supabase-setup.md §5.
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
    _remember_name(request.form.get("display_name"), email)
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
    if not _token_is_plausible(token):
        # Checked before GoTrue (MAJOR-1) but reported exactly like a wrong code,
        # so the response shape teaches an attacker nothing about the address.
        flash("That code didn't work — request a new one.")
        return _render_login(step="code", status=200, email=email)

    try:
        res = _auth_client().auth.verify_otp(
            {"email": email, "token": token, "type": _OTP_TYPE})
    except AuthError as exc:
        # Wrong, expired or already-used code. No session is set, nothing is
        # half-provisioned: the user stays on the code step and may resend.
        #
        # Logged server-side on purpose: the user-facing message must stay
        # generic and identical for every cause, which makes this line the only
        # way to tell a user typo apart from a broken deployment — e.g. the
        # Magic-link template still on {{ .ConfirmationURL }}, so no numeric code
        # is ever issued and EVERY verify 403s (design §6.4 / t4 G1). Without it
        # that outage is silent and undiagnosable from outside the process.
        # The code itself is never logged.
        current_app.logger.warning(
            "otp verify failed for %s: %s (code=%s status=%s)",
            _mask_email(email), exc, getattr(exc, "code", None),
            getattr(exc, "status", None))
        flash("That code didn't work — request a new one.")
        return _render_login(step="code", status=200, email=email)

    user = getattr(res, "user", None)
    uid = getattr(user, "id", None)
    if not uid:
        flash("That code didn't work — request a new one.")
        return _render_login(step="code", status=200, email=email)

    meta = getattr(user, "user_metadata", None) or {}
    name = meta.get("display_name") or _pending_name(email)
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
    """The OAuth redirect_to, built from config ONLY (t4 MINOR-2).

    Deliberately no `request.url_root` fallback: this value is handed to the
    provider as the destination for an auth code, so letting a Host header
    influence it — even in a branch that today's config can never reach — puts
    a request-controlled string inside an auth redirect. A missing base is a
    deployment error, so it is turned into a 503 instead of a guess. Whatever
    this returns must also be present in dashboard → Auth → URL Configuration →
    Additional redirect URLs, or GoTrue refuses the callback.
    """
    base = (current_app.config.get("OAUTH_REDIRECT_BASE") or "").strip()
    if not base:
        current_app.logger.error("OAUTH_REDIRECT_BASE is unset; refusing to build "
                                 "an OAuth redirect from the request host")
        abort(503)
    return base + current_app.config.get("OAUTH_CALLBACK_PATH", "/auth/oauth/callback")


@auth_bp.route("/auth/oauth/callback")
def oauth_callback():
    # Strip before the truthiness test: `?code=%20` is a *truthy* whitespace
    # string, and without this it would sail into the exchange (BUG-T3-1).
    code = (request.args.get("code") or "").strip()
    if not code:
        # Covers user-cancel, provider denial and a stripped query alike.
        _clear_pkce_verifier()
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
        # The library only removes the verifier when the request did NOT raise,
        # so a failed exchange would otherwise leave it in the cookie.
        _clear_pkce_verifier()
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))

    user = getattr(res, "user", None)
    uid = getattr(user, "id", None)
    if not uid:
        _clear_pkce_verifier()
        flash("Social sign-in didn't complete — try the email code.")
        return redirect(url_for("auth.login"))

    # Same-email linking is Supabase's job, not ours: legacy accounts are
    # email-confirmed, so the provider attaches to the existing user and no
    # duplicate row is created (design §8). Do not add custom link logic.
    # Success: the client already removed the verifier, but that leaves an
    # empty "_sb_pkce" bucket in the cookie; drop it so the session carries no
    # auth scratch state once the flow is done.
    _clear_pkce_verifier()

    meta = getattr(user, "user_metadata", None) or {}
    email = getattr(user, "email", None)
    name = meta.get("full_name") or meta.get("name") or meta.get("display_name")
    return _complete_auth(uid, email=email,
                          name_hint=name or _pending_name(email))


@auth_bp.route("/auth/logout")
def logout():
    _clear_otp_state()
    _clear_pkce_verifier()
    session.pop("user_id", None)
    return redirect(url_for("main.index"))
