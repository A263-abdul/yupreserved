-- ════════════════════════════════════════════════════════════════════════════
--  01_basics.sql · SELECT, PROJECT and the fundamental relational operations
--  Each block below is one named query (used by the CLI `yup q <name>`,
--  the API /api/lab/queries and the frontend "Under the hood" page).
-- ════════════════════════════════════════════════════════════════════════════

-- @name: basics.selection
-- @title: Selection (σ) — 5-star hotels in Rajasthan
-- @topic: Relational algebra › Selection
-- @algebra: σ star_rating = 5 ∧ state_code = 'RJ' (hotels ⋈ cities)
-- @explain: σ keeps the rows that satisfy a predicate. WHERE is the SQL form of σ.
SELECT h.hotel_id, h.hotel_name, c.city_name, h.star_rating
FROM hotels h JOIN cities c ON c.city_id = h.city_id
WHERE h.star_rating = 5 AND c.state_code = 'RJ'
ORDER BY c.city_name, h.hotel_name;

-- @name: basics.projection
-- @title: Projection (π) — the distinct property types on the platform
-- @topic: Relational algebra › Projection
-- @algebra: π property_type (hotels)
-- @explain: π keeps chosen columns. Relational algebra works on sets, so duplicates disappear — SQL needs DISTINCT for that.
SELECT DISTINCT property_type
FROM hotels
ORDER BY property_type;

-- @name: basics.rename
-- @title: Rename (ρ) — guests as 'travellers' with computed age
-- @topic: Relational algebra › Rename
-- @algebra: ρ traveller(name, age) (π first_name, age(date_of_birth) (guests))
-- @explain: ρ renames a relation or its attributes; SQL uses AS. Age is a derived attribute — computed, never stored.
SELECT g.first_name || ' ' || g.last_name AS traveller_name,
       date_part('year', age(g.date_of_birth))::int AS age_years
FROM guests AS g
ORDER BY g.guest_id
LIMIT 10;

-- @name: basics.predicates
-- @title: BETWEEN, IN, LIKE, IS NULL — budget hill stays without a tagline
-- @topic: SQL fundamentals › Predicates
-- @algebra: σ base_price BETWEEN 1500 AND 3000 ∧ city ∈ {…} (…)
-- @explain: Combines range (BETWEEN), set membership (IN), pattern (ILIKE) and NULL tests. NULL is "unknown", so it needs IS NULL, never = NULL.
SELECT h.hotel_name, c.city_name, rt.type_name, rt.base_price
FROM hotels h
JOIN cities c      ON c.city_id = h.city_id
JOIN room_types rt ON rt.hotel_id = h.hotel_id
WHERE c.city_name IN ('Shimla', 'Manali', 'Munnar', 'Ooty', 'Darjeeling')
  AND rt.base_price BETWEEN 1500 AND 3000
  AND rt.type_name ILIKE '%deluxe%'
  AND h.tagline IS NULL
ORDER BY rt.base_price
LIMIT 15;

-- @name: basics.case
-- @title: CASE — classify hotels into price bands
-- @topic: SQL fundamentals › Conditional expressions
-- @algebra: π hotel_name, band(from_price) (v_hotel_cards)
-- @explain: CASE turns a numeric value into a category, the way the frontend shows "Budget / Mid-range / Luxury" chips.
SELECT CASE WHEN from_price < 2000  THEN '1 · Budget'
            WHEN from_price < 6000  THEN '2 · Mid-range'
            WHEN from_price < 15000 THEN '3 · Upscale'
            ELSE '4 · Luxury' END AS price_band,
       count(*) AS hotels,
       round(avg(from_price)) AS avg_from_price
FROM v_hotel_cards
GROUP BY 1
ORDER BY 1;

-- @name: basics.counts
-- @title: Row count of every core table
-- @topic: Catalog › Table sizes
-- @algebra: — (catalog query)
-- @explain: Exact COUNT(*) of all 15 tables, the way the project report's first output does.
SELECT 'states' AS table_name, count(*) AS rows FROM states UNION ALL
SELECT 'cities', count(*) FROM cities UNION ALL
SELECT 'landmarks', count(*) FROM landmarks UNION ALL
SELECT 'hotels', count(*) FROM hotels UNION ALL
SELECT 'hotel_landmarks', count(*) FROM hotel_landmarks UNION ALL
SELECT 'amenities', count(*) FROM amenities UNION ALL
SELECT 'hotel_amenities', count(*) FROM hotel_amenities UNION ALL
SELECT 'room_types', count(*) FROM room_types UNION ALL
SELECT 'rooms', count(*) FROM rooms UNION ALL
SELECT 'seasons', count(*) FROM seasons UNION ALL
SELECT 'guests', count(*) FROM guests UNION ALL
SELECT 'bookings', count(*) FROM bookings UNION ALL
SELECT 'booking_rooms', count(*) FROM booking_rooms UNION ALL
SELECT 'payments', count(*) FROM payments UNION ALL
SELECT 'reviews', count(*) FROM reviews;
