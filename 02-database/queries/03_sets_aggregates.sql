-- ════════════════════════════════════════════════════════════════════════════
--  03_sets_aggregates.sql · Set operations, grouping, and relational division
-- ════════════════════════════════════════════════════════════════════════════

-- @name: sets.union
-- @title: UNION — every place name a guest can type into search
-- @topic: Relational algebra › Union
-- @algebra: π name (cities) ∪ π name (landmarks)
-- @explain: Both inputs must be union-compatible (same number and types of columns). UNION removes duplicates; UNION ALL keeps them and is faster.
SELECT city_name AS place, 'city' AS kind FROM cities WHERE city_name ILIKE 'ma%'
UNION
SELECT landmark_name, 'landmark' FROM landmarks WHERE landmark_name ILIKE 'ma%'
ORDER BY place;

-- @name: sets.intersect
-- @title: INTERSECT — guests who stayed in both Goa and Mumbai
-- @topic: Relational algebra › Intersection
-- @algebra: π guest_id (σ city='Goa' (…)) ∩ π guest_id (σ city='Mumbai' (…))
-- @explain: Rows present in both results. (MySQL only added INTERSECT in 8.0.31.)
SELECT b.guest_id FROM bookings b JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id)
WHERE c.city_name = 'Goa' AND b.status = 'COMPLETED'
INTERSECT
SELECT b.guest_id FROM bookings b JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id)
WHERE c.city_name = 'Mumbai' AND b.status = 'COMPLETED'
ORDER BY guest_id
LIMIT 20;

-- @name: sets.except
-- @title: EXCEPT (set difference) — signature hotels with no pool
-- @topic: Relational algebra › Set difference
-- @algebra: π hotel_id (σ is_signature (hotels)) − π hotel_id (hotel_amenities ⋈ σ name='Swimming Pool' (amenities))
-- @explain: Rows in the first result that are not in the second.
SELECT h.hotel_id, h.hotel_name FROM hotels h WHERE h.is_signature
EXCEPT
SELECT ha.hotel_id, h.hotel_name FROM hotel_amenities ha
JOIN amenities a USING (amenity_id) JOIN hotels h USING (hotel_id)
WHERE a.amenity_name = 'Swimming Pool'
ORDER BY hotel_id;

-- @name: agg.group_having
-- @title: GROUP BY + HAVING — cities with more than 50 hotels
-- @topic: Additional operations › Aggregation (𝒢)
-- @algebra: σ hotels > 50 ( city_name 𝒢 count(hotel_id) → hotels, avg(star_rating) (hotels ⋈ cities) )
-- @explain: WHERE filters rows before grouping; HAVING filters groups after.
SELECT c.city_name, count(*) AS hotels, round(avg(h.star_rating), 2) AS avg_stars,
       min(v.from_price) AS cheapest_from
FROM hotels h JOIN cities c USING (city_id) JOIN v_hotel_cards v USING (hotel_id)
GROUP BY c.city_name
HAVING count(*) > 50
ORDER BY hotels DESC;

-- @name: agg.rollup
-- @title: ROLLUP — revenue by region → state, with subtotals and grand total
-- @topic: Data mining / OLAP › ROLLUP
-- @algebra: — (OLAP extension of 𝒢)
-- @explain: ROLLUP(a, b) = GROUP BY (a,b) ∪ (a) ∪ (). NULL in the output marks a subtotal row.
SELECT coalesce(s.region::text, '— ALL REGIONS —') AS region,
       coalesce(s.state_name, '— subtotal —')      AS state,
       count(DISTINCT b.booking_id)                AS bookings,
       sum(br.room_subtotal)                       AS room_revenue
FROM bookings b
JOIN booking_rooms br USING (booking_id)
JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id) JOIN states s USING (state_code)
WHERE b.status = 'COMPLETED'
GROUP BY ROLLUP (s.region, s.state_name)
ORDER BY s.region NULLS LAST, room_revenue DESC NULLS FIRST;

-- @name: agg.cube
-- @title: CUBE — bookings by status × payment method
-- @topic: Data mining / OLAP › CUBE
-- @algebra: — (OLAP extension of 𝒢)
-- @explain: CUBE(a, b) produces every combination of subtotals: (a,b), (a), (b) and ().
SELECT coalesce(b.status::text, 'ALL') AS status,
       coalesce(p.method::text, 'ALL') AS method,
       count(*) AS payments
FROM payments p JOIN bookings b USING (booking_id)
WHERE p.kind = 'CHARGE' AND p.status = 'SUCCESS'
GROUP BY CUBE (b.status, p.method)
ORDER BY b.status NULLS LAST, p.method NULLS LAST;

-- @name: agg.filter
-- @title: Conditional aggregates — how guests pay
-- @topic: SQL fundamentals › Aggregates with FILTER
-- @algebra: 𝒢 count(*) … (payments)
-- @explain: FILTER (WHERE …) computes several conditional counts in one pass — UPI is the first-class payment method.
SELECT count(*) FILTER (WHERE method = 'UPI')          AS upi,
       count(*) FILTER (WHERE method = 'CARD')         AS card,
       count(*) FILTER (WHERE method = 'NETBANKING')   AS netbanking,
       count(*) FILTER (WHERE method = 'WALLET')       AS wallet,
       count(*) FILTER (WHERE method = 'PAY_AT_HOTEL') AS pay_at_hotel,
       round(100.0 * count(*) FILTER (WHERE method = 'UPI') / count(*), 1) AS upi_share_pct
FROM payments WHERE kind = 'CHARGE' AND status = 'SUCCESS';

-- @name: division.not_exists
-- @title: Division (÷) — hotels that have ALL of Pool, Spa and Free Wi-Fi (double NOT EXISTS)
-- @topic: Relational algebra › Division · Tuple relational calculus
-- @algebra: π hotel_id, amenity_id (hotel_amenities) ÷ π amenity_id (σ name ∈ {Pool, Spa, Wi-Fi} (amenities))
-- @explain: "Hotels for which there is NO required amenity that they do NOT have." This is the SQL form of the TRC formula {h | ∀a (a ∈ Req → ∃ha (ha.hotel=h ∧ ha.amenity=a))}.
SELECT h.hotel_id, h.hotel_name, c.city_name
FROM hotels h JOIN cities c USING (city_id)
WHERE NOT EXISTS (
    SELECT 1 FROM amenities a
    WHERE a.amenity_name IN ('Swimming Pool', 'Spa', 'Free Wi-Fi')
      AND NOT EXISTS (SELECT 1 FROM hotel_amenities ha
                      WHERE ha.hotel_id = h.hotel_id AND ha.amenity_id = a.amenity_id))
ORDER BY c.city_name, h.hotel_name;

-- @name: division.count
-- @title: Division (÷) — the same answer with GROUP BY / HAVING COUNT
-- @topic: Relational algebra › Division
-- @algebra: same as division.not_exists
-- @explain: Keep each hotel's rows for the required amenities and accept it only if it matched all 3. Usually faster than double NOT EXISTS.
SELECT h.hotel_id, h.hotel_name, c.city_name
FROM hotel_amenities ha
JOIN amenities a USING (amenity_id)
JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id)
WHERE a.amenity_name IN ('Swimming Pool', 'Spa', 'Free Wi-Fi')
GROUP BY h.hotel_id, h.hotel_name, c.city_name
HAVING count(DISTINCT a.amenity_id) = 3
ORDER BY c.city_name, h.hotel_name;
