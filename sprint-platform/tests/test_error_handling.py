"""Regression tests for the app-crash fixes (P0-1, P0-2, P1-1, P1-3).

- obtain_supabase() never returns None (returns client or aborts 503).
- A DB outage on any route yields a clean 503, not a 500 traceback.
- Global handlers render a friendly page for 404/500/503 with no traceback leak.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import create_app
from routes import obtain_supabase


def _make_app(testing=True):
    return create_app({
        "TESTING": testing,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-key",
        "SUPABASE_SERVICE_KEY": "test-key",
        "SUPABASE_ANON_KEY": "test-anon",
    })


@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "test-key",
        "SUPABASE_SERVICE_KEY": "test-key",
        "SUPABASE_ANON_KEY": "test-anon",
    })
    with app.test_client() as c:
        yield c


def test_obtain_supabase_returns_client(monkeypatch):
    import routes as _routes

    class Dummy:
        pass

    monkeypatch.setattr(_routes, "get_supabase", lambda: Dummy())
    assert isinstance(obtain_supabase(), Dummy)


def test_obtain_supabase_aborts_without_creds(monkeypatch):
    import routes.sprints as sm

    # Bypass the login gate so the request reaches obtain_supabase(); with EMPTY
    # Supabase creds the helper must abort(503), never crash with a 500.
    monkeypatch.setattr(sm, "require_login", lambda: None)
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test",
        "SUPABASE_URL": "",
        "SUPABASE_KEY": "",
        "SUPABASE_SERVICE_KEY": "",
        "SUPABASE_ANON_KEY": "",
    })
    c = app.test_client()
    resp = c.get("/sprints/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 503


def test_obtain_supabase_function_aborts(monkeypatch):
    from werkzeug.exceptions import ServiceUnavailable

    import routes as _routes

    def boom():
        raise RuntimeError("no creds")

    monkeypatch.setattr(_routes, "get_supabase", boom)
    app = _make_app(testing=True)
    with app.app_context():
        with pytest.raises(ServiceUnavailable):
            obtain_supabase()


def test_error_handlers_render_friendly_404(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    body = resp.data.lower()
    assert b"not found" in body
    # 404 carries no error ref (only 500/503 do), so no <code> ref block.
    assert b"<code>" not in resp.data


def test_unhandled_exception_returns_500():
    app = _make_app(testing=False)

    @app.route("/__test_boom__")
    def _boom():
        raise ValueError("kaboom")

    c = app.test_client()
    resp = c.get("/__test_boom__")
    assert resp.status_code == 500
    body = resp.data.lower()
    assert b"something went wrong" in body
    assert b"kaboom" not in resp.data  # no raw traceback leak


def test_503_handler_renders_friendly_page():
    app = _make_app(testing=False)

    @app.route("/__test_503__")
    def _boom503():
        from flask import abort
        abort(503)

    c = app.test_client()
    resp = c.get("/__test_503__")
    assert resp.status_code == 503
    assert b"temporarily unavailable" in resp.data.lower()


def test_lesson_engine_reraises_non_llm_error():
    import services.lesson_engine as le

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, sb, table):
            self.sb = sb
            self.table = table

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def update(self, payload):
            self.sb.updates.append((self.table, payload))
            return self

        def execute(self):
            # Both sprint + day queries fail → outer handler's stamp query also
            # fails → non-LLM error must still propagate (so main.py also records).
            raise ConnectionError("db down")

    class FakeSB:
        def __init__(self):
            self.updates = []

        def table(self, name):
            return Query(self, name)

    sb = FakeSB()
    with pytest.raises(ConnectionError):
        le.generate_sprint_content(sb, "00000000-0000-0000-0000-000000000000")


def test_lesson_engine_stamps_generation_error_for_non_llm(monkeypatch):
    import services.lesson_engine as le

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, sb, table, rows):
            self.sb = sb
            self.table = table
            self.rows = rows

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def update(self, payload):
            self.sb.updates.append((self.table, payload))
            return self

        def execute(self):
            return Result(self.rows)

    SID = "00000000-0000-0000-0000-000000000000"
    day_row = {"day_no": 1, "action_payload": {}}

    class FakeSB:
        def __init__(self):
            self.updates = []

        def table(self, name):
            if name == "sprints":
                return Query(self, name, [{"cluster_key": "email-automation"}])
            if name == "sprint_days":
                return Query(self, name, [day_row])
            if name == "copywork_projects":
                return Query(self, name, [])
            return Query(self, name, [])

    # lesson_for_day raises a non-LLM error → per-day handler stamps it.
    def boom(*a, **k):
        raise ConnectionError("llm backend unreachable")

    monkeypatch.setattr(le, "lesson_for_day", boom)

    sb = FakeSB()
    le.generate_sprint_content(sb, SID)

    assert sb.updates, "expected a stamp update on failure"
    stamped = sb.updates[0][1]["action_payload"].get("generation_error")
    assert stamped and "Generation failed" in stamped
