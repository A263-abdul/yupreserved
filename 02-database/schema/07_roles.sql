-- ════════════════════════════════════════════════════════════════════════════
--  07_roles.sql  ·  Database users and privileges (DCL: GRANT / REVOKE)
--  Syllabus: Database users · Database languages (DCL) · Security via views
--
--   role          who                         can do
--   postgres      DBA                         everything (owner of all objects)
--   yup_app       the FastAPI backend         read all tables, write booking data,
--                                             run the booking functions
--   yup_analyst   the business analyst        SELECT on views only; no personal data
--   yup_lab       the "Under the hood" lab    full DML so constraint demos reach the
--                                             constraint; every lab statement is rolled back
-- ════════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_app') THEN
        CREATE ROLE yup_app LOGIN PASSWORD 'yup_app';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_analyst') THEN
        CREATE ROLE yup_analyst LOGIN PASSWORD 'yup_analyst';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_lab') THEN
        CREATE ROLE yup_lab LOGIN PASSWORD 'yup_lab';
    END IF;
END
$$;

-- start from nothing, then grant only what is needed (principle of least privilege)
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE yupreserved TO yup_app, yup_analyst, yup_lab;
GRANT USAGE ON SCHEMA public TO yup_app, yup_analyst, yup_lab;

-- backend
GRANT SELECT ON ALL TABLES IN SCHEMA public TO yup_app;
GRANT INSERT, UPDATE ON bookings, booking_rooms, payments, reviews, guests TO yup_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO yup_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO yup_app;
GRANT EXECUTE ON PROCEDURE sp_cancel_booking(integer) TO yup_app;
-- the app may never delete bookings or payments: history is kept forever
REVOKE DELETE ON bookings, payments FROM yup_app;

-- analyst: views only
GRANT SELECT ON v_hotel_cards, v_hotel_photo, v_booking_summary, v_guest_directory, mv_city_performance TO yup_analyst;
REVOKE ALL ON guests FROM yup_analyst;

-- lab: may try anything (the lab always rolls back) and may switch to the analyst role
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO yup_lab;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO yup_lab;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO yup_lab;
GRANT yup_analyst TO yup_lab;
