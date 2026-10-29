# ─────────────────────────────────────────────────────────────────────────────
#  YupReserved — one container: FastAPI API + the built React website
#  The database is external (Neon / Render Postgres / any PostgreSQL 14+),
#  given through YUP_DATABASE_URL and YUP_LAB_DATABASE_URL.
# ─────────────────────────────────────────────────────────────────────────────

# 1 · build the website
FROM node:20-alpine AS web
WORKDIR /web
COPY 05-frontend/package.json 05-frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY 05-frontend/ ./
RUN npm run build

# 2 · the API, serving the website from the same origin
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    YUP_STATIC_DIR=/app/05-frontend/dist PORT=8000
WORKDIR /app
COPY 03-backend/requirements.txt 03-backend/requirements.txt
RUN pip install --no-cache-dir -r 03-backend/requirements.txt
# the API reads the named-query library and demo files from 02-database
COPY 02-database/queries 02-database/queries
COPY 02-database/demos 02-database/demos
COPY 03-backend 03-backend
COPY --from=web /web/dist 05-frontend/dist
RUN useradd --create-home yup
USER yup
WORKDIR /app/03-backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
