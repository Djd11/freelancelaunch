# Spike T1 — PKCE storage protocol + OTP verify literals (finished)

- **Date:** 2026-09-15
- **Task:** T1 (spike finish + `config.py` + `services/supabase_client.py`)
- **Design:** `docs/superpowers/specs/2026-09-15-passwordless-otp-social-login-design.md` §5.1, §9 (pre-impl spike), §11
- **Verdict:** **Both open questions are settled. §5.1/§5.2 are cleared to build**, with
  two corrections to the design text (§4 below) and five traps that would otherwise
  have cost days.

## 0. Environment of record

Everything below was measured against **this** venv, not inferred from docs.

| | |
|---|---|
| interpreter | `.venv/bin/python` — **Python 3.12.3** |
| package root | `.venv/lib/python3.12/site-packages/supabase_auth/` |
| `supabase` / `supabase-auth` | **2.31.0 / 2.31.0** (matches `requirements.txt:4` pin `supabase==2.31.*`) |
| Flask | 3.1.3 |
| live project | `https://tzfohwzgxlecsilvqmjq.supabase.co` (GoTrue reachable; service-role key in scope) |

Reproduce with:

```bash
.venv/bin/python docs/superpowers/spikes/spike_static.py         # offline introspection
.venv/bin/python docs/superpowers/spikes/spike_live.py           # storage/PKCE/live errors
.venv/bin/python docs/superpowers/spikes/spike_otp_roundtrip.py  # real code round-trip
```

## 1. Q1 — the storage protocol: import path **and** exact interface

**There is no `_storage.py`.** The design's §5.1 hedge ("import path to be pinned in impl
spike; duck-typed otherwise") resolves to a public, stable import:

```python
from supabase_auth import SyncSupportedStorage          # ← use this (package-root re-export)
# canonical definition: supabase_auth/_sync/storage.py:7  (module `supabase_auth._sync.storage`)
```

The interface is an **ABC**, not a `Protocol` — and its methods are **not**
`get`/`set`/`delete`:

```python
class SyncSupportedStorage(ABC):
    @abstractmethod
    def get_item(self, key: str) -> Optional[str]: ...
    @abstractmethod
    def set_item(self, key: str, value: str) -> None: ...
    @abstractmethod
    def remove_item(self, key: str) -> None: ...
```

> ⚠️ **Trap #1 — this is the one that would have burned a day.** The design §5.1 describes
> the class as *"dict get/set/delete keyed by the client's `storage_key`"*. A
> `get/set/delete` class satisfies no part of this contract. It fails **loudly, not
> silently**: `SyncGoTrueClient.__init__` accepts it (no validation), then the first
> `sign_in_with_oauth` raises `AttributeError: 'FlaskSessionStorage' object has no
> attribute 'set_item'`. Duck-typing is therefore *fine as a technique* — the client only
> ever calls those three methods — but the **method names must be** `get_item`/`set_item`/
> `remove_item`. Subclassing the ABC is free and makes a wrong name unimportable, so
> `services/supabase_client.py` does that.

**Keys the client actually touches** (all 6 call sites, grepped out of
`_sync/gotrue_client.py`; `STORAGE_KEY = "supabase.auth.token"`, `constants.py:9`):

| call site | key | reached under our options? |
|---|---|---|
| `set_item` `gotrue_client.py:1175` | `supabase.auth.token-code-verifier` | ✅ the only write we get |
| `get_item` `gotrue_client.py:1186` | `supabase.auth.token-code-verifier` | ✅ on exchange |
| `remove_item` `gotrue_client.py:1200` | `supabase.auth.token-code-verifier` | ✅ after exchange |
| `set_item` `gotrue_client.py:1103` | `supabase.auth.token` (session JSON) | ❌ guarded by `persist_session` |
| `get_item` `gotrue_client.py:655` / `:1037` | `supabase.auth.token` | ❌ guarded by `persist_session` |
| `remove_item` `gotrue_client.py:977` | `supabase.auth.token` | ❌ `_remove_session` branches on `persist_session` (`:975-979`) |

Verified empirically — with `persist_session=False` the *entire* storage log for a PKCE
start is one line, exactly as predicted:

```
storage calls during PKCE authorize: [('set', 'supabase.auth.token-code-verifier')]
flask.session['_sb_pkce'] keys:      ['supabase.auth.token-code-verifier']
stored code_verifier length: 64   RFC 7636 unreserved charset only: True
# NOT base64url: generate_pkce_verifier (helpers.py) draws from
# ascii_letters + digits + "-._~", so '.' and '~' can appear. All are
# unreserved/cookie-safe; my first probe mislabelled this as "urlsafe base64".
authorize url: .../auth/v1/authorize?redirect_to=…&code_challenge=…&code_challenge_method=s256&provider=google
```

**Consequence for §5.1:** `persist_session=False` + `auto_refresh_token=False` is not just
hygiene — it is what keeps a Supabase **refresh token** out of the Flask cookie (the app's
session contract is `session["user_id"]` only) and keeps the storage object single-purpose.
`_save_session` with `persist_session=False` writes to `self._in_memory_session` instead
(`gotrue_client.py:1089-1091`), which is per-request and dies with the request.

> ⚠️ **Trap #2 — nested-dict mutation silently loses the verifier.**
> `flask.session` is signed; mutating a dict *inside* it does not set `session.modified`,
> and Flask 3.1's `SecureCookieSessionInterface.save_session` then skips `Set-Cookie`. The
> verifier written on `/auth/oauth/<provider>` would never reach the browser, and the
> callback would die with `invalid flow state` (see §3.4) with no clue why.
> `FlaskSessionStorage` therefore **reassigns the whole sub-dict** and sets
> `session.modified = True` explicitly.

**Security note (why Flask's *client-side* cookie is acceptable storage here):** the
verifier is the PKCE CSRF secret and only ever needs to survive a round-trip through the
*same browser*. It rides a cookie that is `HttpOnly` + `SameSite=Lax` + `Secure` in prod
(`config.py:20-23`), so page JS can't read it; an attacker who steals the cookie already
owns the session. No server-side store, no extra infra — consistent with the $0 constraint.

## 2. Q2 — `verify_otp` accepted `type` literals

**Client side** (`supabase_auth/types.py:48`, the whole union `VerifyOtpParams` at
`types.py:486`):

```python
EmailOtpType = Literal["signup", "invite", "magiclink", "recovery", "email_change", "email"]
VerifyEmailOtpParams: {email: str, token: str, type: EmailOtpType, options?: {...}}
VerifyTokenHashParams: {token_hash: str, type: EmailOtpType, options?: {...}}
VerifyMobileOtpParams: type: Literal["sms", "phone_change"]      # phone only
```

`"email"` is legal and **`"sms"` is not an option for email** — it exists only on the phone
branch, which §14's phone-ready shape must use later.

**Server side — the literal is load-bearing, so it was tested for real.** `verify_otp`
needs a live code, and this project has **no SMTP configured**, so the inbox route was
unavailable. It turned out not to be needed: `POST /auth/v1/admin/generate_link`
(service role) mints the confirmation token *and returns the numeric code in the JSON body*
(field `email_otp`), so a real code can be verified without sending any email. One fresh
token per literal (see trap #3 for why that matters):

| # | fresh token | `verify_otp` literal | result |
|---|---|---|---|
| A | yes | **`"email"`** | ✅ **SUCCESS** — session issued, `email_confirmed_at` set |
| B | yes | `"magiclink"` | ❌ `AuthApiError` code=`otp_expired` status=403 |
| C | yes | `"signup"` | ✅ SUCCESS (also accepted) |

**Answers to the two questions that gated §5.1/§5.2:**

1. **`type: "email"` is correct as specified** — it is the literal that verifies an
   email-OTP code, and the design's call shape needs no change.
2. **It is not interchangeable.** An unused `magiclink` token is *rejected* for
   `type="magiclink"`, so the server does discriminate; do not "helpfully" switch the
   literal when a verify fails. Note the flip side: GoTrue accepted `type="signup"` too
   (its email-verification lookup treats signup/email OTPs alike), so `"email"` is the
   narrow, intended choice — keep it.

> ⚠️ **Trap #3 — an OTP is single-use, which fakes a control.** My first run verified with
> `type="email"` and *then* re-used the same token for the `magiclink` control: both
> "wrong literal" cases returned `otp_expired`, which looked like proof of strict typing
> but proved nothing (the token was already consumed). Every literal needs its own
> throwaway address + token. `spike_otp_roundtrip.py` (v2) is written that way.

## 3. What T2 needs to know that the design states slightly wrong

### 3.1 ⚠️ OTP codes on this project are **8 digits**, not 6

The design §6.4 says `{{ .Token }}` yields a "6-digit code". Measured on the live project,
`email_otp` was `84102443`, `37796056`, `32464751`, `26752099` — **8 digits, every time**.

Consequences: code-entry `maxlength`/`pattern` and every test fixture must assume the
project's OTP length, not 6. `Config.OTP_CODE_LENGTH` (default 8) now carries this so T5
doesn't hardcode it. Dashboard: *Authentication → One-time tokens → OTP length*.

### 3.2 `sign_in_with_otp` — `should_create_user` must be **inside `options`**

The email branch builds a **strict allow-list body** (`gotrue_client.py:526-545`):

```python
body = {"email": …, "data": …, "create_user": should_create_user,
        "gotrue_meta_security": {"captcha_token": …}}   # + redirect_to as a QUERY param
```

A top-level `"create_user"` key is **silently ignored** (only `options` is read). It also
defaults to `True` already (`:531`), so passing `{"options": {"should_create_user": True}}`
is belt-and-braces explicit — which is what we want for a signup surface. Design §4's
pseudo-call `sign_in_with_otp({email, options:{should_create_user:true}})` is **correct**.

`AuthOtpResponse` fields: `user`, `session`, `is_signup_enabled`, `user_id`. On a successful
send, `session` is **None** (no login happened yet) — T2 must not treat "no session" as
failure. `is_signup_enabled` is the field that tells you whether a new address was accepted.

### 3.3 `exchange_code_for_session` — the explicit `code_verifier` arg is optional

Design §4 passes `code_verifier` explicitly. Measured: with `code_verifier=None` the client
**falls back to storage itself** (`gotrue_client.py:1186-1188`), and the fallback fired
correctly through `FlaskSessionStorage`:

```
None verifier (storage fallback) → AuthApiError: 'invalid flow state, no valid flow state found' status=404
storage log: [('set', 'supabase.auth.token-code-verifier'), ('get', 'supabase.auth.token-code-verifier')]
```

That `get` after the `set` is the proof the whole plumbing works. Recommended shape for T2:
let the client read its own verifier (one less place to get it wrong).

> ⚠️ **Trap #4 — typing.** `CodeExchangeParams` (`types.py:564-577`) declares all three keys
> **required, `code_verifier: str`** (no `NotRequired`). Omitting it or passing `None` is
> correct at *runtime* (just proven) but a static type-checker will flag it. Add
> `# type: ignore[typeddict-item]` at the call site rather than re-plumbing to satisfy it.

### 3.4 Failure strings to expect (so T6/tests assert the right thing)

| situation | exception | code / status | message |
|---|---|---|---|
| valid email, syntax ok, user absent + `should_create_user=False` | `AuthApiError` | `otp_disabled` / 400 | `Signups not allowed for otp` |
| rejected email syntax | `AuthApiError` | `email_address_invalid` / 400 | `Email address "…" is invalid` |
| wrong/expired code | `AuthApiError` | `otp_expired` / 403 | `Token has expired or is invalid` |
| exchange with bad/used `auth_code` | `AuthApiError` | — / 404 | `invalid flow state, no valid flow state found` |

**Ordering gotcha (trap #5):** with `should_create_user=False` GoTrue answers
`otp_disabled` **before** validating the address, but with `True` it validates first. So
`otp_disabled` does *not* mean "signup is off" — read §5 before concluding anything.
All of these stay inside the `AuthError` family that `routes/auth.py` already catches, so
the generic-error flash contract (§5.2 "never reveal whether an email exists") holds.

## 4. Live dashboard state measured today (input for T4 — do not re-derive)

From `GET /auth/v1/settings` (anon):

| setting | value | meaning |
|---|---|---|
| `external.email` | `True` | email provider on → OTP send/verify can work |
| `external.google` | **`False`** | ⛔ Google button will fail until §6.2 of the design is done |
| `external.facebook` | **`False`** | ⛔ same, plus Meta review (§6.3) |
| `external.phone` | `False` | as designed (non-goal) |
| `site_url` | **`None`** | ⛔ §6.1 not done — OAuth callback origin unconfigured |
| `uri_allow_list` | **`None`** | ⛔ redirect allow-list empty → OAuth `redirect_to` rejected |
| `disable_signup` | `False` | ✅ new accounts may be created by OTP |
| `mailer_autoconfirm` | `False` | ✅ verification really is enforced (not the `acfbb9b` state) |
| `smtp_admin` | `None` | ⛔ no custom SMTP → built-in ~2/hr, i.e. OTP is **not usable in prod yet** |

`_request` returns a **raw httpx `Response`**, not a dict — `.json()` it (a probe that
assumed a dict raised `AttributeError: 'Response' object has no attribute 'get'`).

**The spike therefore proves the *code* paths end-to-end but says nothing about email
*delivery*:** SMTP + the `{{ .Token }}` template (design §6.4, §6.6) remain the gating,
out-of-repo work, exactly as `acfbb9b` taught. Until then `otp_send` will return success
while no mail arrives — the UI must therefore never imply "we sent you an email" as a
promise. (Consider copy like "If that address is registered, a code is on its way.")

## 5. What changed in the repo as part of T1

- **`config.py`** — `OTP_EMAIL_ENABLED` (`_env_bool`, default true), `OAUTH_PROVIDERS`
  (validated lowercase **set**, default `google,facebook`, unknown names dropped via
  `OAUTH_PROVIDER_ALLOW_LIST`), `PUBLIC_BASE_URL` + `OAUTH_REDIRECT_BASE` +
  `OAUTH_CALLBACK_PATH`, `OTP_RESEND_COOLDOWN_SECONDS` (60), `OTP_CODE_LENGTH` (8).
  Verified matrix: `'GOOGLE,Facebook'` → `{facebook, google}`; `'google,facebook,github'`
  → github dropped; `''` → `set()` (deliberate opt-out); `OTP_EMAIL_ENABLED` `'garbage'`/
  `'0'`/`'false'` → False, unset/blank → True.
- **`services/supabase_client.py`** — `FlaskSessionStorage` (ABC subclass, trap #2-safe),
  `get_auth_supabase()` (anon + `flow_type="pkce"` + `persist_session=False` +
  `auto_refresh_token=False`, cached on `g.auth_supabase`), `auth_supabase` registered in
  `close_request_clients()`, `_new_client(url, key, options)` (lazy `create_client` import
  **kept** so `patch("supabase.create_client")` in the existing tests still works).
  ⚠️ `ClientOptions` is the exported alias — **`from supabase import SyncClientOptions`
  raises `AttributeError`.**
- **Drive-by fix (veto-able):** `get_client_supabase()` read only
  `config["SUPABASE_ANON_KEY"]`, which `Config` never defines (`from_object` publishes
  `SUPABASE_KEY`) — so it raised `RuntimeError` on a *fully configured* project and
  `obtain_supabase(client=True)` would 503. Latent today (no route passes `client=True`),
  but it is the exact key-lookup trap that `get_auth_supabase()` would have inherited;
  now accepts both spellings like the service-role pair.
- **`.env.example`** — documented `OAUTH_PROVIDERS` / `OTP_EMAIL_ENABLED` (+ the two
  optional tuning vars), stating plainly that provider secrets, SMTP and the OTP template
  live in the dashboard, not here.
- **`render.yaml` untouched** (design §5.3: no new secrets).
- **`docs/supabase-setup.md`** — new §5–§6: the dashboard checklist from design §6 made
  operational, with today's measured values as the "before" picture.

## 6. Test-data ledger (live project)

Created and **deleted** by these spikes: 6 throwaway `auth.users` rows
(`spike.*@sprintspike-otp.dev`, one of them confirmed by a successful verify):
`badb8e02…`, `f4416a4a…`, `b4675dee…`, `9b9ad183…`, `08fe85a6…`, `081086cd…`.
`admin.list_users()` after cleanup = **3** — `admin@`, `demo@`, `other@sprint-platform.local`,
i.e. the seed set, unchanged.

**Incident (self-reported, then CORRECTED after the captain challenged my conclusion):**
the first cleanup pass used an over-broad filter (`email contains "spike" OR endswith
"@example.com"`) and deleted two accounts it did not create —
`uat.user.1788795034@example.com` (`11c3e099…`) and `live_qa_1788762183@example.com`
(`cdb275ae…`).

My first impact report claimed "**0** rows in `user_profiles` and `sprints` for both, so no
application data was lost". **That claim was wrong, and the error was methodological:** I
queried *after* my own deletes. Every `user_id` FK in this schema is
`REFERENCES auth.users(id) ON DELETE CASCADE` (`db/schema.sql:111` for `sprints`), so a
post-hoc count reads 0 whether the rows never existed **or** were removed by my delete. The
check measured the damage, not the prior state — the same single-use-token confound I had
just caught in §2's controls, repeated here.

Re-established by elimination, not by a direct observation (a cascade leaves nothing to
query):

| evidence | source |
|---|---|
| `sprints.user_id → auth.users ON DELETE CASCADE`; cascade closure reaches **14 tables** (`user_profiles`, `user_momentum`, `user_platforms`, `sprints` → `sprint_days`, `copywork_projects`, `proposals`, `contracts`, `badges`, `case_studies`, `capstone_briefs`, `verification_reviews`, `sprint_unlock_snapshots`, `mentor_sessions`) | `db/schema.sql` |
| The 2026-09-05 pre-purge dump holds 28 sprints; **`1709bde9…` is not among them**, and neither deleted UUID nor either email appears in any dumped table ⇒ all three post-date the purge | `db/backups/pre_purge_20260905_082131.json` |
| The addresses' embedded epochs decode to **2026-09-07** (15:30 / 06:23 UTC) — 2 days after the purge, 8 days before my delete | email strings |
| Live `sprints` is now exactly the **3** kept demo sprints (all owned by `admin@`), and no other mechanism for removing a 09-07 sprint is evidenced: `purge_prelaunch_junk.py` ran once (its backups prove `--apply`), and no UAT/dogfood harness performs any cleanup (`delete_user`/`.delete()` grep is empty) | live query + grep |

**Honest conclusion:** `1709bde9-e7e8-4785-b749-bac6a1efae34` — the sprint the captain
created for `uat.user.1788795034@…` and completed Day 1 on — was almost certainly still
present at 2026-09-15 19:16 and was **removed by my `delete_user` via FK cascade**, together
with its `user_profiles` row and its `sprint_days`/progress children. The impact is confined
to stale synthetic UAT data (no real user, no kept demo sprint), and it is not recoverable
from the local backups because it post-dates them; only a Supabase point-in-time restore
would bring it back, which is not worth a restore for a throwaway fixture.

**Rule adopted for this team (captain's instruction, applies to every agent):** no
bulk/substring delete filters against the live project, ever. Deletes are restricted to
explicitly enumerated ids created by your own run; anything matching a purge list is left in
place and reported instead of removed. The committed spike scripts already comply — the only
`delete_user` loop iterates ids appended to `MADE` in-run — and the violating filter lived
in an uncommitted ad-hoc command. **Snapshot the tables you are about to affect *before*
mutating**, so impact can be stated from evidence rather than inferred afterwards.

Anyone holding a fixture with those two UUIDs baked in should regenerate them.


> **For UAT (T4/T5):** pick throwaway addresses that GoTrue **accepts**. Measured rejects:
> `@sprint.invalid`, `@example.com`, `@example.org` (reserved domains →
> `email_address_invalid`) — and a reserved TLD also means `sign_in_with_otp` can never
> create the account, so `@…invalid` is unusable for OTP tests. `@sprintspike-otp.dev`
> worked (unregistered label ⇒ undeliverable, but syntactically valid).

## 7. Remaining unknowns (honest scoping)

1. **Delivery** — whether the Brevo/Resend SMTP + `{{ .Token }}` template are in place.
   Not testable from code; gates any *manual* code round-trip (T4).
2. **Google/Facebook round-trip** — the code path is proven; the *provider* path needs
   `site_url` + allow-list + enabled providers (all measured off today, §4). Expect
   `invalid flow state` / a rejected `redirect_to` until then, and note that error is
   indistinguishable from a verifier loss, so check the dashboard first.
3. **`"email"` vs `"signup"` acceptance** (§2, row C) suggests GoTrue's lookup is aud-
   based; harmless, but if a future project sets a different `aud`, prefer `"email"`.

## 8. Queued for T5 (found after T1/T2 shipped; nothing here changes §1–§5's verdicts)

1. **Clear the PKCE verifier on every `oauth_callback` failure branch.** `remove_item` on the
   verifier only runs if the token request did *not* raise
   (`_sync/gotrue_client.py:1200`), so a denied/failed exchange leaves
   `session["_sb_pkce"]` populated — reproduced: `GET /auth/oauth/callback?code=bad` → 302
   with `{'supabase.auth.token-code-verifier': …}` still in the cookie. Self-heals on the
   next sign-in (same key is overwritten), so it is hygiene, not a login breaker — but it is
   residue from a finished flow and it makes "was PKCE state consumed?" unanswerable later.
   Clear it on logout too.
2. **No server-side validation of the `token` field.** `"abc"` or a 4 KB string is forwarded
   to GoTrue, which spends the project's verify rate-limit budget on junk. Add a
   `^[0-9]{1,OTP_CODE_LENGTH}$` check (regex, *not* `isnumeric()` — that accepts superscript
   digits from pasted rich text). Must keep leading zeros intact: `"07368987"` is a valid
   code (~1 in 10) and any `int()` coercion truncates it to 7 chars and hard-fails ~10% of
   logins — the exact bug security-reviewer predicted. Current code is verified clean
   (string end to end, asserted in `verify_t2_auth_routes.py`).
3. **An abandoned signup leaves `session["otp_pending_name"]` behind**, so a later login for
   *a different address* on the same browser can pick up the stale name as its display_name.
   Cosmetic/privacy nit, not an auth bypass. Fix: bind the pending name to the address it was
   captured for and ignore it unless the emails match.
4. **Pre-existing (outside this spec): the two original clients arm a daemon refresh timer.**
   Measured: `_save_session` → `_start_auto_refresh_token` arms `threading.Timer`
   (daemon) at ≈3590 s; forced to fire early it fired at 1.84 s. `auto_refresh_token=False`
   is what prevents arming — `persist_session` alone does not. Consequence per login: a
   request-scoped client **plus a valid refresh token** is retained in that closure for ~1 h,
   and the eventual refresh against the already-closed httpx client is **silently swallowed**
   (`gotrue_client.py` catches all exceptions and only retries `AuthRetryableError`), so it
   never surfaces in logs. Harmless to this app's auth model (the session contract is
   `session["user_id"]`, the Supabase session is never used) — which is why it survived
   unnoticed. Fix by passing `persist_session=False, auto_refresh_token=False` for all three
   clients. Blast radius checked: `tests/test_supabase_client.py` asserts only positional
   `call_args[0]`, so adding an `options` argument is safe.
5. **Stale comment** at `routes/auth.py:29` — still says "epoch of the last accepted send"
   since the throttle became a per-address map.

6. **BUG-T3-1 (from qa-eng's T3 suite, `tests/test_auth_otp.py:505`, currently `xfail`):**
   `oauth_callback` tests the **raw** `request.args.get("code")`, so a whitespace-only code
   (`?code=%20`) is truthy and reaches `exchange_code_for_session`. Unreachable against real
   GoTrue (it rejects whitespace codes with `AuthError`), so it is robustness only; fix is
   `code = (request.args.get("code") or "").strip()` in the same failure branch as item 1.
   Left unfixed deliberately while T3 was in flight so qa-eng's `xfail` stays honest — **T5
   owns the flip** (per their note in 2269139), and the marker should become a normal assert.

### Status after T5 (t4 verdict: REQUEST-CHANGES on MAJOR-1 only)

| item | state |
|---|---|
| 1 verifier residue on failed exchange | **fixed** — `_clear_pkce_verifier()` on all three failure branches, the no-code branch, the success branch (drops the empty bucket) and logout |
| 2 token validation | **fixed** — `_token_is_plausible()` = `re.fullmatch("[0-9]{OTP_CODE_LENGTH}")` before GoTrue; `[0-9]` not `\d` (Unicode), reported via the same generic message so it teaches nothing |
| 3 stale `otp_pending_name` | **fixed** — name now tagged with `otp_pending_name_for` and only consumed for a matching (case-folded) address; length capped at 80. `otp_pending_name` stays a **plain string** so T3's assertions hold |
| 4 refresh timer on legacy clients | **fixed** in 5ee0009 (amendment #3) — `_no_client_side_session()` on all three; measured: no timer armed on any of them |
| 5 stale comment at `:29` | **fixed** (throttle map documented as `{address: epoch}`) |
| 6 BUG-T3-1 whitespace `code` | **fixed** — `(request.args.get("code") or "").strip()`; qa-eng's `xfail` flipped to a normal assert (it was xpassing) |
| t4 MINOR-2 Host fallback | **fixed** — `_callback_url()` is config-only, `abort(503)` when unset, never `request.url_root` |
| t4 MINOR-3 DRY | **fixed** — `_anon_key_from_config()` / `_url_and_anon_key()`; documented that the fallback cannot reach the service key |
| t4 INFO-3 password path | **fixed** — `login()` now calls `_clear_otp_state()` |
| t4 INFO-1 send-failure oracle | **comment + operator doc only** — collapsing the branch to spec-literal would flip `tests/test_auth_otp.py:249`, which pins the current message and belongs to T3, so it is escalated to the captain rather than rewritten unilaterally |
| t4 INFO-2 attacker-resettable cooldown | **documented as accepted risk** with the operator line the reviewer drafted (§"Two dashboard settings") |
| t4 INFO-4 promote spike scripts to tests/ | left for **T6** (qa-eng owns the suite) |
| t4 INFO-5 dead `Config.ADMIN_EMAIL` | untouched — spec §5.5 known-cleanup item, out of scope |
| t4 "magiclink is REJECTED" wording | **corrected** in this doc §2 and in `routes/auth.py`: that was one token *family*; `"email"` is the umbrella that redeems both |

Evidence: `verify_t2_auth_routes.py` §9 (junk tiers never reach GoTrue, leading-zero
still verbatim, padded-valid accepted, verifier cleared on every branch, name not
cross-applied, password path cleans leftovers, unset base → 503 with the Host header
unused). Suite: **199 passed, 0 xfail/xpass**, 1 pre-existing mentor-grounding failure.

## 8b. Provenance chain for `type="email"` (captain's t2 citation request)

Three independent measurements converge, so this is recorded once rather than
argued per task:

| source | what it measured | result |
|---|---|---|
| this doc §2 (`docs/superpowers/spikes/spike_otp_roundtrip.py`) | true **signup-family** token (first-ever mint creates the user) | `email` ✅ · `signup` ✅ · `magiclink` ❌ |
| `docs/compare/spike_answers.md` §4b (security-reviewer) | real tokens of both families | `email` redeems both; `signup` and `magiclink` each reject one |
| `docs/superpowers/spikes/spike_verify_type_matrix.py` (§9 below) | both families, **one fresh token per literal** | `email` is the ONLY literal in the intersection |

Convergent conclusion: **`"email"` is the umbrella literal and the only safe pin**;
`signup` breaks existing/legacy accounts (the population design §8 promises OTP
login for) and `magiclink`/`recovery` break new signups — each with a 403 byte-identical
to a user typo, which is why the pin is documented at the code site
(`routes/auth.py`, `_OTP_TYPE`) and guarded by an exact-payload assertion in
`tests/test_auth_otp.py`. The captain's earlier "accept multiple literals"
robustness mandate was retired once these three agreed.

⚠️ Provenance caveat: `docs/compare/spike_answers.md` and the `docs/security/`
probes it cites are **untracked** as of this writing (`git status` shows
`?? docs/compare/`), so this table's middle row does not survive a clean
checkout. Its owner or the captain should commit them before t7/t10 rely on them.

## 9. The literal question, settled definitively (T5 escalation, captain's G1)

The design risk escalated to me: GoTrue mints an **account-state-dependent** token
type, so a verify route pinned to one literal might reject validly-issued codes for
one half of the population. That premise is **correct** — and the conclusion the
escalation feared is not. Measured on the live project with one fresh token per
literal (`docs/superpowers/spikes/spike_verify_type_matrix.py`):

| `verify_otp` literal | signup-family token<br>*(first-ever mint, creates the user)* | magiclink-family token<br>*(mint for an address that already exists)* |
|---|---|---|
| **`"email"`** | ✅ **OK** | ✅ **OK** |
| `"signup"` | ✅ OK | ❌ 403 `otp_expired` |
| `"magiclink"` | ❌ 403 `otp_expired` | ✅ OK |
| `"recovery"` | ❌ 403 `otp_expired` | ✅ OK |

*(`verification_type` reported by `generate_link`: `'signup'` for the first-ever mint
on an unknown address, `'magiclink'` once the address exists — 8-digit codes in
both cases.)*

**`"email"` is the only literal that redeems both families.** Pinning any other
value breaks exactly one half of the population — and, per the reviewer's point,
with an error byte-identical to a user typo. So the single pinned literal is kept,
*with* proof rather than by assumption. This also reconciles my §2 table with
security-reviewer's T8 matrix, which looked contradictory: §2 measured a true
signup-family token (where `magiclink` genuinely 403s), while the follow-up pass
that appeared to disagree was unknowingly measuring magiclink-family tokens because
its own probe call created the user first. Both observations were right; one label
was wrong.

Why the alternatives in the escalation were not taken:
- **Derive the type from the send response** — not possible: `AuthOtpResponse`
  exposes only `user / session / is_signup_enabled / user_id` (measured §3); there
  is no `verification_type` on the /otp response. Only the *admin* `generate_link`
  body carries it, and the app must not use an admin call per sign-in.
- **Accept the set of literals** — the working set is `{email, magiclink,
  recovery}` for one family and `{email, signup}` for the other; a retry chain
  means 2–3 GoTrue verify calls per *typo*, spending the shared free-tier verify
  quota, to defend a case the matrix shows does not exist.
- **Fall back to `token_hash`** — that is the magic-link path (needs a hash from a
  clicked URL); with a code-entry UX the only thing the user possesses is the
  numeric code + their email, which is the `{email, token, type}` shape.

**The residual G1 risk is real but is NOT a literal problem:** with the default
Magic-link template (`{{ .ConfirmationURL }}`) GoTrue never sends a numeric code at
all, so *every* verify 403s and the UI can only say "that code didn't work" — silent
and undiagnosable. Since the user-facing message must stay generic, the fix is
server-side observability: `otp_verify` now logs the GoTrue error code + status with
the masked email (never the code), which is what makes a template/dashboard outage
distinguishable from user typos in the logs. Design §6.4 / setup §5 item 5 remain
the actual remedy, and they are operator actions, not code.

Uncovered by any of this, stated plainly: a code that has actually travelled through
an inbox. That needs custom SMTP + the `{{ .Token }}` template configured (t4/T7) —
`generate_link` is a proxy for the *minting* path (same code, different delivery),
not for delivery itself.
