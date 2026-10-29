"""
Vercel entry point
==================
The FastAPI app from 03-backend, run as one Vercel serverless function.
vercel.json rewrites every /api/* request here; the website is served as static files.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03-backend"))

from app.db import lab_pool, pool  # noqa: E402
from app.main import app  # noqa: E402,F401  (Vercel loads the top-level name `app`)

# A serverless runtime may not run the ASGI lifespan, so open the pools on import.
# If the lifespan does run, its open() on an already open pool does nothing.
pool.open()
lab_pool.open()
