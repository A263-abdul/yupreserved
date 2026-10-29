"""
yup — the YupReserved database from the command line.

    ./yup tables                     the 15 tables with row counts and keys
    ./yup show hotels -n 10          rows of a table
    ./yup describe bookings          columns, constraints, indexes, triggers
    ./yup keys                       every primary, candidate and foreign key
    ./yup queries [-t join]          the named query library
    ./yup q joins.left_outer         run a named query (with its relational algebra)
    ./yup plans / explain <name>     how PostgreSQL executes a query (Unit 4)
    ./yup why [name]                 "why can't I …?" constraint demonstrations
    ./yup txn deadlock               concurrency demos with two real sessions (Unit 5)
    ./yup quote 1 2026-12-24 2026-12-26     price breakdown for a stay
    ./yup find "gateway"             search cities, landmarks and hotels
    ./yup sql "SELECT …"             any read-only SQL   (--write to change data)
    ./yup recovery                   crash-recovery (WAL) demonstration

  actions — everything the website does:
    ./yup search Udaipur --in 2026-12-24 --out 2026-12-26 --stars 4
    ./yup hotel 3                    a hotel: rooms, amenities, landmarks, rating
    ./yup avail 3 2026-12-24 2026-12-26
    ./yup signup                     create a guest account
    ./yup guest 9876543210           a guest and their trips (by phone or id)
    ./yup book --phone 98… --room-type 7 --in 2026-12-24 --out 2026-12-26
    ./yup booking YRSBVACG           one booking with rooms and payments
    ./yup cancel YRSBVACG            cancel, with the refund the policy gives
    ./yup review YRSBVACG -r 5 -t "Lovely"
    ./yup stats                      platform dashboard
    ./yup                            interactive menu (no need to remember commands)
    ./yup install                    make `yup` work from any folder

The CLI reuses the backend's modules (03-backend/app) so the CLI, the API and
the website all run exactly the same SQL.
"""
from __future__ import annotations

import atexit
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03-backend"))

import psycopg                                    # noqa: E402
from psycopg.rows import tuple_row                # noqa: E402
import typer                                      # noqa: E402
from rich import box                              # noqa: E402
from rich.console import Console                  # noqa: E402
from rich.panel import Panel                      # noqa: E402
from rich.syntax import Syntax                    # noqa: E402
from rich.table import Table                      # noqa: E402

from app import catalog, concurrency, lab         # noqa: E402
from app.db import lab_pool, pool                 # noqa: E402
from app.errors import explain_db_error           # noqa: E402
from app.routers.lab_routes import TABLES         # noqa: E402

app = typer.Typer(add_completion=False, rich_markup_mode="rich", no_args_is_help=False,
                  help="[bold]yup[/] — explore the YupReserved database from the terminal.")
console = Console()

SAFFRON, INDIGO, MUTED = "#E07A2E", "#5B6CC9", "grey58"


# ── helpers ────────────────────────────────────────────────────────────────
def _open():
    if not pool.closed:
        return
    pool.open(wait=True)
    lab_pool.open()
    atexit.register(lab_pool.close)
    atexit.register(pool.close)


def _rows(sql: str, params=None) -> tuple[list[str], list[tuple]]:
    with pool.connection() as conn:
        try:
            cur = conn.cursor(row_factory=tuple_row)
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(sql, params)
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
        finally:
            conn.rollback()
    return cols, rows


def _fmt(v) -> str:
    if v is None:
        return "[grey50]NULL[/]"
    if isinstance(v, float):
        return f"{int(v):,}" if v.is_integer() else f"{v:,.2f}"
    text = str(v)
    return text if len(text) <= 60 else text[:57] + "…"


def _table(cols, rows, title: str | None = None, caption: str | None = None) -> Table:
    t = Table(title=title, caption=caption, box=box.SIMPLE_HEAVY, header_style=f"bold {SAFFRON}",
              title_style="bold", caption_style=MUTED, show_lines=False)
    for c in cols:
        t.add_column(str(c), overflow="fold")
    for r in rows:
        t.add_row(*[_fmt(v) for v in r])
    return t


def _header(q: catalog.NamedQuery) -> None:
    body = f"[bold]{q.title}[/]\n[{MUTED}]{q.topic}[/]"
    if q.algebra:
        body += f"\n\n[{INDIGO}]RA / RC:[/] {q.algebra}"
    if q.explain:
        body += f"\n\n{q.explain}"
    console.print(Panel(body, title=f"[bold {SAFFRON}]{q.name}[/]", title_align="left", border_style=SAFFRON))


def _write(sql: str, params=None) -> tuple[list[str], list[tuple]]:
    """Run a statement that changes data, in ONE transaction: COMMIT on success, ROLLBACK on any error."""
    with pool.connection() as conn:
        cur = conn.cursor(row_factory=tuple_row)
        try:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            cur.execute("SET CONSTRAINTS ALL IMMEDIATE")      # run deferred checks before COMMIT
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return cols, rows


def _guest_by(who: str) -> tuple | None:
    """Find a guest by phone (a candidate key) or by guest_id."""
    col = "phone" if len(who) == 10 else "guest_id"
    _, rows = _rows(f"SELECT guest_id, first_name, last_name, phone, email FROM guests WHERE {col} = %s",
                    (who if col == "phone" else int(who),))
    return rows[0] if rows else None


def _db_error(err: psycopg.Error) -> None:
    e = explain_db_error(err)
    console.print(Panel(f"[bold red]{e['error']}[/]\n\n[bold]Rule:[/] {e['rule']}"
                        + (f"\n[bold]Hint:[/] {e['hint']}" if e.get("hint") else ""),
                        title="✗ rejected by the database", border_style="red"))


# ── tables ─────────────────────────────────────────────────────────────────
@app.command()
def tables():
    """The 15 core tables with row counts, primary keys and constraint counts."""
    _open()
    cols, rows = _rows("""
        SELECT c.relname,
               (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM %I', c.relname), false, true, '')))[1]::text::bigint,
               (SELECT string_agg(a.attname, ', ' ORDER BY k.ord) FROM pg_constraint p
                CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum, ord)
                JOIN pg_attribute a ON a.attrelid = p.conrelid AND a.attnum = k.attnum
                WHERE p.conrelid = c.oid AND p.contype = 'p'),
               (SELECT count(*) FROM pg_constraint f WHERE f.conrelid = c.oid AND f.contype = 'f'),
               (SELECT count(*) FROM pg_constraint u WHERE u.conrelid = c.oid AND u.contype = 'u'),
               (SELECT count(*) FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype IN ('c','x')),
               pg_size_pretty(pg_total_relation_size(c.oid))
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'""")
    order = list(TABLES)
    rows.sort(key=lambda r: order.index(r[0]))
    t = Table(box=box.SIMPLE_HEAVY, header_style=f"bold {SAFFRON}",
              title="[bold]YupReserved · 15 core tables[/]")
    for c in ("#", "group", "table", "rows", "primary key", "FK", "UNIQUE", "CHECK", "size"):
        t.add_column(c, justify="right" if c in ("#", "rows", "FK", "UNIQUE", "CHECK") else "left")
    total = 0
    for i, r in enumerate(rows, 1):
        total += r[1]
        t.add_row(str(i), f"[{MUTED}]{TABLES[r[0]]}[/]", f"[bold]{r[0]}[/]", f"{r[1]:,}", r[2],
                  str(r[3]), str(r[4]), str(r[5]), r[6])
    t.caption = f"{total:,} rows in total"
    console.print(t)


@app.command()
def show(table: str, n: int = typer.Option(15, "-n", help="number of rows"),
         where: Optional[str] = typer.Option(None, "-w", "--where", help="SQL condition, e.g. \"star_rating = 5\""),
         order: Optional[str] = typer.Option(None, "-o", "--order", help="ORDER BY expression")):
    """Show rows of one table, e.g. [bold]./yup show hotels -w "city_id = 255" -n 5[/]"""
    if table not in TABLES:
        raise typer.BadParameter(f"choose one of: {', '.join(TABLES)}")
    _open()
    cols, _ = _rows(f"SELECT * FROM {table} LIMIT 0")
    cols = [c for c in cols if c != "search_doc"]
    sql = f"SELECT {', '.join(cols)} FROM {table}" + (f" WHERE {where}" if where else "") \
          + (f" ORDER BY {order}" if order else " ORDER BY 1") + f" LIMIT {int(n)}"
    try:
        cols, rows = _rows(sql)
    except psycopg.Error as e:
        return _db_error(e)
    console.print(Syntax(sql, "sql", theme="ansi_dark", word_wrap=True))
    console.print(_table(cols, rows, caption=f"{len(rows)} row(s)"))


@app.command()
def describe(table: str):
    """Columns, keys, constraints, indexes and triggers of a table."""
    if table not in TABLES:
        raise typer.BadParameter(f"choose one of: {', '.join(TABLES)}")
    _open()
    from app.routers.lab_routes import table_schema
    s = table_schema(table)["data"]
    console.print(Panel(f"[bold]{table}[/]  ·  {s['group']}", border_style=SAFFRON))
    console.print(_table(["column", "type", "null?", "default"],
                         [(c["column_name"], c["data_type"], "yes" if c["nullable"] else "NOT NULL",
                           ("GENERATED " if c["generated"] else "") + (c["default_value"] or ""))
                          for c in s["columns"]], title="Columns"))
    console.print(_table(["kind", "name", "definition"],
                         [(c["kind"], c["name"], c["definition"]) for c in s["constraints"]], title="Constraints"))
    if s["referenced_by"]:
        console.print(_table(["child table", "foreign key", "definition"],
                             [(r["child_table"], r["name"], r["definition"]) for r in s["referenced_by"]],
                             title="Referenced by"))
    console.print(_table(["index", "definition"], [(i["name"], i["definition"]) for i in s["indexes"]], title="Indexes"))
    if s["triggers"]:
        console.print(_table(["trigger", "definition"], [(t["name"], t["definition"]) for t in s["triggers"]],
                             title="Triggers"))


@app.command()
def keys():
    """Every primary key, candidate (UNIQUE) key and foreign key."""
    _open()
    for name in ("catalog.primary_keys", "catalog.candidate_keys", "catalog.foreign_keys"):
        q = catalog.load("queries")[name]
        cols, rows = _rows(q.sql)
        console.print(_table(cols, rows, title=q.title))


# ── named queries ──────────────────────────────────────────────────────────
@app.command()
def queries(topic: Optional[str] = typer.Option(None, "-t", "--topic", help="filter, e.g. join, normal, division")):
    """List the named query library."""
    qs = [q for q in catalog.load("queries").values()
          if not topic or topic.lower() in (q.name + q.topic + q.title).lower()]
    console.print(_table(["name", "title", "syllabus topic"], [(q.name, q.title, q.topic) for q in qs],
                         caption=f"{len(qs)} queries · run one with ./yup q <name>"))


@app.command("q")
def run_named(name: str, sql: bool = typer.Option(True, "--sql/--no-sql", help="print the SQL")):
    """Run a named query, e.g. [bold]./yup q division.not_exists[/]"""
    q = catalog.load("queries").get(name)
    if not q:
        raise typer.BadParameter("unknown query — see ./yup queries")
    _open()
    _header(q)
    if sql:
        console.print(Syntax(q.sql, "sql", theme="ansi_dark", word_wrap=True))
    r = lab.run_query(q)
    console.print(_table(r["columns"], r["rows"],
                         caption=f"{len(r['rows'])} row(s){' (truncated)' if r['truncated'] else ''} · {r['ms']} ms"))


@app.command()
def plans():
    """List the query-processing demonstrations."""
    qs = catalog.load("plans").values()
    console.print(_table(["name", "title", "syllabus topic"], [(q.name, q.title, q.topic) for q in qs],
                         caption="./yup explain <name>"))


@app.command()
def explain(name: str):
    """EXPLAIN ANALYZE a plan demo or any named query."""
    q = catalog.load("plans").get(name) or catalog.load("queries").get(name)
    if not q:
        raise typer.BadParameter("unknown name — see ./yup plans")
    _open()
    _header(q)
    if q.setup:
        console.print(f"[{MUTED}]setup:[/] {q.setup}")
    console.print(Syntax(q.sql, "sql", theme="ansi_dark", word_wrap=True))
    r = lab.explain(q)
    console.print(Panel(r["plan_text"], title="EXPLAIN (ANALYZE, BUFFERS)", border_style=INDIGO))
    console.print(f"[bold]operators:[/] {', '.join(r['operators'])}   "
                  f"[bold]planning:[/] {r['planning_ms']} ms   [bold]execution:[/] {r['execution_ms']} ms")


# ── constraints & transactions ─────────────────────────────────────────────
@app.command()
def why(name: Optional[str] = typer.Argument(None, help="scenario name; omit to run them all")):
    """'Why can't I …?' — statements the database must refuse."""
    _open()
    items = catalog.load("why")
    selected = [items[name]] if name else list(items.values())
    for q in selected:
        r = lab.run_why(q)
        status = "[bold green]✓ refused[/]" if r["failed"] else "[bold red]✗ was allowed[/]"
        console.print(Panel(
            f"{status}  [bold]{q.title}[/]\n[{MUTED}]{q.topic}[/]\n\n"
            + (f"[red]{r['error']}[/]\n[bold]Rule:[/] {r['rule']}" if r["failed"] else r["message"])
            + (f"\n\n[{MUTED}]{q.explain}[/]" if name else ""),
            title=q.name, title_align="left", border_style="green" if r["failed"] else "red"))
        if name:
            console.print(Syntax(q.sql, "sql", theme="ansi_dark", word_wrap=True))


@app.command()
def txn(scenario: str = typer.Argument(..., help=" | ".join(concurrency.SCENARIOS))):
    """Run a concurrency / recovery demonstration with two real sessions."""
    fn = concurrency.SCENARIOS.get(scenario)
    if not fn:
        raise typer.BadParameter(f"choose one of: {', '.join(concurrency.SCENARIOS)}")
    with console.status(f"running {scenario} …"):
        r = fn()
    timelines = {"": r["timeline"]} if "timeline" in r else {k: v["timeline"] for k, v in r["results"].items()}
    for label, events in timelines.items():
        t = Table(title=label or scenario, box=box.SIMPLE_HEAVY, header_style=f"bold {SAFFRON}")
        for c in ("t (ms)", "session", "step", "result"):
            t.add_column(c, overflow="fold")
        for e in events:
            colour = SAFFRON if e["session"] == "A" or e["session"] == "Reader" else INDIGO
            t.add_row(str(e["t_ms"]), f"[bold {colour}]{e['session']}[/]", e["step"], _fmt(e["result"]))
        console.print(t)
    console.print(Panel(r["lesson"], title="what this shows", border_style=SAFFRON))


# ── retrieval ──────────────────────────────────────────────────────────────
@app.command()
def quote(room_type_id: int, check_in: str, check_out: str, rooms: int = typer.Option(1, "-r")):
    """Night-by-night price, e.g. [bold]./yup quote 1 2026-12-24 2026-12-26[/]"""
    _open()
    try:
        cols, rows = _rows("""SELECT h.hotel_name, rt.type_name FROM room_types rt JOIN hotels h USING (hotel_id)
                              WHERE rt.room_type_id = %s""", (room_type_id,))
        name = f"{rows[0][0]} · {rows[0][1]}" if rows else f"room type {room_type_id}"
        cols, rows = _rows("SELECT night, day_name AS day, season_name AS season, base_price AS base, "
                           "season_multiplier AS \"×season\", weekend_multiplier AS \"×wkend\", nightly_rate AS rate, "
                           "gst_rate AS \"gst%%\", gst_amount AS gst, night_total AS total "
                           "FROM fn_quote_stay(%s, %s, %s, %s)",
                           (room_type_id, date.fromisoformat(check_in), date.fromisoformat(check_out), rooms))
    except psycopg.Error as e:
        return _db_error(e)
    total = sum(float(r[-1]) for r in rows)
    console.print(_table(cols, rows, title=name,
                         caption=f"{len(rows)} night(s) × {rooms} room(s)  ·  total ₹{total:,.2f} incl. GST"))


@app.command()
def find(text: str):
    """Search cities, landmarks and hotels (what the search box does)."""
    _open()
    from app.routers.catalog_routes import destinations
    rows = destinations(q=text, limit=12)["data"]
    console.print(_table(["kind", "id", "name", "where", "hotels"],
                         [(r["kind"], r["id"], r["label"], r["sublabel"], r["hotels"]) for r in rows]))


@app.command()
def sql(statement: str, write: bool = typer.Option(False, "--write", help="allow INSERT / UPDATE (asks first, then commits)")):
    """Run any SQL. Read-only by default; with --write it can change data — every constraint and trigger still applies."""
    _open()
    try:
        if write:
            console.print(Syntax(statement, "sql", theme="ansi_dark", word_wrap=True))
            if not typer.confirm("This will change the database. Commit it?"):
                raise typer.Abort()
            cols, rows = _write(statement)
            console.print("[green]✓ committed[/]")
        else:
            cols, rows = _rows(statement)
    except psycopg.Error as e:
        return _db_error(e)
    if cols:
        console.print(_table(cols, rows[:200], caption=f"{len(rows)} row(s)"))


# ── crash recovery ─────────────────────────────────────────────────────────
@app.command()
def recovery(yes: bool = typer.Option(False, "--yes", help="skip the confirmation")):
    """Crash-recovery demo: kill the server mid-transaction, restart, let the WAL recover."""
    if not yes and not typer.confirm("This stops PostgreSQL with 'immediate' mode (a simulated crash) and "
                                     "restarts it. Continue?"):
        raise typer.Abort()
    admin = "postgresql://postgres@localhost:5433/yupreserved"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute("CREATE TABLE IF NOT EXISTS lab.recovery_demo (id serial PRIMARY KEY, note text, at timestamptz DEFAULT now())")
        c.execute("INSERT INTO lab.recovery_demo (note) VALUES ('committed before the crash')")
        lsn = c.execute("SELECT pg_current_wal_lsn()::text").fetchone()[0]
    console.print(f"[green]✓[/] committed row written · WAL position {lsn}")
    open_txn = psycopg.connect(admin)
    open_txn.execute("INSERT INTO lab.recovery_demo (note) VALUES ('NOT committed when the crash happened')")
    console.print("[yellow]…[/] second row inserted inside an OPEN transaction (no COMMIT)")
    console.print("[red]⚡ crash:[/] pg_ctl stop -m immediate (no checkpoint, no clean shutdown)")
    subprocess.run([str(ROOT / "scripts" / "db.sh"), "stop-crash"], check=False, capture_output=True)
    try:
        open_txn.close()
    except Exception:
        pass
    time.sleep(1)
    subprocess.run([str(ROOT / "scripts" / "db.sh"), "start"], check=True, capture_output=True)
    console.print("[green]✓[/] server restarted — recovery log:")
    log_dir = Path.home() / ".yupreserved" / "pgdata" / "log"
    latest = max(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
    for line in latest.read_text(errors="ignore").splitlines()[-40:]:
        if any(k in line for k in ("not properly shut down", "automatic recovery", "redo", "ready to accept")):
            console.print(f"   [{MUTED}]{line.split('LOG:')[-1].strip()}[/]")
    with psycopg.connect(admin) as c:
        rows = c.execute("SELECT id, note, at FROM lab.recovery_demo ORDER BY id DESC LIMIT 5").fetchall()
    console.print(_table(["id", "note", "at"], rows, title="lab.recovery_demo after recovery"))
    console.print(Panel("The committed row survived (durability: it was in the write-ahead log before COMMIT "
                        "returned). The uncommitted row is gone (atomicity: REDO replays the log, and the "
                        "unfinished transaction is never marked committed).", border_style=SAFFRON))


# ════════════════════════════════════════════════════════════════════════════
#  ACTIONS — everything the website does, from the terminal
# ════════════════════════════════════════════════════════════════════════════
@app.command()
def search(place: Optional[str] = typer.Argument(None, help="city or landmark, e.g. Udaipur or 'Gateway of India'"),
           check_in: Optional[str] = typer.Option(None, "--in", help="YYYY-MM-DD"),
           check_out: Optional[str] = typer.Option(None, "--out", help="YYYY-MM-DD"),
           stars: Optional[int] = typer.Option(None, "--stars", help="minimum stars"),
           max_price: Optional[int] = typer.Option(None, "--max", help="max price per night (₹)"),
           mood: Optional[str] = typer.Option(None, "--mood", help="heritage | hills | beach | water | spiritual | workation | family | budget"),
           sort: str = typer.Option("recommended", "--sort", help="recommended | price_asc | price_desc | rating | distance"),
           n: int = typer.Option(15, "-n")):
    """Search stays like the website does (same SQL, same filters)."""
    _open()
    from app.routers.catalog_routes import destinations, search as api_search
    city_id = landmark_id = None
    if place:
        hits = destinations(q=place, limit=5)["data"]
        hit = next((h for h in hits if h["kind"] in ("city", "landmark")), None)
        if not hit:
            raise typer.BadParameter(f"no city or landmark like {place!r}")
        city_id = hit["id"] if hit["kind"] == "city" else None
        landmark_id = hit["id"] if hit["kind"] == "landmark" else None
        console.print(f"[{MUTED}]{hit['kind']}:[/] [bold]{hit['label']}[/] ({hit['sublabel']})")
        if landmark_id and sort == "recommended":
            sort = "distance"
    r = api_search(city_id=city_id, landmark_id=landmark_id, q=None, mood=mood,
                   check_in=date.fromisoformat(check_in) if check_in else None,
                   check_out=date.fromisoformat(check_out) if check_out else None,
                   adults=2, min_price=None, max_price=max_price,
                   stars=list(range(stars, 6)) if stars else [],
                   types=[], amenities=[], signature_only=False, sort=sort, page=1, page_size=n)["data"]
    dated = bool(check_in and check_out)
    cols = ["id", "hotel", "type", "★", "rating", "area"] + (["near (km)"] if landmark_id else []) + \
           (["your stay ₹", "free rooms"] if dated else ["from ₹/night"])
    rows = []
    for h in r["results"]:
        row = [h["hotel_id"], ("✦ " if h["is_signature"] else "") + h["hotel_name"], h["property_type"], h["star_rating"] or "–",
               h["avg_rating"] or "new", h["locality"] or h["city_name"]]
        if landmark_id:
            row.append(h["distance_km"])
        row += [h.get("stay_total") or "sold out", h.get("free_rooms")] if dated else [h["from_price"]]
        rows.append(row)
    console.print(_table(cols, rows, caption=f"{r['total']:,} stays match · showing {len(rows)} · ./yup hotel <id> for details"))


@app.command()
def hotel(hotel_id: int):
    """Everything about one hotel: story, rooms and prices, amenities, landmarks, reviews."""
    _open()
    from app.routers.catalog_routes import hotel_detail
    h = hotel_detail(hotel_id)["data"]
    console.print(Panel(f"[bold]{h['hotel_name']}[/]  {'★' * h['star_rating']}  ·  {h['property_type']}\n"
                        f"[{MUTED}]{h['address']}  ·  {h['city_name']}, {h['state_name']}[/]\n\n"
                        + (f"[italic]{h['tagline']}[/]\n" if h.get("tagline") else "") + h["description"]
                        + f"\n\nrating {h['avg_rating'] or '—'} from {h['review_count']} reviews  ·  "
                          f"check-in {h['check_in_time'][:5]}  ·  check-out {h['check_out_time'][:5]}",
                        title=f"hotel {hotel_id}", border_style=SAFFRON))
    console.print(_table(["room_type_id", "room type", "bed", "sleeps", "sq ft", "list ₹/night", "rooms"],
                         [(r["room_type_id"], r["type_name"], r["bed_type"], f"{r['max_adults']}+{r['max_children']}",
                           r["area_sqft"], r["base_price"], r["rooms"]) for r in h["room_types"]], title="Rooms"))
    console.print(_table(["nearby", "category", "distance"], [(l["landmark_name"], l["category"], f"{l['distance_km']} km" if l["distance_km"] is not None else "listed")
                                                              for l in h["landmarks"]], title="Landmarks"))
    console.print(f"[bold]Amenities:[/] {', '.join(a['amenity_name'] for a in h['amenities'])}")
    console.print(f"[{MUTED}]./yup avail {hotel_id} <check-in> <check-out>  ·  ./yup quote <room_type_id> <in> <out>[/]")


@app.command()
def avail(hotel_id: int, check_in: str, check_out: str, rooms: int = typer.Option(1, "-r")):
    """Free rooms of each type for a date range, with the total price."""
    _open()
    try:
        cols, rows = _rows("""SELECT a.room_type_id, a.type_name, a.base_price, a.max_adults, a.free_rooms, a.total_rooms,
                                     CASE WHEN a.free_rooms >= %(r)s THEN fn_stay_total(a.room_type_id, %(i)s, %(o)s, %(r)s) END AS total_incl_gst
                              FROM fn_available_rooms(%(h)s, %(i)s, %(o)s) a""",
                           {"h": hotel_id, "i": date.fromisoformat(check_in), "o": date.fromisoformat(check_out), "r": rooms})
    except psycopg.Error as e:
        return _db_error(e)
    console.print(_table(cols, rows, caption="book with: ./yup book --phone <phone> --room-type <room_type_id> --in … --out …"))


@app.command()
def signup(first: str = typer.Option(..., prompt="First name"), last: str = typer.Option(..., prompt="Last name"),
           phone: str = typer.Option(..., prompt="Mobile (10 digits)"), email: str = typer.Option(..., prompt="Email"),
           dob: str = typer.Option(..., prompt="Date of birth (YYYY-MM-DD)"),
           id_type: str = typer.Option("PAN", prompt="ID type (PAN / PASSPORT / DRIVING_LICENCE / VOTER_ID)"),
           id_number: str = typer.Option(..., prompt="ID number")):
    """Create a guest account (domains, UNIQUE keys and the age CHECK all apply)."""
    _open()
    try:
        _, rows = _write("""INSERT INTO guests (first_name, last_name, phone, email, date_of_birth, id_type, id_number)
                            VALUES (%s, %s, %s, lower(%s), %s, %s, upper(%s)) RETURNING guest_id""",
                         (first, last, phone, email, dob, id_type.upper(), id_number))
    except psycopg.Error as e:
        return _db_error(e)
    console.print(f"[green]✓ guest {rows[0][0]} created[/] — book with ./yup book --phone {phone} …")


@app.command()
def guest(who: str = typer.Argument(..., help="phone number or guest_id")):
    """A guest's profile and all their trips."""
    _open()
    g = _guest_by(who)
    if not g:
        raise typer.BadParameter("no such guest")
    console.print(Panel(f"[bold]{g[1]} {g[2]}[/]  ·  guest {g[0]}\n+91 {g[3]}  ·  {g[4]}", border_style=SAFFRON))
    trips(str(g[0]))


@app.command()
def trips(who: str = typer.Argument(..., help="phone number or guest_id")):
    """All bookings of a guest (v_booking_summary)."""
    _open()
    g = _guest_by(who)
    if not g:
        raise typer.BadParameter("no such guest")
    cols, rows = _rows("""SELECT booking_ref, hotel_name, city_name, check_in, nights, rooms, total, paid, refunded, status
                          FROM v_booking_summary WHERE guest_id = %s ORDER BY check_in DESC""", (g[0],))
    console.print(_table(cols, rows, caption=f"{len(rows)} booking(s) · ./yup booking <ref> for details"))


@app.command()
def booking(ref: str):
    """One booking: guest, hotel, rooms, prices and every payment."""
    _open()
    cols, rows = _rows("SELECT * FROM v_booking_summary WHERE booking_ref = %s", (ref.upper(),))
    if not rows:
        raise typer.BadParameter("no such booking")
    b = dict(zip(cols, rows[0]))
    console.print(Panel(f"[bold]{b['booking_ref']}[/]  ·  {b['status']}\n{b['guest_name']} at [bold]{b['hotel_name']}[/], {b['city_name']}\n"
                        f"{b['check_in']} → {b['check_out']}  ({b['nights']} nights, {b['rooms']} room(s), {b['adults']}+{b['children']} guests)\n"
                        f"total ₹{b['total']:,}  ·  paid ₹{b['paid']:,}  ·  refunded ₹{b['refunded']:,}", border_style=SAFFRON))
    c2, r2 = _rows("""SELECT r.room_number, rt.type_name, br.room_subtotal, br.room_tax FROM booking_rooms br
                      JOIN rooms r USING (room_id) JOIN room_types rt USING (room_type_id) WHERE br.booking_id = %s""", (b["booking_id"],))
    console.print(_table(c2, r2, title="Rooms"))
    c3, r3 = _rows("SELECT kind, method, status, amount, upi_vpa, card_last4, gateway_ref, created_at FROM payments WHERE booking_id = %s ORDER BY payment_id",
                   (b["booking_id"],))
    console.print(_table(c3, r3, title="Payments"))


@app.command()
def book(phone: str = typer.Option(..., "--phone", help="guest's mobile (must have an account: ./yup signup)"),
         room_type: int = typer.Option(..., "--room-type", help="room_type_id (see ./yup hotel <id>)"),
         check_in: str = typer.Option(..., "--in"), check_out: str = typer.Option(..., "--out"),
         rooms: int = typer.Option(1, "--rooms"), adults: int = typer.Option(2, "--adults"), children: int = typer.Option(0, "--children"),
         method: str = typer.Option("UPI", "--method", help="UPI | CARD | NETBANKING | WALLET | PAY_AT_HOTEL"),
         upi: Optional[str] = typer.Option(None, "--upi", help="UPI ID, e.g. name@okaxis"),
         yes: bool = typer.Option(False, "--yes", help="don't ask for confirmation")):
    """Book a stay — the same fn_book_stay transaction the website uses (row locks, triggers, payment)."""
    _open()
    g = _guest_by(phone)
    if not g:
        raise typer.BadParameter("no account for this phone — create one with ./yup signup")
    quote(room_type, check_in, check_out, rooms)
    if not yes and not typer.confirm(f"Book this for {g[1]} {g[2]}?"):
        raise typer.Abort()
    try:
        cols, rows = _write("SELECT * FROM fn_book_stay(%s, %s, %s, %s, %s, %s, %s, %s::payment_method_t, %s, NULL)",
                            (g[0], room_type, date.fromisoformat(check_in), date.fromisoformat(check_out), rooms, adults, children,
                             method.upper(), upi or (f"{g[1].lower()}@okaxis" if method.upper() == "UPI" else None)))
    except psycopg.Error as e:
        return _db_error(e)
    r = dict(zip(cols, rows[0]))
    console.print(Panel(f"[bold green]Yup. It's reserved.[/]  [bold]{r['booking_ref']}[/]  ·  ₹{r['total_amount']:,}  ·  {r['status']}",
                        border_style="green"))


@app.command()
def cancel(ref: str, yes: bool = typer.Option(False, "--yes")):
    """Cancel a booking (CALL sp_cancel_booking) — shows the refund the policy gives first."""
    _open()
    cols, rows = _rows("""SELECT b.booking_id, b.status, b.check_in, b.check_in - DATE '2026-10-29' AS days_left, v.paid - v.refunded AS net
                          FROM bookings b JOIN v_booking_summary v USING (booking_id) WHERE b.booking_ref = %s""", (ref.upper(),))
    if not rows:
        raise typer.BadParameter("no such booking")
    bid, status, ci, days, net = rows[0]
    pct = 100 if days >= 7 else 50 if days >= 2 else 0
    console.print(f"{ref.upper()} is {status}; check-in {ci} ({days} days away) → refund {pct}% of ₹{net:,}")
    if not yes and not typer.confirm("Cancel it?"):
        raise typer.Abort()
    try:
        _, out = _write("CALL sp_cancel_booking(%s, NULL)", (bid,))
    except psycopg.Error as e:
        return _db_error(e)
    console.print(f"[green]✓ cancelled[/] — refund ₹{out[0][0]:,}")


@app.command()
def review(ref: str, rating: int = typer.Option(..., "-r", "--rating", min=1, max=5), title: str = typer.Option(..., "-t", "--title"),
           body: Optional[str] = typer.Option(None, "-b", "--body")):
    """Review a completed stay (trigger checks it was completed; rating rolls up into the hotel)."""
    _open()
    try:
        _, rows = _write("""INSERT INTO reviews (booking_id, rating, title, body)
                            SELECT booking_id, %s, %s, %s FROM bookings WHERE booking_ref = %s RETURNING review_id""",
                         (rating, title, body, ref.upper()))
    except psycopg.Error as e:
        return _db_error(e)
    if not rows:
        raise typer.BadParameter("no such booking")
    console.print(f"[green]✓ review {rows[0][0]} saved[/] — the hotel's average rating was updated by trg_reviews_rollup")


@app.command()
def stats():
    """Platform dashboard: size, money, busiest cities, payment mix."""
    _open()
    _, r = _rows("""SELECT (SELECT count(*) FROM hotels), (SELECT count(*) FROM rooms), (SELECT count(*) FROM guests),
                           (SELECT count(*) FROM bookings), (SELECT count(*) FROM bookings WHERE status IN ('CONFIRMED','PENDING')),
                           (SELECT sum(amount) FILTER (WHERE kind = 'CHARGE') - coalesce(sum(amount) FILTER (WHERE kind = 'REFUND'), 0)
                              FROM payments WHERE status = 'SUCCESS')""")
    h, rm, g, b, up, rev = r[0]
    console.print(Panel(f"[bold]{h:,}[/] hotels · [bold]{rm:,}[/] rooms · [bold]{g:,}[/] guests · [bold]{b:,}[/] bookings "
                        f"([bold]{up:,}[/] upcoming) · net revenue [bold]₹{rev:,.0f}[/]", title="YupReserved today", border_style=SAFFRON))
    cols, rows = _rows("SELECT city_name, hotels, bookings, room_nights, room_revenue, avg_daily_rate FROM mv_city_performance ORDER BY room_revenue DESC LIMIT 8")
    console.print(_table(cols, rows, title="Top cities (materialized view)"))
    run_named("agg.filter", sql=False)


# ── interactive menu & install ─────────────────────────────────────────────
MENU = [
    ("Show the 15 tables", lambda: tables()),
    ("Rows of a table", lambda: show(typer.prompt("table", default="hotels"), n=int(typer.prompt("how many rows", default="10")), where=None, order=None)),
    ("Describe a table (columns, keys, constraints)", lambda: describe(typer.prompt("table", default="bookings"))),
    ("All keys (primary, candidate, foreign)", lambda: keys()),
    ("Search hotels", lambda: search(typer.prompt("city or landmark", default="Udaipur"),
                                     check_in=typer.prompt("check-in (blank = any)", default="", show_default=False) or None,
                                     check_out=typer.prompt("check-out (blank = any)", default="", show_default=False) or None,
                                     stars=None, max_price=None, mood=None, sort="recommended", n=12)),
    ("One hotel's details", lambda: hotel(int(typer.prompt("hotel id", default="1")))),
    ("Price for a stay", lambda: quote(int(typer.prompt("room_type_id", default="1")), typer.prompt("check-in", default="2026-12-24"),
                                       typer.prompt("check-out", default="2026-12-26"), 1)),
    ("Book a stay", lambda: book(typer.prompt("guest phone"), int(typer.prompt("room_type_id")), typer.prompt("check-in"),
                                 typer.prompt("check-out"), 1, int(typer.prompt("adults", default="2")), 0, "UPI", None, False)),
    ("A guest and their trips", lambda: guest(typer.prompt("phone or guest id"))),
    ("Cancel a booking", lambda: cancel(typer.prompt("booking ref"), False)),
    ("Run a named query", lambda: (queries(None), run_named(typer.prompt("query name", default="joins.left_outer"), sql=True))),
    ("Why can't I…? (all constraint demos)", lambda: why(None)),
    ("Query plan", lambda: (plans(), explain(typer.prompt("plan name", default="plan.hash_join")))),
    ("Concurrency demo", lambda: txn(typer.prompt(" | ".join(concurrency.SCENARIOS), default="double_booking_race"))),
    ("Dashboard", lambda: stats()),
    ("Any SQL (read-only)", lambda: sql(typer.prompt("SQL"), write=False)),
]


@app.command()
def menu():
    """Interactive menu — pick an action by number."""
    while True:
        t = Table(box=box.SIMPLE, show_header=False, title="[bold]YupReserved — what would you like to do?[/]")
        t.add_column(justify="right", style=f"bold {SAFFRON}")
        t.add_column()
        for i, (label, _) in enumerate(MENU, 1):
            t.add_row(str(i), label)
        t.add_row("0", "Quit")
        console.print(t)
        choice = typer.prompt("choose", default="0")
        if choice in ("0", "q", "quit", "exit"):
            break
        try:
            MENU[int(choice) - 1][1]()
        except (ValueError, IndexError):
            console.print("[red]pick a number from the list[/]")
        except typer.Abort:
            console.print("[yellow]cancelled[/]")
        except (typer.BadParameter, psycopg.Error) as e:
            console.print(f"[red]{e}[/]")
        typer.prompt("\npress Enter to go back to the menu", default="", show_default=False)


@app.command()
def install():
    """Make `yup` work from any folder (adds one alias line to ~/.zshrc)."""
    rc = Path.home() / ".zshrc"
    line = f'alias yup="{ROOT / "yup"}"'
    if rc.exists() and line in rc.read_text():
        console.print("[green]✓ already installed[/] — open a new terminal and type [bold]yup[/]")
        return
    if not typer.confirm(f"Add this line to {rc}?\n  {line}\n"):
        raise typer.Abort()
    with open(rc, "a") as fh:
        fh.write(f"\n# YupReserved CLI\n{line}\n")
    console.print("[green]✓ installed[/] — open a new terminal (or run [bold]source ~/.zshrc[/]) and type [bold]yup[/] anywhere")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """[bold]yup[/] — run with no command for an interactive menu, or see the commands below."""
    if ctx.invoked_subcommand is None:
        menu()


if __name__ == "__main__":
    app()
