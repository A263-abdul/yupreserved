#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Copy the local YupReserved database to a hosted PostgreSQL (Neon, Render,
#  Supabase, …) and print the two connection strings the web service needs.
#
#    scripts/deploy-db.sh "postgresql://OWNER:PASSWORD@HOST/DBNAME?sslmode=require"
#
#  The URL is the OWNER / admin connection string your provider gives you.
#  The app roles get NEW random passwords (never the demo ones used locally).
# ---------------------------------------------------------------------------
set -euo pipefail
TARGET="${1:?usage: scripts/deploy-db.sh <admin postgres url>}"
PG_BIN="$HOME/.yupreserved/env/bin"
DUMP="$(mktemp -d)/yupreserved.dump"

echo "▸ dumping local database"
"$PG_BIN/pg_dump" -h localhost -p 5433 -U postgres -d yupreserved \
  --format=custom --no-owner --no-privileges --file="$DUMP"
du -h "$DUMP"

APP_PW="$(openssl rand -hex 16)"; LAB_PW="$(openssl rand -hex 16)"; AN_PW="$(openssl rand -hex 16)"

echo "▸ creating roles on the target"
"$PG_BIN/psql" "$TARGET" -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_app')     THEN CREATE ROLE yup_app LOGIN;     END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_lab')     THEN CREATE ROLE yup_lab LOGIN;     END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'yup_analyst') THEN CREATE ROLE yup_analyst LOGIN; END IF;
END \$\$;
ALTER ROLE yup_app     PASSWORD '$APP_PW';
ALTER ROLE yup_lab     PASSWORD '$LAB_PW';
ALTER ROLE yup_analyst PASSWORD '$AN_PW';
SQL

echo "▸ restoring (a few minutes)"
"$PG_BIN/pg_restore" --dbname="$TARGET" --no-owner --no-privileges --clean --if-exists --exit-on-error "$DUMP" || true

echo "▸ re-applying privileges"
DBNAME="$("$PG_BIN/psql" "$TARGET" -Atc 'SELECT current_database()')"
sed "s/DATABASE yupreserved/DATABASE \"$DBNAME\"/" "$(dirname "$0")/../02-database/schema/07_roles.sql" \
  | grep -v "CREATE ROLE\|PASSWORD" | "$PG_BIN/psql" "$TARGET" -q
"$PG_BIN/psql" "$TARGET" -q -f "$(dirname "$0")/../02-database/schema/08_auth.sql"
"$PG_BIN/psql" "$TARGET" -q <<'SQL'
GRANT USAGE ON SCHEMA lab, staging TO yup_app, yup_lab;
GRANT SELECT ON ALL TABLES IN SCHEMA lab, staging TO yup_app, yup_lab;
GRANT UPDATE ON lab.txn_demo TO yup_app;
GRANT EXECUTE ON FUNCTION lab.purge_demo_bookings() TO yup_app;
SQL

HOSTPART="${TARGET#*@}"
echo
echo "✓ done. Set these on the web service:"
echo "  YUP_DATABASE_URL=postgresql://yup_app:$APP_PW@$HOSTPART"
echo "  YUP_LAB_DATABASE_URL=postgresql://yup_lab:$LAB_PW@$HOSTPART"
echo "  YUP_SECRET=$(openssl rand -hex 32)      # Vercel only; Render generates its own"
rm -f "$DUMP"
