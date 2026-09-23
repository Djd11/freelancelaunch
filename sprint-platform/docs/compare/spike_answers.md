# Spike answers — storage protocol, PKCE, `verify_otp` type literals

Branch `feature/passwordless-otp-social-login`. Verdicts for spec §10 item 1
("storage protocol import path + `verify_otp` accepted `type` literals"), which
§5.1/§5.2 gate on.

All claims below were **executed against the pinned venv** (`supabase-auth 2.31.0`,
`supabase-py 2.31.0`), not read off the spec. Reproduce with:

```
.venv/bin/python docs/security/spike_pkce_storage_and_otp_types.py
```

`docs/security/spike_pkce_storage_and_otp_types.py` mutates no state: the storage
part is pure local (`sign_in_with_oauth` only builds a URL and writes the verifier —
it makes **no** HTTP call), and the live part calls `/auth/v1/verify` with a bogus
token, which sends no email, creates no user and spends no SMTP quota.

---

## 1. `SyncSupportedStorage` method names — spec §5.1 is WRONG

The library calls `get_item` / `set_item` / `remove_item`. The spec describes
`get`/`set`/`delete`.

```
SyncSupportedStorage.__abstractmethods__ == ['get_item', 'remove_item', 'set_item']
```

**Exact signatures** (`supabase_auth/_sync/storage.py:7-15`):

```python
get_item(key: str) -> Optional[str]
set_item(key: str, value: str) -> None
remove_item(key: str) -> None
```

**Exact import path:** `from supabase_auth import SyncSupportedStorage`
(top-level re-export; real module `supabase_auth._sync.storage`).

### Measured failure modes for the spec's shape

| `FlaskSessionStorage` shape | Result |
|---|---|
| duck-typed `get`/`set`/`delete` | `AttributeError: 'SpecShapedDuck' object has no attribute 'set_item'` |
| `SyncSupportedStorage` subclass with `get`/`set`/`delete` | `TypeError: Can't instantiate abstract class SpecShapedSubclass without an implementation for abstract methods 'get_item', 'remove_item', 'set_item'` |
| duck-typed `get_item`/`set_item`/`remove_item` | **works** — verifier stored |
| `SyncSupportedStorage` subclass with `get_item`/`set_item`/`remove_item` | **works** — verifier stored |

Both failures are deferred to request time, not import time: the duck-typed one
raises inside `GoTrueClient._get_url_for_provider` on the **first click of the
Google button**, the subclass one on the first request that builds the auth client.

### Why it is not caught earlier (this is the trap)

`SyncClientOptions.storage` *does* exist — `supabase/lib/client_options.py:115`:

```python
storage: SyncSupportedStorage = field(default_factory=SyncMemoryStorage)
```

…but `ClientOptions` is a plain `@dataclass`, **not** a pydantic model, so there is
**no runtime `isinstance` validation**. A wrongly-named duck type constructs
happily and fails later. **Subclass `SyncSupportedStorage` anyway** even though
duck typing is permitted: it costs nothing and converts a silent 500-at-first-click
into an import-time error.

## 2. What PKCE actually writes into `flask.session`

Measured key, from `supabase_auth/constants.py` (`STORAGE_KEY = "supabase.auth.token"`)
plus the `f"{self._storage_key}-code-verifier"` format string at
`_sync/gotrue_client.py:1175`:

```
supabase.auth.token-code-verifier    ->  64-char verifier   (only key written)
```

- Exactly **one** key lands in storage after `sign_in_with_oauth` when
  `persist_session=False`: `_save_session` (`:1090`) skips
  `set_item(storage_key, ...)` unless `persist_session` is on, so the session JSON
  never enters the cookie. Cookie growth ≈ 100 bytes against the ~4 KB budget.
- `storage_key` is **not** configurable through `create_client()` — it is a
  `GoTrueClient` ctor param that `create_client` never passes. Do not design around
  a custom key.
- `exchange_code_for_session` (`:1185`) reads that same key as a fallback when
  `code_verifier` is not supplied, then `remove_item`s it (`:1200`).
- **Caveat:** `remove_item` is only reached if `_request` did not raise. A denied or
  failed exchange leaves a stale verifier in the session. Single key, overwritten on
  the next attempt, so no unbounded growth — but `oauth_callback` should clear it in
  its failure branch too.

### Fixation property to assert in review (t4 item 5)

Because the verifier lives in `flask.session` under one fixed key, it is bound to the
same browser session that redeems it — **provided `FlaskSessionStorage` has no
non-session fallback store**. A module-level dict used to "survive" a missing request
context would let an attacker seed a verifier that a later victim callback redeems →
account takeover. Test: two concurrent test clients in one process, assert verifier
isolation.

## 3. `verify_otp` accepted `type` literals (static)

`supabase_auth/types.py:48-50`:

```python
EmailOtpType = Literal["signup", "invite", "magiclink", "recovery", "email_change", "email"]
```

`VerifyEmailOtpParams{email, token, type: EmailOtpType, options?}` at
`supabase_auth/types.py:463`. **`"email"` is valid.** Use it.

The client does **no** runtime validation: `verify_otp` splats `**params` straight
into the JSON body (`_sync/gotrue_client.py:1187ff`) and `TypedDict` is not enforced
at runtime. A typo, or `"Email"`, reaches the server verbatim.

`"signup"` is the dangerous near-miss: `sign_in_with_otp(should_create_user: true)`
mints a **signup** token for a new address but a **magiclink/recovery** token for an
existing one, so pinning `"signup"` strands exactly the legacy accounts spec §8
promises "OTP log-in works immediately" for.

## 4. Live probe — ran it; the API structurally cannot answer this

`POST {SUPABASE_URL}/auth/v1/verify`, `token="000000"`,
`email="sec-spike-probe@example.com"` (throwaway; not a real mailbox):

| `type` | Response |
|---|---|
| `email` | `HTTP 403 {"code":403,"error_code":"otp_expired","msg":"Token has expired or is invalid"}` |
| `signup` | `HTTP 403 {"code":403,"error_code":"otp_expired","msg":"Token has expired or is invalid"}` |
| `magiclink` | `HTTP 403 {"code":403,"error_code":"otp_expired","msg":"Token has expired or is invalid"}` |
| `recovery` | `HTTP 403 {"code":403,"error_code":"otp_expired","msg":"Token has expired or is invalid"}` |
| `totally-bogus` | `HTTP 403 {"code":403,"error_code":"otp_expired","msg":"Token has expired or is invalid"}` |
| `sms` (with an email body) | `HTTP 403` — same, byte-identical |
| `emaill` (typo) | `HTTP 403` — same |
| `EMAIL` (uppercase) | `HTTP 403` — same |
| *(omit `type`)* | `HTTP 400 {"code":400,"error_code":"validation_failed","msg":"Verify requires a verification type"}` |
| *(omit `token`)* | `HTTP 400 {"code":400,"error_code":"validation_failed","msg":"Verify requires either a token or a token hash"}` |

**Verdict: PASS with conditions — and the conditions are the point.** Token lookup
happens *before* any type validation, so every `type` string is indistinguishable
from an expired code. A wrong literal therefore produces a silent, permanent
"Invalid code" for 100% of users with **zero diagnostic signal** in the response.
The static check in §3 is necessary but not sufficient.

Required gate before t2/t9 can be called done:

1. **One real 8-digit round-trip, run twice** — (a) a brand-new address, and
   (b) an existing legacy account. (b) is the case that separates `"email"` from
   `"signup"`, and it is spec §8's central claim.
2. **A unit test asserting the exact literal** `type == "email"` in the payload handed
   to a spied `verify_otp`, because nothing else can ever catch a regression here.
3. Both depend on the §6.4 dashboard step (Magic-link template carrying `{{ .Token }}`)
   — configuration, not code, so it must be scheduled explicitly, not assumed.

Do **not** use `docs/dogfood/probe_gotrue_otp.py` for the round-trip: it POSTs
`/auth/v1/otp`, which really sends mail against the ~2/hr built-in SMTP and creates
users. A single deliberate round-trip is fine; that script is not a diagnostic.

## 4b. GoTrue type-matching matrix — REAL tokens (settles what §4 could not)

Bogus tokens can't discriminate because token lookup precedes type validation. So we
issued genuine tokens with `admin/generate_link` (which **sends no email and spends no
SMTP quota**), read `properties.email_otp`, and redeemed that real code (8-digit;
~1 in 10 carry a leading zero, so string-only — see the measured-codes subsection
below) at raw
`POST /auth/v1/verify` across literals — one fresh mint per cell, because GoTrue holds
one pending email token per user and a successful verify consumes it.

Reproduce: `.venv/bin/python docs/security/spike_gotrue_type_matrix.py`
(creates 6 synthetic `@example.com` identities, deletes them in a `finally`).

| verify `type` | magiclink-family token<br>(user exists + confirmed) | signup-family token<br>(new user) |
|---|---|---|
| `email` | **ACCEPTED** (session issued) | **ACCEPTED** (session issued) |
| `magiclink` | ACCEPTED | `403 otp_expired` |
| `signup` | **`403 otp_expired`** | ACCEPTED |
| `recovery` | ACCEPTED | `403 otp_expired` |
| `bogus` | `403 otp_expired` | `403 otp_expired` |

### What this proves

- **`type="email"` is the only literal that redeems both families.** It is the email
  umbrella literal; `magiclink` / `signup` / `recovery` are narrower and mutually
  exclusive (`recovery` behaves like `magiclink` here — it accepts a magiclink token
  but not a signup token).
- **`type="signup"` is a hard break for every existing account**, confirmed with a
  genuine token, not inference: a magiclink-family token returns `403 otp_expired`.
  Since `sign_in_with_otp(should_create_user: true)` mints *signup* for an unknown
  address and *magiclink* for an existing one, pinning `"signup"` would reject 100% of
  logins from the legacy accounts spec §8 says "OTP log-in works immediately" for.
- **`type="magiclink"` symmetrically breaks new signups** — so the naive
  "it's a magic-link template, use magiclink" reading is also wrong.
- No enumeration leak from the discriminator: an unknown literal and a wrong token
  return the identical `403 otp_expired`.

### Measured OTP codes — length is 8, and ~1 in 10 carry a LEADING ZERO (MAJOR)

> **Citation note / supersession.** The stored (immutable) output of team task **t8** says
> the spec's "6-digit" claims are at "§2/§11". That pointer is wrong and is **superseded
> by this section**: they are at **line 37 (§2)** and **line 125 (§6 item 4)**. §11
> contains no digit-length claim. Trust the line numbers below, not t8's summary.

Captured here so t5/t7 can trace the evidence without digging through chat. Five codes
issued on this project on 2026-09-15 via `admin/generate_link`
(`properties.email_otp`), all 8 numeric characters, 5/5:

```
47580843    27280025    07368987    45480348    28922263
                              ^^^^^^^^  leading zero
```

- **Codes are 8 DIGITS, not 6.** The design spec says "6-digit" twice — §2 line 37
  ("GoTrue sends a 6-digit code") and §6 item 4 line 125 ("6-digit code UX") — and both
  are wrong for this project. `Config.OTP_CODE_LENGTH` is the correct pin. A
  `maxlength="6"` code-entry field makes an 8-digit code physically untypeable — that is
  a total login outage, not a cosmetic miss.
- **`07368987` is the MAJOR trigger: roughly 1 in 10 codes begins with `0`.** The token
  must be a **string end to end**. Any `int(token)` / `parseInt` / `Number()` coercion
  anywhere on the path (form validation, a pending-session field, a template filter, a
  fixture) reduces it to `7368987` — 7 chars — and hard-fails verification. The failure
  is intermittent and per-user, and invisible to any test that hard-codes a friendly
  code like `123456`; it would ship reading as "Supabase is flaky".
- Prefer `re.fullmatch(r"[0-9]{N}", token)` over `.isdigit()` / `.isnumeric()`: the
  latter accept non-ASCII lookalikes (superscript/subscript digits pasted from rich
  text) as valid "digits", and a `.isdigit()`-then-`int()` chain is exactly the coercion
  above. `re.fullmatch(r"\d{N}")` is also unsafe — Python's `\d` is Unicode-aware
  without `re.ASCII`, so use `[0-9]` explicitly.
- This measurement was a follow-up to the matrix and ran as an inline script, so it is
  not on disk. To re-measure (quota-free, no email sent):

```python
u = sb.auth.admin.create_user({"email": "seclen-<ts>@example.com",
                               "password": "<random>", "email_confirm": True})
try:
    for _ in range(5):
        p = sb.auth.admin.generate_link({"type": "magiclink",
                                         "email": "seclen-<ts>@example.com"}).properties
        print(repr(p.email_otp), len(p.email_otp), p.email_otp.isdigit())
finally:
    sb.auth.admin.delete_user(u.user.id)
```

  Delete the probe identity afterwards and re-check `admin.list_users()` — see the
  cleanup discipline note in §5.

### Method asymmetry — read this before reusing the addresses

This spike minted its tokens on the **admin** path: `POST /auth/admin/generate_link`
with the service-role key. That endpoint does **not** apply GoTrue's disposable-domain
screening, which is why `@example.com` worked here. The **public app path is the
opposite**: `/auth/v1/otp` and `/signup` reject `@example.com`, `@example.org` and
`*.invalid` as `email_address_invalid` (measured independently by backend-eng on this
project). So:

- **Do not read `@example.com` as sign-up-able through the app.** Any future probe that
  goes through `/otp` needs a well-formed but unregistered domain — e.g.
  `@sprintspike-otp.dev`.
- The type-matching conclusion in this section is **unaffected**: it is a property of
  `/auth/v1/verify` and the minted `verification_type`, and does not depend on how the
  address got into `auth.users`. That is why it carries the HIGH label.
- The domain screening difference is also the only reason cleanup was safe: rows
  created by the admin API are deletable by the admin API, and no application code
  path could have picked them up.

### Confidence labels (per the captain's request)

- **HIGH** — the server-side type-matching rule itself: it is a property of
  `/verify` and the minted `verification_type`, independent of how the token was
  issued, and measured directly with real redeemable codes.
- **MEDIUM** — that `/otp` (the app path) mints exactly these two families. Highly
  likely from `verification_type` on each mint and from GoTrue's design, but this
  script did not go through `/otp`. **This residual is exactly what the t7 app-path
  round-trip must close** — new address *and* existing legacy address.
- **NOT covered** — the user's dashboard "Magic link" template carrying `{{ .Token }}`
  (spec §6.4). `generate_link` returns `email_otp` regardless of template, so template
  configuration is orthogonal to everything measured here and remains a hard
  prerequisite for the live UX.

## Net

| # | Verdict |
|---|---|
| 1 storage protocol | **FAIL as spec'd** — implement `get_item`/`set_item`/`remove_item`, subclass `SyncSupportedStorage` |
| 2 `flow_type` default | **PASS as a gate**, but the spec premise is inverted — see §5 |
| 3 `verify_otp` literals | **PASS** — `"email"` valid; `"signup"` would strand legacy accounts |
| 4 live probe (bogus token) | **Ran. PASS-with-conditions** — inconclusive by design; see §4b for the real-token answer |
| 4b type-matching matrix (real tokens) | **DONE** — `type="email"` is the only literal redeeming both families; `"signup"` returns `403` on an existing user's token |
| 4b measured OTP codes | **MAJOR** — codes are **8 digits** (spec lines 37 and 125 say "6-digit" and are wrong); 5/5 samples in §4b, one (`07368987`) with a **leading zero** ⇒ token must stay a string; pin `Config.OTP_CODE_LENGTH`, server-side `re.fullmatch(r"[0-9]{N}")`, never `int()` |
| t1 claims re-verified | **BOTH CONFIRMED** — 8-digit codes (measured) and `should_create_user` read only from `options{}`; sharper than reported: its **default is `True`**, so omitting options still provisions (fail-open) |

## 5. Bonus finding: the existing clients arm orphaned refresh timers

`ClientOptions.flow_type` defaults to **`"pkce"`**, not `"implicit"`
(`supabase/lib/client_options.py:65`), and `create_client` always forwards it
(`supabase/_sync/client.py:288`). Measured on the current code path:

```
get_supabase() / get_client_supabase():  flow='pkce'  persist_session=True  auto_refresh_token=True  storage=SyncMemoryStorage
```

So §5.1's explicit `flow_type="pkce"` documents nothing new. The live issue is the
other two flags: with `auto_refresh_token=True`, `_save_session` (`:1101`) arms a
daemon `threading.Timer` (`supabase_auth/timer.py`) whose callback calls
`get_session()` → `_call_refresh_token()` on a **request-scoped** client, ~55 minutes
later — after `close_request_clients()` has closed its httpx session. Today's
`sign_in_with_password` reaches `_save_session`, so every password login already
arms one.

**Recommendation:** `persist_session=False, auto_refresh_token=False` on **all three**
clients in `services/supabase_client.py`, not just the new auth client. A
server-rendered Flask app never refreshes client-side; its authority is
`session["user_id"]`, not the access token. If t1 scopes this to the new client only,
that is a MINOR in the t4 review.
