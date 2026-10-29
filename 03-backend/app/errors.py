"""
Turn a PostgreSQL error into an answer to "why can't I do this?".

The response keeps the database's own words (message, constraint name,
SQLSTATE) and adds a one-line explanation of which rule fired, so the
frontend can show both to the user.
"""
from __future__ import annotations

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse

# constraint / trigger name  ->  plain-language rule
RULES = {
    "ck_bookings_dates": "CHECK constraint: check-out must be after check-in.",
    "ck_bookings_max_stay": "CHECK constraint: a booking can be at most 30 nights.",
    "ck_bookings_guests": "CHECK constraint: at least one adult, at most 24 guests.",
    "ck_bookings_booked_before_arrival": "CHECK constraint: you cannot book a stay that has already started.",
    "ck_bookings_cancel_state": "CHECK constraint: status CANCELLED and cancelled_at must go together.",
    "uq_guests_phone": "UNIQUE (candidate key): this phone number already belongs to another guest.",
    "uq_guests_email": "UNIQUE (candidate key): this email already belongs to another guest.",
    "uq_guests_id_document": "UNIQUE composite key (id_type, id_number): this ID document is already registered.",
    "uq_reviews_booking": "UNIQUE: a stay can be reviewed only once (1:1 bookings ↔ reviews).",
    "ex_seasons_no_overlap": "EXCLUDE constraint: two pricing seasons cannot overlap.",
    "fk_bookings_hotels": "FOREIGN KEY (ON DELETE RESTRICT): the hotel still has bookings.",
    "fk_bookings_guests": "FOREIGN KEY: the guest does not exist / still has bookings.",
    "ck_reviews_rating": "CHECK constraint: rating must be between 1 and 5.",
    "ck_guests_adult": "CHECK constraint: a guest must be at least 18 years old.",
    "ck_seasons_dates": "CHECK constraint: a season must end on or after its start date.",
    "ck_payments_amount": "CHECK constraint: a payment amount must be positive.",
    "indian_mobile_check": "DOMAIN indian_mobile: 10 digits, starting with 6, 7, 8 or 9.",
    "email_address_check": "DOMAIN email_address: not a valid email address.",
}

TRIGGERS = {
    "tg_booking_rooms_guard": "TRIGGER trg_booking_rooms_guard: a room must belong to the booking's hotel and be free for those dates.",
    "tg_bookings_status": "TRIGGER trg_bookings_status: that status change is not allowed.",
    "tg_booking_capacity": "DEFERRED CONSTRAINT TRIGGER trg_booking_capacity: too many guests for the rooms chosen.",
    "tg_reviews_guard": "TRIGGER trg_reviews_guard: only completed stays can be reviewed, after check-out.",
    "tg_payments_refund_guard": "TRIGGER trg_payments_refund_guard: refund larger than amount paid.",
    "fn_book_stay": "FUNCTION fn_book_stay: not enough free rooms (rows were locked with SELECT … FOR UPDATE).",
    "fn_quote_stay": "FUNCTION fn_quote_stay: the dates or room type are not valid.",
    "sp_cancel_booking": "PROCEDURE sp_cancel_booking: this booking cannot be cancelled.",
}

STATUS = {"23505": 409, "23503": 409, "23514": 422, "23P01": 409, "22023": 422,
          "P0001": 409, "P0002": 404, "23502": 422, "22P02": 422}


def explain_db_error(err: psycopg.Error) -> dict:
    d = err.diag
    constraint = d.constraint_name
    context = d.context or ""
    # domain checks report their constraint name too, e.g. "indian_mobile_check"
    rule = RULES.get(constraint or "") or next((v for k, v in TRIGGERS.items() if k in context), None)
    if not rule and d.sqlstate == "42501":
        rule = "PRIVILEGES (GRANT / REVOKE): this database role is not allowed to do that."
    return {
        "error": d.message_primary or str(err),
        "detail": d.message_detail,
        "hint": d.message_hint,
        "sqlstate": d.sqlstate,
        "constraint": constraint,
        "table": d.table_name,
        "rule": rule or "The database rejected the statement.",
        "raised_in": context.splitlines()[0] if context else None,
    }


async def db_error_handler(_: Request, err: psycopg.Error) -> JSONResponse:
    body = explain_db_error(err)
    return JSONResponse(status_code=STATUS.get(body["sqlstate"] or "", 400), content=body)
