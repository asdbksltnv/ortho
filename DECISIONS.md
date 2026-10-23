# Decisions and open items

## Phase 0
- **React 18.3.1** pinned (npm's default is 19; the spec says 18).
- **PWA / IndexedDB / form libs** (`vite-plugin-pwa`, `idb`, React Hook Form, Zod, Playwright) are
  not installed yet; they arrive with Phase 2 where they are first used.
- **Health check** `/api/health` does not touch the database, so a DB outage does not make Render
  restart the web service. A readiness check can be added in Phase 1.
- **SECRET_KEY validation** happens when the web app starts (`validate_for_web`), not in `Settings`,
  so cron jobs need no secret key.
- **CSP** is strict (`'self'` only, no inline styles/scripts), skipped for `/docs` and `/redoc`,
  which are disabled when `ENV=production`.
- **Logging**: JSON lines, no request bodies; exceptions log the class name only.
- **Job stubs** `app/jobs/daily_digest.py`, `lab_expiry.py` only log; real logic is Phase 3.
- **Seed command** for demo data is Phase 1 (needs the schema); `render.yaml` pre-deploy runs only
  `alembic upgrade head` for now.
- **Cron times**: Render cron is UTC. 18:00 Asia/Tashkent (UTC+5, no DST) = `0 13 * * *`.
- **Render plans**: web `starter`, database `free` (Render free Postgres expires after a limited
  period; upgrade before relying on it). `preDeployCommand` may need a paid web plan.

## Not verified
- `docker compose up` and the Docker build were **not run** (Docker is not installed on the dev
  machine); CI has a `docker build` job. Run it once before the Render deploy.
- `render.yaml` was written from the Render Blueprint docs but not validated on Render. Check the
  Blueprint preview when creating it.
- pytest warns that Starlette's TestClient prefers `httpx2`; harmless, revisit on upgrade.
