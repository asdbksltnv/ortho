# Deployment

## A. Render pilot (demo mode, synthetic data only)

1. Push the repo to GitHub.
2. Render dashboard → New → Blueprint → select the repo. Render reads `render.yaml`
   and shows a preview (web service, Postgres, two cron jobs). Fix any schema errors it reports.
3. When prompted for `sync: false` variables, set `TELEGRAM_BOT_TOKEN` (optional) and
   `ANTHROPIC_API_KEY` (optional). `SECRET_KEY` and `DATABASE_URL` are filled automatically.
4. Deploy. Pre-deploy runs `alembic upgrade head`; the health check is `/api/health`.
5. Open the service URL: the amber banner «Демо-режим: не вводите реальные данные пациентов»
   must be visible. Never enter real patient data.
6. Demo credentials will be printed in the deploy log by the Phase 1 seed command, never in the UI.

Cron jobs run in UTC: digest `0 13 * * *` (= 18:00 Asia/Tashkent), lab expiry `0 2 * * *`.

## B. Hospital server or Uzbek cloud (real patients)

Required by Uzbekistan's personal data law: data stored on servers in Uzbekistan.

1. Host with Docker and Docker Compose; a PostgreSQL 16 instance (compose `db` service or managed).
2. Create `.env` from `.env.example`: `ENV=production`, `DEMO_MODE=false`, a strong `SECRET_KEY`,
   `DATABASE_URL`, `STORAGE_BACKEND` (`local` or `s3`).
3. Build and run: `docker build -t orthoready .`, then
   `docker run --env-file .env -p 8000:8000 orthoready`, after `alembic upgrade head`
   (`docker run --env-file .env orthoready alembic upgrade head`).
4. Put a TLS reverse proxy (nginx/Caddy) in front; cookies are `Secure`.
5. Schedule jobs with the host cron (use local time, no UTC conversion needed if the host is set to
   Asia/Tashkent): `docker run --env-file .env orthoready python -m app.jobs.daily_digest` at 18:00,
   `python -m app.jobs.lab_expiry` daily.
6. Back up the database nightly.

The image has no Render-specific code; everything is configured via environment variables.
