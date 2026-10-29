"""
Generate the project diagrams with Graphviz.

    er-diagram        relational schema read LIVE from the PostgreSQL catalog
                      (tables, columns, PK / FK markers, FK arrows)
    er-chen           conceptual ER diagram in Chen notation (entities,
                      relationships, cardinalities, weak entity)
    architecture      three-tier system architecture
    workflow          booking workflow (what happens on "Confirm & pay")

Output: 06-docs/diagrams/*.svg|png and 05-frontend/public/er-diagram.svg
Run:    ~/.yupreserved/venv/bin/python 06-docs/diagrams/build_diagrams.py
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOT = Path.home() / ".yupreserved" / "env" / "bin" / "dot"
DB = "postgresql://postgres@localhost:5433/yupreserved"

INK, PAPER, SINDOOR, HALDI, PEACOCK, MONSOON, LINE = "#1E2233", "#FBF7F0", "#C4472B", "#E3A72F", "#1F6F6B", "#5B6C8F", "#DDD0BB"
GROUP_COLOUR = {"GEOGRAPHY": PEACOCK, "PROPERTY": SINDOOR, "INVENTORY": HALDI, "CUSTOMER": MONSOON, "BOOKING": INK}
GROUPS = {
    "GEOGRAPHY": ["states", "cities", "landmarks"],
    "PROPERTY": ["hotels", "hotel_landmarks", "amenities", "hotel_amenities"],
    "INVENTORY": ["room_types", "rooms", "seasons"],
    "CUSTOMER": ["guests"],
    "BOOKING": ["bookings", "booking_rooms", "payments", "reviews"],
}
FONT = "Helvetica"


def render(name: str, dot_src: str, png: bool = True) -> None:
    (HERE / f"{name}.dot").write_text(dot_src)
    subprocess.run([str(DOT), "-Tsvg", "-o", str(HERE / f"{name}.svg"), str(HERE / f"{name}.dot")], check=True)
    if png:
        subprocess.run([str(DOT), "-Tpng", "-Gdpi=170", "-o", str(HERE / f"{name}.png"), str(HERE / f"{name}.dot")], check=True)
    print(f"  ✓ {name}")


def er_diagram() -> None:
    with psycopg.connect(DB) as c:
        cols = c.execute("""
            SELECT a.attrelid::regclass::text, a.attname, format_type(a.atttypid, a.atttypmod), a.attnum,
                   EXISTS (SELECT 1 FROM pg_constraint p WHERE p.conrelid = a.attrelid AND p.contype = 'p' AND a.attnum = ANY(p.conkey)),
                   EXISTS (SELECT 1 FROM pg_constraint f WHERE f.conrelid = a.attrelid AND f.contype = 'f' AND a.attnum = ANY(f.conkey)),
                   EXISTS (SELECT 1 FROM pg_constraint u WHERE u.conrelid = a.attrelid AND u.contype = 'u' AND a.attnum = ANY(u.conkey))
            FROM pg_attribute a JOIN pg_class t ON t.oid = a.attrelid JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND t.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY 1, a.attnum""").fetchall()
        fks = c.execute("""
            SELECT conrelid::regclass::text, confrelid::regclass::text,
                   (SELECT string_agg(attname, ',') FROM pg_attribute WHERE attrelid = conrelid AND attnum = ANY(conkey))
            FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE contype = 'f' AND n.nspname = 'public'""").fetchall()

    by_table: dict[str, list] = {}
    for t, col, typ, _n, pk, fk, uq in cols:
        if col == "search_doc":
            typ = "tsvector (generated)"
        by_table.setdefault(t, []).append((col, typ, pk, fk, uq))

    def node(t: str, colour: str) -> str:
        rows = "".join(
            f'<TR><TD ALIGN="LEFT" PORT="{col}"><FONT COLOR="{SINDOOR if pk else INK}">'
            f'{"<B>" if pk else ""}{("PK " if pk else "") + ("FK " if fk else "") + ("UQ " if uq and not pk else "")}{col}{"</B>" if pk else ""}'
            f'</FONT></TD><TD ALIGN="LEFT"><FONT COLOR="#7B7F8F">{typ.replace("character varying", "varchar")}</FONT></TD></TR>'
            for col, typ, pk, fk, uq in by_table[t])
        return (f'"{t}" [label=<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{PAPER}">'
                f'<TR><TD COLSPAN="2" BGCOLOR="{colour}"><FONT COLOR="white"><B>{t}</B></FONT></TD></TR>{rows}</TABLE>> '
                f'shape=plain];')

    out = [f'digraph ER {{ graph [rankdir=LR, bgcolor="white", nodesep=0.5, ranksep=1.1, fontname="{FONT}", pad=0.3, splines=true];',
           f'node [fontname="{FONT}", fontsize=10]; edge [color="{MONSOON}", arrowhead=crow, arrowtail=tee, dir=both, penwidth=1.2];']
    for g, tables in GROUPS.items():
        out.append(f'subgraph "cluster_{g}" {{ label=<<B>{g}</B>>; fontcolor="{GROUP_COLOUR[g]}"; color="{LINE}"; style="rounded,dashed";')
        out += [node(t, GROUP_COLOUR[g]) for t in tables]
        out.append("}")
    for child, parent, col in fks:
        # arrow from parent (one) to child (many); crow's foot on the child side
        out.append(f'"{parent}" -> "{child}" [tooltip="{child}.{col} → {parent}"];')
    out.append("}")
    render("er-diagram", "\n".join(out))
    shutil.copy(HERE / "er-diagram.svg", ROOT / "05-frontend" / "public" / "er-diagram.svg")


def er_chen() -> None:
    E = f'shape=box, style="filled", fillcolor="{PAPER}", color="{INK}", penwidth=1.4, fontname="{FONT} Bold"'
    W = f'shape=box, peripheries=2, style="filled", fillcolor="{PAPER}", color="{INK}", fontname="{FONT} Bold"'
    R = f'shape=diamond, style="filled", fillcolor="#F3E3C3", color="{INK}", fontsize=10'
    WR = f'shape=diamond, peripheries=2, style="filled", fillcolor="#F3E3C3", color="{INK}", fontsize=10'
    A = f'shape=ellipse, color="{MONSOON}", fontsize=9'
    entities = {"STATE": E, "CITY": E, "LANDMARK": E, "HOTEL": E, "AMENITY": E, "ROOM_TYPE": E, "ROOM": W,
                "SEASON": E, "GUEST": E, "BOOKING": E, "PAYMENT": E, "REVIEW": E}
    rels = [  # (name, a, card_a, b, card_b, style)
        ("in_state", "CITY", "N", "STATE", "1", R), ("located_in", "HOTEL", "N", "CITY", "1", R),
        ("in_city", "LANDMARK", "N", "CITY", "1", R), ("near\n(distance_km)", "HOTEL", "M", "LANDMARK", "N", R),
        ("offers", "HOTEL", "M", "AMENITY", "N", R), ("sells", "HOTEL", "1", "ROOM_TYPE", "N", R),
        ("has", "HOTEL", "1", "ROOM", "N", WR), ("of_type", "ROOM", "N", "ROOM_TYPE", "1", R),
        ("makes", "GUEST", "1", "BOOKING", "N", R), ("at", "BOOKING", "N", "HOTEL", "1", R),
        ("holds\n(subtotal, tax)", "BOOKING", "M", "ROOM", "N", R), ("paid_by", "BOOKING", "1", "PAYMENT", "N", R),
        ("reviewed_in", "BOOKING", "1", "REVIEW", "1", R), ("refers", "GUEST", "1", "GUEST", "N", R),
        ("lives_in", "GUEST", "N", "CITY", "1", R),
        ("prices\n(theta join on night)", "SEASON", "1", "BOOKING", "N", R),
    ]
    attrs = {"HOTEL": ["<U>hotel_id</U>", "name", "star_rating", "{amenities}*", "avg_rating (derived)"],
             "GUEST": ["<U>guest_id</U>", "name (first, last)", "phone", "email", "age (derived)"],
             "BOOKING": ["<U>booking_id</U>", "booking_ref", "check_in", "check_out", "nights (derived)"],
             "ROOM": ["<U>room_number</U> (partial key)", "floor_no"], "SEASON": ["<U>season_id</U>", "dates", "multiplier"]}
    out = [f'graph Chen {{ graph [layout=neato, overlap=false, sep="+18", splines=true, bgcolor="white", fontname="{FONT}"]; '
           f'node [fontname="{FONT}"]; edge [color="{INK}", fontname="{FONT} Bold"];']
    for e, style in entities.items():
        out.append(f'"{e}" [{style}];')
    for i, (name, a, ca, b, cb, style) in enumerate(rels):
        rid = f"r{i}"
        out.append(f'{rid} [label="{name}", {style}];')
        out.append(f'"{a}" -- {rid} [label="{ca}", fontsize=10, fontcolor="{SINDOOR}"' + (', penwidth=2.2' if style == WR else "") + "];")
        out.append(f'{rid} -- "{b}" [label="{cb}", fontsize=10, fontcolor="{SINDOOR}"];')
    for e, list_ in attrs.items():
        for j, a in enumerate(list_):
            out.append(f'"{e}_a{j}" [label=<{a}>, {A}' + (', peripheries=2' if "*" in a else "") + (', style=dashed' if "derived" in a else "") + "];")
            out.append(f'"{e}" -- "{e}_a{j}" [color="{MONSOON}"];')
    out.append("}")
    render("er-chen", "\n".join(out))


def architecture() -> None:
    src = f'''digraph A {{
  graph [rankdir=LR, bgcolor="white", nodesep=0.35, ranksep=0.8, fontname="{FONT}", pad=0.3];
  node [shape=box, style="rounded,filled", fontname="{FONT}", fontsize=11, color="{INK}", fillcolor="{PAPER}", margin="0.18,0.1"];
  edge [color="{MONSOON}", fontname="{FONT}", fontsize=9, fontcolor="{MONSOON}"];
  subgraph cluster_client {{ label=<<B>1 · PRESENTATION</B>>; fontcolor="{SINDOOR}"; color="{LINE}"; style="rounded,dashed";
    browser [label="Browser / phone\\nReact 18 + TypeScript\\nVite · Tailwind · Motion"];
    cli [label="Terminal\\n./yup (Typer + Rich)"];
  }}
  subgraph cluster_api {{ label=<<B>2 · APPLICATION</B>>; fontcolor="{SINDOOR}"; color="{LINE}"; style="rounded,dashed";
    api [label="FastAPI (Python)\\nrouters: browse · booking · lab\\nraw SQL, no ORM", fillcolor="#F3E3C3"];
    pool [label="psycopg 3 connection pools\\nyup_app  ·  yup_lab"];
    err [label="errors.py\\nconstraint → plain-language rule"];
  }}
  subgraph cluster_db {{ label=<<B>3 · DATA</B>>; fontcolor="{SINDOOR}"; color="{LINE}"; style="rounded,dashed";
    pg [label="PostgreSQL 16  ·  database yupreserved", fillcolor="{INK}", fontcolor="white"];
    core [label="schema public\\n15 tables · 8 triggers\\n7 functions/procedures · 5 views"];
    labs [label="schemas staging + lab\\nraw dataset · NF walk-through\\nOODB · fragments · media"];
    wal [label="WAL + MVCC\\nrecovery & concurrency"];
  }}
  subgraph cluster_data {{ label=<<B>0 · DATASET</B>>; fontcolor="{SINDOOR}"; color="{LINE}"; style="rounded,dashed";
    raw [label="Goibibo listings (4,000)\\n+ reference CSVs"];
    etl [label="pipeline/build_dataset.py\\nclean → enrich → simulate"];
    csv [label="processed/*.csv\\n14 files · 329,508 rows"];
  }}
  raw -> etl -> csv;
  csv -> pg [label="\\\\copy (build.sql)"];
  browser -> api [label="HTTPS · JSON\\n/api/…"];
  api -> browser [label="data + SQL trace", style=dashed];
  cli -> api [label="imports same modules", style=dotted];
  api -> pool -> pg [label="SQL"];
  pg -> err [style=dashed, label="SQLSTATE"];
  pg -> core; pg -> labs; pg -> wal;
}}'''
    render("architecture", src)


def workflow() -> None:
    src = f'''digraph W {{
  graph [rankdir=TB, bgcolor="white", nodesep=0.3, ranksep=0.34, fontname="{FONT}", pad=0.3];
  node [shape=box, style="rounded,filled", fontname="{FONT}", fontsize=10.5, color="{INK}", fillcolor="{PAPER}", width=3.6];
  edge [color="{MONSOON}", fontname="{FONT}", fontsize=9, fontcolor="{MONSOON}"];
  s1 [label="1 · Search: city / landmark / mood\\nGET /api/destinations → UNION of cities, landmarks, hotels"];
  s2 [label="2 · Results\\nGET /api/search → joins + full-text + division (must-have amenities)"];
  s3 [label="3 · Hotel page\\nGET /api/hotels/:id  ·  fn_available_rooms()  ·  fn_quote_stay()"];
  s4 [label="4 · Sign in with phone + OTP\\nlookup by candidate key guests.phone  (or INSERT new guest)"];
  s5 [label="5 · Confirm & pay  →  POST /api/bookings  →  fn_book_stay()", fillcolor="#F3E3C3"];
  t1 [label="BEGIN"];
  t2 [label="SELECT … FROM rooms … ORDER BY room_id FOR UPDATE\\n(lock every room of the type — 2PL, no deadlock)"];
  t3 [label="pick free rooms: fn_room_is_free()  (date-range overlap)"];
  d1 [label="enough rooms?", shape=diamond, width=1.8, fillcolor="#FFFFFF"];
  t4 [label="INSERT bookings   (trg_bookings_ref → YRxxxxxx)"];
  t5 [label="INSERT booking_rooms   (trg_booking_rooms_guard: same hotel, no overlap)"];
  t6 [label="INSERT payments   (CHECK amount > 0, UPI VPA format)"];
  t7 [label="deferred trg_booking_capacity  → guests fit?"];
  ok [label="COMMIT  →  /booked/YRxxxxxx", fillcolor="{PEACOCK}", fontcolor="white"];
  no [label="ROLLBACK  →  error + rule shown to the guest", fillcolor="{SINDOOR}", fontcolor="white"];
  s1 -> s2 -> s3 -> s4 -> s5 -> t1 -> t2 -> t3 -> d1;
  d1 -> t4 [label="yes"]; d1 -> no [label="no"];
  t4 -> t5 -> t6 -> t7 -> ok;
  t5 -> no [style=dashed, label="overlap"]; t7 -> no [style=dashed, label="too many guests"];
}}'''
    render("workflow", src)


if __name__ == "__main__":
    print("Building diagrams")
    er_diagram()
    er_chen()
    architecture()
    workflow()
