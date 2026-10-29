-- ════════════════════════════════════════════════════════════════════════════
--  07_unit5.sql · Object-relational, distributed and multimedia databases
-- ════════════════════════════════════════════════════════════════════════════

-- @name: oodb.inheritance
-- @title: Inheritance — querying the parent class returns all subclasses
-- @topic: Unit 5 › Object-oriented databases (IS-A hierarchy)
-- @algebra: —
-- @explain: lab.heritage_property and lab.floating_property INHERIT lab.property. tableoid::regclass tells which "class" each object belongs to.
SELECT tableoid::regclass::text AS stored_in, count(*) AS objects
FROM lab.property GROUP BY 1
UNION ALL
SELECT 'ONLY lab.property', count(*) FROM ONLY lab.property;

-- @name: oodb.composite_type
-- @title: Composite type and a method on it
-- @topic: Unit 5 › Object-oriented databases (user-defined types)
-- @algebra: —
-- @explain: address is an object with its own attributes (address).city; lab.label(p) behaves like a method.
SELECT p.name, (p.address).city AS city, (p.address).state AS state, p.era, lab.label(p) AS label
FROM lab.heritage_property p
ORDER BY (p.address).state, p.name
LIMIT 12;

-- @name: dist.horizontal
-- @title: Horizontal fragmentation — bookings stored per region "site"
-- @topic: Unit 5 › Distributed databases (fragmentation)
-- @algebra: bookings = site_north ∪ site_south ∪ site_east ∪ site_west ∪ site_central ∪ site_northeast
-- @explain: Each fragment holds the rows of one region. The union of all fragments is the whole relation (completeness), and no row is in two fragments (disjointness).
SELECT tableoid::regclass AS fragment, count(*) AS rows,
       min(check_in) AS first_stay, max(check_in) AS last_stay
FROM lab.bookings_by_region
GROUP BY 1 ORDER BY rows DESC;

-- @name: dist.vertical
-- @title: Vertical fragmentation — guest columns at two sites, rejoined on the key
-- @topic: Unit 5 › Distributed databases (vertical fragmentation)
-- @algebra: guests = guest_contact ⋈ guest_profile
-- @explain: Each fragment keeps the primary key, so the natural join reconstructs the original rows exactly (lossless).
SELECT (SELECT count(*) FROM guests) AS original_rows,
       (SELECT count(*) FROM lab.guest_contact_frag c JOIN lab.guest_profile_frag p USING (guest_id)) AS rejoined_rows;

-- @name: media.posters
-- @title: Multimedia — SVG posters stored as binary (bytea) in the database
-- @topic: Unit 5 › Multimedia databases
-- @algebra: —
-- @explain: The content column holds the image bytes; metadata (title, MIME type, size) sits alongside. The API serves them at /api/media/{id}.
SELECT media_id, hotel_id, title, mime_type, bytes
FROM lab.hotel_media ORDER BY media_id;
