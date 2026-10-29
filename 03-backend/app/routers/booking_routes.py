"""Sign-in (phone + OTP), guests, bookings, cancellations, reviews.

Every guest action needs the signed session token from /auth/verify, and the
API checks that the booking belongs to that guest."""
from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import security
from ..db import Trace, fetch, fetch_one, transaction

router = APIRouter(prefix="/api", tags=["booking"])

class PhoneIn(BaseModel):
    phone: str = Field(pattern=r"^[6-9][0-9]{9}$")


class VerifyIn(PhoneIn):
    otp: str


class GuestIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=40)
    last_name: str = Field(min_length=1, max_length=40)
    email: str
    date_of_birth: date
    id_type: Literal["PAN", "PASSPORT", "DRIVING_LICENCE", "VOTER_ID"]
    id_number: str = Field(min_length=4, max_length=20)
    home_city_id: int | None = None


class BookingIn(BaseModel):
    room_type_id: int
    check_in: date
    check_out: date
    rooms: int = Field(1, ge=1, le=6)
    adults: int = Field(2, ge=1)
    children: int = Field(0, ge=0)
    method: Literal["UPI", "CARD", "NETBANKING", "WALLET", "PAY_AT_HOTEL"] = "UPI"
    upi_vpa: str | None = None
    special_request: str | None = Field(None, max_length=200)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = Field(min_length=2, max_length=100)
    body: str | None = None


GUEST_COLUMNS = """g.guest_id, g.first_name, g.last_name, g.phone, g.email, g.date_of_birth,
                   g.id_type, g.home_city_id, c.city_name AS home_city, g.created_at"""


@router.post("/auth/otp")
def send_otp(body: PhoneIn):
    """Create a one-time code: rate-limited, stored only as an HMAC, valid 5 minutes."""
    trace = Trace()
    with transaction() as conn:
        recent = fetch_one(conn, """
            SELECT count(*) AS sent, max(created_at) AS last_at,
                   extract(epoch FROM now() - max(created_at))::int AS seconds_ago
            FROM auth.otp_challenges
            WHERE phone = %s AND created_at > now() - make_interval(mins => %s)""",
            (body.phone, security.SEND_WINDOW_MIN), trace)
        if recent["sent"] >= security.SEND_LIMIT:
            raise HTTPException(429, f"Too many codes requested. Try again in {security.SEND_WINDOW_MIN} minutes.")
        if recent["seconds_ago"] is not None and recent["seconds_ago"] < security.RESEND_COOLDOWN_S:
            wait = security.RESEND_COOLDOWN_S - recent["seconds_ago"]
            raise HTTPException(429, f"Please wait {wait} seconds before asking for a new code.")
        code = security.new_code()
        fetch(conn, """
            INSERT INTO auth.otp_challenges (phone, code_hash, expires_at)
            VALUES (%s, %s, now() + make_interval(secs => %s))""",
            (body.phone, security.code_hash(body.phone, code), security.OTP_TTL_SECONDS), trace)
        security.send_sms(body.phone, code)
    data = {"sent": True, "expires_in": security.OTP_TTL_SECONDS, "resend_in": security.RESEND_COOLDOWN_S,
            "provider": security.SMS_PROVIDER}
    if security.OTP_DEMO:
        data["demo_otp"] = code          # demo mode only: no SMS account is configured
    return {"data": data, "trace": trace.steps}


@router.post("/auth/verify")
def verify_otp(body: VerifyIn):
    trace = Trace()
    with transaction() as conn:
        ch = fetch_one(conn, """
            SELECT challenge_id, code_hash, attempts, expires_at < now() AS expired
            FROM auth.otp_challenges
            WHERE phone = %s AND verified_at IS NULL
            ORDER BY created_at DESC LIMIT 1
            FOR UPDATE""", (body.phone,), trace)
        if not ch:
            raise HTTPException(400, "Ask for a code first.")
        if ch["expired"]:
            raise HTTPException(410, "That code has expired. Ask for a new one.")
        if ch["attempts"] >= security.OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many wrong attempts. Ask for a new code.")
        if not security.codes_match(ch["code_hash"].strip(), body.phone, body.otp.strip()):
            fetch(conn, "UPDATE auth.otp_challenges SET attempts = attempts + 1 WHERE challenge_id = %s",
                  (ch["challenge_id"],), trace)
            conn.commit()
            left = security.OTP_MAX_ATTEMPTS - ch["attempts"] - 1
            raise HTTPException(401, f"That code doesn't match. {left} attempt{'s' if left != 1 else ''} left.")
        fetch(conn, "UPDATE auth.otp_challenges SET verified_at = now() WHERE challenge_id = %s",
              (ch["challenge_id"],), trace)
        # phone is a candidate key, so this returns at most one guest
        guest = fetch_one(conn, f"""SELECT {GUEST_COLUMNS} FROM guests g
                                     LEFT JOIN cities c ON c.city_id = g.home_city_id
                                     WHERE g.phone = %s""", (body.phone,), trace)
    token = security.issue_token(body.phone, guest["guest_id"] if guest else None)
    return {"data": {"guest": guest, "is_new": guest is None, "token": token}, "trace": trace.steps}


@router.post("/guests", status_code=201)
def create_guest(body: GuestIn, s: dict = Depends(security.session)):
    """The phone comes from the verified session, never from the request body."""
    trace = Trace()
    with transaction() as conn:
        guest = fetch_one(conn, """
            INSERT INTO guests (first_name, last_name, phone, email, date_of_birth, id_type, id_number, home_city_id)
            VALUES (%(first_name)s, %(last_name)s, %(phone)s, lower(%(email)s), %(date_of_birth)s,
                    %(id_type)s, upper(%(id_number)s), %(home_city_id)s)
            RETURNING guest_id""", {**body.model_dump(), "phone": s["phone"]}, trace)
        guest = fetch_one(conn, f"""SELECT {GUEST_COLUMNS} FROM guests g
                                     LEFT JOIN cities c ON c.city_id = g.home_city_id
                                     WHERE g.guest_id = %s""", (guest["guest_id"],), trace)
    return {"data": {"guest": guest, "token": security.issue_token(s["phone"], guest["guest_id"])},
            "trace": trace.steps}


@router.get("/guests/demo")
def demo_guests():
    """A few real guests from the dataset, so the viva demo can sign in quickly.
    Only available in demo mode (no real SMS provider configured)."""
    if not security.OTP_DEMO:
        return {"data": []}
    with transaction(read_only=True) as conn:
        rows = fetch(conn, """
            SELECT g.guest_id, g.first_name, g.last_name, g.phone, count(b.booking_id) AS bookings
            FROM guests g JOIN bookings b USING (guest_id)
            GROUP BY g.guest_id ORDER BY count(b.booking_id) DESC LIMIT 4""")
    return {"data": rows}


@router.post("/bookings", status_code=201)
def create_booking(body: BookingIn, s: dict = Depends(security.session)):
    """One call to fn_book_stay: lock rooms → pick free ones → insert booking,
    booking_rooms and payment — all in ONE transaction. The guest is the
    signed-in one, never a guest_id sent by the browser."""
    guest_id = security.require_guest(s)
    trace = Trace()
    with transaction() as conn:
        result = fetch_one(conn, """
            SELECT * FROM fn_book_stay(%(guest_id)s, %(room_type_id)s, %(check_in)s, %(check_out)s,
                                       %(rooms)s, %(adults)s, %(children)s, %(method)s::payment_method_t,
                                       %(upi_vpa)s, %(special_request)s)""", {**body.model_dump(), "guest_id": guest_id}, trace)
        # the deferred capacity trigger fires here, before COMMIT
        fetch(conn, "SET CONSTRAINTS ALL IMMEDIATE", trace=trace)
    return {"data": result, "trace": trace.steps}


@router.get("/guests/{guest_id}/bookings")
def guest_bookings(guest_id: int, s: dict = Depends(security.session)):
    security.require_guest(s, guest_id)
    trace = Trace()
    with transaction(read_only=True) as conn:
        rows = fetch(conn, """
            SELECT v.*, h.property_type, h.locality,
                   EXISTS (SELECT 1 FROM reviews r WHERE r.booking_id = v.booking_id) AS reviewed
            FROM v_booking_summary v JOIN hotels h USING (hotel_id)
            WHERE v.guest_id = %s
            ORDER BY v.check_in DESC""", (guest_id,), trace)
    return {"data": rows, "trace": trace.steps}


@router.get("/bookings/{ref}")
def booking_detail(ref: str, s: dict = Depends(security.session)):
    trace = Trace()
    with transaction(read_only=True) as conn:
        booking = fetch_one(conn, "SELECT * FROM v_booking_summary WHERE booking_ref = %s", (ref.upper(),), trace)
        if not booking:
            raise HTTPException(404, "booking not found")
        security.require_guest(s, booking["guest_id"])
        booking["rooms_detail"] = fetch(conn, """
            SELECT r.room_number, r.floor_no, rt.type_name, rt.bed_type, br.room_subtotal, br.room_tax
            FROM booking_rooms br JOIN rooms r USING (room_id) JOIN room_types rt USING (room_type_id)
            WHERE br.booking_id = %s ORDER BY r.room_number""", (booking["booking_id"],), trace)
        booking["payments"] = fetch(conn, """
            SELECT kind, method, status, amount, upi_vpa, card_last4, gateway_ref, created_at
            FROM payments WHERE booking_id = %s ORDER BY payment_id""", (booking["booking_id"],), trace)
    return {"data": booking, "trace": trace.steps}


@router.post("/bookings/{ref}/cancel")
def cancel_booking(ref: str, s: dict = Depends(security.session)):
    trace = Trace()
    with transaction() as conn:
        b = fetch_one(conn, "SELECT booking_id, guest_id FROM bookings WHERE booking_ref = %s", (ref.upper(),), trace)
        if not b:
            raise HTTPException(404, "booking not found")
        security.require_guest(s, b["guest_id"])
        out = fetch_one(conn, "CALL sp_cancel_booking(%s, NULL)", (b["booking_id"],), trace)
    return {"data": {"booking_ref": ref.upper(), "refund_amount": out["refund_amount"]}, "trace": trace.steps}


@router.post("/bookings/{ref}/review", status_code=201)
def review_booking(ref: str, body: ReviewIn, s: dict = Depends(security.session)):
    guest_id = security.require_guest(s)
    trace = Trace()
    with transaction() as conn:
        row = fetch_one(conn, """
            INSERT INTO reviews (booking_id, rating, title, body)
            SELECT booking_id, %s, %s, %s FROM bookings WHERE booking_ref = %s AND guest_id = %s
            RETURNING review_id""", (body.rating, body.title, body.body, ref.upper(), guest_id), trace)
        if not row:
            raise HTTPException(404, "booking not found")
    return {"data": row, "trace": trace.steps}
