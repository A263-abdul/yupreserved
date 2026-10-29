-- ════════════════════════════════════════════════════════════════════════════
--  05_indexes.sql  ·  Secondary indexes
--  Syllabus: Query processing & optimisation · Database tuning
--
--  PRIMARY KEY and UNIQUE constraints already create B-tree indexes.
--  PostgreSQL does NOT index foreign-key columns automatically, so the joins
--  and the ON DELETE checks below would otherwise scan the whole child table.
-- ════════════════════════════════════════════════════════════════════════════

-- foreign keys (join columns)
CREATE INDEX ix_cities_state            ON cities (state_code);
CREATE INDEX ix_landmarks_city          ON landmarks (city_id);
CREATE INDEX ix_hotels_city             ON hotels (city_id);
CREATE INDEX ix_hotel_landmarks_lmk     ON hotel_landmarks (landmark_id);
CREATE INDEX ix_hotel_amenities_amenity ON hotel_amenities (amenity_id);
CREATE INDEX ix_rooms_room_type         ON rooms (room_type_id);
CREATE INDEX ix_guests_home_city        ON guests (home_city_id);
CREATE INDEX ix_guests_referred_by      ON guests (referred_by);
CREATE INDEX ix_bookings_guest          ON bookings (guest_id);
CREATE INDEX ix_booking_rooms_room      ON booking_rooms (room_id);
CREATE INDEX ix_payments_booking        ON payments (booking_id);

-- composite index: "bookings of this hotel in this date window"
CREATE INDEX ix_bookings_hotel_dates    ON bookings (hotel_id, check_in, check_out);

-- partial index: only live bookings are searched for availability
CREATE INDEX ix_bookings_live_checkin   ON bookings (check_in)
       WHERE status IN ('PENDING', 'CONFIRMED', 'CHECKED_IN');

-- full-text search (GIN = inverted index, like the index at the back of a book)
CREATE INDEX ix_hotels_search_doc       ON hotels USING gin (search_doc);

-- fuzzy name search:  WHERE hotel_name % 'samudra mahl'
CREATE INDEX ix_hotels_name_trgm        ON hotels USING gin (hotel_name gin_trgm_ops);
CREATE INDEX ix_landmarks_name_trgm     ON landmarks USING gin (landmark_name gin_trgm_ops);

-- expression index for case-insensitive city lookup
CREATE INDEX ix_cities_lower_name       ON cities (lower(city_name));
