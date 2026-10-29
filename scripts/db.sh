#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  YupReserved — local PostgreSQL helper
#
#  The database server lives OUTSIDE the project folder so the workspace stays
#  clean:  binaries -> ~/.yupreserved/env      data -> ~/.yupreserved/pgdata
#
#  usage:  scripts/db.sh start | stop | status | psql | build | reset | stop-crash
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_BIN="$HOME/.yupreserved/env/bin"
PGDATA="$HOME/.yupreserved/pgdata"
PORT=5433
DB=yupreserved

export PATH="$PG_BIN:$PATH"

case "${1:-status}" in
  start)
    pg_ctl -D "$PGDATA" -l "$PGDATA/server.log" -w start
    ;;
  stop)
    pg_ctl -D "$PGDATA" -m fast stop
    ;;
  stop-crash)
    # used by `./yup recovery`: stop WITHOUT a checkpoint, like a power cut
    pg_ctl -D "$PGDATA" -m immediate stop
    ;;
  status)
    pg_ctl -D "$PGDATA" status || true
    ;;
  psql)
    shift
    psql -h localhost -p "$PORT" -U postgres -d "$DB" "$@"
    ;;
  build)
    # Recreate the database from scratch: schema -> data -> lab objects
    cd "$ROOT/02-database"
    psql -h localhost -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -q -f build.sql
    ;;
  reset)
    "$0" stop || true
    "$0" start
    "$0" build
    ;;
  *)
    echo "usage: scripts/db.sh start|stop|status|psql|build|reset" >&2
    exit 1
    ;;
esac
