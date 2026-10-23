# OrthoReady

Pre-operative preparation and ward workflow app for the Department of Orthopedics and
Traumatology, Akfa Medline University Hospital, Tashkent. UI in Russian (i18n ready for Uzbek).

One deployable: FastAPI serves the built React app at `/` and the API at `/api/v1`.
Health check: `/api/health`.

**Status: Phase 2 done (intake form, offline drafts, EMR documents T1-T3).** Phases 3-4 follow BUILD_PROMPT.md.
See DECISIONS.md for assumptions and open items.

## Run with Docker

```bash
docker compose up --build
# http://localhost:8000  (demo mode on, banner visible)
```

## Run for development

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # edit DATABASE_URL if needed
.venv/bin/uvicorn app.main:app --reload --port 8000

cd frontend && npm ci && npm run dev    # http://localhost:5173, proxies /api to :8000
```

## Checks (same as CI)

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app && .venv/bin/pytest
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Browser tests

```bash
cd frontend && npm ci && npm run build          # the tests serve the built app
cd ../e2e && npm ci && npx playwright install chromium && npx playwright test
```

## Data protection

Render pilot = `DEMO_MODE=true`, synthetic data only. Real patient data must run on a server in
Uzbekistan. No patient identifiers in URLs, logs, Telegram, error reports or LLM requests.
See DEPLOY.md.
