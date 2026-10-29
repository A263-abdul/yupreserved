-- ════════════════════════════════════════════════════════════════════════════
--  06_views.sql  ·  Views and a materialized view
--  Syllabus: Relational model › Views · Database abstraction (external level)
--
--  A view stores a query, not data. Each one below is an "external schema":
--  the frontend, the analyst and the front desk each see the shape of data
--  they need, without knowing how the 15 tables are joined underneath.
-- ════════════════════════════════════════════════════════════════════════════

-- One representative photo per hotel. Listings carry no photos, so we show the
-- nearest photographed landmark (≤ 4 km); otherwise one of the city's photos
-- (the city itself or any photographed landmark in it), chosen by hotel_id so
-- neighbouring cards differ. Always credited, always captioned with the place.
CREATE VIEW v_hotel_photo AS
SELECT h.hotel_id,
       coalesce(near.photo_url, pick.photo_url)         AS photo_url,
       coalesce(near.photo_url_hd, pick.photo_url_hd)   AS photo_url_hd,
       coalesce(near.photo_credit, pick.photo_credit)   AS photo_credit,
       coalesce(near.caption, pick.caption)             AS photo_caption
FROM hotels h
LEFT JOIN LATERAL (
    SELECT l.landmark_name AS caption, l.photo_url, l.photo_url_hd, l.photo_credit
    FROM hotel_landmarks hl JOIN landmarks l ON l.landmark_id = hl.landmark_id
    WHERE hl.hotel_id = h.hotel_id AND l.photo_url IS NOT NULL AND hl.distance_km <= 4
    ORDER BY hl.distance_km
    LIMIT 1
) near ON true
LEFT JOIN LATERAL (
    SELECT x.caption, x.photo_url, x.photo_url_hd, x.photo_credit
    FROM (SELECT c.city_name AS caption, c.photo_url, c.photo_url_hd, c.photo_credit, 0 AS ord
          FROM cities c WHERE c.city_id = h.city_id AND c.photo_url IS NOT NULL
          UNION ALL
          SELECT l.landmark_name, l.photo_url, l.photo_url_hd, l.photo_credit, l.landmark_id
          FROM landmarks l WHERE l.city_id = h.city_id AND l.photo_url IS NOT NULL) x
    ORDER BY x.ord
    OFFSET (h.hotel_id % greatest(1, (SELECT count(*) FROM landmarks l2 WHERE l2.city_id = h.city_id AND l2.photo_url IS NOT NULL)
                                     + (SELECT count(*) FROM cities c2 WHERE c2.city_id = h.city_id AND c2.photo_url IS NOT NULL)))
    LIMIT 1
) pick ON true;


-- Hotel cards for search results (one row per hotel)
CREATE VIEW v_hotel_cards AS
SELECT h.hotel_id,
       h.hotel_name,
       h.property_type,
       h.star_rating,
       h.is_signature,
       h.tagline,
       h.locality,
       c.city_id,
       c.city_name,
       s.state_code,
       s.state_name,
       s.region,
       h.latitude,
       h.longitude,
       h.avg_rating,
       h.review_count,
       p.from_price,
       p.room_types,
       ph.photo_url,
       ph.photo_credit,
       ph.photo_caption
FROM hotels h
JOIN cities c ON c.city_id = h.city_id
JOIN states s ON s.state_code = c.state_code
JOIN v_hotel_photo ph ON ph.hotel_id = h.hotel_id
LEFT JOIN LATERAL (
    SELECT min(rt.base_price) AS from_price, count(*) AS room_types
    FROM room_types rt WHERE rt.hotel_id = h.hotel_id
) p ON true;


-- One row per booking with money totals (what the front desk sees)
CREATE VIEW v_booking_summary AS
SELECT b.booking_id,
       b.booking_ref,
       b.status,
       g.guest_id,
       g.first_name || ' ' || g.last_name                       AS guest_name,
       h.hotel_id,
       h.hotel_name,
       c.city_name,
       b.check_in,
       b.check_out,
       b.nights,
       b.adults,
       b.children,
       br.rooms,
       br.subtotal,
       br.tax,
       br.subtotal + br.tax                                      AS total,
       coalesce(pm.paid, 0)                                      AS paid,
       coalesce(pm.refunded, 0)                                  AS refunded,
       b.booked_at
FROM bookings b
JOIN guests g ON g.guest_id = b.guest_id
JOIN hotels h ON h.hotel_id = b.hotel_id
JOIN cities c ON c.city_id = h.city_id
JOIN LATERAL (
    SELECT count(*) AS rooms, sum(room_subtotal) AS subtotal, sum(room_tax) AS tax
    FROM booking_rooms x WHERE x.booking_id = b.booking_id
) br ON true
LEFT JOIN LATERAL (
    SELECT sum(amount) FILTER (WHERE kind = 'CHARGE') AS paid,
           sum(amount) FILTER (WHERE kind = 'REFUND') AS refunded
    FROM payments p WHERE p.booking_id = b.booking_id AND p.status = 'SUCCESS'
) pm ON true;


-- Security view: guest directory with personal data masked.
-- The analyst role can read this view but NOT the guests table (see 07_roles.sql).
CREATE VIEW v_guest_directory AS
SELECT g.guest_id,
       g.first_name,
       left(g.last_name, 1) || '.'                               AS last_initial,
       left(g.phone, 2) || 'XXXXXX' || right(g.phone, 2)          AS phone_masked,
       left(g.email, 2) || '***@' || split_part(g.email, '@', 2)  AS email_masked,
       date_part('year', age(g.date_of_birth))::int               AS age,
       c.city_name                                               AS home_city,
       g.created_at::date                                        AS member_since
FROM guests g
LEFT JOIN cities c ON c.city_id = g.home_city_id;


-- Updatable view WITH CHECK OPTION: the front desk may edit upcoming arrivals,
-- but cannot push a row out of the view (e.g. set its status to COMPLETED).
CREATE VIEW v_upcoming_arrivals AS
SELECT booking_id, booking_ref, guest_id, hotel_id, check_in, check_out,
       adults, children, status, special_request
FROM bookings
WHERE status IN ('PENDING', 'CONFIRMED')
  AND check_in >= DATE '2026-10-29'
WITH CHECK OPTION;


-- Materialized view: stores its result. Refresh with
--   REFRESH MATERIALIZED VIEW mv_city_performance;
CREATE MATERIALIZED VIEW mv_city_performance AS
SELECT c.city_id,
       c.city_name,
       c.state_code,
       count(DISTINCT h.hotel_id)                                         AS hotels,
       count(DISTINCT b.booking_id)                                       AS bookings,
       coalesce(sum(b.nights * br.rooms), 0)                              AS room_nights,
       coalesce(sum(br.subtotal), 0)                                      AS room_revenue,
       round(coalesce(sum(br.subtotal) / nullif(sum(b.nights * br.rooms), 0), 0), 0) AS avg_daily_rate,
       round(avg(h.avg_rating), 2)                                        AS avg_hotel_rating
FROM cities c
JOIN hotels h ON h.city_id = c.city_id
LEFT JOIN bookings b ON b.hotel_id = h.hotel_id AND b.status IN ('COMPLETED', 'CHECKED_IN')
LEFT JOIN LATERAL (
    SELECT count(*) AS rooms, sum(room_subtotal) AS subtotal
    FROM booking_rooms x WHERE x.booking_id = b.booking_id
) br ON true
GROUP BY c.city_id
WITH NO DATA;

CREATE UNIQUE INDEX ux_mv_city_performance ON mv_city_performance (city_id);
