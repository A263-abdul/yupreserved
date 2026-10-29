# 04 · CLI — `yup`

Everything the website does — and every DBMS demonstration — from the terminal. It reuses the
backend's own modules, so it runs exactly the SQL the website runs, with every constraint and
trigger in force.

## How to open it

1. Open **Terminal** (or the terminal inside VS Code: *View → Terminal*).
2. Go to the project folder and make sure the database is running:
   ```bash
   cd "~/DBMS-Project hotel management system"
   scripts/db.sh start
   ```
3. Run it:
   ```bash
   ./yup            # an interactive menu: type a number, press Enter
   ./yup --help     # every command
   ```
4. Optional — use it from any folder: `./yup install` (adds `alias yup=…` to `~/.zshrc`, asks first),
   open a new terminal, then just type `yup`.

## Actions (change or read business data)

| command | does |
|---------|------|
| `yup search Udaipur --in 2026-12-24 --out 2026-12-26 --stars 4` | search stays (city or landmark), exact totals for dates |
| `yup search "Gateway of India"` | stays near a landmark, nearest first |
| `yup hotel 3` | a hotel: story, room types (with ids), landmarks, amenities |
| `yup avail 3 2026-12-24 2026-12-26` | free rooms per type and the total price |
| `yup quote 7 2026-12-24 2026-12-26` | night-by-night price (season × weekend × GST) |
| `yup signup` | create a guest (asks for each field) |
| `yup book --phone 9811122233 --room-type 7 --in 2027-01-12 --out 2027-01-14` | book through `fn_book_stay` |
| `yup booking YRSFGND3` | a booking with its rooms and payments |
| `yup cancel YRSFGND3` | cancel through `sp_cancel_booking`, shows the refund first |
| `yup review YRSFGND3 -r 5 -t "Lovely"` | review a completed stay |
| `yup guest 9811122233` / `yup trips 26001` | a guest and their bookings |
| `yup stats` | dashboard: totals, top cities, payment mix |
| `yup sql "UPDATE … " --write` | any SQL that changes data (asks, then commits) |

## DBMS demonstrations

| command | shows |
|---------|-------|
| `yup tables` · `yup keys` · `yup describe bookings` · `yup show hotels -n 10` | schema, keys, rows |
| `yup queries -t join` · `yup q joins.full_outer` | named queries with relational algebra |
| `yup plans` · `yup explain plan.external_sort` | how PostgreSQL executes queries |
| `yup why` · `yup why why.double_booking` | statements the database refuses, and the rule |
| `yup txn double_booking_race` · `deadlock` · `isolation_levels` · `mvcc_versions` · `atomic_rollback` | concurrency with two real sessions |
| `yup recovery` | crash recovery from the write-ahead log |
| `yup sql "SELECT …"` | any read-only SQL |
