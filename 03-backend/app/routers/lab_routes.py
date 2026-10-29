"""'Under the hood' — the DBMS lab: tables, schema, named queries, plans,
constraint scenarios and concurrency demonstrations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from .. import catalog, concurrency, lab
from ..db import fetch, fetch_one, transaction

router = APIRouter(prefix="/api/lab", tags=["lab"])

# The 15 core tables, grouped as in 02-database/schema/02_tables.sql
TABLES = {
    "states": "GEOGRAPHY", "cities": "GEOGRAPHY", "landmarks": "GEOGRAPHY",
    "hotels": "PROPERTY", "hotel_landmarks": "PROPERTY", "amenities": "PROPERTY", "hotel_amenities": "PROPERTY",
    "room_types": "INVENTORY", "rooms": "INVENTORY", "seasons": "INVENTORY",
    "guests": "CUSTOMER",
    "bookings": "BOOKING", "booking_rooms": "BOOKING", "payments": "BOOKING", "reviews": "BOOKING",
}
HIDDEN_COLUMNS = {"search_doc"}          # tsvector: noisy in a table view


def _check_table(name: str) -> None:
    if name not in TABLES:              # whitelist: table names can't be bound as parameters
        raise HTTPException(404, f"unknown table {name!r}")


@router.get("/overview")
def overview():
    with transaction(read_only=True) as conn:
        rows = fetch(conn, """
            SELECT c.relname AS table_name, c.reltuples::bigint AS approx_rows,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
                   (SELECT string_agg(a.attname, ', ' ORDER BY k.ord)
                    FROM pg_constraint p CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum, ord)
                    JOIN pg_attribute a ON a.attrelid = p.conrelid AND a.attnum = k.attnum
                    WHERE p.conrelid = c.oid AND p.contype = 'p') AS primary_key,
                   (SELECT count(*) FROM pg_constraint f WHERE f.conrelid = c.oid AND f.contype = 'f') AS foreign_keys,
                   (SELECT count(*) FROM pg_constraint u WHERE u.conrelid = c.oid AND u.contype = 'u') AS unique_keys,
                   (SELECT count(*) FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype IN ('c','x')) AS checks,
                   obj_description(c.oid) AS comment
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY c.relname""")
    for r in rows:
        r["group"] = TABLES.get(r["table_name"])
    order = list(TABLES)
    rows.sort(key=lambda r: order.index(r["table_name"]) if r["table_name"] in order else 99)
    return {"data": rows}


@router.get("/tables/{name}")
def table_rows(name: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    _check_table(name)
    with transaction(read_only=True) as conn:
        cols = [r["column_name"] for r in fetch(conn, """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position""", (name,))
                if r["column_name"] not in HIDDEN_COLUMNS]
        pk = fetch_one(conn, """
            SELECT string_agg(quote_ident(a.attname), ', ' ORDER BY k.ord) AS pk
            FROM pg_constraint p CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = p.conrelid AND a.attnum = k.attnum
            WHERE p.conrelid = %s::regclass AND p.contype = 'p'""", (name,))["pk"]
        col_list = ", ".join(f'"{c}"' for c in cols)
        sql = f"SELECT {col_list} FROM {name} ORDER BY {pk} LIMIT %s OFFSET %s"
        rows = fetch(conn, sql, (page_size, (page - 1) * page_size))
        total = fetch_one(conn, "SELECT reltuples::bigint AS n FROM pg_class WHERE oid = %s::regclass", (name,))["n"]
    return {"data": {"table": name, "columns": cols, "rows": [list(r.values()) for r in rows],
                     "page": page, "page_size": page_size, "approx_total": total,
                     "sql": sql.replace("%s", str(page_size), 1).replace("%s", str((page - 1) * page_size), 1)}}


@router.get("/tables/{name}/schema")
def table_schema(name: str):
    _check_table(name)
    with transaction(read_only=True) as conn:
        columns = fetch(conn, """
            SELECT a.attname AS column_name, format_type(a.atttypid, a.atttypmod) AS data_type,
                   NOT a.attnotnull AS nullable, pg_get_expr(d.adbin, d.adrelid) AS default_value,
                   a.attgenerated <> '' AS generated
            FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum""", (name,))
        constraints = fetch(conn, """
            SELECT conname AS name,
                   CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE'
                                WHEN 'c' THEN 'CHECK' WHEN 'x' THEN 'EXCLUDE' END AS kind,
                   pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE conrelid = %s::regclass
            ORDER BY array_position(ARRAY['p','u','f','c','x']::"char"[], contype), conname""", (name,))
        referenced_by = fetch(conn, """
            SELECT conrelid::regclass::text AS child_table, conname AS name, pg_get_constraintdef(oid) AS definition
            FROM pg_constraint WHERE confrelid = %s::regclass AND contype = 'f'
            ORDER BY 1""", (name,))
        indexes = fetch(conn, "SELECT indexname AS name, indexdef AS definition FROM pg_indexes "
                              "WHERE schemaname = 'public' AND tablename = %s ORDER BY 1", (name,))
        triggers = fetch(conn, """
            SELECT tgname AS name, pg_get_triggerdef(oid) AS definition
            FROM pg_trigger WHERE tgrelid = %s::regclass AND NOT tgisinternal ORDER BY 1""", (name,))
    return {"data": {"table": name, "group": TABLES[name], "columns": columns, "constraints": constraints,
                     "referenced_by": referenced_by, "indexes": indexes, "triggers": triggers}}


def _entries(collection: str) -> list[dict]:
    return [{k: v for k, v in q.as_dict().items()} for q in catalog.load(collection).values()]


def _get(collection: str, name: str):
    q = catalog.load(collection).get(name)
    if not q:
        raise HTTPException(404, f"unknown entry {name!r}")
    return q


@router.get("/queries")
def list_queries():
    return {"data": _entries("queries")}


@router.post("/queries/{name}/run")
def run_query(name: str):
    return {"data": lab.run_query(_get("queries", name))}


@router.post("/queries/{name}/explain")
def explain_query(name: str):
    return {"data": lab.explain(_get("queries", name))}


@router.get("/plans")
def list_plans():
    return {"data": _entries("plans")}


@router.post("/plans/{name}/run")
def run_plan(name: str):
    return {"data": lab.explain(_get("plans", name))}


@router.get("/why")
def list_why():
    return {"data": _entries("why")}


@router.post("/why/{name}/run")
def run_why(name: str):
    return {"data": lab.run_why(_get("why", name))}


@router.get("/concurrency")
def list_concurrency():
    return {"data": [{"name": k, "doc": (v.__doc__ or "").strip()} for k, v in concurrency.SCENARIOS.items()]}


@router.post("/concurrency/{name}/run")
def run_concurrency(name: str):
    fn = concurrency.SCENARIOS.get(name)
    if not fn:
        raise HTTPException(404, f"unknown scenario {name!r}")
    return {"data": fn()}


@router.get("/media/{media_id}")
def media(media_id: int):
    """Unit 5 multimedia: an image stored as bytea, served with its MIME type."""
    with transaction(read_only=True) as conn:
        row = fetch_one(conn, "SELECT mime_type, content FROM lab.hotel_media WHERE media_id = %s", (media_id,))
    if not row:
        raise HTTPException(404, "media not found")
    return Response(content=bytes(row["content"]), media_type=row["mime_type"],
                    headers={"Cache-Control": "public, max-age=86400"})
