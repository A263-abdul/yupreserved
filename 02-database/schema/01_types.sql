-- ════════════════════════════════════════════════════════════════════════════
--  01_types.sql  ·  Extensions, DOMAINs and ENUM types
--  Syllabus: Relational model › Types · Integrity (domain constraints)
--
--  A DOMAIN is a named data type with a constraint attached. Every column that
--  uses it inherits the rule, so "what is a valid phone number" is written once.
-- ════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS btree_gist;   -- lets EXCLUDE constraints mix = and &&
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram index for fuzzy name search

-- ── Domains ────────────────────────────────────────────────────────────────
CREATE DOMAIN rupees        AS numeric(12,2) CHECK (VALUE >= 0);
CREATE DOMAIN indian_mobile AS varchar(10)   CHECK (VALUE ~ '^[6-9][0-9]{9}$');
CREATE DOMAIN email_address AS varchar(120)
       CHECK (VALUE ~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$');
CREATE DOMAIN lat_deg       AS numeric(9,6)  CHECK (VALUE BETWEEN -90  AND 90);
CREATE DOMAIN lon_deg       AS numeric(9,6)  CHECK (VALUE BETWEEN -180 AND 180);

-- ── Enumerated types (closed lists of allowed values) ─────────────────────
CREATE TYPE region_t AS ENUM
  ('NORTH', 'SOUTH', 'EAST', 'WEST', 'CENTRAL', 'NORTHEAST');

CREATE TYPE property_type_t AS ENUM
  ('Hotel', 'Resort', 'Guest House', 'Homestay', 'Service Apartment', 'Lodge',
   'Houseboat', 'Cottage', 'Tent', 'Villa', 'BnB', 'Bungalow', 'Palace',
   'Hostel', 'Motel', 'Farm Stay', 'Luxury Yacht', 'Beach Hut',
   'Heritage Hotel', 'Haveli', 'Boutique Hotel');

CREATE TYPE listing_source_t AS ENUM ('GOIBIBO', 'YUPRESERVED');

CREATE TYPE amenity_category_t AS ENUM
  ('ESSENTIALS', 'DINING', 'WELLNESS', 'BUSINESS', 'FAMILY', 'TRANSPORT',
   'SERVICES', 'EXPERIENCE');

CREATE TYPE landmark_category_t AS ENUM
  ('HERITAGE', 'BEACH', 'NATURE', 'TEMPLE', 'MARKET', 'LAKE', 'LANDMARK', 'BUSINESS');

CREATE TYPE bed_type_t AS ENUM ('SINGLE', 'DOUBLE', 'QUEEN', 'KING', 'TWIN', 'BUNK');

CREATE TYPE id_document_t AS ENUM ('PAN', 'PASSPORT', 'DRIVING_LICENCE', 'VOTER_ID');

CREATE TYPE booking_status_t AS ENUM
  ('PENDING', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED', 'NO_SHOW');

CREATE TYPE payment_kind_t   AS ENUM ('CHARGE', 'REFUND');
CREATE TYPE payment_method_t AS ENUM ('UPI', 'CARD', 'NETBANKING', 'WALLET', 'PAY_AT_HOTEL');
CREATE TYPE payment_status_t AS ENUM ('SUCCESS', 'FAILED', 'PENDING');
