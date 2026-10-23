# OrthoReady

Pre-operative preparation and ward workflow app for the Department of Orthopedics and
Traumatology, Akfa Medline University Hospital, Tashkent. UI in Russian (i18n ready for Uzbek).

One deployable: FastAPI serves the built React app at `/` and the API at `/api/v1`.
Health check: `/api/health`.

**Status: Phases 0-4 built** (scaffold, board, intake and EMR documents, workflow, analytics).
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

The browser suite also contains the axe-core WCAG audit (`a11y.spec.ts`) and the 4G performance
budget for a 60-case board (`perf.spec.ts`).

## Data protection

`render.yaml` is the production configuration (`DEMO_MODE=false`). Uzbekistan's data law requires
real patient data to be stored on servers in Uzbekistan, which Render is not: see DEPLOY.md. No patient identifiers in URLs, logs, Telegram, error reports or LLM requests.
See DEPLOY.md.
