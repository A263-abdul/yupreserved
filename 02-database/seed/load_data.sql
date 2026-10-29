-- ════════════════════════════════════════════════════════════════════════════
--  load_data.sql  ·  Bulk-load 01-dataset/processed/*.csv into the 15 tables
--
--  Loaded in dependency order (parents before children) so every foreign key
--  is satisfied the moment a row arrives. Triggers stay ON during the load:
--  the generated data is validated by exactly the same rules as live bookings.
-- ════════════════════════════════════════════════════════════════════════════

\echo '  · geography'
\copy states    FROM '../01-dataset/processed/states.csv'    WITH (FORMAT csv, HEADER true)
\copy cities    FROM '../01-dataset/processed/cities.csv'    WITH (FORMAT csv, HEADER true)
\copy landmarks FROM '../01-dataset/processed/landmarks.csv' WITH (FORMAT csv, HEADER true)

\echo '  · properties'
\copy hotels (hotel_id, source_ref, source, hotel_name, property_type, star_rating, city_id, locality, address, latitude, longitude, tagline, description, check_in_time, check_out_time, is_signature) FROM '../01-dataset/processed/hotels.csv' WITH (FORMAT csv, HEADER true)
\copy hotel_landmarks FROM '../01-dataset/processed/hotel_landmarks.csv' WITH (FORMAT csv, HEADER true)
\copy amenities       FROM '../01-dataset/processed/amenities.csv'       WITH (FORMAT csv, HEADER true)
\copy hotel_amenities FROM '../01-dataset/processed/hotel_amenities.csv' WITH (FORMAT csv, HEADER true)

\echo '  · inventory'
\copy room_types FROM '../01-dataset/processed/room_types.csv' WITH (FORMAT csv, HEADER true)
\copy rooms (hotel_id, room_number, room_type_id, floor_no) FROM '../01-dataset/processed/rooms.csv' WITH (FORMAT csv, HEADER true)
\copy seasons (season_id, season_name, start_date, end_date, multiplier, notes) FROM '../01-dataset/processed/seasons.csv' WITH (FORMAT csv, HEADER true)

\echo '  · guests'
\copy guests FROM '../01-dataset/processed/guests.csv' WITH (FORMAT csv, HEADER true)

\echo '  · bookings'
\copy bookings (booking_id, booking_ref, guest_id, hotel_id, check_in, check_out, adults, children, status, special_request, booked_at, cancelled_at) FROM '../01-dataset/processed/bookings.csv' WITH (FORMAT csv, HEADER true)

\echo '  · booking_rooms (priced night-by-night with fn_quote_stay)'
CREATE TEMP TABLE tmp_booking_rooms (booking_id integer, hotel_id integer, room_number varchar(8));
\copy tmp_booking_rooms FROM '../01-dataset/processed/booking_rooms.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO booking_rooms (booking_id, room_id, room_subtotal, room_tax)
SELECT t.booking_id, r.room_id, q.subtotal, q.tax
FROM tmp_booking_rooms t
JOIN rooms    r ON r.hotel_id = t.hotel_id AND r.room_number = t.room_number
JOIN bookings b ON b.booking_id = t.booking_id
CROSS JOIN LATERAL (
    SELECT sum(nightly_rate) AS subtotal, sum(gst_amount) AS tax
    FROM fn_quote_stay(r.room_type_id, b.check_in, b.check_out)
) q
ORDER BY t.booking_id, r.room_id;

\echo '  · payments (derived from bookings, deterministic)'
CREATE TEMP TABLE tmp_pay AS
SELECT b.booking_id, b.status, b.booked_at, b.cancelled_at, b.check_in, g.guest_id,
       lower(g.first_name) AS first_name,
       abs(hashtext(b.booking_ref))         % 100   AS h_method,
       abs(hashtext(b.booking_ref || 'f'))  % 100   AS h_fail,
       abs(hashtext(b.booking_ref || 'c'))  % 10000 AS h_card,
       (SELECT sum(room_subtotal + room_tax) FROM booking_rooms x WHERE x.booking_id = b.booking_id) AS total
FROM bookings b JOIN guests g ON g.guest_id = b.guest_id;

ALTER TABLE tmp_pay ADD COLUMN method payment_method_t;
UPDATE tmp_pay SET method = CASE WHEN h_method < 55 THEN 'UPI'
                                 WHEN h_method < 80 THEN 'CARD'
                                 WHEN h_method < 90 THEN 'NETBANKING'
                                 WHEN h_method < 95 THEN 'WALLET'
                                 ELSE 'PAY_AT_HOTEL' END::payment_method_t;

-- failed first attempts (about 4 % of online payments)
INSERT INTO payments (booking_id, kind, method, status, amount, upi_vpa, card_last4, gateway_ref, created_at)
SELECT booking_id, 'CHARGE', method, 'FAILED', total,
       CASE WHEN method = 'UPI' THEN first_name || (guest_id % 97) || '@' ||
            (ARRAY['okaxis','oksbi','okhdfcbank','ybl','paytm','ibl'])[1 + h_card % 6] END,
       CASE WHEN method = 'CARD' THEN lpad(h_card::text, 4, '0') END,
       'pay_' || substr(md5('f' || booking_id), 1, 16),
       booked_at + INTERVAL '1 minute'
FROM tmp_pay
WHERE h_fail < 4 AND method IN ('UPI', 'CARD') AND status <> 'PENDING'
ORDER BY booking_id;

-- successful (or pending pay-at-hotel) charges
INSERT INTO payments (booking_id, kind, method, status, amount, upi_vpa, card_last4, gateway_ref, created_at)
SELECT booking_id, 'CHARGE', method,
       CASE WHEN method = 'PAY_AT_HOTEL' AND status = 'CONFIRMED' THEN 'PENDING' ELSE 'SUCCESS' END::payment_status_t,
       total,
       CASE WHEN method = 'UPI' THEN first_name || (guest_id % 97) || '@' ||
            (ARRAY['okaxis','oksbi','okhdfcbank','ybl','paytm','ibl'])[1 + h_card % 6] END,
       CASE WHEN method = 'CARD' THEN lpad(h_card::text, 4, '0') END,
       'pay_' || substr(md5('c' || booking_id), 1, 16),
       CASE WHEN method = 'PAY_AT_HOTEL' THEN check_in + TIME '14:00' ELSE booked_at + INTERVAL '3 minutes' END
FROM tmp_pay
WHERE status <> 'PENDING'
  AND NOT (method = 'PAY_AT_HOTEL' AND status IN ('CANCELLED', 'NO_SHOW'))
ORDER BY booking_id;

-- refunds for cancelled, prepaid bookings (same policy as sp_cancel_booking)
INSERT INTO payments (booking_id, kind, method, status, amount, upi_vpa, gateway_ref, created_at)
SELECT booking_id, 'REFUND', method, 'SUCCESS',
       round(total * CASE WHEN check_in - (cancelled_at AT TIME ZONE 'Asia/Kolkata')::date >= 7 THEN 1.0 ELSE 0.5 END, 2),
       CASE WHEN method = 'UPI' THEN first_name || (guest_id % 97) || '@' ||
            (ARRAY['okaxis','oksbi','okhdfcbank','ybl','paytm','ibl'])[1 + h_card % 6] END,
       'rfd_' || substr(md5('r' || booking_id), 1, 16),
       cancelled_at + INTERVAL '1 hour'
FROM tmp_pay
WHERE status = 'CANCELLED' AND method <> 'PAY_AT_HOTEL'
  AND check_in - (cancelled_at AT TIME ZONE 'Asia/Kolkata')::date >= 2
ORDER BY booking_id;

\echo '  · reviews (trigger keeps hotels.avg_rating in sync)'
\copy reviews FROM '../01-dataset/processed/reviews.csv' WITH (FORMAT csv, HEADER true)

\echo '  · resetting identity sequences'
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES ('cities','city_id'), ('landmarks','landmark_id'), ('hotels','hotel_id'),
                                   ('amenities','amenity_id'), ('room_types','room_type_id'), ('rooms','room_id'),
                                   ('seasons','season_id'), ('guests','guest_id'), ('bookings','booking_id'),
                                   ('payments','payment_id'), ('reviews','review_id')) v(tbl, col)
    LOOP
        EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, %L), (SELECT max(%I) FROM %I))',
                       r.tbl, r.col, r.col, r.tbl);
    END LOOP;
END
$$;

REFRESH MATERIALIZED VIEW mv_city_performance;
ANALYZE;
