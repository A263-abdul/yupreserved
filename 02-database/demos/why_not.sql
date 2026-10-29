-- ════════════════════════════════════════════════════════════════════════════
--  why_not.sql · "Why can't I …?" — each statement here is SUPPOSED to fail.
--  The CLI (`yup why <name>`) and the API (/api/lab/why) run every scenario
--  inside a transaction that is always rolled back, and show which rule fired.
-- ════════════════════════════════════════════════════════════════════════════

-- @name: why.checkout_before_checkin
-- @title: Why can't I check out before I check in?
-- @topic: CHECK constraint (tuple-level)
-- @explain: ck_bookings_dates requires check_out > check_in for every row.
INSERT INTO bookings (guest_id, hotel_id, check_in, check_out)
VALUES (1, 1, DATE '2026-12-10', DATE '2026-12-08');

-- @name: why.stay_too_long
-- @title: Why can't I book 45 nights?
-- @topic: CHECK constraint (business limit)
-- @explain: ck_bookings_max_stay limits a booking to 30 nights.
INSERT INTO bookings (guest_id, hotel_id, check_in, check_out)
VALUES (1, 1, DATE '2026-12-01', DATE '2027-01-15');

-- @name: why.double_booking
-- @title: Why can't two guests get the same room on the same night?
-- @topic: Trigger (multi-row rule)
-- @explain: trg_booking_rooms_guard looks at OTHER bookings of the same room and rejects any overlapping date range. A CHECK constraint cannot see other rows, so this must be a trigger.
WITH taken AS (
    SELECT br.room_id, b.check_in, b.check_out, b.hotel_id
    FROM booking_rooms br JOIN bookings b USING (booking_id)
    WHERE b.status = 'CONFIRMED' AND b.hotel_id = 1
    ORDER BY b.check_in LIMIT 1
), nb AS (
    INSERT INTO bookings (guest_id, hotel_id, check_in, check_out, status)
    SELECT 2, hotel_id, check_in, check_out, 'CONFIRMED' FROM taken
    RETURNING booking_id
)
INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax)
SELECT nb.booking_id, taken.room_id, 1000, 50 FROM nb, taken;

-- @name: why.too_many_guests
-- @title: Why can't 9 adults share one Harbour Room?
-- @topic: Deferred constraint trigger (checked at COMMIT)
-- @explain: trg_booking_capacity is DEFERRABLE INITIALLY DEFERRED: it waits until all rooms of a booking are added, then compares guests with total room capacity.
WITH nb AS (
    INSERT INTO bookings (guest_id, hotel_id, check_in, check_out, adults, status)
    VALUES (3, 1, DATE '2027-02-02', DATE '2027-02-04', 9, 'CONFIRMED')
    RETURNING booking_id
)
INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax)
SELECT nb.booking_id, (SELECT min(room_id) FROM rooms WHERE room_type_id = 1), 37000, 6660 FROM nb;
SET CONSTRAINTS ALL IMMEDIATE;

-- @name: why.sold_out
-- @title: Why can't I book 3 Maharani Suites?
-- @topic: Stored function with row locks (SELECT … FOR UPDATE)
-- @explain: Pichola Rajbagh has only one Maharani Suite. fn_book_stay locks the rooms, counts the free ones and raises an error when there are not enough.
SELECT * FROM fn_book_stay(10, (SELECT room_type_id FROM room_types WHERE hotel_id = 3 AND type_name = 'Maharani Suite'),
                            DATE '2026-12-28', DATE '2026-12-30', 3);

-- @name: why.uncancel
-- @title: Why can't a completed stay be moved back to CONFIRMED?
-- @topic: Trigger (state machine)
-- @explain: trg_bookings_status allows only PENDING→CONFIRMED→CHECKED_IN→COMPLETED (plus cancellation / no-show). History cannot be rewritten.
UPDATE bookings SET status = 'CONFIRMED'
WHERE booking_id = (SELECT min(booking_id) FROM bookings WHERE status = 'COMPLETED');

-- @name: why.delete_hotel
-- @title: Why can't I delete a hotel that has bookings?
-- @topic: Foreign key · ON DELETE RESTRICT
-- @explain: fk_bookings_hotels is RESTRICT: deleting the parent would leave bookings pointing at nothing (a dangling reference).
DELETE FROM hotels WHERE hotel_id = 1;

-- @name: why.bad_phone
-- @title: Why is 12345 67890 not accepted as a phone number?
-- @topic: DOMAIN constraint
-- @explain: The domain indian_mobile requires 10 digits starting with 6–9. Every column of that type inherits the rule.
INSERT INTO guests (first_name, last_name, phone, email, date_of_birth, id_type, id_number)
VALUES ('Test', 'User', '1234567890', 'test.user@example.in', DATE '1995-05-05', 'PAN', 'ABCDE1234F');

-- @name: why.duplicate_phone
-- @title: Why can't I sign up with a phone that is already registered?
-- @topic: UNIQUE constraint (candidate key)
-- @explain: phone is a candidate key of guests (uq_guests_phone): it must identify exactly one guest.
INSERT INTO guests (first_name, last_name, phone, email, date_of_birth, id_type, id_number)
SELECT 'Copy', 'Cat', phone, 'copy.cat@example.in', DATE '1990-01-01', 'PAN', 'ZZZZZ9999Z'
FROM guests WHERE guest_id = 1;

-- @name: why.underage
-- @title: Why can't a 15-year-old create an account?
-- @topic: CHECK constraint using a date expression
-- @explain: ck_guests_adult requires the guest to be at least 18 on the day the account is created.
INSERT INTO guests (first_name, last_name, phone, email, date_of_birth, id_type, id_number)
VALUES ('Young', 'Traveller', '9000000001', 'young.t@example.in', DATE '2011-06-01', 'PAN', 'YOUNG1234Y');

-- @name: why.review_unfinished
-- @title: Why can't I review a stay that hasn't happened yet?
-- @topic: Trigger (cross-table rule)
-- @explain: trg_reviews_guard checks the booking: only COMPLETED stays, and only after the check-out date.
INSERT INTO reviews (booking_id, rating, title)
VALUES ((SELECT min(booking_id) FROM bookings WHERE status = 'CONFIRMED'), 5, 'Can''t wait!');

-- @name: why.second_review
-- @title: Why can't I review the same stay twice?
-- @topic: UNIQUE on a foreign key (1:1 relationship)
-- @explain: uq_reviews_booking makes booking_id unique in reviews, turning the 1:N relationship into 1:1.
INSERT INTO reviews (booking_id, rating, title)
SELECT booking_id, 4, 'Second thoughts' FROM reviews WHERE review_id = 1;

-- @name: why.season_overlap
-- @title: Why can't I add a "Wedding Season" that overlaps Diwali?
-- @topic: EXCLUDE constraint
-- @explain: ex_seasons_no_overlap uses a GiST index on date ranges so that no two seasons share a night; otherwise a night would have two prices.
INSERT INTO seasons (season_name, start_date, end_date, multiplier)
VALUES ('Wedding Season 2026', DATE '2026-11-08', DATE '2026-11-30', 1.30);

-- @name: why.refund_too_much
-- @title: Why can't I refund more than the guest paid?
-- @topic: Trigger (aggregate rule)
-- @explain: trg_payments_refund_guard sums the booking's successful charges and refunds before allowing a new refund.
INSERT INTO payments (booking_id, kind, method, status, amount, gateway_ref)
SELECT booking_id, 'REFUND', 'CARD', 'SUCCESS', amount * 2, 'rfd_demo_too_much'
FROM payments WHERE kind = 'CHARGE' AND status = 'SUCCESS' AND method = 'CARD' LIMIT 1;

-- @name: why.wrong_hotel_room
-- @title: Why can't a Mumbai booking use a room in Udaipur?
-- @topic: Trigger + composite key consistency
-- @explain: trg_booking_rooms_guard checks that the room's hotel_id equals the booking's hotel_id.
WITH nb AS (
    INSERT INTO bookings (guest_id, hotel_id, check_in, check_out, status)
    VALUES (4, 1, DATE '2027-03-01', DATE '2027-03-02', 'CONFIRMED') RETURNING booking_id
)
INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax)
SELECT nb.booking_id, (SELECT min(room_id) FROM rooms WHERE hotel_id = 3), 24000, 4320 FROM nb;

-- @name: why.analyst_reads_guests
-- @title: Why can't the analyst read guests' phone numbers?
-- @topic: DCL · GRANT / REVOKE · security views
-- @explain: yup_analyst has SELECT only on views. v_guest_directory shows masked phones; the guests table itself is off-limits.
SET LOCAL ROLE yup_analyst;
SELECT phone FROM guests LIMIT 1;
