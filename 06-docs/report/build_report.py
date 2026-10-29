"""
Build the YupReserved project log & report (PDF).

    ~/.yupreserved/venv/bin/python 06-docs/report/build_report.py

Reads the work log (worklog.py), the diagrams (06-docs/diagrams) and LIVE
results from the database (row counts, keys, constraints, query outputs,
EXPLAIN plans, concurrency timelines), so the report always matches the
project. Writes:
    ~/Desktop/YupReserved Project Log/YupReserved_Project_Log.pdf
    06-docs/YupReserved_Project_Report.pdf
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "03-backend"))
sys.path.insert(0, str(HERE))

import psycopg                                                           # noqa: E402
from reportlab.lib import colors                                         # noqa: E402
from reportlab.lib.enums import TA_CENTER                                # noqa: E402
from reportlab.lib.pagesizes import A4                                   # noqa: E402
from reportlab.lib.styles import ParagraphStyle                          # noqa: E402
from reportlab.lib.units import mm                                       # noqa: E402
from reportlab.pdfbase import pdfmetrics                                 # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                             # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,  # noqa: E402
                                Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents          # noqa: E402

from app import catalog, concurrency, lab                                # noqa: E402
from app.db import lab_pool, pool                                        # noqa: E402
import worklog                                                           # noqa: E402

DESKTOP_DIR = Path.home() / "Desktop" / "YupReserved Project Log"
OUT_DESKTOP = DESKTOP_DIR / "YupReserved_Project_Log.pdf"
OUT_REPO = ROOT / "06-docs" / "YupReserved_Project_Report.pdf"
DIAGRAMS = ROOT / "06-docs" / "diagrams"
ADMIN_DB = "postgresql://postgres@localhost:5433/yupreserved"

# ── fonts & styles ─────────────────────────────────────────────────────────
FONT_DIR = HERE / "fonts"                       # DejaVu (free licence, see fonts/LICENSE_DEJAVU)
for name, file in [("Sans", "DejaVuSans.ttf"), ("Sans-Bold", "DejaVuSans-Bold.ttf"),
                   ("Sans-Italic", "DejaVuSans-Oblique.ttf"), ("Serif", "DejaVuSerif.ttf"),
                   ("Serif-Bold", "DejaVuSerif-Bold.ttf"), ("Mono", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic", boldItalic="Sans-Bold")

INK = colors.HexColor("#1E2233")
INK2 = colors.HexColor("#4A4F63")
INK3 = colors.HexColor("#7B7F8F")
SINDOOR = colors.HexColor("#C4472B")
PEACOCK = colors.HexColor("#1F6F6B")
HALDI = colors.HexColor("#E3A72F")
PAPER = colors.HexColor("#FBF7F0")
PAPER2 = colors.HexColor("#F1E8DA")
LINE = colors.HexColor("#DDD0BB")

S = {
    "title": ParagraphStyle("title", fontName="Serif-Bold", fontSize=30, leading=36, textColor=INK, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName="Sans", fontSize=12.5, leading=18, textColor=INK2, alignment=TA_CENTER),
    "part": ParagraphStyle("part", fontName="Serif-Bold", fontSize=24, leading=30, textColor=SINDOOR, spaceBefore=6, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Serif-Bold", fontSize=16.5, leading=21, textColor=INK, spaceBefore=14, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=11.5, leading=15, textColor=PEACOCK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Sans", fontSize=9.6, leading=14, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=8.2, leading=11, textColor=INK2),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=7.8, leading=10, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Sans-Bold", fontSize=7.8, leading=10, textColor=colors.white),
    "q": ParagraphStyle("q", fontName="Sans-Bold", fontSize=9.8, leading=13.5, textColor=SINDOOR, spaceBefore=8, spaceAfter=2),
    "a": ParagraphStyle("a", fontName="Sans", fontSize=9.4, leading=13.6, textColor=INK, leftIndent=10, spaceAfter=4),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.3, leading=9.4, textColor=INK, backColor=PAPER2,
                           borderPadding=6, leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8),
    "algebra": ParagraphStyle("algebra", fontName="Sans", fontSize=8.8, leading=12, textColor=PEACOCK, leftIndent=6, spaceAfter=4),
    "toc1": ParagraphStyle("toc1", fontName="Sans-Bold", fontSize=10, leading=15),
    "toc2": ParagraphStyle("toc2", fontName="Sans", fontSize=9, leading=13, leftIndent=14),
}

# symbols DejaVu Sans lacks → textbook alternatives
SUBST = {"⟕": "⋈ᴸ", "⟖": "⋈ᴿ", "⟗": "⋈ᶠ", "𝒢": "γ"}


def clean(text: str) -> str:
    for k, v in SUBST.items():
        text = text.replace(k, v)
    return text


def p(text: str, style: str = "body") -> Paragraph:
    """Paragraph with light markup (<b>, <i>) allowed."""
    return Paragraph(clean(text), S[style])


def t(text) -> str:
    """Escape data for use inside a Paragraph."""
    return escape(clean("" if text is None else str(text)))


def code(sql: str) -> Preformatted:
    lines = []
    for line in clean(sql).splitlines():
        while len(line) > 112:
            lines.append(line[:112])
            line = "    " + line[112:]
        lines.append(line)
    return Preformatted("\n".join(lines), S["code"])


def table(header: list[str], rows: list[list], widths: list[float] | None = None, max_rows: int | None = None,
          zebra: bool = True) -> Table:
    rows = rows[:max_rows] if max_rows else rows
    data = [[Paragraph(t(h), S["cellb"]) for h in header]]
    for r in rows:
        data.append([Paragraph(t(_fmt(v)), S["cell"]) for v in r])
    total = 170 * mm
    if widths is None:
        widths = [total / len(header)] * len(header)
    else:
        scale = total / sum(widths)
        widths = [w * scale for w in widths]
    tb = Table(data, colWidths=widths, repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if zebra:
        style += [("BACKGROUND", (0, i), (-1, i), PAPER) for i in range(2, len(data), 2)]
    tb.setStyle(TableStyle(style))
    return tb


def _fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    s = str(v)
    return s if len(s) <= 140 else s[:137] + "…"


def image(path: Path, max_w=170 * mm, max_h=230 * mm) -> Image:
    img = Image(str(path))
    ratio = min(max_w / img.imageWidth, max_h / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * ratio, img.imageHeight * ratio
    return img


def bullets(items: list[str], style="body") -> list[Paragraph]:
    return [Paragraph(clean(f"•&nbsp;&nbsp;{i}"), ParagraphStyle("b", parent=S[style], leftIndent=12, firstLineIndent=-9)) for i in items]


# ── live data ──────────────────────────────────────────────────────────────
def q(sql: str, params=None) -> tuple[list[str], list[tuple]]:
    with psycopg.connect(ADMIN_DB) as c:
        cur = c.execute(sql, params)
        return [d.name for d in cur.description], cur.fetchall()


def named(name: str, collection="queries"):
    return catalog.load(collection)[name]


def run_named(name: str):
    r = lab.run_query(named(name))
    return r["columns"], r["rows"]


def query_block(name: str, max_rows: int = 12, widths=None) -> list:
    nq = named(name)
    cols, rows = run_named(name)
    out = [p(f"<b>{t(nq.title)}</b>  <font color='#7B7F8F' size='8'>[{t(nq.name)}]</font>", "h2")]
    if nq.algebra:
        out.append(p(f"RA / RC:  {t(nq.algebra)}", "algebra"))
    out.append(p(t(nq.explain), "small"))
    out.append(code(nq.sql))
    out.append(table(cols, rows, widths, max_rows))
    if len(rows) > max_rows:
        out.append(p(f"… {len(rows) - max_rows} more row(s) not shown.", "small"))
    out.append(Spacer(1, 6))
    return out


# ── document with a table of contents ──────────────────────────────────────
class Doc(SimpleDocTemplate):
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("part", "h1"):
            level = 0 if f.style.name == "part" else 1
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(f.getPlainText(), key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, f.getPlainText(), self.page, key))


def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Sans", 7.5)
        canvas.setFillColor(INK3)
        canvas.drawString(20 * mm, 12 * mm, "YupReserved · DBMS project log & report")
        canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
        canvas.setStrokeColor(SINDOOR)
        canvas.setLineWidth(1.2)
        canvas.line(20 * mm, 285 * mm, 190 * mm, 285 * mm)
    canvas.restoreState()


# ════════════════════════════════════════════════════════════════════════════
def build() -> Path:
    pool.open(wait=True)
    lab_pool.open()
    story: list = []
    H1 = lambda s: story.append(p(s, "h1"))                     # noqa: E731
    H2 = lambda s: story.append(p(s, "h2"))                     # noqa: E731
    P = lambda s: story.append(p(s))                            # noqa: E731

    counts_cols, counts = run_named("basics.counts")
    total_rows = sum(r[1] for r in counts)

    # ── title ──────────────────────────────────────────────────────────────
    story += [Spacer(1, 60 * mm), p("YupReserved", "title"), Spacer(1, 4 * mm),
              p("A hotel reservation system for India", "subtitle"),
              p("Database Management Systems — project log, report and viva guide", "subtitle"),
              Spacer(1, 16 * mm),
              p(f"PostgreSQL 16 · 15 tables · {total_rows:,} rows · FastAPI · React", "subtitle"),
              Spacer(1, 50 * mm),
              p("Submitted by: ____________________ &nbsp;&nbsp; Enrolment no.: ____________________", "subtitle"),
              p("Course: ____________________ &nbsp;&nbsp; Guide: ____________________", "subtitle"),
              Spacer(1, 6 * mm),
              p(f"Last updated {datetime.now():%d %B %Y, %H:%M} · session {worklog.SESSIONS[-1]['number']}", "subtitle"),
              PageBreak()]

    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    story += [Paragraph("Contents", ParagraphStyle("contents", parent=S["part"])), toc, PageBreak()]

    # ════════════════════ PART A — WORK LOG ═══════════════════════════════
    story.append(p("Part A · Work log", "part"))
    P("This part is updated after every working session, so the whole history of the project can be traced: "
      "what was built, which files were added, which tables and concepts were involved, and why each decision was taken.")
    for s in worklog.SESSIONS:
        H1(f"Session {s['number']} — {s['date']}: {t(s['title'])}")
        P(t(s["summary"]))
        H2("Decisions and why")
        for d, why in s["decisions"]:
            story.append(p(f"<b>{t(d)}.</b> {t(why)}"))
        H2("Files added or changed")
        story.append(table(["file / folder", "what it is"], [[f, w] for f, w in s["files"]], [70, 100]))
        H2("Tables involved")
        P(", ".join(s["tables"]))
        H2("DBMS concepts used")
        story += bullets([t(c) for c in s["concepts"]])
        H2("Verified")
        story += bullets([t(v) for v in s["verified"]])
    story.append(PageBreak())

    # ════════════════════ PART B — PROJECT REPORT ═════════════════════════
    story.append(p("Part B · Project report", "part"))

    H1("1. Introduction and problem statement")
    P("Travellers in India book everything from a sea-facing heritage hotel in Mumbai to a ₹1,500 guest house near "
      "the ghats of Varanasi. Behind every booking a platform must answer hard questions instantly and correctly: "
      "Which rooms are free for these dates? What does each night cost during Diwali? Can two people book the last "
      "room at the same moment? <b>YupReserved</b> is a hotel reservation platform whose database answers these "
      "questions with relational guarantees instead of application code.")
    story.append(table(["problem", "how YupReserved solves it"], [
        ["Listing data is messy: lists in one cell, inconsistent state names", "A cleaning pipeline normalises the real dataset into 15 tables (up to BCNF / 4NF, rooms deliberately 3NF)"],
        ["A room must never be sold twice for overlapping nights", "Trigger trg_booking_rooms_guard + row locks (SELECT … FOR UPDATE) in fn_book_stay"],
        ["Prices change with festivals, weekends and GST slabs", "seasons table (EXCLUDE: no overlaps) + fn_quote_stay computes every night"],
        ["Invalid data (check-out before check-in, bad phone numbers, under-age guests)", "Domains, CHECK, UNIQUE and foreign keys enforced by the DBMS itself"],
        ["Users need to know why an action was refused", "The API translates the violated constraint into a plain-language rule"],
        ["Reports need joins across many tables", "Views (v_hotel_cards, v_booking_summary) and a materialized view"],
    ], [80, 120]))

    H2("1.1 Technologies")
    story.append(table(["layer", "technology", "why"], [
        ["Database", "PostgreSQL 16", "full SQL standard support, enforced CHECK, EXCLUDE, deferred constraints, MVCC, WAL, EXPLAIN ANALYZE"],
        ["Dataset pipeline", "Python 3.13, pandas", "repeatable, seeded cleaning and simulation"],
        ["Backend", "FastAPI, psycopg 3, connection pool", "small, fast, typed; raw SQL so every query is visible"],
        ["CLI", "Typer + Rich", "retrieve tables and run every demo from the terminal"],
        ["Frontend", "React 18, TypeScript, Vite, Tailwind CSS 4, Motion, TanStack Query", "fast to build, small static bundle, deploys to any static host"],
        ["Diagrams / report", "Graphviz, ReportLab", "diagrams and this report are generated from the live catalog"],
    ], [28, 62, 110]))

    H2("1.2 Basic concepts used")
    story.append(table(["term", "meaning", "where in YupReserved"], [
        ["Relation (table)", "a set of tuples with the same attributes", "15 tables in schema public"],
        ["Primary key", "minimal attribute set that identifies each tuple; never NULL", "every table, e.g. bookings(booking_id)"],
        ["Candidate / alternate key", "another minimal unique identifier not chosen as PK", "guests.phone, guests.email, bookings.booking_ref"],
        ["Foreign key", "attribute(s) that must match a key of another (or the same) table", "17 FKs, e.g. bookings.hotel_id → hotels"],
        ["Domain", "named type with a rule", "indian_mobile, email_address, rupees"],
        ["Trigger", "event → condition → action rule inside the DBMS", "8 triggers (04_triggers.sql)"],
        ["View", "stored query, virtual table", "v_hotel_cards, v_booking_summary, v_guest_directory"],
        ["Transaction (ACID)", "all-or-nothing unit of work", "fn_book_stay, sp_cancel_booking"],
    ], [34, 76, 90]))

    # 2 architecture
    H1("2. System architecture and workflow")
    P("YupReserved is a <b>three-tier</b> system with a fourth, offline data tier that prepares the dataset. The browser "
      "never talks to the database: it calls the FastAPI application over HTTP/JSON, and only the application holds "
      "database credentials. The CLI reuses the backend's own modules, so the CLI, the API and the website run the "
      "same SQL.")
    story.append(image(DIAGRAMS / "architecture.png", max_h=95 * mm))
    H2("Why this architecture")
    story += bullets([
        "<b>Separation of concerns</b> — presentation, business logic and data can be changed independently (data independence at the application level).",
        "<b>Security</b> — the browser has no SQL access; the API connects as yup_app, a least-privilege role that cannot DELETE bookings or touch rooms directly.",
        "<b>Rules live in the database</b> — constraints and triggers protect the data whichever program writes to it (website, CLI or psql).",
        "<b>Transparency</b> — every API response carries the SQL it ran, which the website shows in its 'Under the hood' drawer.",
        "<b>Laptop-friendly</b> — PostgreSQL runs with 128 MB shared buffers and 30 connections; the frontend is static files.",
    ])
    H2("2.1 Booking workflow")
    P("The workflow below follows one guest from search to a committed booking. Steps 5–9 run inside a single "
      "database transaction in the function fn_book_stay.")
    story.append(image(DIAGRAMS / "workflow.png", max_h=150 * mm))
    story.append(PageBreak())

    # 3 dataset
    H1("3. Dataset")
    P("<b>Source:</b> 'Indian Hotels on Goibibo' (PromptCloud, published on Kaggle; mirrored on Hugging Face as "
      "jason1966/PromptCloudHQ_hotels-on-goibibo): 4,000 listings, 36 columns, crawled in 2016. It is kept untouched in "
      "01-dataset/raw/ and also loaded as-is into staging.goibibo_raw for the normalisation walk-through.")
    import json
    manifest = json.loads((ROOT / "01-dataset" / "processed" / "_manifest.json").read_text())
    story.append(table(["cleaning rule", "rows"], [[k, v] for k, v in manifest["cleaning_rules"].items()], [150, 30]))
    P("Other cleaning: state names normalised to 2-letter codes (e.g. 'ANDHRA PRADESH', 'Andhra Pradesh' → AP; "
      "'Orissa' → OD); 2016-era filings corrected (Hyderabad → Telangana, Leh → Ladakh, Chandigarh → its own UT); "
      "'Cochin' / 'Ernakulam' → Kochi; 356 raw facility labels mapped to 52 canonical amenities "
      "(processed/_amenity_mapping.csv); check-in/out times parsed from the policy text; HTML entities decoded.")
    P("<b>Enrichment and simulation.</b> The listings give one room type and a room count per hotel, but no prices, guests "
      "or bookings. The pipeline (seed 2026, so it is reproducible) adds room-type tiers, physical rooms, a festival "
      "calendar, 26,000 guests, 72,000 bookings and 19,041 reviews. Base prices follow a documented model (star rating × "
      "property type × city factor × review quality, with noise); nightly prices and all payments are then computed "
      f"inside PostgreSQL. Resulting base-price quartiles: ₹{manifest['base_price_quartiles_inr']['p25']:,} / "
      f"₹{manifest['base_price_quartiles_inr']['median']:,} / ₹{manifest['base_price_quartiles_inr']['p75']:,}. "
      "Eighteen 'Signature' hotels are original YupReserved properties written for the platform.")
    H2("3.1 Rows per table")
    story.append(table(counts_cols, counts, [80, 40]))

    # 4 design
    H1("4. Database design")
    H2("4.1 Conceptual model — ER diagram (Chen notation)")
    P("Rectangles are entities, diamonds relationships, ellipses attributes. ROOM is a <b>weak entity</b> (double box) "
      "identified through HOTEL by the partial key room_number; 'has' is its identifying relationship. "
      "{amenities} is a multivalued attribute (double ellipse), dashed ellipses are derived attributes, and 'refers' is "
      "a recursive relationship on GUEST.")
    story.append(image(DIAGRAMS / "er-chen.png", max_h=205 * mm))
    story.append(PageBreak())
    H2("4.2 Logical model — relational schema (generated from the live catalog)")
    story.append(image(DIAGRAMS / "er-diagram.png", max_h=235 * mm))
    story.append(PageBreak())
    H2("4.3 ER → relational mapping")
    story.append(table(["ER construct", "mapped to", "example"], [
        ["Strong entity", "own table, own PK", "HOTEL → hotels(hotel_id)"],
        ["Weak entity + identifying relationship", "table with owner's key + partial key", "ROOM → rooms: candidate key (hotel_id, room_number); surrogate room_id as PK"],
        ["1:N relationship", "FK on the N side", "located_in → hotels.city_id"],
        ["M:N relationship", "separate table, composite PK of both keys", "offers → hotel_amenities(hotel_id, amenity_id)"],
        ["M:N with attributes", "attributes go into the relationship table", "near(distance_km) → hotel_landmarks.distance_km; holds(subtotal, tax) → booking_rooms"],
        ["1:1 relationship", "FK + UNIQUE", "reviewed_in → reviews.booking_id UNIQUE"],
        ["Recursive relationship", "self-referencing FK", "refers → guests.referred_by → guests.guest_id"],
        ["Multivalued attribute", "separate table (1NF)", "{amenities} → hotel_amenities"],
        ["Composite attribute", "one column per component", "name → first_name, last_name"],
        ["Derived attribute", "computed, or stored and maintained", "nights GENERATED; age in a view; avg_rating kept by trigger"],
    ], [42, 58, 100]))

    H2("4.4 The 15 tables")
    cols, rows = q("""SELECT c.relname, obj_description(c.oid),
        (SELECT string_agg(a.attname, ', ' ORDER BY k.ord) FROM pg_constraint p
           CROSS JOIN LATERAL unnest(p.conkey) WITH ORDINALITY k(attnum, ord)
           JOIN pg_attribute a ON a.attrelid = p.conrelid AND a.attnum = k.attnum
           WHERE p.conrelid = c.oid AND p.contype = 'p'),
        (SELECT string_agg(DISTINCT confrelid::regclass::text, ', ') FROM pg_constraint f WHERE f.conrelid = c.oid AND f.contype = 'f')
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'""")
    purpose = {
        "states": "Indian states and union territories (natural key)", "cities": "cities, each in one state",
        "landmarks": "places guests search by", "hotels": "one row per property",
        "hotel_landmarks": "which landmarks are near which hotel, with distance", "amenities": "controlled amenity vocabulary",
        "hotel_amenities": "which hotel offers which amenity", "room_types": "what a hotel sells, with list price",
        "rooms": "physical rooms (weak entity of hotel)", "seasons": "festival / holiday pricing calendar",
        "guests": "customers", "bookings": "reservation header: guest, hotel, dates, status",
        "booking_rooms": "rooms held by a booking, with agreed price", "payments": "charges and refunds",
        "reviews": "one review per completed stay"}
    order = list(purpose)
    rows = sorted(rows, key=lambda r: order.index(r[0]))
    story.append(table(["#", "table", "stores", "primary key", "references"],
                       [[i + 1, r[0], purpose[r[0]], r[2], r[3] or "—"] for i, r in enumerate(rows)], [6, 26, 70, 40, 46]))
    story.append(PageBreak())

    # 5 keys
    H1("5. Keys")
    P("<b>Super key</b>: any attribute set that uniquely identifies a tuple (e.g. {booking_id, guest_id}). <b>Candidate "
      "key</b>: a minimal super key. <b>Primary key</b>: the candidate key chosen to identify rows; the others become "
      "<b>alternate keys</b> enforced with UNIQUE. A <b>surrogate</b> key is a system-generated number with no business "
      "meaning; a <b>natural</b> key comes from the real world.")
    story += query_block("catalog.primary_keys", 15, [30, 34, 40, 20])
    story.append(table(["table", "why this primary key"], [
        ["states (state_code)", "natural key: 2-letter codes are short, stable and universally used (MH, RJ), so no surrogate is needed"],
        ["cities, landmarks, hotels, room_types, guests, bookings, payments, reviews (…_id)", "surrogate integer identity: natural candidates (names, phone, email) can change or be long; a small integer makes joins and FKs fast and stable"],
        ["rooms (room_id)", "surrogate PK; the natural candidate key (hotel_id, room_number) is kept as UNIQUE. A single-column key keeps booking_rooms in 2NF"],
        ["amenities, seasons (smallint)", "small lookup tables: 2-byte keys are enough"],
        ["hotel_amenities, hotel_landmarks, booking_rooms (composite)", "M:N relationship tables: the pair of foreign keys IS the identity; a pair can appear only once"],
    ], [60, 140]))
    story += query_block("catalog.candidate_keys", 16, [30, 40, 70])
    story += query_block("catalog.foreign_keys", 17, [24, 90, 36, 18])
    H2("Why these ON DELETE rules")
    story += bullets([
        "<b>RESTRICT</b> where history matters: a hotel, guest or booking that is still referenced cannot disappear (bookings → hotels, payments → bookings).",
        "<b>CASCADE</b> for composition: a hotel's room types, rooms, amenity links and landmark links are part of the hotel; a booking's booking_rooms are part of the booking.",
        "<b>SET NULL</b> for optional links: if a referrer guest or a home city is removed, the guest stays and the link becomes unknown.",
        "<b>Composite FK</b> rooms(room_type_id, hotel_id) → room_types(room_type_id, hotel_id): a room can never point at another hotel's room type.",
    ])
    story.append(PageBreak())

    # 6 constraints
    H1("6. Constraints, triggers, functions and views")
    H2("6.1 Domains")
    story.append(table(["domain", "rule"], [["rupees", "numeric(12,2), ≥ 0"], ["indian_mobile", "10 digits, first digit 6–9"],
                                            ["email_address", "regular expression for an email"], ["lat_deg / lon_deg", "valid latitude / longitude"]], [40, 120]))
    story += query_block("catalog.checks", 40, [24, 46, 14, 100])
    story += query_block("catalog.triggers", 10, [24, 40, 26, 30, 36])
    H2("6.2 Functions and procedures")
    story.append(table(["routine", "type", "what it does"], [
        ["fn_gst_rate(tariff)", "function (IMMUTABLE)", "GST slab: 0% ≤ ₹1,000 · 5% ≤ ₹7,500 · 18% above"],
        ["fn_quote_stay(type, in, out, rooms)", "set-returning function", "night-by-night price: base × season × weekend, then GST"],
        ["fn_stay_total(…)", "function", "sum of fn_quote_stay"],
        ["fn_room_is_free(room, in, out)", "function", "overlap test on half-open date ranges"],
        ["fn_available_rooms(hotel, in, out)", "set-returning function", "free rooms per room type"],
        ["fn_book_stay(…)", "function, SECURITY DEFINER", "the whole booking as one transaction with row locks"],
        ["sp_cancel_booking(id, OUT refund)", "PROCEDURE (CALL)", "cancel + refund policy (100% / 50% / 0%)"],
    ], [52, 40, 90]))
    H2("6.3 Views")
    story.append(table(["view", "purpose"], [
        ["v_hotel_cards", "hotel + city + state + cheapest price (search cards)"],
        ["v_booking_summary", "booking + guest + hotel + rooms + money (front desk, My trips)"],
        ["v_guest_directory", "security view: masked phone/email; the only guest data the analyst role can read"],
        ["v_upcoming_arrivals", "updatable view WITH CHECK OPTION: edits cannot push a row out of the view"],
        ["mv_city_performance", "materialized view: revenue, room nights, ADR per city (REFRESH to update)"],
    ], [42, 140]))
    story.append(PageBreak())

    # 7 normalization
    H1("7. Functional dependencies and normalization")
    P("A functional dependency X → Y means: any two tuples that agree on X also agree on Y. Normalisation removes "
      "dependencies that cause redundancy and update, insertion and deletion anomalies. YupReserved was normalised "
      "<b>on the real raw dataset</b>; every step below exists as tables in schema lab.")
    H2("7.1 Functional dependencies of the final design")
    story.append(table(["table", "functional dependencies", "highest NF"], [
        ["states", "state_code → state_name, region, is_ut;  state_name → state_code", "BCNF"],
        ["cities", "city_id → city_name, state_code, lat, lon, is_metro, tier;  (city_name, state_code) → city_id", "BCNF"],
        ["landmarks", "landmark_id → city_id, name, category, lat, lon;  (city_id, name) → landmark_id", "BCNF"],
        ["hotels", "hotel_id → all attributes;  source_ref → hotel_id", "BCNF"],
        ["hotel_landmarks", "(hotel_id, landmark_id) → distance_km", "BCNF / 4NF"],
        ["amenities", "amenity_id → name, category;  name → amenity_id", "BCNF"],
        ["hotel_amenities", "no non-trivial FD (all-key)", "BCNF / 4NF"],
        ["room_types", "room_type_id → hotel_id, type_name, bed, capacity, area, base_price;  (hotel_id, type_name) → room_type_id", "BCNF"],
        ["rooms", "room_id → hotel_id, room_number, room_type_id;  (hotel_id, room_number) → room_id;  room_type_id → hotel_id", "3NF (not BCNF, by choice)"],
        ["seasons", "season_id → name, dates, multiplier;  name → season_id", "BCNF"],
        ["guests", "guest_id → all;  phone → guest_id;  email → guest_id;  (id_type, id_number) → guest_id", "BCNF"],
        ["bookings", "booking_id → guest, hotel, dates, guests, status, …;  booking_ref → booking_id;  (check_in, check_out) → nights", "3NF*"],
        ["booking_rooms", "(booking_id, room_id) → room_subtotal, room_tax", "BCNF"],
        ["payments", "payment_id → booking_id, kind, method, status, amount, …;  gateway_ref → payment_id", "BCNF"],
        ["reviews", "review_id → booking_id, rating, title, body, created_at;  booking_id → review_id", "BCNF"],
    ], [24, 130, 26]))
    P("* nights is a <b>generated column</b>: the DBMS computes it from (check_in, check_out), so it can never disagree "
      "with them. The redundancy is controlled, not an anomaly.")
    H2("7.2 UNF → 1NF → 2NF → 3NF on the raw data")
    story += query_block("nf.unf", 3, [26, 40, 20, 90])
    story += query_block("fd.violation_raw", 8, [24, 26, 110])
    P("<b>Why this matters.</b> A decomposition is only lossless if the dependency it splits on really holds. When the "
      "walk-through was first run on the uncleaned names, the 3NF re-join produced 357 lost or spurious rows, because "
      "'city → state' is false in the raw file (e.g. Hyderabad filed under both Andhra Pradesh and Telangana). City "
      "names are not even unique after cleaning — Aurangabad exists in both Maharashtra and Bihar. So the walk-through "
      "(and the real cities table) uses the surrogate city_id, for which city_id → city_name, state holds.")
    story += query_block("nf.first", 6, [28, 40, 20, 26, 50])
    story += query_block("nf.second", 6)
    story += query_block("nf.third", 1)
    H2("7.3 BCNF — and why rooms stays in 3NF")
    story += query_block("nf.bcnf_rooms", 3)
    P("In rooms, room_type_id → hotel_id has a determinant that is not a superkey, so rooms is not in BCNF. It is in "
      "3NF because hotel_id is a <b>prime attribute</b> (part of the candidate key {hotel_id, room_number}). The BCNF "
      "decomposition R1(room_type_id, hotel_id), R2(room_id, room_number, room_type_id) is lossless but <b>not "
      "dependency-preserving</b>: '(hotel_id, room_number) is unique' could no longer be checked in a single table. We "
      "therefore keep 3NF and guarantee consistency with the composite foreign key (room_type_id, hotel_id).")
    H2("7.4 4NF and 5NF")
    story += query_block("nf.fourth", 8)
    story += query_block("nf.fifth", 3)
    story.append(PageBreak())

    # 8 SQL
    H1("8. Relational algebra, calculus and SQL")
    P("Every query below is stored in 02-database/queries with its relational-algebra (or calculus) form; the outputs "
      "are produced live from the database while this report is built.")
    for name in ["basics.selection", "basics.projection", "joins.inner", "joins.natural", "joins.theta", "joins.left_outer",
                 "joins.right_outer", "joins.full_outer", "joins.self", "joins.cross", "joins.semi", "joins.anti",
                 "joins.lateral", "joins.multiway", "sets.union", "sets.intersect", "sets.except",
                 "agg.group_having", "agg.rollup", "agg.cube", "division.not_exists", "division.count",
                 "sub.scalar", "sub.any_all", "sub.cte", "sub.recursive", "calculus.trc", "calculus.drc", "sub.window"]:
        story += query_block(name, 8)
    story.append(PageBreak())

    H1("9. Retrieval: what the website asks the database")
    for name in ["app.quote_two_nights", "app.quote_compare_dates", "app.availability", "app.near_landmark",
                 "app.mood_search", "app.fuzzy_name", "app.occupancy", "app.top_cities"]:
        story += query_block(name, 10)
    H2("9.1 'Why can't I…?' — every refusal is a named rule")
    rows = []
    for nq in catalog.load("why").values():
        r = lab.run_why(nq)
        rows.append([nq.title, nq.topic, r.get("error") if r["failed"] else "allowed (unexpected)", r.get("rule", "")])
    story.append(table(["attempt", "mechanism", "database message", "rule"], rows, [44, 32, 64, 60]))
    story.append(PageBreak())

    # 10 query processing
    H1("10. Query processing and optimization")
    P("PostgreSQL translates SQL into a tree of relational-algebra operators and chooses an algorithm for each using "
      "cost estimates from table statistics (ANALYZE). The plans below were produced by EXPLAIN (ANALYZE, BUFFERS) on "
      "the project data; '@setup' settings disable alternatives so each algorithm can be seen.")
    for nq in catalog.load("plans").values():
        r = lab.explain(nq)
        block = [p(f"<b>{t(nq.title)}</b>", "h2"), p(t(nq.topic), "algebra"), p(t(nq.explain), "small")]
        if nq.setup:
            block.append(p(f"setup: {t(nq.setup)}", "small"))
        block += [code(nq.sql), code(r["plan_text"]),
                  p(f"operators: {t(', '.join(r['operators']))} · execution {r['execution_ms']} ms", "small"), Spacer(1, 4)]
        story.append(KeepTogether(block[:4]))
        story += block[4:]
    story.append(PageBreak())

    # 11 transactions
    H1("11. Transactions, concurrency control and recovery")
    P("ACID: <b>Atomicity</b> — fn_book_stay inserts booking, rooms and payment together or not at all. <b>Consistency</b> — "
      "every constraint and trigger holds at commit (the capacity trigger is deferred to commit time). <b>Isolation</b> — "
      "row locks and MVCC snapshots keep concurrent bookings apart. <b>Durability</b> — the write-ahead log (WAL) is "
      "flushed before COMMIT returns. Each demonstration below was run with two real sessions while building this report.")
    for name, fn in concurrency.SCENARIOS.items():
        r = fn()
        H2(name.replace("_", " ").capitalize())
        timelines = [("", r["timeline"])] if "timeline" in r else [(k, v["timeline"]) for k, v in r["results"].items()]
        for label, events in timelines:
            if label:
                story.append(p(f"<b>{t(label)}</b>", "small"))
            story.append(table(["t (ms)", "session", "step", "result"],
                               [[e["t_ms"], e["session"], e["step"], e["result"]] for e in events], [12, 14, 100, 60]))
        P(t(r["lesson"]))
    H2("Crash recovery")
    P("./yup recovery commits one row, leaves a second row in an open transaction, stops the server with "
      "'pg_ctl stop -m immediate' (no checkpoint — like a power cut) and restarts it. The server log shows 'database "
      "system was not properly shut down; automatic recovery in progress' and 'redo starts at …'. Afterwards the "
      "committed row is present (durability) and the uncommitted row is absent (atomicity): REDO replays the WAL, and "
      "a transaction without a commit record is never visible.")
    story.append(PageBreak())

    # 12 unit 5
    H1("12. Distributed, object-oriented, multimedia databases, data mining and digital libraries")
    for name in ["dist.horizontal", "dist.vertical", "oodb.inheritance", "oodb.composite_type", "media.posters",
                 "mining.amenity_rules", "mining.city_pairs"]:
        story += query_block(name, 8)
    P("<b>Digital libraries / information retrieval:</b> hotels.search_doc is a generated tsvector (weighted name, "
      "locality, tagline and description) with a GIN inverted index; 'quiet hill stay' is matched by word stems and "
      "ranked with ts_rank (section 9). A trigram index gives typo-tolerant name search.")
    story.append(PageBreak())

    # 13 interfaces
    H1("13. Interfaces: API, CLI and website")
    story.append(table(["method", "endpoint", "SQL / object used"], [
        ["GET", "/api/destinations?q=", "UNION of cities, landmarks, hotels with trigram similarity"],
        ["GET", "/api/search?…", "joins + full-text + division (must-have amenities) + fn_available_rooms"],
        ["GET", "/api/hotels/{id}", "hotels ⋈ cities ⋈ states, amenities, landmarks, room types, reviews"],
        ["GET", "/api/hotels/{id}/availability", "fn_available_rooms, fn_stay_total"],
        ["GET", "/api/quote", "fn_quote_stay (night-by-night price)"],
        ["POST", "/api/auth/otp, /api/auth/verify", "lookup by candidate key guests.phone (OTP mocked)"],
        ["POST", "/api/guests", "INSERT guests (domains, UNIQUE, CHECK age)"],
        ["POST", "/api/bookings", "fn_book_stay (locks, triggers, payment) in one transaction"],
        ["POST", "/api/bookings/{ref}/cancel", "CALL sp_cancel_booking"],
        ["POST", "/api/bookings/{ref}/review", "INSERT reviews (trg_reviews_guard, trg_reviews_rollup)"],
        ["GET/POST", "/api/lab/…", "catalog browser, named queries, EXPLAIN, why-not, concurrency"],
    ], [16, 60, 110]))
    H2("13.1 CLI")
    story.append(code("""./yup tables                       15 tables, rows, PK, FK/UNIQUE/CHECK counts
./yup show hotels -w "star_rating = 5" -n 10
./yup describe bookings            columns, constraints, referenced-by, indexes, triggers
./yup keys                         primary, candidate and foreign keys
./yup queries -t join              list named queries        ./yup q joins.full_outer
./yup plans                        ./yup explain plan.external_sort
./yup why                          run all 16 constraint scenarios   ./yup why why.double_booking
./yup txn deadlock                 (double_booking_race | isolation_levels | mvcc_versions | atomic_rollback)
./yup quote 1 2026-12-24 2026-12-26
./yup find "gateway"               ./yup sql "SELECT count(*) FROM bookings"
./yup recovery                     crash-recovery demonstration"""))
    H2("13.2 Website")
    P("Home (search by city, landmark or mood; signature stays; festival price calendar) → Search results (filters in "
      "the URL, compare up to three stays) → Hotel page (story, neighbourhood with walking times, rooms priced for your "
      "dates, night-by-night breakdown, reviews) → Checkout (phone + OTP sign-in, UPI first, honest price) → "
      "Confirmation (booking reference) → My trips (cancel with refund preview, write a review) → Under the hood "
      "(tables, query library, plans, why-not, transactions). English / हिंदी and light / dark themes; motion respects "
      "the reduce-motion setting; all imagery is lightweight SVG drawn in code.")

    H1("14. How to run")
    story.append(code("""scripts/db.sh start                         # PostgreSQL on port 5433
scripts/db.sh build                         # (re)create the database from 01-dataset/processed (~3 min)
cd 03-backend && ~/.yupreserved/venv/bin/uvicorn app.main:app --port 8000
cd 05-frontend && npm run dev               # http://localhost:5173
./yup tables                                # CLI
python3 01-dataset/pipeline/build_dataset.py            # regenerate the dataset (optional)
~/.yupreserved/venv/bin/python 06-docs/report/build_report.py   # rebuild this PDF"""))
    story.append(PageBreak())

    # ════════════════════ PART C — VIVA Q&A ═══════════════════════════════
    story.append(p("Part C · Viva questions and answers", "part"))
    from viva import QA
    for section, items in QA:
        H1(section)
        for question, answer in items:
            story.append(KeepTogether([p(t(question), "q"), p(answer, "a")]))
    story.append(PageBreak())

    # ════════════════════ PART D — SYLLABUS MAP ═══════════════════════════
    story.append(p("Part D · Syllabus coverage", "part"))
    from viva import SYLLABUS
    for unit, rows in SYLLABUS:
        H1(unit)
        story.append(table(["topic", "where it is in YupReserved"], rows, [52, 148]))

    DESKTOP_DIR.mkdir(parents=True, exist_ok=True)
    doc = Doc(str(OUT_REPO), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
              title="YupReserved — DBMS project log & report", author="YupReserved project")
    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    shutil.copy(OUT_REPO, OUT_DESKTOP)
    lab_pool.close()
    pool.close()
    return OUT_DESKTOP


if __name__ == "__main__":
    print("Building report …")
    out = build()
    print(f"✓ {out}\n✓ {OUT_REPO}")
