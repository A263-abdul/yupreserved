-- ════════════════════════════════════════════════════════════════════════════
--  04_subqueries_calculus.sql · Nested queries, CTEs, recursion, and the
--  relational calculi (TRC / DRC) written as SQL
-- ════════════════════════════════════════════════════════════════════════════

-- @name: sub.scalar
-- @title: Scalar subquery — room types priced above their city's average
-- @topic: SQL fundamentals › Correlated subquery
-- @algebra: σ base_price > avg_city (room_types ⋈ hotels)
-- @explain: The inner query is re-evaluated for each outer row (correlated) because it refers to h.city_id.
SELECT h.hotel_name, c.city_name, rt.type_name, rt.base_price,
       (SELECT round(avg(rt2.base_price)) FROM room_types rt2 JOIN hotels h2 USING (hotel_id)
        WHERE h2.city_id = h.city_id) AS city_avg
FROM room_types rt JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id)
WHERE c.city_name = 'Udaipur'
  AND rt.base_price > (SELECT avg(rt2.base_price) FROM room_types rt2 JOIN hotels h2 USING (hotel_id)
                       WHERE h2.city_id = h.city_id)
ORDER BY rt.base_price DESC
LIMIT 10;

-- @name: sub.any_all
-- @title: > ALL — rooms dearer than every room in Varanasi
-- @topic: SQL fundamentals › ANY / ALL
-- @algebra: σ price > max(π price (σ city='Varanasi' …))
-- @explain: x > ALL (S) is true when x beats every element of S; x > ANY (S) when it beats at least one.
SELECT h.hotel_name, rt.type_name, rt.base_price
FROM room_types rt JOIN hotels h USING (hotel_id)
WHERE rt.base_price > ALL (SELECT rt2.base_price FROM room_types rt2
                           JOIN hotels h2 USING (hotel_id) JOIN cities c2 USING (city_id)
                           WHERE c2.city_name = 'Varanasi')
ORDER BY rt.base_price
LIMIT 10;

-- @name: sub.cte
-- @title: CTE (WITH) — each city's busiest hotel
-- @topic: SQL fundamentals › Common table expressions
-- @algebra: — (named sub-expressions)
-- @explain: A CTE names an intermediate result so a long query reads top-to-bottom.
WITH per_hotel AS (
    SELECT h.city_id, h.hotel_id, h.hotel_name, count(*) AS bookings
    FROM bookings b JOIN hotels h USING (hotel_id)
    WHERE b.status = 'COMPLETED'
    GROUP BY h.hotel_id
), ranked AS (
    SELECT *, rank() OVER (PARTITION BY city_id ORDER BY bookings DESC) AS rnk FROM per_hotel
)
SELECT c.city_name, r.hotel_name, r.bookings
FROM ranked r JOIN cities c USING (city_id)
WHERE r.rnk = 1
ORDER BY r.bookings DESC
LIMIT 15;

-- @name: sub.recursive
-- @title: Recursive CTE — the full referral chain above a guest
-- @topic: SQL fundamentals › Recursive queries (transitive closure)
-- @algebra: — (transitive closure is NOT expressible in basic relational algebra)
-- @explain: Starts from one guest and repeatedly joins to the referrer until there is none. Classic recursive relationship.
WITH RECURSIVE chain AS (
    SELECT guest_id, first_name, last_name, referred_by, 0 AS depth
    FROM guests
    WHERE guest_id = (SELECT g.guest_id FROM guests g
                      JOIN guests p ON p.guest_id = g.referred_by
                      JOIN guests gp ON gp.guest_id = p.referred_by
                      WHERE gp.referred_by IS NOT NULL
                      ORDER BY g.guest_id LIMIT 1)
  UNION ALL
    SELECT g.guest_id, g.first_name, g.last_name, g.referred_by, c.depth + 1
    FROM guests g JOIN chain c ON g.guest_id = c.referred_by
)
SELECT depth, guest_id, first_name || ' ' || last_name AS guest, referred_by
FROM chain ORDER BY depth;

-- @name: calculus.trc
-- @title: Tuple relational calculus — guests who reviewed a Udaipur stay with 5★
-- @topic: Relational calculus › Tuple relational calculus
-- @algebra: { g.first_name | guests(g) ∧ ∃b ∃r ∃h ∃c (bookings(b) ∧ reviews(r) ∧ hotels(h) ∧ cities(c) ∧ b.guest_id = g.guest_id ∧ r.booking_id = b.booking_id ∧ r.rating = 5 ∧ b.hotel_id = h.hotel_id ∧ h.city_id = c.city_id ∧ c.city_name = 'Udaipur') }
-- @explain: TRC variables range over TUPLES. "∃" becomes EXISTS, "∧" becomes AND. SQL itself is based on TRC.
SELECT g.guest_id, g.first_name, g.last_name
FROM guests g
WHERE EXISTS (SELECT 1 FROM bookings b, reviews r, hotels h, cities c
              WHERE b.guest_id = g.guest_id AND r.booking_id = b.booking_id AND r.rating = 5
                AND b.hotel_id = h.hotel_id AND h.city_id = c.city_id AND c.city_name = 'Udaipur')
ORDER BY g.guest_id
LIMIT 15;

-- @name: calculus.drc
-- @title: Domain relational calculus — names and stars of Goa beach huts
-- @topic: Relational calculus › Domain relational calculus
-- @algebra: { ⟨n, s⟩ | ∃i ∃t ∃c ( hotels(i, n, t, s, c) ∧ t = 'Beach Hut' ∧ ∃cn ( cities(c, cn) ∧ cn = 'Goa' ) ) }
-- @explain: DRC variables range over attribute VALUES (domains), not whole tuples. Each variable here is a column.
SELECT n AS hotel_name, s AS star_rating
FROM (SELECT hotel_id AS i, hotel_name AS n, property_type AS t, star_rating AS s, city_id AS c FROM hotels) AS hotels_dom
WHERE t IN ('Beach Hut', 'Cottage')
  AND EXISTS (SELECT 1 FROM (SELECT city_id AS c2, city_name AS cn FROM cities) cities_dom
              WHERE cities_dom.c2 = hotels_dom.c AND cn = 'Goa')
ORDER BY n;

-- @name: sub.window
-- @title: Window functions — monthly revenue with running total and month-on-month change
-- @topic: Data mining / OLAP › Window functions
-- @algebra: — (OLAP)
-- @explain: Window functions compute across related rows without collapsing them, unlike GROUP BY.
WITH monthly AS (
    SELECT date_trunc('month', b.check_in)::date AS month, sum(br.room_subtotal) AS revenue
    FROM bookings b JOIN booking_rooms br USING (booking_id)
    WHERE b.status IN ('COMPLETED', 'CHECKED_IN')
    GROUP BY 1
)
SELECT month, revenue,
       sum(revenue) OVER (ORDER BY month)                       AS running_total,
       round(100.0 * (revenue / lag(revenue) OVER (ORDER BY month) - 1), 1) AS mom_change_pct,
       rank() OVER (ORDER BY revenue DESC)                      AS revenue_rank
FROM monthly ORDER BY month;
