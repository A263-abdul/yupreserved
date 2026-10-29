# YupReserved — a hotel reservation system for India

DBMS course project. Real hotel listings from **543 Indian cities**, normalised into a
**15-table PostgreSQL database (408,192 rows)**, with a FastAPI backend, a terminal CLI and a
React website. Every syllabus topic, from ER modelling to crash recovery, can be demonstrated live.

```
01-dataset/    raw dataset → cleaning pipeline → one clean CSV per table
02-database/   schema (15 tables, keys, constraints, triggers, functions, views, roles),
               seed script, 66 named queries, demos (why-not, query plans), lab objects
03-backend/    FastAPI app: plain SQL, every response carries the SQL it ran
04-cli/        ./yup — browse tables, run queries, plans, constraint & transaction demos
05-frontend/   the YupReserved website (React + TypeScript)
06-docs/       ER / architecture / workflow diagrams and the project report (PDF)
scripts/       db.sh (start / stop / build) · start.sh (everything at once) · deploy-db.sh
yup            CLI launcher
api/ · vercel.json          Vercel deployment (static website + the API as a Python function)
Dockerfile · render.yaml   one-container deployment (API + website)
```

The project log and report is also kept on the Desktop:
`~/Desktop/YupReserved Project Log/YupReserved_Project_Log.pdf` (updated after every session).

## Run it

```bash
scripts/start.sh                 # PostgreSQL + API (8000) + website (5173)
open http://localhost:5173
./yup tables                     # the 15 tables from the terminal
```

First time only, or to rebuild everything from the dataset:

```bash
scripts/db.sh start
scripts/db.sh build              # ~3 minutes: schema → 408k rows → roles → lab objects
```

The PostgreSQL server, its data directory and the Python environment live in `~/.yupreserved/`,
outside this folder, which keeps the project tree clean.

## The CLI

```bash
./yup                 # interactive menu
./yup --help          # all commands — see 04-cli/README.md
./yup install         # then type `yup` from any folder
```

## On a phone (installable app)

YupReserved is a Progressive Web App. Open the site on a phone and choose **Install app**
(Android / Chrome) or **Share → Add to Home Screen** (iPhone). It opens full-screen with a bottom
tab bar, and pages you have visited keep working on a poor connection.

## Sign-in with OTP

Codes are random, stored only as an HMAC hash (`auth.otp_challenges`), valid 5 minutes, 5 tries,
3 sends per 10 minutes. Real SMS needs a provider — set on the server:

| provider | variables |
|----------|-----------|
| demo (default) | `YUP_SMS_PROVIDER=console` — the code is shown on screen and in the server log |
| Fast2SMS (India) | `YUP_SMS_PROVIDER=fast2sms`, `FAST2SMS_API_KEY=…`, `YUP_OTP_DEMO=0` |
| Twilio | `YUP_SMS_PROVIDER=twilio`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `YUP_OTP_DEMO=0` |

## Deploy

The database goes to a hosted PostgreSQL first (e.g. [Neon](https://neon.tech), free):

```bash
scripts/deploy-db.sh "postgresql://OWNER:PASSWORD@HOST/neondb?sslmode=require"
```

It copies the data, gives the app roles fresh random passwords and prints `YUP_DATABASE_URL`,
`YUP_LAB_DATABASE_URL` and `YUP_SECRET`. Then host the site in one of two ways:

| | Vercel | Render |
|---|---|---|
| how | *Add New → Project*, import this repository | *New → Blueprint*, pick this repository |
| config read | `vercel.json` — website as static files, the API as one Python function (`api/index.py`) | `render.yaml` + `Dockerfile` — one container |
| environment | paste the three printed variables | paste the two database URLs (the secret is generated) |
| idle | no sleep; cold start ≈ 1–2 s | free plan sleeps; wakes in ≈ 30 s |

## A 10-minute viva demo

| # | show | how |
|---|------|-----|
| 1 | The 15 tables and their keys | `./yup tables`, `./yup keys`, website → *Under the hood → Overview & ER* |
| 2 | A table's constraints | `./yup describe bookings` |
| 3 | Price for two nights | `./yup quote 1 2026-12-24 2026-12-26` or any hotel page → *Price breakdown* |
| 4 | Search by landmark | website: type *Gateway of India* → results sorted by real distance |
| 5 | Book a stay | sign in with a demo guest (OTP is shown on screen) → Reserve → Confirm |
| 6 | The SQL behind it | the floating **SQL · Under the hood** button on every page |
| 7 | "Why can't I…?" | `./yup why` (16 rules), or *Under the hood → Why can't I…?* |
| 8 | Joins, division, calculus | `./yup q joins.full_outer`, `./yup q division.not_exists`, `./yup q calculus.trc` |
| 9 | Normalisation on real data | `./yup q nf.unf` → `nf.first` → `nf.second` → `nf.third` → `nf.fourth` → `nf.fifth` |
| 10 | Query processing | `./yup explain plan.external_sort`, `plan.merge_join`, `plan.heuristic_pushdown` |
| 11 | Concurrency | `./yup txn double_booking_race`, `./yup txn deadlock`, `./yup txn isolation_levels` |
| 12 | Crash recovery | `./yup recovery` |

## Photos

Listings carry no photos, so each hotel shows a real photo of its nearest landmark or its city,
from Wikimedia Commons under free licences, credited on screen (`01-dataset/pipeline/fetch_photos.py`).

## Stack

PostgreSQL 16 · Python 3.13 (pandas, FastAPI, psycopg 3, Typer, Rich, ReportLab) ·
React 18 · TypeScript · Vite · Tailwind CSS 4 · Motion · TanStack Query · Graphviz
