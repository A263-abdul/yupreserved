"""
Lab engine: runs catalog entries safely.

Every lab statement runs inside a transaction that is ALWAYS rolled back, so
nothing in the lab can change the data — even the "why not" scenarios that
try to insert, update or delete.
"""
from __future__ import annotations

import json
import time

import psycopg

from .catalog import NamedQuery
from .db import _jsonable, lab_pool, pool
from .errors import explain_db_error

MAX_ROWS = 200


def _run_setup(cur, q: NamedQuery) -> None:
    for stmt in filter(None, (s.strip() for s in q.setup.split(";"))):
        cur.execute(stmt)


def run_query(q: NamedQuery) -> dict:
    """Run a read-only named query and return columns + rows (capped)."""
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                _run_setup(cur, q)
                t0 = time.perf_counter()
                cur.execute(q.sql)
                rows = cur.fetchmany(MAX_ROWS + 1)
                ms = (time.perf_counter() - t0) * 1000
                columns = [d.name for d in cur.description]
        finally:
            conn.rollback()
    return {
        "query": q.as_dict(),
        "columns": columns,
        "rows": [_jsonable(list(r.values())) for r in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
        "ms": round(ms, 2),
    }


def explain(q: NamedQuery, analyze: bool = True) -> dict:
    """EXPLAIN (ANALYZE, BUFFERS) a query; returns the text plan and a summary."""
    options = "ANALYZE, BUFFERS, " if analyze else ""
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                _run_setup(cur, q)
                cur.execute(f"EXPLAIN ({options}FORMAT TEXT) {q.sql}")
                text_plan = "\n".join(next(iter(r.values())) for r in cur.fetchall())
                cur.execute(f"EXPLAIN ({options}FORMAT JSON) {q.sql}")
                json_plan = next(iter(cur.fetchone().values()))
        finally:
            conn.rollback()
    plan = json_plan[0] if isinstance(json_plan, list) else json.loads(json_plan)[0]
    return {
        "query": q.as_dict(),
        "plan_text": text_plan,
        "operators": sorted(_operators(plan["Plan"])),
        "planning_ms": plan.get("Planning Time"),
        "execution_ms": plan.get("Execution Time"),
    }


def _operators(node: dict) -> set[str]:
    ops = {node["Node Type"] + (f" ({node['Join Type']})" if node.get("Join Type") else "")}
    if node.get("Sort Method"):
        ops.add(f"Sort Method: {node['Sort Method']}")
    for child in node.get("Plans", []):
        ops |= _operators(child)
    return ops


def run_why(q: NamedQuery) -> dict:
    """Run a statement that is expected to fail; report which rule stopped it."""
    with lab_pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                for stmt in _split(q.sql):
                    cur.execute(stmt)
            outcome = {"failed": False, "message": "The statement succeeded (and was rolled back)."}
        except psycopg.Error as err:
            outcome = {"failed": True, **explain_db_error(err)}
        finally:
            conn.rollback()
    return {"query": q.as_dict(), **outcome}


def _split(sql: str) -> list[str]:
    """Split on top-level semicolons (the scenarios contain no strings with ';')."""
    return [s.strip() for s in sql.split(";\n") if s.strip()]
