"""
FakeSupabase — in-memory test double for the Supabase client.

The real routes/services call `get_supabase()` which returns a chainable
client:  sb.table(...).select(...).eq(...).order(...).limit(...).execute()
and for writes: .insert(...) / .update(...) / .upsert(...) / .delete().

This double reproduces the subset of that fluent API used across the app so
HTTP-level BDD tests can exercise real request→route→response cycles without a
live database. It is intentionally stateful per scenario and reset via reset().
"""
import re


class Result:
    """Return object for execute(); mirrors supabase's .data / .count."""

    def __init__(self, data):
        self.data = data or []
        self.count = len(self.data)


class Builder:
    """Fluent query builder mirroring the Supabase postgrest chain."""

    def __init__(self, table):
        self._t = table
        self._kind = "read"          # read | insert | update | upsert | delete
        self._payload = None
        self._on_conflict = None
        self._filters = []           # list of (op, key, value)
        self._order_cols = []        # list of (col, desc)
        self._limit_n = None
        self._count_exact = False
        self._select_cols = None

    # ── chain: reads ───────────────────────────────────────────────────
    def select(self, *cols, **kwargs):
        self._count_exact = kwargs.get("count") == "exact"
        if cols and cols[0] != "*":
            # Supabase/postgrest accepts a comma-separated column string, e.g.
            # select("cluster_key,current_day"). Split it like postgrest does.
            parsed = []
            for c in cols:
                for part in str(c).split(","):
                    part = part.strip()
                    if part:
                        parsed.append(part)
            self._select_cols = parsed
        return self

    def eq(self, k, v):
        self._filters.append(("eq", k, v))
        return self

    def in_(self, k, values):
        self._filters.append(("in", k, list(values)))
        return self

    def neq(self, k, v):
        self._filters.append(("neq", k, v))
        return self

    def gt(self, k, v):
        self._filters.append(("gt", k, v))
        return self

    def gte(self, k, v):
        self._filters.append(("gte", k, v))
        return self

    def lt(self, k, v):
        self._filters.append(("lt", k, v))
        return self

    def lte(self, k, v):
        self._filters.append(("lte", k, v))
        return self

    def order(self, *cols, **kwargs):
        desc = kwargs.get("desc", False)
        for c in cols:
            self._order_cols.append((c, desc))
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def range(self, lo, hi):  # noqa: A003 - mirror supabase api
        return self

    def single(self):
        self._limit_n = 1
        return self

    # ── chain: writes ──────────────────────────────────────────────────
    def insert(self, rows):
        self._kind = "insert"
        self._payload = rows
        return self

    def update(self, data):
        self._kind = "update"
        self._payload = dict(data)
        return self

    def upsert(self, data, on_conflict=None):
        self._kind = "upsert"
        self._payload = data
        self._on_conflict = on_conflict
        return self

    def delete(self):
        self._kind = "delete"
        return self

    # ── execute ────────────────────────────────────────────────────────
    def _matches(self, row):
        for op, k, v in self._filters:
            rv = row.get(k)
            if op == "eq" and rv != v:
                return False
            if op == "neq" and rv == v:
                return False
            if op == "in" and rv not in v:
                return False
            if op == "gt" and not (rv is not None and rv > v):
                return False
            if op == "gte" and not (rv is not None and rv >= v):
                return False
            if op == "lt" and not (rv is not None and rv < v):
                return False
            if op == "lte" and not (rv is not None and rv <= v):
                return False
        return True

    def _row_matches_conflict(self, row):
        """Conflict resolution for upsert — match on the on_conflict key(s)."""
        if not self._on_conflict:
            return False
        keys = [k.strip() for k in self._on_conflict.split(",")]
        for k in keys:
            if k in self._payload and row.get(k) == self._payload.get(k):
                return True
        return False

    def execute(self):
        rows = self._t._rows
        if self._kind == "read":
            out = [dict(r) for r in rows if self._matches(r)]
            for col, desc in self._order_cols:
                out.sort(key=lambda r: _key(r.get(col)), reverse=desc)
            if self._limit_n is not None:
                out = out[: self._limit_n]
            if self._select_cols:
                out = [{k: r.get(k) for k in self._select_cols if k in r} for r in out]
            return Result(out)
        if self._kind == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted = []
            for p in payloads:
                row = dict(p)
                if "id" not in row:
                    row["id"] = f"{self._t.name}-{len(rows) + 1}"
                rows.append(row)
                inserted.append(dict(row))
            return Result(inserted)
        if self._kind == "update":
            n = 0
            for i, r in enumerate(rows):
                if self._matches(r):
                    for k, v in self._payload.items():
                        rows[i][k] = _resolve_value(rows[i].get(k), v)
                    n += 1
            return Result(rows)
        if self._kind == "upsert":
            # update first matching row by conflict key, else insert
            target = None
            for i, r in enumerate(rows):
                if self._matches(r) and self._row_matches_conflict(r):
                    target = i
                    break
            if target is None:
                row = dict(self._payload)
                if "id" not in row:
                    row["id"] = f"{self._t.name}-{len(rows) + 1}"
                rows.append(row)
                return Result([dict(row)])
            for k, v in self._payload.items():
                rows[target][k] = _resolve_value(rows[target].get(k), v)
            return Result([dict(rows[target])])
        if self._kind == "delete":
            remaining = [r for r in rows if not self._matches(r)]
            self._t._rows = remaining
            return Result([])
        return Result([])


def _key(v):
    return (v is not None, v)


def _resolve_value(old, new):
    """Resolve SQL-ish string increments like "col + 1" to a real int."""
    if isinstance(new, str) and re.fullmatch(r"[a-z_]+ ?\+ ?\d+", new):
        col, _, num = re.split(r"\s*\+\s*", new)
        try:
            base = int(old) if old is not None else 0
            return base + int(num)
        except (TypeError, ValueError):
            return new
    return new


class _Table:
    def __init__(self, store, name):
        self._store = store
        self.name = name
        self._rows = store._data.setdefault(name, [])

    def select(self, *cols, **kwargs):
        return Builder(self).select(*cols, **kwargs)

    def insert(self, rows):
        return Builder(self).insert(rows)

    def update(self, data):
        return Builder(self).update(data)

    def upsert(self, data, on_conflict=None):
        return Builder(self).upsert(data, on_conflict)

    def delete(self):
        return Builder(self).delete()


class FakeSupabase:
    """In-memory supabase client. seed(table, rows) adds fixtures; reset() clears."""

    def __init__(self):
        self._data = {}

    def table(self, name):
        return _Table(self, name)

    def seed(self, table, rows):
        self._data.setdefault(table, []).extend([dict(r) for r in rows])

    def rows(self, table):
        return list(self._data.get(table, []))

    def reset(self):
        self._data = {}


def make_get_supabase(fake):
    """Return a callable that mimics get_supabase() returning the fake."""

    def _get_supabase():
        return fake

    return _get_supabase
