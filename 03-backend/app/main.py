"""
YupReserved API
===============
FastAPI application between the React frontend and PostgreSQL.

    browser  ──HTTP/JSON──►  FastAPI (this app)  ──SQL──►  PostgreSQL 16

Run:   cd 03-backend && uvicorn app.main:app --reload --port 8000
Docs:  http://localhost:8000/docs   (interactive, generated from the code)
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_ORIGINS
from .db import fetch_one, lab_pool, pool, transaction
from .errors import db_error_handler
from .routers import booking_routes, catalog_routes, lab_routes


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open(wait=True)
    lab_pool.open()
    yield
    lab_pool.close()
    pool.close()


app = FastAPI(
    title="YupReserved API",
    version="1.0.0",
    description="Hotel reservation platform for India — DBMS project. Every response carries a "
                "`trace` of the SQL that produced it.",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.add_exception_handler(psycopg.Error, db_error_handler)

app.include_router(catalog_routes.router)
app.include_router(booking_routes.router)
app.include_router(lab_routes.router)


@app.get("/api/health", tags=["meta"])
def health():
    with transaction(read_only=True) as conn:
        row = fetch_one(conn, "SELECT current_database() AS database, current_user AS role, "
                              "split_part(version(), ' ', 2) AS postgres, now() AS server_time")
    return {"status": "ok", **row}


# ── production: serve the built website from the same origin ─────────────
# YUP_STATIC_DIR points at 05-frontend/dist (set in the Dockerfile). Unknown
# paths fall back to index.html so React Router can handle /stay/3 etc.
STATIC = Path(os.getenv("YUP_STATIC_DIR", "")) if os.getenv("YUP_STATIC_DIR") else None
if STATIC and STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = (STATIC / path).resolve()
        if path and file.is_file() and STATIC.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
