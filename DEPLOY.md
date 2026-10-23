# Deployment

## A. Render pilot (demo mode, synthetic data only)

1. Push the repo to GitHub.
2. Render dashboard → New → Blueprint → select the repo. Render reads `render.yaml`
   and shows a preview (web service and Postgres: 2 resources). Fix any schema errors it reports.
3. When prompted for `sync: false` variables, set `TELEGRAM_BOT_TOKEN` (optional) and
   `ANTHROPIC_API_KEY` (optional). `SECRET_KEY` and `DATABASE_URL` are filled automatically.
4. Deploy. Pre-deploy runs `python -m app.predeploy` (migrations, then demo seed); the health check is `/api/health`.
5. Open the service URL: the amber banner «Демо-режим: не вводите реальные данные пациентов»
   must be visible. Never enter real patient data.
6. Demo credentials are printed once in the deploy log (look for `DEMO CREDENTIALS`) by the
   pre-deploy seed, never in the UI. Logins: doctor1, doctor2, nurse1, anaesth1, head1,
   headnurse1, admin1. The seed runs only when the database has no users.

Cron jobs live in `render-cron.yaml` so the main Blueprint stays at 2 resources (Render limits
resources per workspace). They are stubs until Phase 3. To add them, create a second Blueprint with
file path `render-cron.yaml`. If Render rejects its `fromDatabase` reference to a database from
another Blueprint, set `DATABASE_URL` by hand on each cron job (copy the internal connection string).
Cron runs in UTC: digest `0 13 * * *` (= 18:00 Asia/Tashkent), lab expiry `0 2 * * *`.

## B. Hospital server or Uzbek cloud (real patients)

Required by Uzbekistan's personal data law: data stored on servers in Uzbekistan.

1. Host with Docker and Docker Compose; a PostgreSQL 16 instance (compose `db` service or managed).
2. Create `.env` from `.env.example`: `ENV=production`, `DEMO_MODE=false`, a strong `SECRET_KEY`,
   `DATABASE_URL`, `STORAGE_BACKEND` (`local` or `s3`).
3. Build the image: `docker build -t orthoready .`. Apply migrations:
   `docker run --rm --env-file .env orthoready alembic upgrade head`. Create the first administrator:
   `docker run --rm -it --env-file .env orthoready python -m app.create_admin --login admin --full-name "Администратор"`
   (password prompted, or set `ADMIN_PASSWORD`). No demo data is created when `DEMO_MODE=false`.
   Run: `docker run -d --env-file .env -p 8000:8000 orthoready`.
4. Put a TLS reverse proxy (nginx/Caddy) in front; cookies are `Secure`.
5. Schedule jobs with the host cron (use local time, no UTC conversion needed if the host is set to
   Asia/Tashkent): `docker run --env-file .env orthoready python -m app.jobs.daily_digest` at 18:00,
   `python -m app.jobs.lab_expiry` daily.
6. Back up the database nightly.

The image has no Render-specific code; everything is configured via environment variables.
