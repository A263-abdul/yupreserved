-- ════════════════════════════════════════════════════════════════════════════
--  lab_objects.sql  ·  Teaching objects, kept OUT of the 15 core tables
--
--  schema staging  the untouched raw dataset (exactly as downloaded)
--  schema lab      normalization walk-through (UNF → 1NF → 2NF → 3NF → 4NF/5NF)
--                  object-relational features (Unit 5: OODB)
--                  fragmentation / partitioning (Unit 5: distributed DB)
--                  multimedia storage (Unit 5: multimedia DB)
-- ════════════════════════════════════════════════════════════════════════════
CREATE SCHEMA staging;
CREATE SCHEMA lab;


-- ── 1. RAW DATA (staging) ───────────────────────────────────────────────────
-- Every column is text, exactly as in the CSV. Columns such as hotel_facilities
-- hold "A|B|C" lists: a repeating group, so this table is NOT in 1NF.
CREATE TABLE staging.goibibo_raw (
    additional_info text, address text, area text, city text, country text,
    crawl_date text, guest_recommendation text, hotel_brand text, hotel_category text,
    hotel_description text, hotel_facilities text, hotel_star_rating text,
    image_count text, latitude text, locality text, longitude text, pageurl text,
    point_of_interest text, property_id text, property_name text, property_type text,
    province text, qts text, query_time_stamp text, review_count_by_category text,
    room_area text, room_count text, room_facilities text, room_type text,
    similar_hotel text, site_review_count text, site_review_rating text,
    site_stay_review_rating text, sitename text, state text, uniq_id text
);
\copy staging.goibibo_raw FROM '../01-dataset/raw/goibibo_com-travel_sample.csv' WITH (FORMAT csv, HEADER true)


-- ── 2. NORMALIZATION WALK-THROUGH (on the real raw data) ───────────────────
-- UNF: one row per hotel, facilities as a list
CREATE VIEW lab.unf_listing AS
SELECT property_id, property_name, city, state, hotel_facilities
FROM staging.goibibo_raw;

-- 1NF: atomic values — one row per (hotel, facility). Key = (property_id, facility).
-- Built from the CLEANED listings: in the raw file city → state does not even hold
-- (query fd.violation_raw), and a city name is not unique either (Aurangabad is in
-- both Maharashtra and Bihar), so the decomposition below uses city_id.
CREATE TABLE lab.nf1_listing_facility AS
SELECT DISTINCT r.property_id, h.hotel_name AS property_name, c.city_id, c.city_name AS city,
       s.state_name AS state, trim(f) AS facility
FROM staging.goibibo_raw r
JOIN hotels h ON h.source_ref = r.property_id
JOIN cities c ON c.city_id = h.city_id
JOIN states s ON s.state_code = c.state_code,
     LATERAL unnest(string_to_array(r.hotel_facilities, '|')) AS f
WHERE trim(f) <> '';
ALTER TABLE lab.nf1_listing_facility ADD PRIMARY KEY (property_id, facility);

-- 2NF: remove the partial dependency  property_id → property_name, city_id, city, state
CREATE TABLE lab.nf2_property AS
SELECT DISTINCT property_id, property_name, city_id, city, state FROM lab.nf1_listing_facility;
ALTER TABLE lab.nf2_property ADD PRIMARY KEY (property_id);

CREATE TABLE lab.nf2_property_facility AS
SELECT property_id, facility FROM lab.nf1_listing_facility;
ALTER TABLE lab.nf2_property_facility ADD PRIMARY KEY (property_id, facility);

-- 3NF: remove the transitive dependency  property_id → city_id → city, state
CREATE TABLE lab.nf3_city AS
SELECT DISTINCT city_id, city, state FROM lab.nf2_property;
ALTER TABLE lab.nf3_city ADD PRIMARY KEY (city_id);

CREATE TABLE lab.nf3_property AS
SELECT property_id, property_name, city_id FROM lab.nf2_property;
ALTER TABLE lab.nf3_property ADD PRIMARY KEY (property_id);
ALTER TABLE lab.nf3_property ADD FOREIGN KEY (city_id) REFERENCES lab.nf3_city (city_id);

-- 4NF: two INDEPENDENT multivalued facts about a hotel stored together.
-- hotel ↠ amenity and hotel ↠ landmark  ⇒ every amenity is paired with every
-- landmark (a cross product). Built for the 18 signature hotels only.
CREATE TABLE lab.mvd_hotel_amenity_landmark AS
SELECT h.hotel_id, h.hotel_name, a.amenity_name, l.landmark_name
FROM hotels h
JOIN hotel_amenities ha ON ha.hotel_id = h.hotel_id
JOIN amenities a        ON a.amenity_id = ha.amenity_id
JOIN hotel_landmarks hl ON hl.hotel_id = h.hotel_id
JOIN landmarks l        ON l.landmark_id = hl.landmark_id
WHERE h.is_signature;
-- The 4NF decomposition is exactly the core tables hotel_amenities + hotel_landmarks.

-- 5NF / join dependency: R(hotel, meal_plan, channel) where the business rule is
-- "if a hotel offers a meal plan, and sells through a channel, and that meal plan
--  is sold on that channel, then the hotel sells that plan on that channel".
-- Then R = π(hotel,plan)R ⋈ π(hotel,channel)R ⋈ π(plan,channel)R, but NOT the
-- join of any two of them.
CREATE TABLE lab.jd_offer (
    hotel      text,
    meal_plan  text,
    channel    text,
    PRIMARY KEY (hotel, meal_plan, channel)
);
INSERT INTO lab.jd_offer VALUES
    ('Samudra Mahal',       'CP (breakfast)',     'WEB'),
    ('Samudra Mahal',       'MAP (half board)',   'CORPORATE'),
    ('Samudra Mahal',       'CP (breakfast)',     'CORPORATE'),
    ('Charminar Courtyard', 'CP (breakfast)',     'WEB'),
    ('Pichola Rajbagh',     'MAP (half board)',   'WEB'),
    ('Pichola Rajbagh',     'CP (breakfast)',     'WEB');
CREATE VIEW lab.jd_hotel_plan     AS SELECT DISTINCT hotel, meal_plan FROM lab.jd_offer;
CREATE VIEW lab.jd_hotel_channel  AS SELECT DISTINCT hotel, channel   FROM lab.jd_offer;
CREATE VIEW lab.jd_plan_channel   AS SELECT DISTINCT meal_plan, channel FROM lab.jd_offer;


-- ── 3. OBJECT-RELATIONAL FEATURES (Unit 5: object-oriented databases) ──────
-- user-defined composite type (an "object" with attributes)
CREATE TYPE lab.address_t AS (line text, locality text, city text, state text);

-- base "class"
CREATE TABLE lab.property (
    property_id  integer PRIMARY KEY,
    name         text NOT NULL,
    address      lab.address_t,
    stars        smallint
);
-- subclasses inherit every column of the parent (IS-A / specialization)
CREATE TABLE lab.heritage_property (
    era          text
) INHERITS (lab.property);
CREATE TABLE lab.floating_property (
    water_body   text
) INHERITS (lab.property);

INSERT INTO lab.heritage_property (property_id, name, address, stars, era)
SELECT h.hotel_id, h.hotel_name, ROW(h.address, h.locality, c.city_name, s.state_name)::lab.address_t,
       h.star_rating, CASE WHEN h.property_type = 'Palace' THEN 'Royal' ELSE 'Colonial / Mughal' END
FROM hotels h JOIN cities c USING (city_id) JOIN states s USING (state_code)
WHERE h.property_type IN ('Palace', 'Heritage Hotel', 'Haveli');

INSERT INTO lab.floating_property (property_id, name, address, stars, water_body)
SELECT h.hotel_id, h.hotel_name, ROW(h.address, h.locality, c.city_name, s.state_name)::lab.address_t,
       h.star_rating, CASE WHEN c.city_name = 'Srinagar' THEN 'Dal Lake' ELSE 'Kerala backwaters' END
FROM hotels h JOIN cities c USING (city_id) JOIN states s USING (state_code)
WHERE h.property_type IN ('Houseboat', 'Luxury Yacht');

INSERT INTO lab.property (property_id, name, address, stars)
SELECT h.hotel_id, h.hotel_name, ROW(h.address, h.locality, c.city_name, s.state_name)::lab.address_t,
       h.star_rating
FROM hotels h JOIN cities c USING (city_id) JOIN states s USING (state_code)
WHERE h.property_type IN ('Hotel', 'Boutique Hotel') AND h.is_signature;

-- a "method" on the object type
CREATE FUNCTION lab.label(p lab.property) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT p.name || ' — ' || (p.address).city || ', ' || (p.address).state;
$$;


-- ── 4. FRAGMENTATION (Unit 5: distributed databases) ───────────────────────
-- Horizontal fragmentation: each region's bookings live in their own fragment
-- ("site"). The parent table is the global relation = UNION of fragments.
CREATE TABLE lab.bookings_by_region (
    booking_id  integer,
    region      region_t NOT NULL,
    city_name   text,
    hotel_name  text,
    check_in    date,
    nights      smallint,
    status      booking_status_t,
    PRIMARY KEY (region, booking_id)
) PARTITION BY LIST (region);

CREATE TABLE lab.site_north     PARTITION OF lab.bookings_by_region FOR VALUES IN ('NORTH');
CREATE TABLE lab.site_south     PARTITION OF lab.bookings_by_region FOR VALUES IN ('SOUTH');
CREATE TABLE lab.site_east      PARTITION OF lab.bookings_by_region FOR VALUES IN ('EAST');
CREATE TABLE lab.site_west      PARTITION OF lab.bookings_by_region FOR VALUES IN ('WEST');
CREATE TABLE lab.site_central   PARTITION OF lab.bookings_by_region FOR VALUES IN ('CENTRAL');
CREATE TABLE lab.site_northeast PARTITION OF lab.bookings_by_region FOR VALUES IN ('NORTHEAST');

INSERT INTO lab.bookings_by_region
SELECT b.booking_id, s.region, c.city_name, h.hotel_name, b.check_in, b.nights, b.status
FROM bookings b JOIN hotels h USING (hotel_id) JOIN cities c USING (city_id) JOIN states s USING (state_code);

-- Vertical fragmentation: guest columns split across two sites, both keep the key
CREATE TABLE lab.guest_contact_frag AS SELECT guest_id, phone, email FROM guests;
CREATE TABLE lab.guest_profile_frag AS SELECT guest_id, first_name, last_name, date_of_birth, home_city_id FROM guests;
ALTER TABLE lab.guest_contact_frag ADD PRIMARY KEY (guest_id);
ALTER TABLE lab.guest_profile_frag ADD PRIMARY KEY (guest_id);


-- ── 5. MULTIMEDIA (Unit 5: multimedia databases) ───────────────────────────
-- Binary content stored in the database (bytea) with its metadata.
CREATE TABLE lab.hotel_media (
    media_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hotel_id   integer NOT NULL REFERENCES hotels (hotel_id) ON DELETE CASCADE,
    title      text NOT NULL,
    mime_type  text NOT NULL CHECK (mime_type IN ('image/svg+xml', 'image/png', 'image/jpeg')),
    content    bytea NOT NULL,
    bytes      integer GENERATED ALWAYS AS (octet_length(content)) STORED
);

-- A small railway-poster style SVG for every signature hotel, generated in SQL
INSERT INTO lab.hotel_media (hotel_id, title, mime_type, content)
SELECT h.hotel_id, h.hotel_name || ' — poster', 'image/svg+xml',
       convert_to(format(
'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400">
  <rect width="300" height="400" fill="%s"/>
  <circle cx="210" cy="120" r="54" fill="#F2B544"/>
  <path d="M0 260 Q75 200 150 250 T300 230 V400 H0Z" fill="%s"/>
  <path d="M0 310 Q90 270 170 300 T300 290 V400 H0Z" fill="#1F2A44" opacity=".85"/>
  <text x="20" y="360" font-family="Georgia" font-size="22" fill="#FFF6E8">%s</text>
  <text x="20" y="384" font-family="Georgia" font-size="12" fill="#FFF6E8" letter-spacing="3">%s · YUPRESERVED</text>
</svg>',
         (ARRAY['#E9D5B7','#C9DDE0','#F3C9A8','#D8D3E8'])[1 + h.hotel_id % 4],
         (ARRAY['#C4553A','#2F6F73','#B8862F','#6B4E8F'])[1 + h.hotel_id % 4],
         h.hotel_name, upper(c.city_name)), 'UTF8')
FROM hotels h JOIN cities c USING (city_id)
WHERE h.is_signature;


-- ── 6. TRANSACTION DEMOS (Unit 5: concurrency control) ─────────────────────
-- A scratch table for the deadlock / isolation / MVCC demonstrations, so the
-- demos never touch real business data.
CREATE TABLE lab.txn_demo (
    item_id  integer PRIMARY KEY,
    label    text    NOT NULL,
    qty      integer NOT NULL CHECK (qty >= 0)
);
INSERT INTO lab.txn_demo VALUES (1, 'Harbour Room inventory', 10), (2, 'Lake Suite inventory', 4);

-- The double-booking race really commits a booking; this function removes
-- such demo bookings afterwards. SECURITY DEFINER = it runs with the owner's
-- rights, so yup_app can call it without being allowed to DELETE bookings.
CREATE FUNCTION lab.purge_demo_bookings() RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    n integer;
BEGIN
    DELETE FROM payments WHERE booking_id IN (SELECT booking_id FROM bookings WHERE special_request = 'LAB DEMO');
    DELETE FROM bookings WHERE special_request = 'LAB DEMO';
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;
REVOKE ALL ON FUNCTION lab.purge_demo_bookings() FROM PUBLIC;

GRANT USAGE ON SCHEMA lab, staging TO yup_app, yup_lab;
GRANT SELECT ON ALL TABLES IN SCHEMA lab, staging TO yup_app, yup_lab;
GRANT UPDATE ON lab.txn_demo TO yup_app;
GRANT EXECUTE ON FUNCTION lab.purge_demo_bookings() TO yup_app;
ANALYZE staging.goibibo_raw;
