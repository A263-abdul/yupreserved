-- ════════════════════════════════════════════════════════════════════════════
--  05_retrieval.sql · The questions a real hotel platform answers every second
-- ════════════════════════════════════════════════════════════════════════════

-- @name: app.quote_two_nights
-- @title: Price for two nights — Samudra Mahal Harbour Room, 24 → 26 Dec 2026
-- @topic: Retrieval › Stored function
-- @algebra: room_types × nights ⟕ seasons  (inside fn_quote_stay)
-- @explain: Night-by-night breakdown: base price × festival multiplier × weekend multiplier, then GST slab per night.
SELECT * FROM fn_quote_stay(1, DATE '2026-12-24', DATE '2026-12-26');

-- @name: app.quote_compare_dates
-- @title: Same room, three different weekends — why prices differ
-- @topic: Retrieval › Function in a join
-- @algebra: dates ⋈ fn_stay_total(…)
-- @explain: The same 2-night stay costs more in Diwali and Christmas week (season multiplier) than in the monsoon.
SELECT d.label, d.check_in, d.check_in + 2 AS check_out,
       fn_stay_total(1, d.check_in, d.check_in + 2) AS total_incl_gst
FROM (VALUES ('Monsoon weekend', DATE '2026-08-14'),
             ('Ordinary weekend', DATE '2026-11-20'),
             ('Diwali weekend',   DATE '2026-11-06'),
             ('Christmas',        DATE '2026-12-25')) AS d(label, check_in)
ORDER BY total_incl_gst;

-- @name: app.availability
-- @title: Availability — free rooms per type at Pichola Rajbagh for Diwali
-- @topic: Retrieval › Availability (anti-join on date overlap)
-- @algebra: rooms ▷ (booking_rooms ⋈ σ overlaps(stay) ∧ status ≠ CANCELLED (bookings))
-- @explain: A room is free if no live booking overlaps the requested half-open range [check_in, check_out).
SELECT * FROM fn_available_rooms(3, DATE '2026-11-07', DATE '2026-11-09');

-- @name: app.near_landmark
-- @title: "Near Gateway of India" — hotels within 3 km, nearest first
-- @topic: Retrieval › Landmark search
-- @algebra: π … (σ landmark_name ILIKE … ∧ distance_km ≤ 3 (landmarks ⋈ hotel_landmarks ⋈ hotels))
-- @explain: The M:N table hotel_landmarks carries the distance, an attribute of the relationship itself.
SELECT h.hotel_name, h.star_rating, hl.distance_km, v.from_price
FROM landmarks l
JOIN hotel_landmarks hl USING (landmark_id)
JOIN hotels h USING (hotel_id)
JOIN v_hotel_cards v USING (hotel_id)
WHERE l.landmark_name ILIKE '%gateway of india%' AND hl.distance_km <= 3
ORDER BY hl.distance_km
LIMIT 15;

-- @name: app.mood_search
-- @title: Mood search — "quiet hill stay" with full-text ranking
-- @topic: Unit 5 › Digital libraries / information retrieval
-- @algebra: — (ranked retrieval)
-- @explain: to_tsquery matches word stems (hills → hill) through the GIN index; ts_rank orders by relevance like a search engine.
SELECT h.hotel_name, c.city_name, h.property_type,
       round(ts_rank(h.search_doc, q)::numeric, 3) AS relevance
FROM hotels h JOIN cities c USING (city_id),
     websearch_to_tsquery('english', 'quiet hill stay') AS q
WHERE h.search_doc @@ q
ORDER BY relevance DESC, h.avg_rating DESC NULLS LAST
LIMIT 12;

-- @name: app.fuzzy_name
-- @title: Typo-tolerant search — "samudra mahl"
-- @topic: Query processing › Trigram index
-- @algebra: σ similarity(hotel_name, 'samudra mahl') > 0.3 (hotels)
-- @explain: pg_trgm splits strings into 3-letter pieces; the GIN trigram index finds close matches even with typos.
SELECT hotel_name, round(similarity(hotel_name, 'samudra mahl')::numeric, 2) AS similarity
FROM hotels
WHERE hotel_name % 'samudra mahl'
ORDER BY similarity DESC
LIMIT 5;

-- @name: app.guest_trips
-- @title: My trips — every booking of one guest with money totals
-- @topic: Retrieval › View
-- @algebra: σ guest_id = 6511 (v_booking_summary)
-- @explain: The view hides a 6-table join plus payment aggregation behind one simple SELECT.
SELECT booking_ref, hotel_name, city_name, check_in, nights, rooms, total, paid, refunded, status
FROM v_booking_summary
WHERE guest_id = (SELECT guest_id FROM bookings GROUP BY guest_id ORDER BY count(*) DESC LIMIT 1)
ORDER BY check_in DESC
LIMIT 15;

-- @name: app.occupancy
-- @title: Occupancy of signature hotels on Diwali night (8 Nov 2026)
-- @topic: Retrieval › Aggregation over date ranges
-- @algebra: hotels 𝒢 count(rooms booked) / count(rooms)
-- @explain: Rooms in use on a night = live bookings whose range contains that night.
SELECT h.hotel_name,
       count(DISTINCT r.room_id) AS rooms,
       count(DISTINCT br.room_id) AS occupied,
       round(100.0 * count(DISTINCT br.room_id) / count(DISTINCT r.room_id), 1) AS occupancy_pct
FROM hotels h
JOIN rooms r ON r.hotel_id = h.hotel_id
LEFT JOIN booking_rooms br ON br.room_id = r.room_id
     AND EXISTS (SELECT 1 FROM bookings b WHERE b.booking_id = br.booking_id
                 AND b.status <> 'CANCELLED'
                 AND DATE '2026-11-08' >= b.check_in AND DATE '2026-11-08' < b.check_out)
WHERE h.is_signature
GROUP BY h.hotel_id
ORDER BY occupancy_pct DESC;

-- @name: app.top_cities
-- @title: Top 10 cities by room revenue (materialized view)
-- @topic: Views › Materialized view
-- @algebra: π … (mv_city_performance)
-- @explain: Reads precomputed results — instant, but only as fresh as the last REFRESH MATERIALIZED VIEW.
SELECT city_name, state_code, hotels, bookings, room_nights, room_revenue, avg_daily_rate
FROM mv_city_performance
ORDER BY room_revenue DESC
LIMIT 10;

-- @name: mining.amenity_rules
-- @title: Association rules — "hotels with a Spa usually also have …"
-- @topic: Unit 5 › Data mining (support & confidence)
-- @algebra: — (market-basket analysis)
-- @explain: support = P(A ∧ B); confidence = P(B | A). Computed by a self-join of hotel_amenities on hotel_id.
WITH n AS (SELECT count(DISTINCT hotel_id)::numeric AS hotels FROM hotel_amenities),
pairs AS (
    SELECT a.amenity_id AS a_id, b.amenity_id AS b_id, count(*) AS both_count
    FROM hotel_amenities a JOIN hotel_amenities b ON a.hotel_id = b.hotel_id AND a.amenity_id <> b.amenity_id
    GROUP BY 1, 2
), single AS (
    SELECT amenity_id, count(*) AS cnt FROM hotel_amenities GROUP BY amenity_id
)
SELECT am_a.amenity_name AS if_hotel_has, am_b.amenity_name AS then_also_has,
       round(p.both_count / n.hotels, 3) AS support,
       round(p.both_count::numeric / s.cnt, 3) AS confidence
FROM pairs p
JOIN single s ON s.amenity_id = p.a_id
JOIN amenities am_a ON am_a.amenity_id = p.a_id
JOIN amenities am_b ON am_b.amenity_id = p.b_id
CROSS JOIN n
WHERE am_a.amenity_name = 'Spa' AND s.cnt >= 20
ORDER BY confidence DESC
LIMIT 10;

-- @name: mining.city_pairs
-- @title: Travel patterns — which two cities are most often visited by the same guest
-- @topic: Unit 5 › Data mining (co-occurrence)
-- @algebra: ρ x(trips) ⋈ x.guest = y.guest ∧ x.city < y.city ρ y(trips)
-- @explain: A self-join on guest_id finds every pair of cities one guest has stayed in.
WITH trips AS (
    SELECT DISTINCT b.guest_id, c.city_name
    FROM bookings b JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id)
    WHERE b.status = 'COMPLETED'
)
SELECT x.city_name AS city_a, y.city_name AS city_b, count(*) AS shared_guests
FROM trips x JOIN trips y ON x.guest_id = y.guest_id AND x.city_name < y.city_name
GROUP BY 1, 2
ORDER BY shared_guests DESC
LIMIT 10;
