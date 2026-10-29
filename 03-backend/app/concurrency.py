"""
Unit 5 demonstrations with REAL concurrent sessions.

Each scenario opens two database connections (two "users"), runs their
statements on separate threads, and records a timeline of what each one saw.
Business data is never changed:
  * deadlock / isolation / MVCC use the scratch table lab.txn_demo
  * the double-booking race commits a booking tagged 'LAB DEMO' and removes
    it afterwards with lab.purge_demo_bookings() (a SECURITY DEFINER function)

Used by the CLI (`yup txn <scenario>`) and the API (/api/lab/concurrency/…).
"""
from __future__ import annotations

import threading
import time
from typing import Callable

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL
from .db import _jsonable


class Timeline:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.events: list[dict] = []
        self._lock = threading.Lock()

    def log(self, session: str, step: str, result=None):
        with self._lock:
            self.events.append({"t_ms": round((time.perf_counter() - self.t0) * 1000),
                                "session": session, "step": step, "result": _jsonable(result)})


def _connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=autocommit)


def _run_parallel(*fns: Callable[[], None]) -> None:
    threads = [threading.Thread(target=f) for f in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)


# ── 1. two guests race for the last room (lock-based protocol) ─────────────
STAY = ("2027-02-15", "2027-02-17")


def _last_room_type(conn) -> dict:
    """A signature room type that has exactly one physical room, free on STAY."""
    return conn.execute("""
        SELECT rt.room_type_id, rt.type_name, h.hotel_name
        FROM room_types rt JOIN hotels h USING (hotel_id)
        WHERE h.is_signature
          AND (SELECT count(*) FROM rooms r WHERE r.room_type_id = rt.room_type_id) = 1
          AND fn_room_is_free((SELECT room_id FROM rooms r WHERE r.room_type_id = rt.room_type_id),
                              %s::date, %s::date)
        ORDER BY rt.room_type_id LIMIT 1""", STAY).fetchone()


def double_booking_race() -> dict:
    tl = Timeline()
    a, b = _connect(), _connect()
    target = _last_room_type(a)
    a.rollback()
    args = (target["room_type_id"], *STAY)
    a_has_lock = threading.Event()

    def guest_a():
        tl.log("A", f"BEGIN · fn_book_stay(guest 101, {target['type_name']}) → locks the room FOR UPDATE")
        r = a.execute("SELECT booking_ref FROM fn_book_stay(101, %s, %s, %s, p_request => 'LAB DEMO')", args).fetchone()
        tl.log("A", "booking inserted · transaction still open, lock held", r)
        a_has_lock.set()
        time.sleep(1.5)
        a.commit()
        tl.log("A", "COMMIT · lock released")

    def guest_b():
        a_has_lock.wait()
        time.sleep(0.2)
        tl.log("B", "BEGIN · fn_book_stay(guest 202, same room, same dates) → blocked, waiting for A's lock…")
        try:
            r = b.execute("SELECT booking_ref FROM fn_book_stay(202, %s, %s, %s, p_request => 'LAB DEMO')", args).fetchone()
            tl.log("B", "booked (unexpected)", r)
            b.commit()
        except psycopg.Error as e:
            tl.log("B", "lock granted, availability re-checked → REJECTED", e.diag.message_primary)
            b.rollback()

    try:
        _run_parallel(guest_a, guest_b)
    finally:
        with _connect(autocommit=True) as c:
            removed = c.execute("SELECT lab.purge_demo_bookings() AS n").fetchone()["n"]
        tl.log("—", "clean-up: lab.purge_demo_bookings() removed the demo booking", removed)
        a.close(); b.close()
    return {"scenario": "double_booking_race", "target": target, "timeline": tl.events,
            "lesson": "SELECT … FOR UPDATE (an exclusive row lock, two-phase locking) makes B wait until A "
                      "commits. B then re-checks availability and is refused: the last room can never be sold twice."}


# ── 2. deadlock detection ──────────────────────────────────────────────────
def deadlock() -> dict:
    tl = Timeline()
    a, b = _connect(), _connect()
    both_locked = threading.Barrier(2)

    def session(name, conn, first, second):
        conn.execute("UPDATE lab.txn_demo SET qty = qty WHERE item_id = %s", (first,))
        tl.log(name, f"locked row {first}")
        both_locked.wait()
        tl.log(name, f"now asks for row {second} (held by the other session)…")
        try:
            conn.execute("UPDATE lab.txn_demo SET qty = qty WHERE item_id = %s", (second,))
            tl.log(name, f"got row {second} once the victim was aborted")
        except psycopg.errors.DeadlockDetected as e:
            tl.log(name, "ERROR: deadlock detected → chosen as victim, transaction aborted",
                   e.diag.message_detail)
        conn.rollback()

    _run_parallel(lambda: session("A", a, 1, 2), lambda: session("B", b, 2, 1))
    a.close(); b.close()
    return {"scenario": "deadlock", "timeline": tl.events,
            "lesson": "A waits for B and B waits for A: a cycle in the wait-for graph. After deadlock_timeout "
                      "(1 s) PostgreSQL detects it and aborts one victim. fn_book_stay prevents this by "
                      "always locking rooms in room_id order."}


# ── 3. non-repeatable read: READ COMMITTED vs REPEATABLE READ ──────────────
def isolation_levels() -> dict:
    results = {}
    read_sql = "SELECT qty FROM lab.txn_demo WHERE item_id = 1"
    for level in ("READ COMMITTED", "REPEATABLE READ"):
        tl = Timeline()
        reader, writer = _connect(), _connect(autocommit=True)
        reader.execute(f"SET TRANSACTION ISOLATION LEVEL {level}")
        first = reader.execute(read_sql).fetchone()["qty"]
        tl.log("Reader", f"[{level}] first read of qty", first)
        writer.execute("UPDATE lab.txn_demo SET qty = qty - 3 WHERE item_id = 1")
        tl.log("Writer", "UPDATE qty = qty - 3 · COMMIT")
        second = reader.execute(read_sql).fetchone()["qty"]
        tl.log("Reader", "second read inside the SAME transaction", second)
        reader.rollback()
        writer.execute("UPDATE lab.txn_demo SET qty = qty + 3 WHERE item_id = 1")
        reader.close(); writer.close()
        results[level] = {"timeline": tl.events, "repeatable": first == second}
    return {"scenario": "isolation_levels", "results": results,
            "lesson": "READ COMMITTED sees the other transaction's committed change on the second read "
                      "(non-repeatable read). REPEATABLE READ reads from a snapshot taken at its first query, "
                      "so both reads agree."}


# ── 4. MVCC: every UPDATE writes a new row version ─────────────────────────
def mvcc_versions() -> dict:
    tl = Timeline()
    sql = "SELECT xmin::text, xmax::text, ctid::text, qty FROM lab.txn_demo WHERE item_id = 2"
    with _connect() as a, _connect() as b:
        tl.log("A", "row version before (xmin = id of the creating transaction, ctid = physical slot)",
               a.execute(sql).fetchone())
        tl.log("A", "BEGIN · my transaction id", a.execute("SELECT txid_current() AS txid").fetchone())
        a.execute("UPDATE lab.txn_demo SET qty = qty + 1 WHERE item_id = 2")
        tl.log("A", "after UPDATE (uncommitted): a NEW version with my xmin at a new ctid", a.execute(sql).fetchone())
        tl.log("B", "meanwhile B still reads the OLD version — no dirty read, and B did not wait",
               b.execute(sql).fetchone())
        b.rollback()
        a.rollback()
        tl.log("A", "ROLLBACK · the new version is never made visible")
    return {"scenario": "mvcc_versions", "timeline": tl.events,
            "lesson": "Multiversion concurrency control: a writer creates a new tuple version stamped with its "
                      "transaction id (a timestamp), readers see the version valid for their snapshot. Readers "
                      "never block writers, and uncommitted data is never visible."}


# ── 5. atomicity: a failure midway undoes everything ───────────────────────
def atomic_rollback() -> dict:
    tl = Timeline()
    with _connect() as c:
        tl.log("A", "bookings before", c.execute("SELECT count(*) AS n FROM bookings").fetchone())
        c.rollback()
        c.execute("INSERT INTO bookings (guest_id, hotel_id, check_in, check_out, status) "
                  "VALUES (7, 2, DATE '2027-03-01', DATE '2027-03-03', 'CONFIRMED')")
        tl.log("A", "step 1 ✓ booking header inserted (Charminar Courtyard)")
        try:
            c.execute("INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax) "
                      "VALUES (currval(pg_get_serial_sequence('bookings', 'booking_id')), 1, 100, 5)")
        except psycopg.Error as e:
            tl.log("A", "step 2 ✗ room 1 is in Samudra Mahal, not Charminar Courtyard", e.diag.message_primary)
        c.rollback()
        tl.log("A", "ROLLBACK · bookings after — step 1 was undone too",
               c.execute("SELECT count(*) AS n FROM bookings").fetchone())
        c.rollback()
    return {"scenario": "atomic_rollback", "timeline": tl.events,
            "lesson": "Atomicity: a transaction is all-or-nothing. Step 1 succeeded, step 2 broke a rule, so "
                      "the whole unit was undone and the database is exactly as it was."}


SCENARIOS = {
    "double_booking_race": double_booking_race,
    "deadlock": deadlock,
    "isolation_levels": isolation_levels,
    "mvcc_versions": mvcc_versions,
    "atomic_rollback": atomic_rollback,
}
