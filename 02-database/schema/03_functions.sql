-- ════════════════════════════════════════════════════════════════════════════
--  03_functions.sql  ·  Pricing, availability and booking logic
--  Syllabus: SQL fundamentals · Stored functions / procedures · Transactions
--
--  Pricing rule (the only place it is written down):
--      nightly_rate = base_price × season multiplier × weekend multiplier
--      weekend      = Friday and Saturday nights  → × 1.10
--      GST on rooms (slabs from 22-Sep-2025):  ≤ ₹1,000 → 0%,
--                                              ₹1,001-7,500 → 5%,  > ₹7,500 → 18%
-- ════════════════════════════════════════════════════════════════════════════

-- GST slab for one night's tariff
CREATE OR REPLACE FUNCTION fn_gst_rate(tariff numeric)
RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN tariff <= 1000 THEN 0.00
                WHEN tariff <= 7500 THEN 0.05
                ELSE 0.18 END;
$$;


-- Night-by-night price quote:  SELECT * FROM fn_quote_stay(1, '2026-12-24', '2026-12-26');
-- A CROSS JOIN with generate_series produces one row per night, and a THETA
-- (non-equi) LEFT JOIN finds the season that night falls into, if any.
CREATE OR REPLACE FUNCTION fn_quote_stay(p_room_type_id integer,
                              p_check_in     date,
                              p_check_out    date,
                              p_rooms        integer DEFAULT 1)
RETURNS TABLE (night              date,
               day_name           text,
               season_name        varchar,
               base_price         numeric,
               season_multiplier  numeric,
               weekend_multiplier numeric,
               nightly_rate       numeric,
               gst_rate           numeric,
               gst_amount         numeric,
               rooms              integer,
               night_total        numeric)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF p_check_out <= p_check_in THEN
        RAISE EXCEPTION 'Check-out (%) must be after check-in (%)', p_check_out, p_check_in
              USING ERRCODE = '22023', HINT = 'A stay is at least one night.';
    END IF;
    IF p_check_out - p_check_in > 30 THEN
        RAISE EXCEPTION 'Stays are limited to 30 nights (asked for %)', p_check_out - p_check_in
              USING ERRCODE = '22023', HINT = 'Split long stays into two bookings.';
    END IF;
    IF p_rooms < 1 THEN
        RAISE EXCEPTION 'At least one room is required' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM room_types rt WHERE rt.room_type_id = p_room_type_id) THEN
        RAISE EXCEPTION 'Room type % does not exist', p_room_type_id USING ERRCODE = 'P0002';
    END IF;

    RETURN QUERY
    WITH nights AS (
        SELECT d::date AS night
        FROM generate_series(p_check_in, p_check_out - 1, INTERVAL '1 day') AS d
    ), priced AS (
        SELECT n.night,
               s.season_name,
               rt.base_price::numeric                                     AS base,
               coalesce(s.multiplier, 1.00)                               AS s_mult,
               CASE WHEN extract(isodow FROM n.night) IN (5, 6) THEN 1.10 ELSE 1.00 END AS w_mult
        FROM room_types rt
        CROSS JOIN nights n
        LEFT JOIN seasons s ON n.night BETWEEN s.start_date AND s.end_date
        WHERE rt.room_type_id = p_room_type_id
    )
    SELECT p.night,
           to_char(p.night, 'Dy'),
           p.season_name,
           p.base,
           p.s_mult,
           p.w_mult,
           round(p.base * p.s_mult * p.w_mult, 0)                                       AS rate,
           fn_gst_rate(round(p.base * p.s_mult * p.w_mult, 0)),
           round(round(p.base * p.s_mult * p.w_mult, 0) * fn_gst_rate(round(p.base * p.s_mult * p.w_mult, 0)), 2),
           p_rooms,
           round((round(p.base * p.s_mult * p.w_mult, 0)
                  * (1 + fn_gst_rate(round(p.base * p.s_mult * p.w_mult, 0)))) * p_rooms, 2)
    FROM priced p
    ORDER BY p.night;
END;
$$;


-- Total price of a stay (one number)
CREATE OR REPLACE FUNCTION fn_stay_total(p_room_type_id integer, p_check_in date, p_check_out date,
                              p_rooms integer DEFAULT 1)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT sum(night_total) FROM fn_quote_stay(p_room_type_id, p_check_in, p_check_out, p_rooms);
$$;


-- A room is busy for [check_in, check_out) if any non-cancelled booking holds it.
-- Two half-open ranges [a,b) and [c,d) overlap  ⇔  a < d AND c < b.
CREATE OR REPLACE FUNCTION fn_room_is_free(p_room_id integer, p_check_in date, p_check_out date,
                                p_ignore_booking integer DEFAULT NULL)
RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT NOT EXISTS (
        SELECT 1
        FROM booking_rooms br
        JOIN bookings b ON b.booking_id = br.booking_id
        WHERE br.room_id = p_room_id
          AND b.status NOT IN ('CANCELLED')
          AND b.booking_id IS DISTINCT FROM p_ignore_booking
          AND b.check_in < p_check_out
          AND p_check_in < b.check_out
    );
$$;


-- How many rooms of each type are free in a hotel for a date range
CREATE OR REPLACE FUNCTION fn_available_rooms(p_hotel_id integer, p_check_in date, p_check_out date)
RETURNS TABLE (room_type_id integer, type_name varchar, base_price numeric,
               max_adults smallint, max_children smallint,
               total_rooms bigint, free_rooms bigint)
LANGUAGE sql STABLE AS $$
    SELECT rt.room_type_id, rt.type_name, rt.base_price, rt.max_adults, rt.max_children,
           count(r.room_id)                                                        AS total_rooms,
           count(r.room_id) FILTER (WHERE fn_room_is_free(r.room_id, p_check_in, p_check_out)) AS free_rooms
    FROM room_types rt
    LEFT JOIN rooms r ON r.room_type_id = rt.room_type_id AND r.is_active
    WHERE rt.hotel_id = p_hotel_id
    GROUP BY rt.room_type_id
    ORDER BY rt.base_price;
$$;


-- ────────────────────────────────────────────────────────────────────────────
--  fn_book_stay — the whole booking as ONE atomic unit of work.
--
--  Concurrency (Unit 5, lock-based protocol):
--    SELECT … FOR UPDATE takes row-level exclusive locks on every room of the
--    requested type. A second customer booking the same type at the same moment
--    WAITS here until the first transaction commits, then re-checks
--    availability, so the same room can never be sold twice.
--    Rooms are always locked in room_id order, so two transactions can never
--    hold locks in opposite orders, which rules out deadlock between bookings.
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_book_stay(p_guest_id     integer,
                             p_room_type_id integer,
                             p_check_in     date,
                             p_check_out    date,
                             p_rooms        integer          DEFAULT 1,
                             p_adults       integer          DEFAULT 2,
                             p_children     integer          DEFAULT 0,
                             p_method       payment_method_t DEFAULT 'UPI',
                             p_upi_vpa      varchar          DEFAULT NULL,
                             p_request      varchar          DEFAULT NULL)
RETURNS TABLE (booking_id integer, booking_ref char(8), total_amount numeric, status booking_status_t)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public   -- runs with the owner's rights: the app can lock
AS $$                                       -- rooms only through this function
DECLARE
    v_hotel_id   integer;
    v_room_ids   integer[];
    v_booking_id integer;
    v_ref        char(8);
    v_total      numeric;
    v_status     booking_status_t;
BEGIN
    SELECT rt.hotel_id INTO v_hotel_id FROM room_types rt WHERE rt.room_type_id = p_room_type_id;
    IF v_hotel_id IS NULL THEN
        RAISE EXCEPTION 'Room type % does not exist', p_room_type_id USING ERRCODE = 'P0002';
    END IF;

    -- 1. lock every active room of this type, in a fixed order
    PERFORM 1 FROM rooms r
    WHERE r.room_type_id = p_room_type_id AND r.is_active
    ORDER BY r.room_id
    FOR UPDATE;

    -- 2. now that nobody else can change them, pick the free ones
    SELECT array_agg(x.room_id ORDER BY x.room_id) INTO v_room_ids
    FROM (SELECT r.room_id FROM rooms r
          WHERE r.room_type_id = p_room_type_id AND r.is_active
            AND fn_room_is_free(r.room_id, p_check_in, p_check_out)
          ORDER BY r.room_id
          LIMIT p_rooms) x;

    IF coalesce(cardinality(v_room_ids), 0) < p_rooms THEN
        RAISE EXCEPTION 'Only % room(s) of this type are free from % to %',
              coalesce(cardinality(v_room_ids), 0), p_check_in, p_check_out
              USING ERRCODE = 'P0001', HINT = 'Try other dates or another room type.';
    END IF;

    -- 3. header row (booking_ref is generated by trigger trg_bookings_ref)
    v_status := 'CONFIRMED';
    INSERT INTO bookings (guest_id, hotel_id, check_in, check_out, adults, children, status, special_request)
    VALUES (p_guest_id, v_hotel_id, p_check_in, p_check_out, p_adults, p_children, v_status, p_request)
    RETURNING bookings.booking_id, bookings.booking_ref INTO v_booking_id, v_ref;

    -- 4. one line per room, with the price agreed today
    INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax)
    SELECT v_booking_id, rid, q.subtotal, q.tax
    FROM unnest(v_room_ids) AS rid
    CROSS JOIN (SELECT sum(nightly_rate) AS subtotal, sum(gst_amount) AS tax
                FROM fn_quote_stay(p_room_type_id, p_check_in, p_check_out)) q;

    -- 5. payment (mock gateway: UPI / card always succeed in this demo)
    v_total := fn_stay_total(p_room_type_id, p_check_in, p_check_out, p_rooms);
    INSERT INTO payments (booking_id, kind, method, status, amount, upi_vpa, gateway_ref)
    VALUES (v_booking_id, 'CHARGE', p_method,
            CASE WHEN p_method = 'PAY_AT_HOTEL' THEN 'PENDING' ELSE 'SUCCESS' END::payment_status_t,
            v_total,
            CASE WHEN p_method = 'UPI' THEN coalesce(p_upi_vpa, 'guest@upi') END,
            'pay_' || substr(md5(v_booking_id::text || clock_timestamp()::text), 1, 16));

    RETURN QUERY SELECT v_booking_id, v_ref, v_total, v_status;
END;
$$;


-- ────────────────────────────────────────────────────────────────────────────
--  sp_cancel_booking — a PROCEDURE (called with CALL) with an OUT parameter.
--  Refund policy:  ≥ 7 days before check-in → 100 %
--                  2-6 days                 →  50 %
--                  < 2 days                 →   0 %
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_cancel_booking(IN  p_booking_id integer,
                                   OUT refund_amount numeric)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
    v_b        bookings%ROWTYPE;
    v_paid     numeric;
    v_pct      numeric;
    v_method   payment_method_t;
BEGIN
    SELECT * INTO v_b FROM bookings WHERE booking_id = p_booking_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Booking % does not exist', p_booking_id USING ERRCODE = 'P0002';
    END IF;

    IF v_b.status NOT IN ('PENDING', 'CONFIRMED') THEN
        RAISE EXCEPTION 'Booking % is % and cannot be cancelled', v_b.booking_ref, v_b.status
              USING ERRCODE = 'P0001', HINT = 'Only PENDING or CONFIRMED bookings can be cancelled.';
    END IF;

    -- the status-transition trigger is the second line of defence for illegal moves
    UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = p_booking_id;

    SELECT coalesce(sum(amount) FILTER (WHERE kind = 'CHARGE'), 0)
         - coalesce(sum(amount) FILTER (WHERE kind = 'REFUND'), 0),
           (array_agg(method ORDER BY payment_id) FILTER (WHERE kind = 'CHARGE'))[1]
      INTO v_paid, v_method
    FROM payments WHERE booking_id = p_booking_id AND status = 'SUCCESS';

    v_pct := CASE WHEN v_b.check_in - current_date >= 7 THEN 1.00
                  WHEN v_b.check_in - current_date >= 2 THEN 0.50
                  ELSE 0.00 END;
    refund_amount := round(v_paid * v_pct, 2);

    IF refund_amount > 0 THEN
        INSERT INTO payments (booking_id, kind, method, status, amount, upi_vpa, gateway_ref)
        VALUES (p_booking_id, 'REFUND', v_method, 'SUCCESS', refund_amount,
                CASE WHEN v_method = 'UPI' THEN 'refund@upi' END,
                'rfd_' || substr(md5(p_booking_id::text || clock_timestamp()::text), 1, 16));
    END IF;
END;
$$;
