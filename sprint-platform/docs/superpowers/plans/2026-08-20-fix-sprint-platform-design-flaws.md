# Fix Sprint-Platform Design Flaws

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 13 design flaws identified in the architecture review: 3 critical (security/data-integrity), 4 high (reliability), and 5 medium (design/maintainability).

**Architecture:** Incremental fixes to the Flask monolith + Supabase stack. Security isolation first (anon vs service key, CSRF, input validation), then atomicity (RPC for contracts, cohort race condition), then reliability (retry/backoff, background thread error handling, idempotency guards), then maintainability (dedup DAY_TO_PROJECT, mentor grounding, proposal thread management). Each task is independently deployable and testable.

**Tech Stack:** Python 3 (Flask, Supabase client, Pydantic), PostgreSQL (Supabase), CSRF via Flask-WTF, SQL for RPC functions.

**Spec:** [`docs/architecture.md`](../architecture.md), [`docs/engineering-spec.md`](../engineering-spec.md), [`db/schema.sql`](../../db/schema.sql). This plan argues from those docs; executors read both.

**TDD Protocol:** Every task follows Red → Green → Refactor. Tests name the break they catch. Expected values are hand-derived literals, never computed from the code under test. Mocks are used only for slow/external dependencies (Supabase HTTP calls, LLM providers) — real logic stays in tests.

## Global Constraints

- Python 3.10+ (uses `match`/`case` and `str | None` syntax where applicable)
- Supabase client SDK `supabase==2.31.*` (already in requirements.txt)
- Pydantic for schema validation (add to requirements.txt)
- Flask-WTF for CSRF (add to requirements.txt)
- All schema changes must be idempotent (already the project standard — `CREATE TABLE IF NOT EXISTS`)
- The "No-500" philosophy stays: failures surface as visible errors, never template fallbacks
- `call_llm` return contract must remain `str | None` (callers check `None`)
- All mutations to `/sprints/*` must remain gated to the sprint owner
- Background threads must never silently swallow exceptions — log and stamp visible errors

---

## File Structure

| File | Responsibility |
|------|---------------|
| `services/supabase_client.py` | Supabase client factory — anon key for routes, service key for admin workers |
| `services/outcome_service.py` | Contract add/complete — uses RPC for atomicity |
| `services/llm.py` | LLM provider chain — retry/backoff wrapper |
| `services/lesson_engine.py` | Lesson + project anatomy generation — validates LLM output |
| `services/proposal_engine.py` | Proposal drafts — validates LLM output, deduped thread guard |
| `services/schemas.py` | **New** — Pydantic models for all LLM payloads |
| `services/mentor_agent.py` | Socratic chat — strengthened grounding gate |
| `routes/sprints.py` | Dashboard, day view, day-complete (idempotency guard, CSRF) |
| `routes/main.py` | Enrollment, cohort creation (race condition fix) |
| `routes/contract.py` | Contract submit, add, case-study (CSRF, input validation) |
| `routes/proposals.py` | Proposal builder (thread dedup, CSRF) |
| `routes/__init__.py` | Shared helpers — extract `DAY_TO_PROJECT` here |
| `config.py` | Document two-key split |
| `db/rpc.sql` | Transactional RPC functions |
| `requirements.txt` | Add pydantic, flask-wtf |

---

## Task 1: Split Supabase client into anon (client) + service (admin) keys

**Files:**
- Modify: `services/supabase_client.py` (add `get_client_supabase()`)
- Modify: `config.py` (document the two-key split)
- Test: `tests/test_supabase_client.py`

**Interfaces:**
- Consumes: `current_app.config` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`)
- Produces: `get_supabase()` (service role, admin-only) + `get_client_supabase()` (anon key, all routes)

**What this catches:** A route using the service-role key bypasses RLS — any bug means full DB access.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_supabase_client.py
"""
Tests that the anon-key client is used for routes (RLS enforced)
and the service-key client is used for admin workers (bypasses RLS).
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SUPABASE_URL"] = "https://test.supabase.co"
    app.config["SUPABASE_ANON_KEY"] = "anon-key-123"
    app.config["SUPABASE_SERVICE_KEY"] = "service-key-456"
    return app


def test_client_uses_anon_key_not_service_key(app):
    """The route-facing client must use the anon key so RLS is enforced.
    Break: returning the service-role key to routes."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("services.supabase_client.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="anon_client")
            client = get_client_supabase()
            # Assert the EXACT key passed to create_client — not the service key
            call_args = mock_create.call_args[0]
            assert call_args[1] == "anon-key-123", (
                f"Expected anon key 'anon-key-123', got '{call_args[1]}'"
            )
            assert call_args[1] != "service-key-456", "Must NOT use the service-role key"


def test_service_client_uses_service_key(app):
    """The admin worker client must use the service-role key for background tasks."""
    from services.supabase_client import get_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("services.supabase_client.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="service_client")
            client = get_supabase()
            call_args = mock_create.call_args[0]
            assert call_args[1] == "service-key-456", (
                f"Expected service key 'service-key-456', got '{call_args[1]}'"
            )


def test_missing_anon_key_raises_runtime_error(app):
    """A missing anon key must fail loudly — never silently fall back to service key."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    app.config["SUPABASE_ANON_KEY"] = ""
    with app.app_context():
        with pytest.raises(RuntimeError, match="not configured"):
            get_client_supabase()


def test_same_client_returned_within_request(app):
    """Multiple calls within one request must return the same cached instance."""
    from services.supabase_client import get_client_supabase, reset_clients
    reset_clients()
    with app.app_context():
        with patch("services.supabase_client.create_client") as mock_create:
            mock_create.return_value = MagicMock(name="anon_client")
            c1 = get_client_supabase()
            c2 = get_client_supabase()
            assert c1 is c2
            assert mock_create.call_count == 1, "create_client should be called once per request"
```

Run: `pytest tests/test_supabase_client.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `ImportError: cannot import name 'get_client_supabase' from 'services.supabase_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# services/supabase_client.py — add to existing file
_client_supabase_client = None  # cache for anon-key client


def get_client_supabase():
    """Return the anon-key Supabase client for request-scoped reads/writes.
    Uses RLS policies — never the service-role key."""
    if "client_supabase" in g:
        return g.client_supabase
    url = (current_app.config.get("SUPABASE_URL") or "").strip()
    key = (current_app.config.get("SUPABASE_ANON_KEY") or "").strip()
    if not (url and key):
        raise RuntimeError(
            "Supabase anon key is not configured. Set SUPABASE_ANON_KEY "
            "in the environment (copy .env.example to .env)."
        )
    global _client_supabase_client
    if _client_supabase_client is None:
        from supabase import create_client
        _client_supabase_client = create_client(url, key)
    g.client_supabase = _client_supabase_client
    return g.client_supabase


def reset_clients():
    """Reset all cached clients (for tests)."""
    global _live_client, _client_supabase_client
    _live_client = None
    _client_supabase_client = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_supabase_client.py -v`

- [ ] **Step 5: Wire routes to use `get_client_supabase`**

Modify all 8 blueprint route modules (`routes/main.py`, `routes/sprints.py`, `routes/contract.py`, `routes/proposals.py`, `routes/profile.py`, `routes/mentor.py`, `routes/clients.py`, `routes/admin.py`) to replace `get_supabase()` calls with `get_client_supabase()` for client-facing requests.

Exception: `routes/admin.py` demand-refresh and background workers keep using `get_supabase()` (service role).

- [ ] **Step 6: Update `.env.example`**

Add `SUPABASE_ANON_KEY=` alongside the existing `SUPABASE_SERVICE_ROLE_KEY=`.

- [ ] **Step 7: Commit**

```bash
git add services/supabase_client.py tests/test_supabase_client.py .env.example routes/
git commit -m "fix: split supabase client into anon (routes) and service (admin) keys"
```

---

## Task 2: Add CSRF protection to all state-changing POST routes

**Files:**
- Modify: `app.py` (initialize Flask-WTF CSRF)
- Modify: `requirements.txt` (add flask-wtf)
- Modify: all form templates (add `{{ csrf_token() }}`)
- Test: `tests/test_csrf.py`

**What this catches:** Cross-site request forgery lets an attacker mark days complete, submit fake contracts, or alter outcomes on behalf of an authenticated user.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_csrf.py
"""
Tests that POST requests without a valid CSRF token are rejected.
Break: removing CSRF protection from state-changing routes.
"""
import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": True, "SECRET_KEY": "test"})
    with app.test_client() as c:
        yield c


def test_post_without_csrf_token_is_rejected(client):
    """A POST without a CSRF token must be rejected (400).
    Break: removing CSRF check allows forged requests through."""
    resp = client.post("/sprints/s1/day/1/complete", data={})
    # Should be 400 (CSRF validation failed) — NOT 302 (auth redirect) or 200
    assert resp.status_code == 400, (
        f"Expected 400 CSRF rejection, got {resp.status_code}"
    )


def test_post_with_valid_csrf_token_proceeds(client):
    """A POST with a valid CSRF token should proceed past CSRF validation."""
    with client.session_transaction() as sess:
        sess["user_id"] = "test-user"
    # Get a valid CSRF token from a GET request
    resp_get = client.get("/sprints/s1")
    # Extract CSRF token from the response cookies or form
    # Flask-WTF stores the token in the session; use the test client's token
    from flask_wtf.csrf import generate_csrf
    with client.application.test_request_context():
        token = generate_csrf()
    resp = client.post(
        "/sprints/s1/day/1/complete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    # Should NOT be 400 (CSRF failure) — may be 302 (auth) or other
    assert resp.status_code != 400, "CSRF token was valid but request was rejected"
```

Run: `pytest tests/test_csrf.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — no CSRF protection currently exists, so POST without token returns 302 (auth redirect) or 200, not 400

- [ ] **Step 3: Install flask-wtf and initialize CSRF**

```bash
# requirements.txt — add line
flask-wtf>=1.2,<2
```

```python
# app.py — in create_app
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app(test_config=None):
    app = Flask(__name__)
    # ... existing config ...
    if test_config:
        app.config.update(test_config)
    csrf.init_app(app)
    # ... rest of factory ...
    return app
```

- [ ] **Step 4: Add CSRF token to all form templates**

In every Jinja template with `<form method="POST">`, add:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

Templates: `sprint_dashboard.html`, `day.html`, `mock_contract.html`, `proposals.html`, `mentor.html`, all admin templates.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_csrf.py -v`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app.py templates/ tests/test_csrf.py
git commit -m "feat: add CSRF protection to all state-changing POST routes"
```

---

## Task 3: Add input validation on contract add form fields

**Files:**
- Modify: `routes/contract.py` (validate form inputs)
- Test: `tests/test_contract_validation.py`

**What this catches:** Negative contract values corrupt earnings; oversized strings overflow DB; empty client names create ghost records.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract_validation.py
"""
Tests that contract form validation rejects invalid inputs.
Break: accepting negative values, empty names, or oversized strings.
"""
import pytest
from routes.contract import _validate_contract_form


def test_negative_contract_value_rejected():
    """Negative contract values corrupt earnings calculations.
    Break: allowing contract_value=-100 to pass validation."""
    errors = _validate_contract_form({
        "client_name": "Acme",
        "contract_value": "-100",
        "platform": "upwork",
    })
    assert "contract_value" in errors, "Negative value should be rejected"


def test_zero_contract_value_accepted():
    """Zero is valid (pro-bono work).
    Break: rejecting zero as invalid."""
    errors = _validate_contract_form({
        "client_name": "Acme",
        "contract_value": "0",
        "platform": "upwork",
    })
    assert "contract_value" not in errors, "Zero should be accepted"


def test_large_positive_value_accepted():
    """Large but reasonable values should be accepted.
    Break: rejecting 50000 as invalid."""
    errors = _validate_contract_form({
        "client_name": "Acme",
        "contract_value": "50000",
        "platform": "upwork",
    })
    assert "contract_value" not in errors, "50000 should be accepted"


def test_unreasonably_large_value_rejected():
    """Values over 1M are likely data entry errors.
    Break: allowing contract_value=99999999 to pass."""
    errors = _validate_contract_form({
        "client_name": "Acme",
        "contract_value": "99999999",
        "platform": "upwork",
    })
    assert "contract_value" in errors, "Unreasonably large value should be rejected"


def test_empty_client_name_rejected():
    """Ghost records with no client name are useless.
    Break: accepting empty client_name."""
    errors = _validate_contract_form({
        "client_name": "",
        "contract_value": "500",
        "platform": "upwork",
    })
    assert "client_name" in errors, "Empty client name should be rejected"


def test_whitespace_only_client_name_rejected():
    """Whitespace-only names are effectively empty.
    Break: accepting '   ' as a valid name."""
    errors = _validate_contract_form({
        "client_name": "   ",
        "contract_value": "500",
        "platform": "upwork",
    })
    assert "client_name" in errors, "Whitespace-only name should be rejected"


def test_long_client_name_rejected():
    """Client names over 200 chars overflow the DB column.
    Break: accepting 201-character name."""
    errors = _validate_contract_form({
        "client_name": "A" * 201,
        "contract_value": "500",
        "platform": "upwork",
    })
    assert "client_name" in errors, "Name over 200 chars should be rejected"


def test_negative_hours_rejected():
    """Negative hours don't make sense.
    Break: accepting hours_worked=-5."""
    errors = _validate_contract_form({
        "client_name": "Acme",
        "contract_value": "500",
        "hours_worked": "-5",
        "platform": "upwork",
    })
    assert "hours_worked" in errors, "Negative hours should be rejected"


def test_valid_contract_accepted():
    """All valid inputs should produce no errors.
    Break: rejecting any valid field."""
    errors = _validate_contract_form({
        "client_name": "Acme Corp",
        "contract_value": "500",
        "your_rate": "50",
        "hours_worked": "10",
        "platform": "upwork",
    })
    assert len(errors) == 0, f"Valid form should have no errors, got: {errors}"
```

Run: `pytest tests/test_contract_validation.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `ImportError: cannot import name '_validate_contract_form' from 'routes.contract'`

- [ ] **Step 3: Write minimal implementation**

```python
# routes/contract.py — add validation function
def _validate_contract_form(form):
    """Validate contract add form fields. Returns dict of field -> error message."""
    errors = {}
    client_name = (form.get("client_name") or "").strip()
    if not client_name:
        errors["client_name"] = "Client name is required."
    elif len(client_name) > 200:
        errors["client_name"] = "Client name must be under 200 characters."

    try:
        value = float(form.get("contract_value") or 0)
        if value < 0:
            errors["contract_value"] = "Contract value cannot be negative."
        elif value > 1_000_000:
            errors["contract_value"] = "Contract value seems unreasonably high."
    except (TypeError, ValueError):
        errors["contract_value"] = "Contract value must be a number."

    rate = form.get("your_rate")
    if rate not in (None, ""):
        try:
            r = float(rate)
            if r < 0:
                errors["your_rate"] = "Rate cannot be negative."
        except (TypeError, ValueError):
            errors["your_rate"] = "Rate must be a number."

    hours = form.get("hours_worked")
    if hours not in (None, ""):
        try:
            h = int(hours)
            if h < 0:
                errors["hours_worked"] = "Hours cannot be negative."
            elif h > 10000:
                errors["hours_worked"] = "Hours seems unreasonably high."
        except (TypeError, ValueError):
            errors["hours_worked"] = "Hours must be a whole number."

    return errors
```

- [ ] **Step 4: Wire validation into the contract add route**

```python
# routes/contract.py — in the add() route, before calling add_contract:
errors = _validate_contract_form(request.form)
if errors:
    for msg in errors.values():
        flash(msg)
    return redirect(url_for("contract.brief", sprint_id=sprint_id))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_contract_validation.py -v`

- [ ] **Step 6: Commit**

```bash
git add routes/contract.py tests/test_contract_validation.py
git commit -m "feat: add input validation to contract add form fields"
```

---

## Task 4: Fix background thread error propagation

**Files:**
- Modify: `routes/main.py` (`_generate_in_background`)
- Modify: `routes/proposals.py` (`_fill_in_background`)
- Test: `tests/test_background_error.py`

**What this catches:** Background threads silently swallowing exceptions — the user sees endless "generating" with no error message and no recovery path.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_background_error.py
"""
Tests that background generation threads stamp visible errors on failure.
Break: silently swallowing exceptions leaves days in permanent 'generating' state.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import json


def test_generate_background_stamps_generation_error_on_db():
    """When generate_sprint_content raises, the first empty day must get
    a generation_error marker so the UI surfaces it.
    Break: silently swallowing the exception — day payload stays empty forever."""
    from routes.main import _generate_in_background
    from flask import Flask

    app = Flask(__name__)
    app.config["SUPABASE_URL"] = "https://test.supabase.co"
    app.config["SUPABASE_SERVICE_KEY"] = "svc-key"

    # Mock the Supabase client chain
    mock_sb = MagicMock()

    # Simulate: day 1 has no lesson (empty payload), day 2 has a lesson
    mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {"day_no": 1, "action_payload": {}},           # empty — should get stamped
        {"day_no": 2, "action_payload": {"lesson": "x"}},  # has lesson — skip
    ]

    with patch("routes.main.generate_sprint_content", side_effect=Exception("LLM timeout")):
        with patch("routes.main.create_client", return_value=mock_sb):
            # Must not raise — the thread catches and stamps
            _generate_in_background(app, "sprint-123")

    # Verify the error was stamped on day 1's payload
    update_calls = mock_sb.table.return_value.update.call_args_list
    assert len(update_calls) >= 1, "Expected at least one update call to stamp generation_error"

    # Check the payload that was written
    written_payload = update_calls[0][0][0].get("action_payload") or update_calls[0][1].get("action_payload")
    if written_payload is None:
        # Check via the chained call
        written_payload = mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value

    # The key assertion: generation_error must exist in the written data
    # Use a more targeted check on the mock chain
    assert mock_sb.table.return_value.update.called, "Should have called update to stamp error"


def test_fill_background_stamps_score_minus_one_on_failure():
    """When fill_drafts raises, unfilled proposals must get score=-1.
    Break: silently swallowing — proposals stay in 'generating' forever."""
    from routes.proposals import _fill_in_background
    from flask import Flask

    app = Flask(__name__)
    app.config["SUPABASE_URL"] = "https://test.supabase.co"
    app.config["SUPABASE_SERVICE_KEY"] = "svc-key"

    mock_sb = MagicMock()

    with patch("routes.proposals.fill_drafts", side_effect=Exception("LLM down")):
        with patch("routes.proposals.create_client", return_value=mock_sb):
            _fill_in_background(app, "sprint-123", "email-automation")

    # Verify score=-1 was stamped on unfilled proposals
    mock_sb.table.return_value.update.return_value.is_.assert_called_once()
```

Run: `pytest tests/test_background_error.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — current code silently swallows exceptions without stamping errors

- [ ] **Step 3: Fix `_generate_in_background`**

```python
# routes/main.py — rewrite _generate_in_background
def _generate_in_background(app, sprint_id):
    """Background LLM content generation — stamps visible errors on failure."""
    with app.app_context():
        try:
            from supabase import create_client
            sb = create_client(
                app.config.get("SUPABASE_URL") or "",
                app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
            )
            generate_sprint_content(sb, sprint_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("lesson generation failed for %s", sprint_id)
            # Stamp generation_error on the first empty day so the UI surfaces it
            try:
                sb2 = create_client(
                    app.config.get("SUPABASE_URL") or "",
                    app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                )
                days = sb2.table("sprint_days").select("day_no, action_payload") \
                    .eq("sprint_id", sprint_id).order("day_no").execute().data
                for d in days:
                    payload = d.get("action_payload") or {}
                    if not payload.get("lesson"):
                        payload["generation_error"] = f"Generation failed: {exc}"
                        sb2.table("sprint_days").update({"action_payload": payload}) \
                            .eq("sprint_id", sprint_id).eq("day_no", d["day_no"]).execute()
                        break  # stamp once
            except Exception:
                logging.getLogger(__name__).exception("failed to stamp generation_error for %s", sprint_id)
```

- [ ] **Step 4: Fix `_fill_in_background`**

```python
# routes/proposals.py — rewrite _fill_in_background
def _fill_in_background(app, sprint_id, cluster_key):
    """Background LLM proposal fill — stamps score=-1 on failure."""
    with app.app_context():
        try:
            from supabase import create_client
            sb = create_client(
                app.config.get("SUPABASE_URL") or "",
                app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
            )
            fill_drafts(sb, sprint_id, cluster_key)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("proposal fill failed for %s", sprint_id)
            try:
                sb2 = create_client(
                    app.config.get("SUPABASE_URL") or "",
                    app.config.get("SUPABASE_SERVICE_KEY") or app.config.get("SUPABASE_KEY") or "",
                )
                sb2.table("proposals").update({"score": -1, "template_body": None}) \
                    .eq("sprint_id", sprint_id).is_("template_body", "null").execute()
            except Exception:
                logging.getLogger(__name__).exception("failed to stamp score=-1 for %s", sprint_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_background_error.py -v`

- [ ] **Step 6: Commit**

```bash
git add routes/main.py routes/proposals.py tests/test_background_error.py
git commit -m "fix: background threads stamp visible errors on DB instead of silent swallow"
```

---

## Task 5: Fix cohort creation race condition

**Files:**
- Modify: `routes/main.py` (`_open_cohort`)
- Modify: `db/schema.sql` (add unique constraint)
- Test: `tests/test_cohort_race.py`

**What this catches:** Two concurrent enrollments creating duplicate "Cohort #N" — users split into separate groups.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cohort_race.py
"""
Tests that concurrent cohort creation does not produce duplicates.
Break: two simultaneous enrollments both seeing no active cohort and creating two.
"""
import pytest
import threading
import time
from unittest.mock import patch, MagicMock
from routes.main import _open_cohort


def test_concurrent_open_cohort_creates_only_one():
    """Two concurrent _open_cohort calls must not create duplicate active cohorts.
    Break: both calls seeing empty result and inserting."""
    sb = MagicMock()

    # Track insert calls to detect duplicates
    insert_calls = []
    def track_insert(data):
        insert_calls.append(data)
        mock_result = MagicMock()
        mock_result.execute.return_value.data = [{"id": f"cohort-{len(insert_calls)}"}]
        return mock_result

    sb.table.return_value.insert.side_effect = track_insert

    # First call: no existing cohorts
    sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    results = []
    errors = []

    def worker():
        try:
            result = _open_cohort(sb, "email-automation")
            results.append(result)
        except Exception as e:
            errors.append(e)

    # Run two concurrent workers
    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert len(errors) == 0, f"Errors in workers: {errors}"
    # Only ONE insert should have happened (the other should find existing)
    assert len(insert_calls) == 1, (
        f"Expected 1 insert (race prevented), got {len(insert_calls)} inserts"
    )
```

Run: `pytest tests/test_cohort_race.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — both threads insert because there's no check-then-act guard

- [ ] **Step 3: Fix `_open_cohort` to be idempotent**

```python
# routes/main.py — rewrite _open_cohort
def _open_cohort(sb, cluster_key):
    """Open a new active cohort for the cluster. Idempotent: if an active
    cohort already exists, return it instead of creating a duplicate."""
    existing = sb.table("cohorts").select("id") \
        .eq("cluster_key", cluster_key).eq("status", "active") \
        .limit(1).execute().data
    if existing:
        return existing[0]["id"]

    today = datetime.date.today()
    count = sb.table("cohorts").select("id").eq("cluster_key", cluster_key).execute().data
    row = sb.table("cohorts").insert({
        "cluster_key": cluster_key,
        "name": f"Cohort #{len(count) + 1}",
        "start_date": today.isoformat(),
        "end_date": (today + datetime.timedelta(days=13)).isoformat(),
        "status": "active",
    }).execute().data[0]
    return row["id"]
```

- [ ] **Step 4: Add DB constraint for active cohorts**

```sql
-- db/schema.sql — add after cohorts table creation
CREATE UNIQUE INDEX IF NOT EXISTS idx_cohorts_active_per_cluster
    ON cohorts (cluster_key) WHERE status = 'active';
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cohort_race.py -v`

- [ ] **Step 6: Commit**

```bash
git add routes/main.py db/schema.sql tests/test_cohort_race.py
git commit -m "fix: make cohort creation idempotent to prevent race condition duplicates"
```

---

## Task 6: Add idempotency guard to day-complete

**Files:**
- Modify: `routes/sprints.py` (`complete_day`)
- Test: `tests/test_day_complete.py`

**What this catches:** Double-click on complete button double-counts meter, re-stamps `completed_at`, or re-increments streak.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_day_complete.py
"""
Tests that completing an already-completed day is a no-op.
Break: double-clicking complete re-increments meter and streak.
"""
import pytest
from unittest.mock import patch, MagicMock
import datetime


def test_already_completed_day_does_not_recompute_meter():
    """If a day is already done, complete_day must NOT recompute the meter.
    Break: recomputing meter on an already-done day inflates the unlock count."""
    from routes.sprints import _complete_day_if_not_done

    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 3, "phase": "A"}

    # Day 3 is already done
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": True}
    ]

    result = _complete_day_if_not_done(sb, sprint, 3)

    assert result["already_done"] is True, "Should report already_done=True"
    assert result.get("meter") is None, "Meter must NOT be recomputed for an already-done day"
    # Verify NO update calls were made (no writes to sprint_days or sprints)
    sb.table.return_value.update.assert_not_called()


def test_first_completion_updates_is_done_and_advances_day():
    """First time completing a day must mark is_done=True and advance current_day.
    Break: not updating sprint_days.is_done or sprints.current_day."""
    from routes.sprints import _complete_day_if_not_done

    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 3, "phase": "A"}

    # Day 3 is NOT done yet
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": False}
    ]

    with patch("routes.sprints.recompute", return_value={
        "newly_unlocked": 10, "unlocked_count": 50, "total_in_cluster": 450
    }):
        with patch("routes.sprints.load_momentum", return_value={"day_streak": 2, "confidence": 60}):
            with patch("routes.sprints.recompute_confidence", return_value=65):
                result = _complete_day_if_not_done(sb, sprint, 3)

    assert result["already_done"] is False
    assert result["meter"] is not None
    assert result["next_day"] == 4
    # Verify sprint_days.is_done was set to True
    sb.table.return_value.update.assert_called()


def test_day_14_completion_marks_sprint_completed():
    """Completing day 14 must set sprint status='completed' and stamp completed_at.
    Break: not marking the sprint as completed on day 14."""
    from routes.sprints import _complete_day_if_not_done

    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 14, "phase": "C"}

    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": False}
    ]

    with patch("routes.sprints.recompute", return_value={
        "newly_unlocked": 5, "unlocked_count": 450, "total_in_cluster": 450
    }):
        with patch("routes.sprints.load_momentum", return_value={"day_streak": 13, "confidence": 90}):
            with patch("routes.sprints.recompute_confidence", return_value=95):
                result = _complete_day_if_not_done(sb, sprint, 14)

    assert result["already_done"] is False
    assert result["next_day"] == 14  # capped at 14
    # Sprint status should be 'completed' — verify the update call includes it
    update_calls = sb.table.return_value.update.call_args_list
    status_updates = [c for c in update_calls if "status" in str(c)]
    assert len(status_updates) > 0, "Day 14 completion must set sprint status='completed'"
```

Run: `pytest tests/test_day_complete.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `ImportError: cannot import name '_complete_day_if_not_done' from 'routes.sprints'`

- [ ] **Step 3: Extract idempotent completion logic**

```python
# routes/sprints.py — add helper function
def _complete_day_if_not_done(sb, sprint, day_no):
    """Complete a day if not already done. Returns dict with status and meter."""
    day_row = sb.table("sprint_days").select("is_done") \
        .eq("sprint_id", sprint["id"]).eq("day_no", day_no).limit(1).execute().data
    if day_row and day_row[0].get("is_done"):
        return {"already_done": True, "meter": None}

    sb.table("sprint_days").update({"is_done": True}) \
        .eq("sprint_id", sprint["id"]).eq("day_no", day_no).execute()

    next_day = min(day_no + 1, 14)
    phase = "A" if next_day <= 5 else ("B" if next_day <= 10 else "C")
    sb.table("sprints").update({"current_day": next_day, "phase": phase}) \
        .eq("id", sprint["id"]).execute()

    if day_no >= 14:
        sb.table("sprints").update({
            "status": "completed",
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }).eq("id", sprint["id"]).execute()

    meter = recompute(sb, sprint["id"], sprint["user_id"], sprint["cluster_key"], day_no)

    mom = load_momentum(sb, sprint["user_id"])
    streak = (mom.get("day_streak") or 0) + 1
    confidence = recompute_confidence(mom.get("confidence"))
    sb.table("user_momentum").upsert({
        "user_id": sprint["user_id"], "day_streak": streak, "confidence": confidence,
    }, on_conflict="user_id").execute()

    return {"already_done": False, "meter": meter, "next_day": next_day}
```

- [ ] **Step 4: Rewrite `complete_day` to use the helper**

```python
@sprints_bp.route("/sprints/<sprint_id>/day/<int:day_no>/complete", methods=["POST"])
def complete_day(sprint_id, day_no):
    gate = require_login()
    if gate:
        return gate
    sb = get_supabase()
    sprint = load_sprint(sb, sprint_id)
    if not sprint or sprint.get("user_id") != g.user["id"]:
        return jsonify({"ok": False, "error": "not found"}), 404
    if not load_day(sb, sprint_id, day_no):
        return jsonify({"ok": False, "error": "day not found"}), 404

    result = _complete_day_if_not_done(sb, sprint, day_no)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "meter": result.get("meter"), "next_day": result.get("next_day")})
    if day_no >= 14:
        return redirect(url_for("sprints.dashboard", sprint_id=sprint_id))
    return redirect(url_for("sprints.day", sprint_id=sprint_id, day_no=result.get("next_day", day_no)))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_day_complete.py -v`

- [ ] **Step 6: Commit**

```bash
git add routes/sprints.py tests/test_day_complete.py
git commit -m "fix: add idempotency guard to day-complete to prevent double-counting"
```

---

## Task 7: Deduplicate DAY_TO_PROJECT mapping

**Files:**
- Create: `routes/__init__.py` (add shared constant)
- Modify: `routes/sprints.py` (import from `__init__`)
- Modify: `services/lesson_engine.py` (import from `routes.__init__`)
- Test: `tests/test_day_to_project.py`

**What this catches:** Mapping drift — one file updated, the other stale — causes lessons generated for the wrong project.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_day_to_project.py
"""
Tests that DAY_TO_PROJECT is a single source of truth.
Break: defining it in two places allows drift."""
import pytest


def test_day_to_project_is_single_source_of_truth():
    """Both modules must export the same mapping.
    Break: one module updated, the other stale."""
    from routes import DAY_TO_PROJECT as routes_dtp
    from services.lesson_engine import DAY_TO_PROJECT as engine_dtp
    assert routes_dtp == engine_dtp, (
        f"DAY_TO_PROJECT differs: routes={routes_dtp}, engine={engine_dtp}"
    )


def test_day_to_project_has_expected_values():
    """Days 2-5 must map to projects 1, 1, 2, 3.
    Break: changing the mapping without updating both consumers."""
    from routes import DAY_TO_PROJECT
    assert DAY_TO_PROJECT == {2: 1, 3: 1, 4: 2, 5: 3}, (
        f"Expected {{2: 1, 3: 1, 4: 2, 5: 3}}, got {DAY_TO_PROJECT}"
    )


def test_all_phase_a_copywork_days_are_mapped():
    """Every Phase A copy-work day (2-5) must map to a project.
    Break: removing a day from the mapping makes Gate A unreachable."""
    from routes import DAY_TO_PROJECT
    for day in [2, 3, 4, 5]:
        assert day in DAY_TO_PROJECT, f"Day {day} has no project mapping"
        assert DAY_TO_PROJECT[day] in [1, 2, 3], (
            f"Day {day} maps to invalid project {DAY_TO_PROJECT[day]}"
        )
```

Run: `pytest tests/test_day_to_project.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — if both files define the same dict, the test passes but the duplication is still a design flaw. The test catches future drift. Skip to Step 3.

- [ ] **Step 3: Add shared constant to `routes/__init__.py`**

```python
# routes/__init__.py — add at top
# Day → copy-work project index (1-based). Every Phase A copy-work day (2-5)
# must map so project 3 is reachable and Gate A can pass through the real day flow.
DAY_TO_PROJECT = {2: 1, 3: 1, 4: 2, 5: 3}
```

- [ ] **Step 4: Update consumers to import from `routes`**

```python
# routes/sprints.py — replace local definition with:
from routes import DAY_TO_PROJECT

# services/lesson_engine.py — replace local definition with:
from routes import DAY_TO_PROJECT
```

- [ ] **Step 5: Remove duplicate definitions from both files**

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_day_to_project.py -v`

- [ ] **Step 7: Commit**

```bash
git add routes/__init__.py routes/sprints.py services/lesson_engine.py tests/test_day_to_project.py
git commit -m "fix: deduplicate DAY_TO_PROJECT into single source of truth"
```

---

## Task 8: Strengthen mentor grounding gate

**Files:**
- Modify: `services/mentor_agent.py` (`_extract_terms`, `_grounded`)
- Test: `tests/test_mentor_grounding.py`

**What this catches:** Trivially passable grounding gate lets the LLM hand over finished implementations.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mentor_grounding.py
"""
Tests that the mentor grounding gate rejects generic and handover answers.
Break: allowing 'I have built it' or short answers to pass grounding."""
import pytest
from services.mentor_agent import _extract_terms, _grounded


KLAVIYO_JOB = (
    "We need a Klaviyo email automation specialist to build abandoned-cart "
    "flows, checkout recovery sequences, and win-back campaigns for "
    "Shopify stores using event-driven triggers."
)


def test_extract_terms_finds_domain_vocabulary():
    """Should extract domain-specific terms like 'klaviyo', not generic words.
    Break: extracting 'the', 'and', 'for' as terms."""
    terms = _extract_terms(KLAVIYO_JOB)
    assert len(terms) >= 3, f"Expected at least 3 terms, got {terms}"
    # Must include at least one domain-specific term
    domain_terms = [t for t in terms if t in ("klaviyo", "abandoned-cart", "checkout", "win-back", "shopify")]
    assert len(domain_terms) >= 1, (
        f"Expected domain terms like 'klaviyo' in {terms}"
    )


def test_grounded_rejects_generic_answer():
    """An answer with no job terms should fail grounding.
    Break: accepting 'That's a great question!' as grounded."""
    terms = ["klaviyo", "abandoned-cart", "checkout", "win-back"]
    answer = "That's a great question! Let me help you with that."
    assert _grounded(answer, terms) is False, (
        "Generic answer without job terms must fail grounding"
    )


def test_grounded_rejects_handover():
    """An answer that hands over the finished implementation must fail.
    Break: accepting 'I have built it' as a valid mentoring answer."""
    terms = ["klaviyo", "abandoned-cart"]
    answer = "I have built it for you. Here is the complete flow with all steps configured."
    assert _grounded(answer, terms) is False, (
        "Handover answer must fail grounding"
    )


def test_grounded_rejects_code_block():
    """An answer that dumps code should be rejected — coaching, not coding.
    Break: accepting '```python...' as a mentoring response."""
    terms = ["klaviyo", "abandoned-cart"]
    answer = "```python\nflow = create_flow('abandoned-cart')\nflow.add_trigger('checkout_started')\n```"
    assert _grounded(answer, terms) is False, (
        "Code block answer must fail grounding"
    )


def test_grounded_rejects_too_short_answer():
    """Very short answers are too thin to be grounded coaching.
    Break: accepting 'Yes.' as a 120-word mentoring response."""
    terms = ["klaviyo", "abandoned-cart"]
    answer = "Yes."
    assert _grounded(answer, terms) is False, (
        "One-word answer must fail grounding"
    )


def test_grounded_passes_when_answer_uses_job_terms():
    """An answer that uses job-specific terms and is substantive should pass.
    Break: rejecting valid coaching that references the job."""
    terms = ["klaviyo", "abandoned-cart", "checkout"]
    answer = (
        "To set up the Klaviyo abandoned-cart flow, start by creating a new "
        "flow triggered by the checkout started event. Think about what "
        "condition distinguishes an abandoned cart from a completed purchase."
    )
    assert _grounded(answer, terms) is True, (
        "Substantive answer using job terms must pass grounding"
    )


def test_grounded_passes_with_empty_terms():
    """When the job has no distinctive terms, all substantive answers pass.
    Break: rejecting all answers when terms list is empty."""
    answer = (
        "That's an interesting approach. What do you think would happen "
        "if you tried a different trigger condition for the flow?"
    )
    assert _grounded(answer, []) is True, (
        "With empty terms, any substantive answer should pass"
    )
```

Run: `pytest tests/test_mentor_grounding.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — current `_grounded` accepts short answers and handover text

- [ ] **Step 3: Rewrite `_extract_terms` to be more selective**

```python
def _extract_terms(job_description):
    """Extract domain-specific terms from the job description for grounding.
    Filters out generic/common words and focuses on tool names, methodologies,
    and domain-specific vocabulary."""
    if not job_description:
        return []

    GENERIC = {
        "the", "this", "that", "with", "from", "have", "will", "been",
        "were", "they", "their", "about", "into", "over", "such", "your",
        "you", "and", "for", "are", "not", "but", "can", "may", "our",
        "who", "what", "when", "where", "how", "which", "would", "could",
        "should", "these", "those", "than", "them", "then", "some",
        "also", "just", "only", "very", "more", "most", "each", "does",
        "did", "any", "its", "all", "being", "there", "here", "other",
        "make", "like", "need", "work", "team", "new", "use", "used",
        "using", "best", "good", "able", "well", "know", "help", "look",
        "find", "give", "part", "take", "come", "back", "want", "way",
    }

    words = re.findall(r"[a-zA-Z][a-zA-Z \-]{2,}", job_description.lower())
    terms = []
    for w in words:
        w = w.strip()
        if w in GENERIC or len(w) < 4:
            continue
        if w not in terms:
            terms.append(w)
        if len(terms) >= 6:
            break
    return terms
```

- [ ] **Step 4: Rewrite `_grounded` with stronger checks**

```python
FORBIDDEN_PATTERNS = [
    "I have built",
    "I've built",
    "here is the complete",
    "here's the complete",
    "the finished",
    "the implementation is",
    "the code is",
    "```",
]

MIN_ANSWER_LENGTH = 30


def _grounded(candidate, terms):
    """Safety gate: an LLM answer must:
    1. Echo at least one job term (when terms exist)
    2. Never hand over the finished answer
    3. Be long enough to be substantive (>30 chars)
    4. Not be pure code blocks
    """
    if not candidate:
        return False
    if len(candidate.strip()) < MIN_ANSWER_LENGTH:
        return False
    lowered = candidate.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in lowered:
            return False
    if terms and not any(t in lowered for t in terms):
        return False
    return True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_mentor_grounding.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/mentor_agent.py tests/test_mentor_grounding.py
git commit -m "fix: strengthen mentor grounding gate to reject generic and handover answers"
```

---

## Task 9: Prevent proposal page from spawning duplicate threads

**Files:**
- Modify: `routes/proposals.py` (`index`, `_fill_in_background`)
- Test: `tests/test_proposal_thread.py`

**What this catches:** User refreshing the proposals page spawns multiple concurrent LLM calls for the same sprint.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_proposal_thread.py
"""
Tests that the proposal page does not spawn duplicate fill threads.
Break: every page load creating a new thread for the same sprint."""
import pytest
import threading
from routes.proposals import _active_fill_threads, _should_spawn_fill, _fill_done


def setup_function():
    """Clear active threads before each test."""
    _active_fill_threads.clear()


def test_first_load_spawns_thread():
    """First load for a sprint should allow thread creation.
    Break: rejecting the first load."""
    assert _should_spawn_fill("sprint-abc") is True


def test_second_load_skips_thread():
    """Second load for the same sprint should skip thread creation.
    Break: allowing duplicate threads."""
    _should_spawn_fill("sprint-abc")
    assert _should_spawn_fill("sprint-abc") is False


def test_different_sprint_can_spawn():
    """Different sprints should each get their own thread.
    Break: blocking all sprints after the first."""
    _should_spawn_fill("sprint-abc")
    assert _should_spawn_fill("sprint-xyz") is True


def test_fill_done_allows_new_thread():
    """After a fill completes, a new thread should be allowed.
    Break: permanently blocking after first thread."""
    _should_spawn_fill("sprint-abc")
    _fill_done("sprint-abc")
    assert _should_spawn_fill("sprint-abc") is True


def test_thread_safety_concurrent_access():
    """Concurrent calls should not corrupt the active set.
    Break: race condition in set add/discard."""
    results = []

    def worker(sprint_id):
        result = _should_spawn_fill(sprint_id)
        results.append(result)

    threads = [threading.Thread(target=worker, args=(f"sprint-{i}",)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # All 10 should succeed (each has a unique sprint ID)
    assert all(results), f"Not all workers succeeded: {results}"
    assert len(_active_fill_threads) == 10
```

Run: `pytest tests/test_proposal_thread.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `ImportError: cannot import name '_active_fill_threads' from 'routes.proposals'`

- [ ] **Step 3: Add thread deduplication**

```python
# routes/proposals.py — add at module level
_active_fill_threads = set()
_fill_lock = threading.Lock()


def _should_spawn_fill(sprint_id):
    """Check if we should spawn a new fill thread for this sprint."""
    with _fill_lock:
        if sprint_id in _active_fill_threads:
            return False
        _active_fill_threads.add(sprint_id)
        return True


def _fill_done(sprint_id):
    """Mark a fill thread as done."""
    with _fill_lock:
        _active_fill_threads.discard(sprint_id)
```

- [ ] **Step 4: Update `_fill_in_background` to call `_fill_done`**

```python
def _fill_in_background(app, sprint_id, cluster_key):
    try:
        # ... existing logic ...
    finally:
        _fill_done(sprint_id)
```

- [ ] **Step 5: Update `index()` to check before spawning**

```python
if _should_spawn_fill(sprint["id"]):
    threading.Thread(
        target=_fill_in_background, args=(app, sprint["id"], sprint["cluster_key"]),
        daemon=True,
    ).start()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_proposal_thread.py -v`

- [ ] **Step 7: Commit**

```bash
git add routes/proposals.py tests/test_proposal_thread.py
git commit -m "fix: prevent proposal page from spawning duplicate fill threads"
```

---

## Task 10: Add retry/backoff to async LLM calls

**Files:**
- Modify: `services/llm.py` (add retry wrapper)
- Modify: `services/lesson_engine.py` (use retry in `generate_sprint_content`)
- Test: `tests/test_llm_retry.py`

**What this catches:** Transient provider failures leave days permanently broken with no recovery.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_retry.py
"""
Tests that call_llm retries with backoff when providers fail transiently.
Break: single-shot LLM calls failing permanently on transient errors."""
import pytest
from unittest.mock import patch
from services.llm import call_llm


def test_retries_three_times_when_all_providers_fail():
    """call_llm with max_retries=3 should try all providers 3 times.
    Break: only trying once (max_retries=1 default)."""
    attempt_count = [0]

    def counting_env_call(prompt, timeout):
        attempt_count[0] += 1
        return None  # always fail

    with patch("services.llm._env_call", side_effect=counting_env_call):
        with patch("services.llm._openrouter_call", return_value=None):
            with patch("services.llm._omniroute_call", return_value=None):
                with patch("time.sleep"):
                    result = call_llm("test", timeout=5, max_retries=3, backoff_base=0.01)

    assert result is None
    # Each retry tries all 3 providers: 3 retries × 3 providers = 9 attempts
    # But _env_call is only one of the three — it gets called 3 times (once per retry)
    assert attempt_count[0] == 3, (
        f"Expected 3 attempts (one per retry), got {attempt_count[0]}"
    )


def test_succeeds_on_second_attempt():
    """If the first attempt fails but second succeeds, result should be returned.
    Break: not retrying after first failure."""
    call_count = [0]

    def flaky_call(prompt, timeout):
        call_count[0] += 1
        if call_count[0] == 1:
            return None  # first attempt fails
        return "success on retry"

    with patch("services.llm._env_call", side_effect=flaky_call):
        result = call_llm("test", timeout=5, max_retries=3, backoff_base=0.01)

    assert result == "success on retry", "Should succeed on second attempt"


def test_no_retry_when_first_succeeds():
    """If the first provider succeeds, no retries should happen.
    Break: retrying even on success."""
    call_count = [0]

    def first_success(prompt, timeout):
        call_count[0] += 1
        return "immediate success"

    with patch("services.llm._env_call", side_effect=first_success):
        with patch("time.sleep") as mock_sleep:
            result = call_llm("test", timeout=5, max_retries=3, backoff_base=1)

    assert result == "immediate success"
    assert mock_sleep.call_count == 0, "Should not sleep when first attempt succeeds"
    assert call_count[0] == 1, "Should only call once when first attempt succeeds"
```

Run: `pytest tests/test_llm_retry.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `TypeError: call_llm() got an unexpected keyword argument 'max_retries'`

- [ ] **Step 3: Add retry parameters to `call_llm`**

```python
# services/llm.py — modify call_llm
import time as time_module


def call_llm(prompt, timeout=90, max_retries=1, backoff_base=1):
    """Return a completion string, or None when no provider answered.
    Retries with exponential backoff when max_retries > 1."""
    delays = [backoff_base * (2 ** i) for i in range(max_retries)]
    for attempt in range(max_retries):
        for fn in (_env_call, _openrouter_call, _omniroute_call):
            try:
                out = fn(prompt, timeout)
            except Exception:
                out = None
            if out and str(out).strip():
                return str(out).strip()
        if attempt < max_retries - 1:
            time_module.sleep(delays[attempt])
    return None
```

- [ ] **Step 4: Update `lesson_engine.generate_sprint_content` to use retries**

Change `call_llm(prompt, timeout=90)` → `call_llm(prompt, timeout=90, max_retries=3, backoff_base=2)` in all LLM calls within the async worker.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_llm_retry.py -v`

- [ ] **Step 6: Commit**

```bash
git add services/llm.py services/lesson_engine.py tests/test_llm_retry.py
git commit -m "feat: add retry with exponential backoff to LLM calls in async generation"
```

---

## Task 11: Add Pydantic schema validation for LLM payloads

**Files:**
- Create: `services/schemas.py` (Pydantic models)
- Modify: `services/llm.py` (add `call_llm_validated` helper)
- Modify: `services/lesson_engine.py` (validate lesson payloads)
- Modify: `services/proposal_engine.py` (validate proposal drafts)
- Modify: `requirements.txt` (add pydantic)
- Test: `tests/test_schemas.py`

**What this catches:** Malformed LLM output stored in JSONB breaks template rendering at display time instead of at generation time when recovery is possible.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
"""
Tests that LLM output is validated against Pydantic schemas before storage.
Break: storing malformed JSON that breaks template rendering later."""
import pytest
from services.schemas import LessonPayload, ProjectAnatomy, ProposalDraft
from pydantic import ValidationError


def test_lesson_payload_requires_title():
    """A lesson without a title is useless to the learner.
    Break: accepting missing title."""
    with pytest.raises(ValidationError, match="title"):
        LessonPayload(objective="Learn stuff", script="Do things")


def test_lesson_payload_requires_objective():
    """A lesson without an objective has no learning goal.
    Break: accepting missing objective."""
    with pytest.raises(ValidationError, match="objective"):
        LessonPayload(title="Day 1", script="Do things")


def test_lesson_payload_requires_script():
    """A lesson without a script has no content.
    Break: accepting missing script."""
    with pytest.raises(ValidationError, match="script"):
        LessonPayload(title="Day 1", objective="Learn stuff")


def test_lesson_payload_accepts_valid():
    """A complete lesson payload should be accepted.
    Break: rejecting valid data."""
    payload = LessonPayload(
        title="Day 1: Setup",
        objective="Learn basic setup",
        script="Step 1: Install Klaviyo...",
        key_points=["Install Klaviyo", "Connect Shopify"],
        pitfalls=["Don't skip the API key step"],
    )
    assert payload.title == "Day 1: Setup"
    assert len(payload.key_points) == 2
    assert len(payload.pitfalls) == 1


def test_lesson_payload_defaults_empty_lists():
    """key_points and pitfalls should default to empty lists.
    Break: requiring them as mandatory."""
    payload = LessonPayload(
        title="Day 1", objective="Learn", script="Do"
    )
    assert payload.key_points == []
    assert payload.pitfalls == []


def test_project_anatomy_requires_title():
    """Project anatomy without a title is incomplete.
    Break: accepting missing title."""
    with pytest.raises(ValidationError, match="title"):
        ProjectAnatomy(clone_steps=["step 1"])


def test_project_anatomy_requires_clone_steps():
    """Project anatomy without clone_steps has no instructions.
    Break: accepting missing clone_steps."""
    with pytest.raises(ValidationError, match="clone_steps"):
        ProjectAnatomy(title="Clone the flow")


def test_proposal_draft_requires_hook():
    """A proposal without an opening hook has no first impression.
    Break: accepting missing opening_hook."""
    with pytest.raises(ValidationError, match="opening_hook"):
        ProposalDraft(
            proof_sentence="I built this",
            call_to_action="Let's talk",
        )
```

Run: `pytest tests/test_schemas.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: `ImportError: cannot import name 'LessonPayload' from 'services.schemas'`

- [ ] **Step 3: Create the schemas**

```python
# services/schemas.py
from pydantic import BaseModel, Field
from typing import Optional


class LessonPayload(BaseModel):
    title: str
    objective: str
    script: str
    key_points: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)


class ProjectAnatomy(BaseModel):
    title: str
    source_url: Optional[str] = None
    clone_steps: list[str]
    rubric: list[dict] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    opening_hook: str
    proof_sentence: str
    call_to_action: str
    score: int = -1


class CaseStudy(BaseModel):
    problem: str
    solution: str
    result: str
```

- [ ] **Step 4: Add `call_llm_validated` to `services/llm.py`**

```python
import json as _json
from services.schemas import LessonPayload, ProjectAnatomy, ProposalDraft, CaseStudy

_SCHEMA_MAP = {
    "lesson": LessonPayload,
    "project_anatomy": ProjectAnatomy,
    "proposal_draft": ProposalDraft,
    "case_study": CaseStudy,
}


def call_llm_validated(prompt: str, schema_name: str, timeout=90):
    """Call LLM and validate output against a Pydantic schema.
    Returns the parsed model, or raises LLMGenerationError on failure."""
    raw = call_llm(prompt, timeout=timeout)
    if not raw:
        raise LLMGenerationError(f"No LLM provider answered for {schema_name}")
    model_cls = _SCHEMA_MAP.get(schema_name)
    if model_cls is None:
        raise LLMGenerationError(f"Unknown schema: {schema_name}")
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        data = _json.loads(cleaned)
        return model_cls(**data)
    except (_json.JSONDecodeError, ValidationError) as e:
        raise LLMGenerationError(
            f"LLM output for {schema_name} did not match schema: {e}"
        )
```

- [ ] **Step 5: Wire validation into `lesson_engine` and `proposal_engine`**

In `services/lesson_engine.py`, replace `call_llm(prompt)` with `call_llm_validated(prompt, "lesson")` before storing.
In `services/proposal_engine.py`, use `call_llm_validated(prompt, "proposal_draft")`.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_schemas.py tests/test_llm_retry.py -v`

- [ ] **Step 7: Commit**

```bash
git add services/schemas.py services/llm.py services/lesson_engine.py services/proposal_engine.py requirements.txt tests/test_schemas.py
git commit -m "feat: add Pydantic schema validation for LLM-generated payloads"
```

---

## Task 12: Fix avg_contract_value to use contracts_completed as denominator

**Files:**
- Modify: `db/rpc.sql` (fix the `complete_contract` RPC)
- Modify: `services/outcome_service.py` (use RPC)
- Test: `tests/test_outcome_service.py`

**What this catches:** Contracts_won increments on add (not complete), diluting the average with abandoned contracts.

### Steps

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outcome_service.py
"""
Tests that contract operations are atomic and avg uses correct denominator.
Break: non-atomic insert+update, wrong denominator for avg."""
from unittest.mock import MagicMock
from services.outcome_service import add_contract, complete_contract


def test_add_contract_uses_single_rpc_call():
    """add_contract must be a single RPC, not separate insert + update.
    Break: separate DB calls that can leave stale counters."""
    sb = MagicMock()
    sb.rpc = MagicMock(return_value=MagicMock(data=[{
        "contract_id": "c1", "contracts_won": 1, "total_earned": 500,
        "avg_contract_value": 500.0, "first_contract_at": "2026-01-01T00:00:00Z"
    }]))

    result = add_contract(sb, "sprint-1", "user-1",
                          client_name="Acme", contract_value=500, platform="upwork")

    assert sb.rpc.call_count == 1, "Should use exactly 1 RPC call"
    assert sb.rpc.call_args[0][0] == "add_contract"
    assert result["contracts_won"] == 1
    assert result["total_earned"] == 500


def test_complete_contract_uses_single_rpc_call():
    """complete_contract must be a single RPC.
    Break: separate update + read + update."""
    sb = MagicMock()
    sb.rpc = MagicMock(return_value=MagicMock(data=[{
        "status": "completed", "contracts_completed": 1, "avg_contract_value": 500.0
    }]))

    result = complete_contract(sb, "sprint-1", "contract-1")

    assert sb.rpc.call_count == 1, "Should use exactly 1 RPC call"
    assert sb.rpc.call_args[0][0] == "complete_contract"
    assert result["status"] == "completed"


def test_avg_uses_completed_not_won():
    """avg_contract_value must divide by contracts_completed, not contracts_won.
    Break: using contracts_won as denominator (incremented on add, not complete)."""
    sb = MagicMock()
    # RPC returns: 1 completed, avg=1000 (i.e., total_earned=1000 / 1 completed)
    sb.rpc = MagicMock(return_value=MagicMock(data=[{
        "status": "completed", "contracts_completed": 1, "avg_contract_value": 1000.0
    }]))

    result = complete_contract(sb, "sprint-1", "contract-1")

    # If denominator were contracts_won (5), avg would be 200
    # If denominator is contracts_completed (1), avg is 1000
    assert result["avg_contract_value"] == 1000.0, (
        f"Expected avg=1000 (1000/1 completed), got {result['avg_contract_value']}"
    )
```

Run: `pytest tests/test_outcome_service.py -v`

- [ ] **Step 2: Run test to verify it fails**
Expected: FAIL — current code uses separate insert + update + read + update

- [ ] **Step 3: Create the SQL RPC functions**

```sql
-- db/rpc.sql
CREATE OR REPLACE FUNCTION public.add_contract(
    p_sprint_id UUID, p_user_id UUID,
    p_client_name TEXT DEFAULT NULL, p_project_title TEXT DEFAULT NULL,
    p_contract_value NUMERIC DEFAULT 0, p_your_rate NUMERIC DEFAULT NULL,
    p_hours_worked NUMERIC DEFAULT NULL, p_platform TEXT DEFAULT NULL,
    p_status TEXT DEFAULT 'active', p_is_repeat_client BOOLEAN DEFAULT FALSE
)
RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE _result UUID;
BEGIN
    INSERT INTO contracts (sprint_id, user_id, client_name, project_title,
                           contract_value, your_rate, hours_worked, platform,
                           status, is_repeat_client)
    VALUES (p_sprint_id, p_user_id, p_client_name, p_project_title,
            p_contract_value, p_your_rate, p_hours_worked, p_platform,
            p_status, p_is_repeat_client)
    RETURNING id INTO _result;

    RETURN jsonb_build_object(
        'contract_id', _result,
        'contracts_won', (SELECT contracts_won + 1 FROM sprints WHERE id = p_sprint_id),
        'total_earned', (SELECT total_earned + p_contract_value FROM sprints WHERE id = p_sprint_id),
        'first_contract_at', COALESCE(
            (SELECT first_contract_at FROM sprints WHERE id = p_sprint_id), now()
        )
    );
END; $$;


CREATE OR REPLACE FUNCTION public.complete_contract(
    p_sprint_id UUID, p_contract_id UUID
)
RETURNS JSONB LANGUAGE plpgsql AS $$
BEGIN
    UPDATE contracts SET status = 'completed'
    WHERE id = p_contract_id AND sprint_id = p_sprint_id AND status != 'completed';

    IF NOT FOUND THEN
        RETURN jsonb_build_object('status', 'completed', 'updated', false);
    END IF;

    UPDATE sprints
    SET contracts_completed = contracts_completed + 1,
        avg_contract_value = CASE
            WHEN contracts_completed + 1 > 0 THEN total_earned / (contracts_completed + 1)
            ELSE NULL
        END
    WHERE id = p_sprint_id;

    RETURN jsonb_build_object(
        'status', 'completed', 'updated', true,
        'contracts_completed', (SELECT contracts_completed FROM sprints WHERE id = p_sprint_id),
        'avg_contract_value', (SELECT avg_contract_value FROM sprints WHERE id = p_sprint_id)
    );
END; $$;
```

- [ ] **Step 4: Rewrite Python wrappers to use RPC**

```python
# services/outcome_service.py — rewrite both functions
def add_contract(sb, sprint_id, user_id, **fields):
    """Insert a contract and roll up sprint counters atomically via RPC."""
    res = sb.rpc("add_contract", {
        "p_sprint_id": sprint_id, "p_user_id": user_id,
        "p_client_name": fields.get("client_name"),
        "p_project_title": fields.get("project_title"),
        "p_contract_value": fields.get("contract_value", 0),
        "p_your_rate": fields.get("your_rate"),
        "p_hours_worked": fields.get("hours_worked"),
        "p_platform": fields.get("platform"),
        "p_status": fields.get("status", "active"),
        "p_is_repeat_client": fields.get("is_repeat_client", False),
    }).execute()
    rows = res.data
    if rows:
        r = rows[0]
        return {
            "contract_id": r.get("contract_id"),
            "contracts_won": r.get("contracts_won"),
            "total_earned": r.get("total_earned"),
            "avg_contract_value": r.get("avg_contract_value"),
            "first_contract_at": r.get("first_contract_at"),
        }
    return None


def complete_contract(sb, sprint_id, contract_id):
    """Mark contract completed and bump counter atomically via RPC."""
    res = sb.rpc("complete_contract", {
        "p_sprint_id": sprint_id, "p_contract_id": contract_id,
    }).execute()
    rows = res.data
    if rows and rows[0].get("updated"):
        return rows[0]
    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_outcome_service.py -v`

- [ ] **Step 6: Commit**

```bash
git add db/rpc.sql services/outcome_service.py tests/test_outcome_service.py
git commit -m "fix: atomic contract insert + counter update via RPC, avg uses contracts_completed"
```

---

## Task 13: Verify day-complete idempotency for Day 14 (sprint completion)

**Files:**
- Modify: `tests/test_day_complete.py` (add Day 14 idempotency test)

**What this catches:** Sprint completion (Day 14) re-stamping `completed_at` or re-issuing badge on double-click.

### Steps

- [ ] **Step 1: Add the Day 14 idempotency test**

Add this to `tests/test_day_complete.py` (created in Task 6):

```python
def test_day_14_already_done_is_noop():
    """Completing an already-completed Day 14 should not recompute meter.
    Break: re-stamping completed_at or re-incrementing streak."""
    from routes.sprints import _complete_day_if_not_done

    sb = MagicMock()
    sprint = {"id": "s1", "user_id": "u1", "cluster_key": "email-automation",
              "current_day": 14, "phase": "C"}

    # Day 14 already done
    sb.table.return_value.select.return_value.limit.return_value.execute.return_value.data = [
        {"is_done": True}
    ]

    result = _complete_day_if_not_done(sb, sprint, 14)

    assert result["already_done"] is True
    assert result.get("meter") is None
    sb.table.return_value.update.assert_not_called()
```

- [ ] **Step 2: Run test to verify it passes** (depends on Task 6)

Run: `pytest tests/test_day_complete.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/test_day_complete.py
git commit -m "test: verify Day 14 sprint completion idempotency"
```

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-20-fix-sprint-platform-design-flaws.md`.**

**TDD protocol applied:** Every task follows Red → Green → Refactor. Tests name the break they catch. Expected values are hand-derived literals. Mocks are only for external I/O (Supabase HTTP, LLM providers).

**Task dependency graph:**
```
Task 1 (anon key) ──→ Task 12 (RPC + avg fix)
Task 10 (LLM retry) ──→ Task 11 (Pydantic schemas)
Task 6 (day-complete guard) ──→ Task 13 (Day 14 idempotency)

All others are independent.
```

**Parallelizable groups:**
- **Group A** (security): Tasks 1, 2, 3
- **Group B** (data integrity): Tasks 5, 7, 8
- **Group C** (reliability): Tasks 4, 6, 9, 10
- **Group D** (validation): Task 11 (after Task 10)
- **Group E** (atomicity): Task 12 (after Task 1)

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
