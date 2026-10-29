-- ════════════════════════════════════════════════════════════════════════════
--  query_processing.sql · Unit 4 — how PostgreSQL actually executes queries
--  Run with EXPLAIN (ANALYZE) by `yup explain <name>` or /api/lab/plans.
--  "@setup" lines are executed first (SET LOCAL lasts until the end of the
--  transaction, which is always rolled back).
-- ════════════════════════════════════════════════════════════════════════════

-- @name: plan.seq_scan
-- @title: SELECT with no usable index → sequential (linear) scan
-- @topic: Algorithms for SELECT › Linear search
-- @explain: special_request has no index, so every block of bookings is read and each row is tested.
SELECT booking_ref FROM bookings WHERE special_request = 'Celebrating anniversary';

-- @name: plan.index_scan
-- @title: SELECT on a key → B-tree index scan
-- @topic: Algorithms for SELECT › Index search
-- @explain: booking_ref has a UNIQUE index: the B-tree is descended in a few page reads instead of scanning 72,000 rows.
SELECT * FROM bookings WHERE booking_ref = (SELECT booking_ref FROM bookings WHERE booking_id = 500);

-- @name: plan.bitmap_scan
-- @title: SELECT on a range → bitmap index scan
-- @topic: Algorithms for SELECT › Index for range / many rows
-- @explain: Many matching rows: the index builds a bitmap of pages first, then each page is read once in physical order.
SELECT booking_ref, status FROM bookings WHERE hotel_id = 1 AND check_in BETWEEN DATE '2026-01-01' AND DATE '2026-06-30';

-- @name: plan.hash_join
-- @title: JOIN → hash join (the optimizer's default for big equi-joins)
-- @topic: Algorithms for JOIN › Hash join
-- @explain: Build a hash table on the smaller input (hotels), then probe it once per booking row. O(|R| + |S|).
SELECT h.property_type, count(*) FROM bookings b JOIN hotels h ON h.hotel_id = b.hotel_id GROUP BY 1;

-- @name: plan.merge_join
-- @title: Same JOIN, hash join disabled → sort-merge join
-- @topic: Algorithms for JOIN › Sort-merge join
-- @setup: SET LOCAL enable_hashjoin = off; SET LOCAL enable_nestloop = off
-- @explain: Both inputs are sorted on hotel_id (or read in index order) and merged in one pass, like merging two sorted lists.
SELECT h.property_type, count(*) FROM bookings b JOIN hotels h ON h.hotel_id = b.hotel_id GROUP BY 1;

-- @name: plan.nested_loop
-- @title: Same JOIN, hash & merge disabled → (index) nested-loop join
-- @topic: Algorithms for JOIN › Nested-loop join
-- @setup: SET LOCAL enable_hashjoin = off; SET LOCAL enable_mergejoin = off
-- @explain: For each outer row, look up the matching inner rows (here through the hotels primary-key index).
SELECT h.property_type, count(*) FROM bookings b JOIN hotels h ON h.hotel_id = b.hotel_id GROUP BY 1;

-- @name: plan.external_sort
-- @title: ORDER BY bigger than memory → external merge sort on disk
-- @topic: Algorithms for external sorting
-- @setup: SET LOCAL work_mem = '64kB'
-- @explain: With only 64 kB of sort memory, PostgreSQL writes sorted runs to temporary files and merges them (look for "Sort Method: external merge  Disk").
SELECT booking_id, booked_at FROM bookings ORDER BY booked_at DESC;

-- @name: plan.in_memory_sort
-- @title: The same ORDER BY with enough memory → quicksort in RAM
-- @topic: Algorithms for external sorting (comparison)
-- @setup: SET LOCAL work_mem = '32MB'
-- @explain: Now the whole input fits: "Sort Method: quicksort  Memory". Compare the time with plan.external_sort.
SELECT booking_id, booked_at FROM bookings ORDER BY booked_at DESC;

-- @name: plan.top_n
-- @title: ORDER BY … LIMIT → top-N heapsort
-- @topic: Algorithms for sorting › Top-N
-- @explain: Only the best 10 rows are kept in a small heap; the input is never fully sorted.
SELECT booking_id, booked_at FROM bookings ORDER BY booked_at DESC LIMIT 10;

-- @name: plan.project_distinct
-- @title: PROJECT with DISTINCT → hash aggregate (duplicate elimination)
-- @topic: Algorithms for PROJECT and set operations
-- @explain: Duplicate elimination: either read guest_id in sorted (index) order and drop repeats (Unique), or use a hash table (HashAggregate). The optimizer picks the cheaper one.
SELECT DISTINCT guest_id FROM bookings;

-- @name: plan.set_operation
-- @title: INTERSECT → hashed set operation
-- @topic: Algorithms for set operations
-- @explain: Both inputs are appended and a HashSetOp counts which rows came from both sides.
SELECT guest_id FROM bookings WHERE hotel_id = 1
INTERSECT
SELECT guest_id FROM bookings WHERE hotel_id = 3;

-- @name: plan.pipelining
-- @title: Pipelining — rows stream through operators without temp tables
-- @topic: Combining operations using pipelining
-- @explain: Scan → join → filter → limit pass rows one at a time. LIMIT stops the whole pipeline early: note "actual rows" far below table size.
SELECT b.booking_ref, h.hotel_name
FROM bookings b JOIN hotels h ON h.hotel_id = b.hotel_id
WHERE h.star_rating >= 4
LIMIT 5;

-- @name: plan.heuristic_pushdown
-- @title: Heuristic optimization — selection pushed below the join
-- @topic: Using heuristics in query optimization
-- @explain: We wrote the filter on cities after a 3-way join, but the planner applies σ city_name = 'Udaipur' first (on the cities scan), so the joins handle a few rows instead of thousands.
SELECT count(*)
FROM bookings b
JOIN hotels h ON h.hotel_id = b.hotel_id
JOIN cities c ON c.city_id = h.city_id
WHERE c.city_name = 'Udaipur';

-- @name: plan.partition_pruning
-- @title: Distributed fragments — only the relevant "site" is scanned
-- @topic: Unit 5 › Distributed DB (fragment pruning)
-- @explain: The query asks for SOUTH only, so the planner scans lab.site_south and skips the other five fragments.
SELECT count(*) FROM lab.bookings_by_region WHERE region = 'SOUTH';

-- @name: plan.gin_fulltext
-- @title: Full-text search → GIN (inverted) index
-- @topic: Unit 5 › Digital libraries (inverted index)
-- @explain: The GIN index maps each word stem to the hotels containing it, so the search does not read every description.
SELECT hotel_name FROM hotels WHERE search_doc @@ websearch_to_tsquery('english', 'heritage palace lake');
