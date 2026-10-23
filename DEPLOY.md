# Deployment

## A. Render (production configuration, `DEMO_MODE=false`)

`render.yaml` is now the production configuration: no demo data, no demo banner, strict cookies.

1. In the Render dashboard open the service → **Environment** and set:
   - `ADMIN_PASSWORD` (at least 10 characters; the first administrator, used only while no real
     admin exists), and optionally `ADMIN_LOGIN` (default `admin`) and `ADMIN_FULL_NAME`;
   - `OPENAI_API_KEY` and `AI_MODEL` (the note generator falls back to templates without them);
   - `TELEGRAM_BOT_TOKEN` and `PUBLIC_URL` (optional).
   New variables marked `sync: false` in a Blueprint are not always prompted for on an existing
   service, so add them by hand if they are missing.
2. Redeploy. The pre-deploy step runs `python -m app.predeploy`: migrations, then it creates the
   administrator and **retires the demo accounts** (deactivated, not deleted) and takes the demo
   cases off the board. Demo accounts are switched off only once a real administrator exists, so a
   missing `ADMIN_PASSWORD` cannot lock everyone out; the deploy log says what happened.
3. Log in as the administrator, create the real users (Пользователи) and wards/beds
   (Палаты и койки), then review the amber "clinical configuration not approved" list.
4. **Before entering real patient data, read these limits:**
   - Uzbekistan's personal-data law requires citizens' data to be stored on servers in Uzbekistan.
     Render's regions (Oregon, Ohio, Virginia, Frankfurt, Singapore) are not. Use section B for
     real patients unless the hospital's legal team has approved otherwise.
   - A Render **free** Postgres database expires after 30 days and has no backups. For real data use
     a paid database plan with backups and set `plan:` in `render.yaml` accordingly.
   - The filesystem is ephemeral: wound photos need `STORAGE_BACKEND=s3`.

To run a synthetic-data demo instead, set `DEMO_MODE=true` (shows the banner, seeds seven demo
users and twelve cases, prints their random passwords once in the deploy log, or set
`DEMO_PASSWORD` to choose one) and keep real data out.

Cron jobs run in UTC: digest `0 13 * * *` (= 18:00 Asia/Tashkent), lab expiry `0 2 * * *`.

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

## C. Telegram, jobs, AI notes and photos

- **Telegram**: create a bot with @BotFather, set `TELEGRAM_BOT_TOKEN`. In production use
  `TELEGRAM_MODE=webhook` and set `PUBLIC_URL`; the app registers the webhook at start-up and
  authenticates Telegram with a secret header derived from `SECRET_KEY`. For development leave
  `TELEGRAM_MODE=polling`. Users link their account from **Профиль** (one-time code → `/start <code>`).
- **Jobs** (`python -m app.jobs.<name>`): `daily_digest` 18:00, `lab_expiry` daily, `postop_reminder`
  12:00, `alert_scan` every 30 min. On Render they are in `render-cron.yaml` (UTC schedules); on a
  hospital server use the host cron. `SCHEDULER_ENABLED=true` runs them in-process for development.
- **AI notes**: the deterministic template generator is the fallback. To use OpenAI as the main
  model set `AI_PROVIDER=openai`, `OPENAI_API_KEY` and `AI_MODEL` (a model name available to your
  key); Anthropic works the same way (`AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`). Only de-identified structured data is
  sent; any failure falls back to the template text. Every draft stays locked until a doctor
  presses «Проверено».
- **Wound photos**: disabled in demo mode. Elsewhere `STORAGE_BACKEND=local` (needs a persistent
  folder, `STORAGE_DIR`) or `s3` (`pip install -r requirements-s3.txt`, `S3_BUCKET`, optional
  `S3_ENDPOINT_URL`, `S3_REGION`, and the usual `AWS_*` credentials).
