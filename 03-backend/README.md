# 03 · Backend (FastAPI)

```
app/
  main.py            application, CORS, error handler, /api/health
  config.py          connection strings (env vars, see .env.example)
  db.py              psycopg 3 connection pools + Trace (the SQL shown in the website)
  catalog.py         parser for the annotated .sql files in 02-database
  errors.py          PostgreSQL error → "which rule refused this, in plain words"
  lab.py             run / EXPLAIN / why-not — always inside a rolled-back transaction
  concurrency.py     two-session demos: race, deadlock, isolation levels, MVCC, atomicity
  routers/
    catalog_routes.py   stats, destinations, search, hotel page, availability, quote
    booking_routes.py   OTP sign-in (mocked), guests, bookings, cancel, review
    lab_routes.py       /api/lab/* — tables, schema, queries, plans, why, concurrency, media
```

No ORM: every statement is plain SQL you can paste into psql. The API connects as **yup_app**
(least privilege); lab scenarios use **yup_lab** and are always rolled back.

```bash
cd 03-backend
~/.yupreserved/venv/bin/uvicorn app.main:app --reload --port 8000
open http://localhost:8000/docs        # interactive API documentation
```
