-- ════════════════════════════════════════════════════════════════════════════
--  02_joins.sql · Every kind of join, each on a real question
-- ════════════════════════════════════════════════════════════════════════════

-- @name: joins.inner
-- @title: Inner (equi) join — hotels with their city and state
-- @topic: Joins › Inner / equi join
-- @algebra: π hotel_name, city_name, state_name (hotels ⋈ hotels.city_id = cities.city_id cities ⋈ cities.state_code = states.state_code states)
-- @explain: Keeps only pairs of rows whose join columns are equal. Every hotel has a city (FK, NOT NULL), so no hotel is lost.
SELECT h.hotel_name, c.city_name, s.state_name, s.region
FROM hotels h
INNER JOIN cities c ON c.city_id = h.city_id
INNER JOIN states s ON s.state_code = c.state_code
WHERE h.is_signature
ORDER BY s.region, c.city_name;

-- @name: joins.natural
-- @title: Natural join — cities and states on their common column
-- @topic: Joins › Natural join
-- @algebra: cities * states
-- @explain: NATURAL JOIN joins on every column with the same name (here state_code) and shows it once. Convenient, but fragile: adding a same-named column silently changes the join.
SELECT city_name, state_code, state_name, region
FROM cities NATURAL JOIN states
WHERE region = 'NORTHEAST'
ORDER BY state_name, city_name;

-- @name: joins.theta
-- @title: Theta (non-equi) join — which festival season each night of a stay falls in
-- @topic: Joins › Theta join
-- @algebra: nights ⋈ night ≥ start_date ∧ night ≤ end_date seasons
-- @explain: The join condition is a range (BETWEEN), not equality. This is exactly how fn_quote_stay prices a stay across Diwali.
SELECT n.night::date, to_char(n.night, 'Dy') AS day, s.season_name, s.multiplier
FROM generate_series(DATE '2026-11-04', DATE '2026-11-12', INTERVAL '1 day') AS n(night)
JOIN seasons s ON n.night BETWEEN s.start_date AND s.end_date
ORDER BY 1;

-- @name: joins.left_outer
-- @title: Left outer join — every state, even those with no hotels
-- @topic: Joins › Left outer join
-- @algebra: states ⟕ cities ⟕ hotels
-- @explain: Keeps every row of the left table. States with no listed hotels (Lakshadweep, Manipur…) appear with 0 — an inner join would drop them.
SELECT s.state_name, s.region, count(h.hotel_id) AS hotels
FROM states s
LEFT JOIN cities c ON c.state_code = s.state_code
LEFT JOIN hotels h ON h.city_id = c.city_id
GROUP BY s.state_code
ORDER BY hotels, s.state_name;

-- @name: joins.right_outer
-- @title: Right outer join — every amenity, with how many hotels offer it
-- @topic: Joins › Right outer join
-- @algebra: hotel_amenities ⟖ amenities
-- @explain: Mirror image of the left join. Amenities nobody offers yet still appear, with 0.
SELECT a.category, a.amenity_name, count(ha.hotel_id) AS hotels
FROM hotel_amenities ha
RIGHT JOIN amenities a ON a.amenity_id = ha.amenity_id
GROUP BY a.amenity_id
ORDER BY hotels, a.amenity_name;

-- @name: joins.full_outer
-- @title: Full outer join — cities where guests live vs. cities with bookings
-- @topic: Joins › Full outer join
-- @algebra: home_cities ⟗ booked_cities
-- @explain: Keeps unmatched rows from BOTH sides: cities that only send travellers, cities that only receive them, and those that do both. (MySQL has no FULL OUTER JOIN — one reason we chose PostgreSQL.)
WITH home AS (
    SELECT home_city_id AS city_id, count(*) AS guests_living_here
    FROM guests GROUP BY home_city_id
), visited AS (
    SELECT h.city_id, count(*) AS bookings_received
    FROM bookings b JOIN hotels h ON h.hotel_id = b.hotel_id
    GROUP BY h.city_id
)
SELECT c.city_name,
       coalesce(home.guests_living_here, 0) AS guests_living_here,
       coalesce(visited.bookings_received, 0) AS bookings_received,
       CASE WHEN home.city_id IS NULL THEN 'only receives'
            WHEN visited.city_id IS NULL THEN 'only sends'
            ELSE 'both' END AS role
FROM home
FULL OUTER JOIN visited ON visited.city_id = home.city_id
JOIN cities c ON c.city_id = coalesce(home.city_id, visited.city_id)
ORDER BY bookings_received DESC, guests_living_here DESC
LIMIT 20;

-- @name: joins.self
-- @title: Self join — who referred whom
-- @topic: Joins › Self join (recursive relationship)
-- @algebra: ρ g(guests) ⋈ g.referred_by = r.guest_id ρ r(guests)
-- @explain: The same table appears twice under two aliases. guests.referred_by is a foreign key to guests itself.
SELECT g.guest_id, g.first_name || ' ' || g.last_name AS guest,
       r.guest_id AS referrer_id, r.first_name || ' ' || r.last_name AS referred_by
FROM guests g
JOIN guests r ON r.guest_id = g.referred_by
ORDER BY g.guest_id
LIMIT 15;

-- @name: joins.cross
-- @title: Cross join (Cartesian product) — a price calendar
-- @topic: Joins › Cross join
-- @algebra: room_types × nights
-- @explain: Pairs every row with every row (|R| × |S| rows). Useful when you really want all combinations: here every room type of Samudra Mahal × every night of Christmas week.
SELECT rt.type_name, n.night::date,
       round(rt.base_price * coalesce(s.multiplier, 1)) AS rate_before_weekend
FROM room_types rt
CROSS JOIN generate_series(DATE '2026-12-21', DATE '2026-12-27', INTERVAL '1 day') AS n(night)
LEFT JOIN seasons s ON n.night BETWEEN s.start_date AND s.end_date
WHERE rt.hotel_id = 1
ORDER BY rt.base_price, n.night;

-- @name: joins.semi
-- @title: Semi-join (EXISTS) — hotels that have at least one 5★ review
-- @topic: Joins › Semi-join
-- @algebra: hotels ⋉ (bookings ⋈ σ rating = 5 (reviews))
-- @explain: Returns rows of the left table that HAVE a match, without duplicating them per match — unlike a plain join.
SELECT h.hotel_name, h.avg_rating, h.review_count
FROM hotels h
WHERE EXISTS (SELECT 1 FROM bookings b JOIN reviews r ON r.booking_id = b.booking_id
              WHERE b.hotel_id = h.hotel_id AND r.rating = 5)
ORDER BY h.review_count DESC
LIMIT 10;

-- @name: joins.anti
-- @title: Anti-join (NOT EXISTS) — hotels that have never been booked
-- @topic: Joins › Anti-join
-- @algebra: hotels ▷ bookings   (= hotels − (hotels ⋉ bookings))
-- @explain: Rows of the left table with NO match. NOT EXISTS is NULL-safe; NOT IN (subquery) is not (one NULL makes it return nothing).
SELECT c.city_name, count(*) AS never_booked_hotels
FROM hotels h JOIN cities c ON c.city_id = h.city_id
WHERE NOT EXISTS (SELECT 1 FROM bookings b WHERE b.hotel_id = h.hotel_id)
GROUP BY c.city_name
ORDER BY never_booked_hotels DESC
LIMIT 10;

-- @name: joins.lateral
-- @title: LATERAL join — the 2 cheapest room types of each signature hotel
-- @topic: Joins › Lateral (dependent) join
-- @algebra: — (top-N per group; no single classical operator)
-- @explain: The subquery on the right can refer to the current row on the left, like a for-each loop.
SELECT h.hotel_name, cheapest.type_name, cheapest.base_price
FROM hotels h
CROSS JOIN LATERAL (
    SELECT rt.type_name, rt.base_price FROM room_types rt
    WHERE rt.hotel_id = h.hotel_id ORDER BY rt.base_price LIMIT 2
) AS cheapest
WHERE h.is_signature
ORDER BY h.hotel_id, cheapest.base_price;

-- @name: joins.multiway
-- @title: Six-table join — a full booking receipt
-- @topic: Joins › Multi-way join
-- @algebra: bookings ⋈ guests ⋈ hotels ⋈ booking_rooms ⋈ rooms ⋈ room_types
-- @explain: Follows the foreign keys from a booking to everything it touches. This is what the 'My trips' page needs.
SELECT b.booking_ref, g.first_name || ' ' || g.last_name AS guest, h.hotel_name,
       r.room_number, rt.type_name, b.check_in, b.check_out, b.nights,
       br.room_subtotal, br.room_tax, b.status
FROM bookings b
JOIN guests g        ON g.guest_id = b.guest_id
JOIN hotels h        ON h.hotel_id = b.hotel_id
JOIN booking_rooms br ON br.booking_id = b.booking_id
JOIN rooms r         ON r.room_id = br.room_id
JOIN room_types rt   ON rt.room_type_id = r.room_type_id
WHERE b.hotel_id = 1 AND b.check_in >= DATE '2026-12-01'
ORDER BY b.check_in, r.room_number
LIMIT 15;
