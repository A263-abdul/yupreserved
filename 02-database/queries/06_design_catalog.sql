-- ════════════════════════════════════════════════════════════════════════════
--  06_design_catalog.sql · Proving the design: catalog, keys, FDs, normal forms
-- ════════════════════════════════════════════════════════════════════════════

-- @name: catalog.tables
-- @title: The catalog — all tables, views and their sizes
-- @topic: Relational model › The catalog (data dictionary)
-- @algebra: — (system catalog)
-- @explain: The DBMS describes itself in tables too (information_schema / pg_catalog): metadata is data.
SELECT c.relname AS name,
       CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized view' END AS kind,
       c.reltuples::bigint AS approx_rows,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm')
ORDER BY c.relkind, pg_total_relation_size(c.oid) DESC;

-- @name: catalog.primary_keys
-- @title: Primary keys of all 15 tables
-- @topic: Keys › Primary key
-- @algebra: — (catalog)
-- @explain: 11 single-column surrogate/natural keys and 4 composite keys (on the M:N relationship tables).
SELECT con.conrelid::regclass::text AS table_name, con.conname AS constraint_name,
       string_agg(a.attname, ', ' ORDER BY k.ord) AS key_columns,
       CASE WHEN count(*) > 1 THEN 'composite' ELSE 'single' END AS kind
FROM pg_constraint con
JOIN pg_namespace n ON n.oid = con.connamespace
CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
WHERE con.contype = 'p' AND n.nspname = 'public'
GROUP BY con.conrelid, con.conname
ORDER BY kind DESC, table_name;

-- @name: catalog.foreign_keys
-- @title: Foreign keys — child → parent, with ON DELETE rule
-- @topic: Keys › Foreign key · Referential integrity
-- @algebra: — (catalog)
-- @explain: Every arrow of the ER diagram is one row here. ON DELETE says what happens to children when a parent row is deleted.
SELECT con.conrelid::regclass AS child_table,
       pg_get_constraintdef(con.oid) AS definition,
       con.conname AS constraint_name,
       CASE con.confdeltype WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT' END AS on_delete
FROM pg_constraint con
JOIN pg_namespace n ON n.oid = con.connamespace
WHERE con.contype = 'f' AND n.nspname = 'public'
ORDER BY 1, 3;

-- @name: catalog.candidate_keys
-- @title: Alternate (candidate) keys — every UNIQUE constraint
-- @topic: Keys › Candidate / alternate key
-- @algebra: — (catalog)
-- @explain: A candidate key that was not chosen as the primary key is an alternate key, enforced with UNIQUE.
SELECT con.conrelid::regclass AS table_name, con.conname AS constraint_name,
       pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con JOIN pg_namespace n ON n.oid = con.connamespace
WHERE con.contype = 'u' AND n.nspname = 'public'
ORDER BY 1, 2;

-- @name: catalog.checks
-- @title: CHECK and EXCLUDE constraints
-- @topic: Integrity › Domain & tuple constraints
-- @algebra: — (catalog)
-- @explain: Rules the database enforces on every INSERT / UPDATE, whatever program sends it.
SELECT con.conrelid::regclass AS table_name, con.conname AS constraint_name,
       CASE con.contype WHEN 'c' THEN 'CHECK' WHEN 'x' THEN 'EXCLUDE' END AS kind,
       pg_get_constraintdef(con.oid) AS rule
FROM pg_constraint con JOIN pg_namespace n ON n.oid = con.connamespace
WHERE con.contype IN ('c', 'x') AND n.nspname = 'public' AND con.conrelid <> 0
ORDER BY 1, 2;

-- @name: catalog.triggers
-- @title: Triggers
-- @topic: Relational model › Triggers
-- @algebra: — (catalog)
-- @explain: Event → condition → action rules that run inside the database. A constraint trigger can be DEFERRED to COMMIT time.
SELECT t.tgrelid::regclass::text AS table_name, t.tgname AS trigger_name,
       CASE WHEN t.tgconstraint <> 0 THEN 'constraint trigger' ELSE 'trigger' END AS kind,
       substring(pg_get_triggerdef(t.oid) FROM '(BEFORE|AFTER) .* ON') AS fires,
       t.tgfoid::regproc AS function_name
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal AND n.nspname = 'public'
ORDER BY 1, 2;

-- @name: catalog.indexes
-- @title: Indexes and their access methods
-- @topic: Query processing › Indexes
-- @algebra: — (catalog)
-- @explain: btree for equality/range, gin for full-text and trigram search, gist behind the EXCLUDE constraint.
SELECT tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- @name: fd.verify_city_state
-- @title: Verify an FD on real data — does city_id → state_code hold?
-- @topic: Normalization › Functional dependency test
-- @algebra: X → Y holds ⇔ no two tuples agree on X and differ on Y
-- @explain: Group by the determinant and count distinct dependents. Zero rows returned = the FD holds on the data.
SELECT h.city_id, count(DISTINCT c.state_code) AS states_for_this_city
FROM hotels h JOIN cities c USING (city_id)
GROUP BY h.city_id
HAVING count(DISTINCT c.state_code) > 1;

-- @name: fd.violation_raw
-- @title: FD violated in the RAW data — city name → state does NOT hold
-- @topic: Normalization › Why a surrogate city_id
-- @algebra: σ count(DISTINCT state) > 1 ( city 𝒢 … (staging.goibibo_raw))
-- @explain: In the raw dataset the same city name appears under different state spellings, so 'city' alone cannot determine 'state'. That is why cities has key city_id and candidate key (city_name, state_code).
SELECT city, count(DISTINCT state) AS different_state_values, string_agg(DISTINCT state, ' | ') AS values_seen
FROM staging.goibibo_raw
GROUP BY city
HAVING count(DISTINCT state) > 1
ORDER BY 2 DESC, 1;

-- @name: nf.unf
-- @title: UNF — the raw listing stores facilities as a list in one cell
-- @topic: Normalization › Unnormalized form
-- @algebra: —
-- @explain: hotel_facilities holds a repeating group ("A|B|C|…"): not atomic, so not in 1NF. You cannot index, count or join on one facility.
SELECT property_id, property_name, city, left(hotel_facilities, 120) || '…' AS hotel_facilities
FROM lab.unf_listing
WHERE hotel_facilities IS NOT NULL
LIMIT 5;

-- @name: nf.first
-- @title: 1NF — one atomic facility per row (but name and city now repeat)
-- @topic: Normalization › First normal form
-- @algebra: key = (property_id, facility)
-- @explain: Every cell is atomic. But property_id → property_name, city_id, city, state is a PARTIAL dependency on the key: the name and city repeat once per facility (update anomaly).
SELECT * FROM lab.nf1_listing_facility
WHERE property_id = (SELECT property_id FROM lab.nf1_listing_facility LIMIT 1)
ORDER BY facility;

-- @name: nf.second
-- @title: 2NF — split off the partial dependency
-- @topic: Normalization › Second normal form
-- @algebra: R → R1(property_id, name, city, state), R2(property_id, facility)
-- @explain: Now every non-key attribute depends on the WHOLE key. But property_id → city_id → city, state is TRANSITIVE: the city and state are repeated for every hotel of that city.
SELECT city_id, city, state, count(*) AS hotels_repeating_this_city
FROM lab.nf2_property
GROUP BY city_id, city, state
ORDER BY 3 DESC
LIMIT 10;

-- @name: nf.third
-- @title: 3NF — city_id → city, state moved to its own table; lossless join check
-- @topic: Normalization › Third normal form · Lossless decomposition
-- @algebra: R1 ⋈ R2 ⋈ R3 = original 1NF relation
-- @explain: Joining the 3NF tables back gives exactly the 1NF rows — no spurious tuples, nothing lost. That proves the decomposition is lossless.
SELECT (SELECT count(*) FROM lab.nf1_listing_facility) AS rows_in_1nf,
       (SELECT count(*) FROM lab.nf3_property p
          JOIN lab.nf3_city c USING (city_id)
          JOIN lab.nf2_property_facility f USING (property_id)) AS rows_after_rejoin,
       (SELECT count(*) FROM (
            SELECT property_id, property_name, city_id, city, state, facility FROM lab.nf1_listing_facility
            EXCEPT
            SELECT p.property_id, p.property_name, p.city_id, c.city, c.state, f.facility
            FROM lab.nf3_property p JOIN lab.nf3_city c USING (city_id)
            JOIN lab.nf2_property_facility f USING (property_id)) d) AS rows_lost_or_spurious;

-- @name: nf.fourth
-- @title: 4NF — two independent multivalued facts blow up into a cross product
-- @topic: Normalization › Multivalued dependency · 4NF
-- @algebra: hotel ↠ amenity | landmark
-- @explain: Storing amenities and landmarks in one table forces every amenity to pair with every landmark. 4NF keeps them in two tables (hotel_amenities, hotel_landmarks).
SELECT hotel_name,
       count(*) AS rows_if_combined,
       count(DISTINCT amenity_name) AS amenities,
       count(DISTINCT landmark_name) AS landmarks,
       count(DISTINCT amenity_name) + count(DISTINCT landmark_name) AS rows_in_4nf
FROM lab.mvd_hotel_amenity_landmark
GROUP BY hotel_name
ORDER BY rows_if_combined DESC;

-- @name: nf.fifth
-- @title: 5NF — a join dependency: 3-way join is lossless, any 2-way join is not
-- @topic: Normalization › Join dependency · 5NF
-- @algebra: * [ (hotel, plan), (hotel, channel), (plan, channel) ]
-- @explain: Joining only two projections invents spurious rows; joining all three gives back exactly the original 6 rows.
SELECT 'original'           AS relation, count(*) AS rows FROM lab.jd_offer
UNION ALL
SELECT 'hp ⋈ hc (2-way)',   count(*) FROM lab.jd_hotel_plan hp JOIN lab.jd_hotel_channel hc USING (hotel)
UNION ALL
SELECT 'hp ⋈ hc ⋈ pc (3-way)', count(*) FROM lab.jd_hotel_plan hp
       JOIN lab.jd_hotel_channel hc USING (hotel)
       JOIN lab.jd_plan_channel pc ON pc.meal_plan = hp.meal_plan AND pc.channel = hc.channel;

-- @name: nf.bcnf_rooms
-- @title: 3NF but not BCNF — rooms (a deliberate choice)
-- @topic: Normalization › BCNF and dependency preservation
-- @algebra: rooms(room_id, hotel_id, room_number, room_type_id): room_type_id → hotel_id
-- @explain: room_type_id → hotel_id has a determinant that is not a superkey (violates BCNF), but hotel_id is prime (part of candidate key {hotel_id, room_number}), so 3NF holds. Decomposing to BCNF would lose (hotel_id, room_number) → room_id, so we keep 3NF and enforce consistency with a composite FK.
SELECT r.room_type_id, count(DISTINCT r.hotel_id) AS hotels_per_room_type
FROM rooms r
GROUP BY r.room_type_id
HAVING count(DISTINCT r.hotel_id) > 1;
