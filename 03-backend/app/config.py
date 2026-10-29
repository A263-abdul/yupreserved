"""Settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATABASE_URL = os.getenv(
    "YUP_DATABASE_URL",
    "postgresql://yup_app:yup_app@localhost:5433/yupreserved",
)
# "Why can't I…?" scenarios must reach the constraint they demonstrate, so they
# run as yup_lab (full DML). Every lab statement is rolled back.
LAB_DATABASE_URL = os.getenv(
    "YUP_LAB_DATABASE_URL",
    "postgresql://yup_lab:yup_lab@localhost:5433/yupreserved",
)
FRONTEND_ORIGINS = os.getenv(
    "YUP_FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# The simulated platform's "today" (matches the dataset pipeline)
TODAY = os.getenv("YUP_TODAY", "2026-10-29")
