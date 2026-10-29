-- ════════════════════════════════════════════════════════════════════════════
--  04_triggers.sql  ·  Business rules that a CHECK or FK cannot express
--  Syllabus: Relational model › Triggers · Integrity
--
--  A CHECK constraint can only look at one row of one table. Rules that need
--  other rows ("is this room already taken?") or other tables ("was this stay
--  completed?") are written as triggers.
--
--   #  trigger                      table          timing                 rule
--   1  trg_bookings_ref             bookings       BEFORE INSERT          generate YRxxxxxx reference
--   2  trg_bookings_status          bookings       BEFORE UPDATE          legal status transitions only
--   3  trg_booking_rooms_guard      booking_rooms  BEFORE INSERT/UPDATE   same hotel + no double booking
--   4  trg_bookings_dates           bookings       BEFORE UPDATE          re-check rooms if dates move
--   5  trg_booking_capacity         booking_rooms  AFTER INSERT (DEFERRED) guests fit in the rooms
--   6  trg_reviews_guard            reviews        BEFORE INSERT/UPDATE   only completed stays, after check-out
--   7  trg_reviews_rollup           reviews        AFTER I/U/D            keep hotels.avg_rating in sync
--   8  trg_payments_refund_guard    payments       BEFORE INSERT          refund ≤ amount paid
-- ════════════════════════════════════════════════════════════════════════════


-- 1 ── booking reference ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION tg_bookings_ref() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    alphabet constant text := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';   -- no 0/O, 1/I/L
    candidate text;
BEGIN
    IF NEW.booking_ref IS NULL THEN
        LOOP
            SELECT 'YR' || string_agg(substr(alphabet, 1 + floor(random() * length(alphabet))::int, 1), '')
              INTO candidate FROM generate_series(1, 6);
            EXIT WHEN NOT EXISTS (SELECT 1 FROM bookings WHERE booking_ref = candidate);
        END LOOP;
        NEW.booking_ref := candidate;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bookings_ref
    BEFORE INSERT ON bookings
    FOR EACH ROW EXECUTE FUNCTION tg_bookings_ref();


-- 2 ── status state machine ─────────────────────────────────────────────────
--   PENDING ──► CONFIRMED ──► CHECKED_IN ──► COMPLETED
--      │            │  └──────► NO_SHOW
--      └────────────┴─────────► CANCELLED
CREATE OR REPLACE FUNCTION tg_bookings_status() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;
    IF NOT (
        (OLD.status = 'PENDING'    AND NEW.status IN ('CONFIRMED', 'CANCELLED')) OR
        (OLD.status = 'CONFIRMED'  AND NEW.status IN ('CHECKED_IN', 'CANCELLED', 'NO_SHOW')) OR
        (OLD.status = 'CHECKED_IN' AND NEW.status = 'COMPLETED')
    ) THEN
        RAISE EXCEPTION 'A % booking cannot become %', OLD.status, NEW.status
              USING ERRCODE = 'P0001',
                    HINT = 'Allowed: PENDING→CONFIRMED/CANCELLED, CONFIRMED→CHECKED_IN/CANCELLED/NO_SHOW, CHECKED_IN→COMPLETED';
    END IF;
    IF NEW.status = 'CANCELLED' THEN
        NEW.cancelled_at := coalesce(NEW.cancelled_at, now());
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bookings_status
    BEFORE UPDATE OF status ON bookings
    FOR EACH ROW EXECUTE FUNCTION tg_bookings_status();


-- 3 ── no double booking + room belongs to the booking's hotel ─────────────
CREATE OR REPLACE FUNCTION tg_booking_rooms_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    b      bookings%ROWTYPE;
    r      rooms%ROWTYPE;
    clash  char(8);
BEGIN
    SELECT * INTO b FROM bookings WHERE booking_id = NEW.booking_id;
    SELECT * INTO r FROM rooms    WHERE room_id    = NEW.room_id;

    IF r.hotel_id <> b.hotel_id THEN
        RAISE EXCEPTION 'Room % belongs to hotel %, but booking % is at hotel %',
              r.room_number, r.hotel_id, b.booking_ref, b.hotel_id USING ERRCODE = '23514';
    END IF;
    IF NOT r.is_active THEN
        RAISE EXCEPTION 'Room % is under maintenance', r.room_number USING ERRCODE = '23514';
    END IF;

    IF b.status <> 'CANCELLED' THEN
        SELECT o.booking_ref INTO clash
        FROM booking_rooms obr
        JOIN bookings o ON o.booking_id = obr.booking_id
        WHERE obr.room_id = NEW.room_id
          AND o.booking_id <> NEW.booking_id
          AND o.status <> 'CANCELLED'
          AND o.check_in < b.check_out AND b.check_in < o.check_out
        LIMIT 1;
        IF FOUND THEN
            RAISE EXCEPTION 'Room % is already booked (%) for an overlapping stay', r.room_number, clash
                  USING ERRCODE = '23P01', HINT = 'Choose other dates or another room.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_booking_rooms_guard
    BEFORE INSERT OR UPDATE ON booking_rooms
    FOR EACH ROW EXECUTE FUNCTION tg_booking_rooms_guard();


-- 4 ── moving dates (or un-cancelling) must not create an overlap ──────────
CREATE OR REPLACE FUNCTION tg_bookings_dates() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    clash text;
BEGIN
    IF NEW.status = 'CANCELLED' THEN
        RETURN NEW;
    END IF;
    SELECT r.room_number INTO clash
    FROM booking_rooms br
    JOIN rooms r ON r.room_id = br.room_id
    WHERE br.booking_id = NEW.booking_id
      AND NOT fn_room_is_free(br.room_id, NEW.check_in, NEW.check_out, NEW.booking_id)
    LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'Room % is not free for the new dates % → %', clash, NEW.check_in, NEW.check_out
              USING ERRCODE = '23P01';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bookings_dates
    BEFORE UPDATE OF check_in, check_out ON bookings
    FOR EACH ROW EXECUTE FUNCTION tg_bookings_dates();


-- 5 ── capacity: a DEFERRED constraint trigger ─────────────────────────────
-- Runs at COMMIT, after all rooms of the booking have been inserted, so a
-- booking for 5 adults in 2 rooms is judged on both rooms together.
CREATE OR REPLACE FUNCTION tg_booking_capacity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    b        bookings%ROWTYPE;
    cap_a    integer;
    cap_c    integer;
BEGIN
    SELECT * INTO b FROM bookings WHERE booking_id = NEW.booking_id;
    IF NOT FOUND THEN
        RETURN NULL;                       -- booking deleted in the same transaction
    END IF;
    SELECT sum(rt.max_adults), sum(rt.max_children) INTO cap_a, cap_c
    FROM booking_rooms br
    JOIN rooms r       ON r.room_id = br.room_id
    JOIN room_types rt ON rt.room_type_id = r.room_type_id
    WHERE br.booking_id = NEW.booking_id;

    IF b.adults > cap_a OR b.adults + b.children > cap_a + cap_c THEN
        RAISE EXCEPTION 'Booking % has % adults + % children but the rooms hold % adults + % children',
              b.booking_ref, b.adults, b.children, cap_a, cap_c
              USING ERRCODE = '23514', HINT = 'Add another room.';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_booking_capacity
    AFTER INSERT ON booking_rooms
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION tg_booking_capacity();


-- 6 ── reviews only for completed stays, after check-out ───────────────────
CREATE OR REPLACE FUNCTION tg_reviews_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    b bookings%ROWTYPE;
BEGIN
    SELECT * INTO b FROM bookings WHERE booking_id = NEW.booking_id;
    IF b.status <> 'COMPLETED' THEN
        RAISE EXCEPTION 'Booking % is %; only completed stays can be reviewed', b.booking_ref, b.status
              USING ERRCODE = '23514';
    END IF;
    IF (NEW.created_at AT TIME ZONE 'Asia/Kolkata')::date < b.check_out THEN
        RAISE EXCEPTION 'A review cannot be written before check-out (%)', b.check_out
              USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_reviews_guard
    BEFORE INSERT OR UPDATE OF booking_id, created_at ON reviews
    FOR EACH ROW EXECUTE FUNCTION tg_reviews_guard();


-- 7 ── keep the derived attributes hotels.avg_rating / review_count correct ─
CREATE OR REPLACE FUNCTION tg_reviews_rollup() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    hid integer;
BEGIN
    FOR hid IN
        SELECT DISTINCT b.hotel_id FROM bookings b
        WHERE b.booking_id IN (CASE WHEN TG_OP <> 'INSERT' THEN OLD.booking_id END,
                               CASE WHEN TG_OP <> 'DELETE' THEN NEW.booking_id END)
    LOOP
        UPDATE hotels h
        SET (avg_rating, review_count) = (
            SELECT round(avg(rv.rating), 1), count(*)
            FROM reviews rv JOIN bookings b ON b.booking_id = rv.booking_id
            WHERE b.hotel_id = hid)
        WHERE h.hotel_id = hid;
    END LOOP;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_reviews_rollup
    AFTER INSERT OR UPDATE OF rating, booking_id OR DELETE ON reviews
    FOR EACH ROW EXECUTE FUNCTION tg_reviews_rollup();


-- 8 ── refunds can never exceed what was actually paid ─────────────────────
CREATE OR REPLACE FUNCTION tg_payments_refund_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    net numeric;
BEGIN
    IF NEW.kind = 'REFUND' AND NEW.status = 'SUCCESS' THEN
        SELECT coalesce(sum(amount) FILTER (WHERE kind = 'CHARGE'), 0)
             - coalesce(sum(amount) FILTER (WHERE kind = 'REFUND'), 0)
          INTO net
        FROM payments WHERE booking_id = NEW.booking_id AND status = 'SUCCESS';
        IF NEW.amount > net THEN
            RAISE EXCEPTION 'Refund ₹% is more than the ₹% paid for this booking', NEW.amount, net
                  USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_payments_refund_guard
    BEFORE INSERT ON payments
    FOR EACH ROW EXECUTE FUNCTION tg_payments_refund_guard();
