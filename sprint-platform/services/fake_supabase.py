"""
FakeSupabase — in-memory test/demo double for the Supabase client.

Mirrors the chainable fluent API used across the app:
  sb.table(...).select(...).eq(...).order(...).limit(...).execute()
  sb.table(...).insert(...) / .update(...) / .upsert(...) / .delete()

When no SUPABASE_URL is configured the app serves from this store (dev mode,
localhost). BDD tests reset it per scenario and seed fixtures via steps.
Supports SQL-ish increment strings ("proposals_sent + 1") like postgrest.
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
        self._kind = "read"
        self._payload = None
        self._on_conflict = None
        self._filters = []
        self._order_cols = []
        self._limit_n = None
        self._count_exact = False
        self._select_cols = None

    # ── chain: reads ────────────────────────────────────────────────
    def select(self, *cols, **kwargs):
        self._count_exact = kwargs.get("count") == "exact"
        if cols and cols[0] != "*":
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

    def range(self, lo, hi):
        return self

    def single(self):
        self._limit_n = 1
        return self

    # ── chain: writes ───────────────────────────────────────────────
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

    # ── execute ─────────────────────────────────────────────────────
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
        if not self._on_conflict:
            return False
        keys = [k.strip() for k in self._on_conflict.split(",")]
        # Composite unique keys require ALL conflict columns to match.
        return all(
            k in self._payload and row.get(k) == self._payload.get(k)
            for k in keys
        )

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
            target = None
            for i, r in enumerate(rows):
                # Prefer on_conflict match; fall back to active eq-filters.
                if self._on_conflict:
                    if self._row_matches_conflict(r):
                        target = i
                        break
                elif self._matches(r):
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
    if isinstance(new, str) and re.fullmatch(r"[a-z_]+ ?\+ ?\d+", new):
        parts = re.split(r"\s*\+\s*", new)
        col, num = parts[0], parts[1]
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
