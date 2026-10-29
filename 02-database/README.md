# 02 · Database (PostgreSQL 16, database `yupreserved`, port 5433)

```
build.sql             rebuild everything:  scripts/db.sh build
schema/
  01_types.sql        extensions, DOMAINs (rupees, indian_mobile, email_address…), ENUM types
  02_tables.sql       the 15 tables with every key and constraint, named pk_/uq_/fk_/ck_/ex_
  03_functions.sql    fn_quote_stay, fn_available_rooms, fn_book_stay, sp_cancel_booking …
  04_triggers.sql     8 triggers (double booking, status machine, deferred capacity check …)
  05_indexes.sql      FK, composite, partial, GIN full-text, trigram and expression indexes
  06_views.sql        v_hotel_cards, v_booking_summary, v_guest_directory, v_upcoming_arrivals, mv_city_performance
  07_roles.sql        yup_app, yup_analyst, yup_lab — GRANT / REVOKE
seed/load_data.sql    \copy from 01-dataset/processed, then prices & payments derived in SQL
lab/lab_objects.sql   schemas staging + lab: raw data, UNF→5NF, OODB, fragments, media, txn demo
queries/              66 named queries, each with relational algebra and an explanation
demos/
  why_not.sql         16 statements the database must refuse
  query_processing.sql 15 EXPLAIN demonstrations (scans, joins, sorts, pipelining, heuristics)
```

## The 15 tables

| group | tables |
|-------|--------|
| geography | states · cities · landmarks |
| property  | hotels · hotel_landmarks · amenities · hotel_amenities |
| inventory | room_types · rooms · seasons |
| customer  | guests |
| booking   | bookings · booking_rooms · payments · reviews |

15 primary keys (11 single-column, 4 composite) · 17 foreign keys · 15 UNIQUE · 33 CHECK/EXCLUDE · 8 triggers.

## Connect

```bash
scripts/db.sh psql                         # as postgres
psql -h localhost -p 5433 -U yup_analyst yupreserved   # password yup_analyst (views only)
```
