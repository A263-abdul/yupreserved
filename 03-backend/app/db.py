"""
Database access layer.

No ORM on purpose: every statement the app runs is plain SQL that can be read,
copied into psql and explained in the viva. Each helper returns the rows AND a
`trace` (the SQL text, parameters and time taken), which the frontend shows in
its "Under the hood" drawer.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime
from decimal import Decimal
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL, LAB_DATABASE_URL

# check_connection tests each connection when it is handed out, so a database
# restart (e.g. the crash-recovery demo) never surfaces as an error to the user
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=6, open=False, check=ConnectionPool.check_connection,
                      kwargs={"row_factory": dict_row, "autocommit": False})
lab_pool = ConnectionPool(LAB_DATABASE_URL, min_size=0, max_size=2, open=False, check=ConnectionPool.check_connection,
                          kwargs={"row_factory": dict_row, "autocommit": False})


@dataclass
class Trace:
    """What the database was asked, for the 'Under the hood' panel."""
    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, sql: str, params: Any, rows: int, ms: float) -> None:
        self.steps.append({"sql": _clean(sql), "params": _jsonable(params), "rows": rows, "ms": round(ms, 2)})


def _clean(sql: str) -> str:
    lines = [l.rstrip() for l in sql.strip("\n").splitlines()]
    indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return "\n".join(l[indent:] for l in lines)


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime, dtime)):
        return v.isoformat()
    return v


@contextmanager
def transaction(read_only: bool = False) -> Iterator[Connection]:
    """A connection inside one transaction: COMMIT on success, ROLLBACK on error."""
    with pool.connection() as conn:
        if read_only:
            conn.execute("SET TRANSACTION READ ONLY")
        yield conn


def fetch(conn: Connection, sql: str, params: Any = None, trace: Trace | None = None) -> list[dict]:
    t0 = time.perf_counter()
    cur = conn.execute(sql, params)
    rows = cur.fetchall() if cur.description else []
    if trace is not None:
        trace.add(sql, params, len(rows), (time.perf_counter() - t0) * 1000)
    return [_jsonable(r) for r in rows]


def fetch_one(conn: Connection, sql: str, params: Any = None, trace: Trace | None = None) -> dict | None:
    rows = fetch(conn, sql, params, trace)
    return rows[0] if rows else None


def columns_of(cur) -> list[str]:
    return [d.name for d in cur.description] if cur.description else []
