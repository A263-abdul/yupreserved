"""
Viva questions & answers and the syllabus coverage map (Parts C and D).
Answers may use <b> / <i>. Avoid raw '<' and '&' (use ≤, 'and').
"""

QA = [
    ("Design and ER model", [
        ("Why did you choose a hotel reservation system?",
         "It needs almost every DBMS idea for real reasons: many-to-many relationships (hotels ↔ amenities, bookings ↔ rooms), "
         "a weak entity (rooms), date-range rules no CHECK can express (double booking), money that must be exact, and "
         "concurrency (two people booking the last room)."),
        ("Why exactly these 15 tables?",
         "Each is one entity or one M:N relationship of the ER model: 12 entities (states, cities, landmarks, hotels, amenities, "
         "room_types, rooms, seasons, guests, bookings, payments, reviews) and 3 M:N relationship tables (hotel_amenities, "
         "hotel_landmarks, booking_rooms). Nothing is stored twice except controlled derived values."),
        ("Why is ROOM a weak entity?",
         "A room number like '101' means nothing on its own — every hotel has a room 101. It is identified only together with "
         "its hotel: room_number is a <b>partial key</b>, and (hotel_id, room_number) identifies the room. In the table we "
         "keep that as a UNIQUE candidate key and add a surrogate room_id as primary key."),
        ("What is the cardinality of bookings and rooms?",
         "M:N. A booking can hold several rooms (a family books 2), and a room appears in many bookings over time. Hence "
         "booking_rooms with composite PK (booking_id, room_id) and the relationship attributes room_subtotal and room_tax."),
        ("Where is a 1:1 relationship?",
         "bookings ↔ reviews: reviews.booking_id is a foreign key AND UNIQUE, so a stay has at most one review."),
        ("Where is a recursive relationship?",
         "guests.referred_by references guests.guest_id ('refers'). The self join and the recursive CTE (sub.recursive) use it."),
        ("Which attributes are derived and how are they handled?",
         "bookings.nights is a GENERATED column (check_out − check_in); age is computed in v_guest_directory; hotels.avg_rating "
         "and review_count are stored for speed and kept correct by trigger trg_reviews_rollup."),
    ]),
    ("Keys", [
        ("Why is state_code a natural primary key but hotels use a surrogate key?",
         "State codes (MH, RJ) are short, stable and universally known, so they make good natural keys. Hotel names are not "
         "unique and can change; source_ref is long text. A surrogate integer is small, never changes and keeps joins fast."),
        ("Name a super key, a candidate key and an alternate key in guests.",
         "Super key: {guest_id, phone}. Candidate keys: {guest_id}, {phone}, {email}, {id_type, id_number}. Primary key: "
         "guest_id. Alternate keys: phone, email and (id_type, id_number), each enforced with UNIQUE."),
        ("Why is (id_type, id_number) a composite key?",
         "Neither column is unique alone — two guests can both use PAN, and a passport and a PAN could share digits — but the "
         "pair identifies one document."),
        ("Why does rooms have UNIQUE (room_type_id, hotel_id) in room_types?",
         "So that rooms can declare the composite foreign key (room_type_id, hotel_id) → room_types. That FK guarantees a "
         "room's type belongs to the same hotel as the room; a single-column FK could not."),
        ("Why does booking_rooms NOT contain hotel_id?",
         "With key (booking_id, room_id), hotel_id would depend on booking_id alone — a partial dependency (2NF violation). "
         "The trigger trg_booking_rooms_guard checks that the room's hotel equals the booking's hotel instead."),
        ("Why ON DELETE RESTRICT for bookings → hotels but CASCADE for room_types → hotels?",
         "Bookings and payments are history and money: deleting a hotel must not silently erase them. Room types, rooms and "
         "amenity links are part of the hotel (composition), so they go with it — but only if no booking still uses a room."),
    ]),
    ("Constraints and triggers", [
        ("Why can't I enter a check-out date before the check-in date?",
         "CHECK constraint ck_bookings_dates (check_out > check_in). The DBMS rejects the row whatever program sends it."),
        ("Why is double booking prevented by a trigger and not a CHECK?",
         "A CHECK sees only the row being inserted. 'Is this room already taken for an overlapping range?' needs OTHER rows of "
         "booking_rooms and bookings, so it is a BEFORE INSERT trigger (trg_booking_rooms_guard)."),
        ("How do you test whether two stays overlap?",
         "Stays are half-open ranges [check_in, check_out). Two ranges [a,b) and [c,d) overlap exactly when a &lt; d AND c &lt; b. "
         "So checking out and another guest checking in on the same day is allowed."),
        ("What is a deferred constraint trigger and why use one?",
         "trg_booking_capacity is DEFERRABLE INITIALLY DEFERRED: it runs at COMMIT. A booking for 5 adults inserts its rooms one "
         "by one; checking after the first room would wrongly fail. At commit all rooms exist and capacity can be judged."),
        ("What does the EXCLUDE constraint on seasons do?",
         "It uses a GiST index on daterange(start_date, end_date) with the overlap operator so that no two seasons share a "
         "night; otherwise a night would have two multipliers."),
        ("Your photo CHECK first rejected cities without a photo. Why?",
         "CHECK (photo_url ~ '^https://' AND photo_credit IS NOT NULL): for a NULL photo the regex gives UNKNOWN and "
         "the credit test gives FALSE; UNKNOWN AND FALSE = FALSE, so the row was rejected (a CHECK fails only on FALSE, "
         "passes on TRUE or UNKNOWN). The fix: CHECK (photo_url IS NULL OR (photo_url ~ '^https://' AND photo_credit IS NOT NULL))."),
        ("How is the OTP stored securely?",
         "Never in plain text: auth.otp_challenges keeps an HMAC-SHA256 of (phone, code) with a server secret, an expiry "
         "time and an attempt counter (CHECK attempts BETWEEN 0 AND 5). Verification locks the row FOR UPDATE and compares "
         "hashes in constant time."),
        ("What is a domain? Give an example.",
         "A named type with a rule: indian_mobile is varchar(10) CHECK (VALUE ~ '^[6-9][0-9]{9}$'). Every phone column uses it."),
        ("Why can't a completed booking go back to CONFIRMED?",
         "trg_bookings_status implements a state machine: PENDING → CONFIRMED → CHECKED_IN → COMPLETED, plus CANCELLED / NO_SHOW. "
         "Any other change raises an error, so history cannot be rewritten."),
    ]),
    ("Normalization", [
        ("Where did 1NF fail in your raw data?",
         "hotel_facilities held 'Parking|Room Service|Wi-Fi|…' in one cell — a repeating group. lab.nf1_listing_facility makes "
         "one row per (hotel, facility); the final design is hotel_amenities."),
        ("Show a partial dependency you removed (2NF).",
         "In nf1_listing_facility(property_id, facility, property_name, city, state) with key (property_id, facility), "
         "property_id → property_name, city, state depends on part of the key. Split into nf2_property and nf2_property_facility."),
        ("Show a transitive dependency you removed (3NF).",
         "property_id → city → state. The state was repeated for every hotel of a city; nf3_city(city, state) removes it. "
         "In the final schema: hotels.city_id → cities.state_code."),
        ("How do you prove the decomposition is lossless?",
         "Query nf.third rejoins the 3NF tables and compares with the 1NF table using EXCEPT: zero rows lost, zero spurious. "
         "Theory: each split shares a key of one side (R1 ∩ R2 → R1 or R1 ∩ R2 → R2)."),
        ("What happens if you decompose on an FD that does not hold?",
         "The join is lossy. On the raw names, city → state is false (Hyderabad under two states), and the 3NF re-join gave 357 "
         "lost/spurious rows. City names are not unique either (Aurangabad: Maharashtra and Bihar), which is why cities has "
         "the surrogate key city_id and the candidate key (city_name, state_code)."),
        ("Is every table in BCNF?",
         "All except rooms, deliberately. room_type_id → hotel_id has a non-superkey determinant. rooms is still 3NF because "
         "hotel_id is prime. A BCNF split would lose the dependency (hotel_id, room_number) → room_id, so we keep 3NF and a "
         "composite FK."),
        ("What is a multivalued dependency here (4NF)?",
         "hotel ↠ amenity and hotel ↠ landmark are independent. Storing both in one table forces every amenity to pair with every "
         "landmark (nf.fourth shows the blow-up). 4NF keeps them in hotel_amenities and hotel_landmarks."),
        ("What is a join dependency (5NF)?",
         "lab.jd_offer(hotel, meal_plan, channel) equals the join of its three binary projections, but the join of any two "
         "creates spurious rows (nf.fifth). That 3-way join dependency is what 5NF is about."),
        ("Why do you store room_subtotal if prices can be calculated?",
         "It is not derivable later: base prices and seasons can change, but the price agreed at booking time is a fact of that "
         "booking. It depends on the whole key (booking_id, room_id)."),
    ]),
    ("Queries, algebra and calculus", [
        ("How do you retrieve the price for two nights from date X to date Y?",
         "SELECT * FROM fn_quote_stay(room_type_id, X, Y): a CROSS JOIN of the room type with generate_series(nights), a THETA "
         "LEFT JOIN to seasons (night BETWEEN start AND end), × weekend factor, then the GST slab per night."),
        ("Which join returns states that have no hotels?",
         "LEFT OUTER JOIN states → cities → hotels (joins.left_outer): Lakshadweep and Manipur appear with 0."),
        ("Write division in SQL.",
         "Hotels that have ALL of {Pool, Spa, Wi-Fi}: double NOT EXISTS — 'no required amenity that the hotel lacks' "
         "(division.not_exists), or GROUP BY hotel HAVING count(DISTINCT amenity) = 3 (division.count)."),
        ("What is the difference between TRC and DRC?",
         "In tuple relational calculus variables range over whole tuples ({g | guests(g) ∧ ∃b …}); in domain relational calculus "
         "they range over attribute values ({⟨n, s⟩ | ∃i, t, c hotels(i, n, t, s, c) ∧ …}). SQL's EXISTS is TRC."),
        ("Semi-join vs inner join?",
         "An inner join repeats a hotel once per matching review; a semi-join (EXISTS) returns each hotel once if any match exists."),
        ("Why NOT EXISTS and not NOT IN for the anti-join?",
         "If the subquery returns a NULL, x NOT IN (…) is UNKNOWN for every row and returns nothing; NOT EXISTS is NULL-safe."),
    ]),
    ("Query processing", [
        ("Which join algorithm does PostgreSQL use for bookings ⋈ hotels and why?",
         "Hash join: build a hash table on the smaller input (3,583 hotels) and probe it with 72,000 bookings — one pass over "
         "each, O(|R| + |S|). With hash joins disabled it chooses a sort-merge join, and with both disabled a nested loop."),
        ("Show external sorting.",
         "plan.external_sort sets work_mem = 64 kB; the plan reports 'Sort Method: external merge Disk: … kB' — sorted runs "
         "written to temp files and merged. With 32 MB it becomes an in-memory quicksort."),
        ("What is pipelining?",
         "Operators pass tuples to their parent one at a time without materialising intermediate tables. In plan.pipelining "
         "LIMIT 5 stops the scan and join after a handful of rows."),
        ("Give an example of heuristic optimization.",
         "Selection pushdown: in plan.heuristic_pushdown the filter city_name = 'Udaipur' is applied on the cities scan before "
         "the joins, so the joins process a few rows instead of thousands."),
        ("Why a GIN index on search_doc?",
         "A GIN index is an inverted index (word → hotels containing it), so full-text search does not read every description."),
    ]),
    ("Transactions, concurrency and recovery", [
        ("What happens if two guests book the last room at the same time?",
         "fn_book_stay locks the room rows with SELECT … FOR UPDATE. The second transaction waits; when the first commits, the "
         "second re-checks availability and is refused ('Only 0 room(s) … are free'). The race demo shows the 1.3 s wait."),
        ("How do you avoid deadlocks in booking?",
         "Rooms are always locked in room_id order, so two transactions can never hold locks in opposite orders. The deadlock "
         "demo shows what happens otherwise: PostgreSQL detects the cycle after deadlock_timeout and aborts one victim."),
        ("Is PostgreSQL lock-based or timestamp-based?",
         "Both ideas: writers take row locks (two-phase locking), while reads use MVCC — each row version carries transaction "
         "ids (xmin / xmax), a form of timestamp, and each statement or transaction reads a snapshot. Readers never block writers."),
        ("Show a non-repeatable read.",
         "In READ COMMITTED a second read in the same transaction sees another session's committed update; in REPEATABLE READ "
         "both reads return the same value (txn isolation_levels)."),
        ("How does the database recover from a crash?",
         "Write-ahead logging: every change is written to the WAL before it is applied, and COMMIT waits for the WAL flush. After "
         "a crash PostgreSQL REDOes the log from the last checkpoint; transactions without a commit record stay invisible. "
         "./yup recovery demonstrates it."),
        ("Why is fn_book_stay SECURITY DEFINER?",
         "The app role yup_app may not UPDATE or lock rooms directly. The function runs with its owner's rights, so the only way "
         "the app can lock rooms is through this one audited booking routine — least privilege."),
    ]),
    ("Dataset, system and Unit 5", [
        ("Where does your data come from and is it real?",
         "Hotel listings are real: the Goibibo dataset (4,000 Indian properties, Kaggle/PromptCloud). Prices, guests, bookings "
         "and reviews are simulated with a fixed seed because no public dataset contains them; the 18 Signature hotels are "
         "original. All of this is documented in 01-dataset/README.md."),
        ("Why did you choose PostgreSQL over MySQL?",
         "The installed MySQL 5.7 ignores CHECK constraints and lacks FULL OUTER JOIN, INTERSECT/EXCEPT, CTEs and window "
         "functions. PostgreSQL also gives EXCLUDE, deferred constraints, inheritance, partitioning and full-text search."),
        ("How is a distributed database shown?",
         "lab.bookings_by_region is horizontally fragmented by region into six partitions ('sites'); the planner prunes "
         "fragments (plan.partition_pruning). Vertical fragments of guests rejoin losslessly on the key."),
        ("How is an object-oriented database shown?",
         "A composite type lab.address_t (an object with attributes), tables that INHERIT from lab.property (IS-A), and a "
         "function lab.label(p) acting as a method."),
        ("How is a multimedia database shown?",
         "lab.hotel_media stores SVG posters as bytea with MIME type and size; the API streams them and the hotel page displays them."),
        ("Where is data mining?",
         "Association rules on amenities (support and confidence via a self-join), co-visited city pairs, ROLLUP / CUBE and "
         "window functions."),
    ]),
]

SYLLABUS = [
    ("Unit 1 · Introduction", [
        ["Concept and goals of DBMS", "Part B §1: data integrity, sharing, security, independence achieved by PostgreSQL"],
        ["Database languages", "DDL (schema/*.sql), DML (seed, queries), DCL (07_roles.sql), TCL (BEGIN/COMMIT/ROLLBACK in fn_book_stay, lab)"],
        ["Database users", "roles postgres (DBA), yup_app (application), yup_analyst (end user via views), yup_lab"],
        ["Database abstraction", "physical (files, indexes), logical (15 tables), view level (v_hotel_cards, v_guest_directory)"],
        ["Database architecture", "three-tier architecture (Part B §2); client–server PostgreSQL"],
        ["Relational model and constraints", "02_tables.sql: domain, key, entity-integrity, referential-integrity, CHECK, EXCLUDE"],
        ["ER model, relationship sets, keys, mapping, design", "Part B §4: Chen diagram, weak entity, cardinalities, ER → relational mapping table"],
    ]),
    ("Unit 2 · Relational model", [
        ["The catalog", "catalog.* queries (pg_catalog / information_schema), ./yup describe, Lab 'Tables' tab"],
        ["Types", "ENUM types and DOMAINs (01_types.sql), composite type lab.address_t"],
        ["Keys", "catalog.primary_keys / candidate_keys / foreign_keys; Part B §5"],
        ["Relational algebra (fundamental + additional operations)", "σ π ρ ∪ − × in basics.*, sets.*, joins.cross; ⋈ ÷ ∩ γ in joins.*, division.*, agg.*"],
        ["Tuple and domain relational calculus", "calculus.trc, calculus.drc, division.not_exists"],
        ["SQL fundamentals", "66 named queries: predicates, CASE, subqueries, CTEs, recursion, window functions"],
        ["Integrity", "constraints + 16 why-not scenarios"],
        ["Triggers", "8 triggers incl. a deferred constraint trigger (04_triggers.sql)"],
        ["Views", "5 views incl. updatable WITH CHECK OPTION and a materialized view"],
    ]),
    ("Unit 3 · Relational database design", [
        ["Normalization using functional dependencies", "Part B §7: FD table; UNF → 1NF → 2NF → 3NF on the real data (lab.nf*)"],
        ["BCNF and dependency preservation", "nf.bcnf_rooms — rooms deliberately 3NF"],
        ["Multivalued dependency (4NF)", "nf.fourth (lab.mvd_hotel_amenity_landmark)"],
        ["Join dependency (5NF)", "nf.fifth (lab.jd_offer)"],
        ["Lossless decomposition", "nf.third and dist.vertical"],
    ]),
    ("Unit 4 · Query processing, optimization and tuning", [
        ["Translating SQL into relational algebra", "every named query carries its RA form; EXPLAIN shows the operator tree"],
        ["External sorting", "plan.external_sort vs plan.in_memory_sort, plan.top_n"],
        ["SELECT algorithms", "plan.seq_scan, plan.index_scan, plan.bitmap_scan"],
        ["JOIN algorithms", "plan.hash_join, plan.merge_join, plan.nested_loop"],
        ["PROJECT and set operations", "plan.project_distinct, plan.set_operation"],
        ["Pipelining", "plan.pipelining"],
        ["Heuristic optimization", "plan.heuristic_pushdown"],
        ["Database tuning", "05_indexes.sql: FK, composite, partial, GIN, trigram and expression indexes; laptop-tuned settings"],
    ]),
    ("Unit 5 · Transactions, concurrency, recovery and new applications", [
        ["Transaction processing concepts", "ACID in fn_book_stay; txn atomic_rollback"],
        ["Lock-based protocols", "SELECT … FOR UPDATE; txn double_booking_race"],
        ["Timestamp-based protocols", "MVCC transaction ids xmin/xmax; txn mvcc_versions"],
        ["Deadlock handling", "txn deadlock (detection + victim); ordered locking prevents it in bookings"],
        ["Crash recovery", "WAL; ./yup recovery"],
        ["Distributed database", "horizontal + vertical fragmentation (lab.bookings_by_region, guest fragments)"],
        ["Object-oriented database", "composite types, table inheritance, method function (lab.*)"],
        ["Multimedia database", "lab.hotel_media (bytea), served at /api/lab/media/{id}"],
        ["Data mining", "mining.amenity_rules, mining.city_pairs, agg.rollup, agg.cube, sub.window"],
        ["Digital libraries", "full-text search (tsvector + GIN), app.mood_search, trigram search"],
    ]),
]
