-- ════════════════════════════════════════════════════════════════════════════
--  build.sql  ·  Rebuild the whole YupReserved database from scratch
--
--      cd 02-database && psql -p 5433 -U postgres -d postgres -f build.sql
--  or simply:   scripts/db.sh build
-- ════════════════════════════════════════════════════════════════════════════
\set ON_ERROR_STOP on
\timing off

\echo '▸ creating database yupreserved'
DROP DATABASE IF EXISTS yupreserved WITH (FORCE);
CREATE DATABASE yupreserved ENCODING 'UTF8' TEMPLATE template0;
ALTER DATABASE yupreserved SET timezone TO 'Asia/Kolkata';
\connect yupreserved
SET client_min_messages = warning;
SET timezone = 'Asia/Kolkata';

\echo '▸ schema'
\ir schema/01_types.sql
\ir schema/02_tables.sql
\ir schema/03_functions.sql
\ir schema/04_triggers.sql
\ir schema/05_indexes.sql
\ir schema/06_views.sql

\echo '▸ data'
\ir seed/load_data.sql

\echo '▸ security'
\ir schema/07_roles.sql
\ir schema/08_auth.sql

\echo '▸ lab objects (staging data, normalization, unit-5 demos)'
\ir lab/lab_objects.sql

\echo '▸ done — row counts:'
SELECT relname AS table_name, n_live_tup AS rows
FROM pg_stat_user_tables WHERE schemaname = 'public' ORDER BY relname;
