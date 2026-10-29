# YupReserved — notes for Claude

DBMS course project (hotel reservation system for India) that the user presents in a viva.

## Standing rules from the user
- **After every working session, update the project log PDF.** Append a session entry to
  `06-docs/report/worklog.py` (date, what was built, files added, tables touched, concepts, decisions
  and why, what was verified), then run
  `~/.yupreserved/venv/bin/python 06-docs/report/build_report.py`. It writes
  `~/Desktop/YupReserved Project Log/YupReserved_Project_Log.pdf` and `06-docs/YupReserved_Project_Report.pdf`.
- Exactly **15 core tables** in schema `public`; demo/teaching objects go in schemas `lab` / `staging`.
- Every syllabus topic must stay demonstrable (see Part D of the report, `06-docs/report/viva.py`).
- Keep folders presentable: `01-dataset 02-database 03-backend 04-cli 05-frontend 06-docs scripts` (+ `api/`, required by Vercel).
- Be gentle with the laptop: disk is nearly full; run builds one at a time.

## Environment
- PostgreSQL 16 binaries `~/.yupreserved/env/bin`, data `~/.yupreserved/pgdata`, port **5433**.
  `scripts/db.sh start|stop|build|psql`. Full rebuild ≈ 3 min.
- Python venv `~/.yupreserved/venv` (FastAPI, psycopg, typer, rich, reportlab).
- Roles: `postgres` (owner), `yup_app` (API, least privilege), `yup_lab` (lab, always rolled back), `yup_analyst` (views only).
- The simulated "today" is 2026-10-29 (dataset pipeline and frontend `TODAY`).

## Conventions
- Raw SQL only (no ORM). Named queries live in `02-database/queries/*.sql` with `-- @name/@title/@topic/@algebra/@explain` headers;
  the CLI, API and report all read them through `03-backend/app/catalog.py`.
- New business rules: add a named constraint/trigger, a scenario in `02-database/demos/why_not.sql`,
  and a plain-language entry in `03-backend/app/errors.py`.
- Functions/triggers use `CREATE OR REPLACE`, so `scripts/db.sh psql -f 02-database/schema/03_functions.sql` re-applies them.
