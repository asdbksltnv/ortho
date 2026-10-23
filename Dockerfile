# syntax=docker/dockerfile:1

# ---- Stage 1: build the frontend ----
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime serving API + built frontend ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY app ./app
COPY config ./config
COPY migrations ./migrations
COPY --from=frontend /frontend/dist ./frontend/dist

RUN useradd --system --uid 10001 appuser
USER appuser

EXPOSE 8000
# PORT is provided by Render; defaults to 8000 elsewhere.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
