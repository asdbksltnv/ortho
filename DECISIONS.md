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

## Render resource limit
- Render rejected the 4-resource Blueprint (workspace limit of 25 resources). Cron jobs moved to
  `render-cron.yaml`; `render.yaml` has the web service and database only.
- Unverified: whether a second Blueprint may reference `orthoready-db` through `fromDatabase`.
- Render does not shell-parse `dockerCommand`: `sh -c "uvicorn ..."` was run as one executable name
  (exit 127). The web service now relies on the Dockerfile `CMD`, which reads `$PORT`.

## Phase 1 (foundation and readiness board)
- **Ready rules** (`app/domain/readiness.py`): `always` blocks unless done/not_applicable;
  `day_of_surgery` blocks from the planned date onwards (never when no date is set);
  `per_procedure` blocks when the procedure template lists the item in `blocking_items`;
  `if_applicable` blocks when its `auto_applies_flag` is set on the case (`takes_anticoagulant`).
  For both of the last two, an item someone has set to `pending` or `problem` also blocks until
  resolved. `not_applicable` never blocks. Emergency cases compute Ready the same way; the
  emergency exemption is applied when calling to the OR (Phase 3).
- **Checklist permissions** (`app/domain/permissions.py`): head of department any item; doctor any
  item except `anaesthesia` on their own patients; nurse and head nurse the nurse-owned items plus
  `consent_surgical` (consent received on the ward); anaesthesiologist only `anaesthesia`.
  "Full edit of their own patients' cases" for doctors was read as excluding anaesthesia clearance.
- **Admin has no clinical access at all**: not even read access to the board or cases (section 4
  gives admin no clinical rights). Admin can read the audit log and config status.
- **Only the head reassigns the treating doctor**; a doctor creating a case is its treating doctor.
- **Initials** are the first letters of up to three name parts ("И. А. Д.").
- **Sessions**: JWT in an httpOnly cookie plus a signed CSRF claim echoed from a readable
  `csrf_token` cookie in `X-CSRF-Token`. The cookie is re-issued on every authenticated request
  (sliding expiry), so the inactivity timeout is `SESSION_TIMEOUT_MIN`. The SPA also logs out
  client-side after the same idle period. `Secure` defaults to on in production.
- **Login rate limit** is in-memory per process (5 failures / 15 min per ip+login). Adequate for the
  single-instance pilot; move to the database or Redis before running several instances.
- **Argon2** uses library defaults in production; tests use cheap parameters.
- **Audit log** is append-only by convention (no code path or route updates or deletes rows); a
  database-level trigger or revoked privileges would be stricter. `diff` holds statuses and flags,
  never notes or free text (`note_changed: true` instead).
- **Concurrency**: checklist updates send `expected_updated_at`; a mismatch returns 409 with the
  current value, and the UI offers to apply the user's value on top.
- **Polling** every 5 s on the board (target: other users' changes within 10 s).
- **Time**: all timestamps are timezone-aware UTC in the database; the UI formats Asia/Tashkent.
  "Today" for readiness uses `TZ_DISPLAY`.
- **Schema**: Phase 1 tables only (users, wards, rooms, beds, patients, cases, checklist items,
  lab results, consents, status events, audit log). Types are portable (UUID, JSON with a JSONB
  variant) so tests run on SQLite while production uses Postgres; migrations were generated and
  round-tripped (up, check, down, up) on a real Postgres 16.
- **Lab results and consents** are recorded but do not change checklist items automatically.
- **Demo seed** runs from `python -m app.predeploy` when `DEMO_MODE=true` and there are no users;
  passwords are random and printed once to stdout. Production uses `python -m app.create_admin`.
- **Short column labels** (`short_label_ru`) were added to the checklist config so the board header
  fits a phone; the full label is the tooltip and the editor title.

## Phase 2 (intake form and EMR documents)
- **Nothing clinical was invented.** Normal-finding sentences are `null` for every system except
  the neurological one (the only one given), so «Норма» for those shows "текст не задан" and the
  generated T1 field stays empty until the department supplies the sentence in
  `config/defaults_ru.yaml`. Columbia question wording, diet names, ICD codes and surgery texts
  (risks, tactics, complications, blood loss) are also `null`/empty with `TODO(clinical)`.
  Picklist options not listed in BUILD_PROMPT (alcohol, tobacco, economic assessment, severity,
  consciousness, position, epidemiological, inspection, movements, ...) are input vocabulary I
  chose; they are in `defaults_ru.yaml`, flagged `requires_clinical_validation`, and any value is
  accepted so editing a list never invalidates saved forms.
- **Procedure templates pre-fill only structure**: the joint segment (knee/hip), the anaesthesia
  consult, the core lab names and the Caprini "elective arthroplasty" / "arthroscopic surgery"
  factors (flagged `TODO(clinical): confirm`). The doctor can change all of it.
- **Caprini**: age factors are automatic from the birth date and today's Tashkent date; the BMI
  factor is also automatic once weight and height are known (a manual tick counts only until
  then). The score is recomputed in the browser (works offline) and on the server; both are tested
  against the same `config/caprini.yaml`.
- **EMR engine** (`app/domain/emr.py`, pure): sources `form`, `generated`, `copy:<tpl>.<key>`,
  `board`, `schedule`, `staff`, `skip`, plus two additions: `case` (e.g. anaesthesia type) and
  `procedure` (surgery texts from the procedure template). Extra field options: `path`,
  `fallback_path` (heart rate falls back to pulse), `override_path` (T3 "copy, then update"),
  `format`, `keep_if_empty`, `only_if`, `required`. Every template is validated at startup:
  unknown intake paths, missing generators, bad `copy:` references and unknown gating items stop
  the app from starting.
- **Sentences** come from Jinja2 templates in `app/templates_ru/` fed with recorded facts only;
  anything not recorded is omitted. "Заключение" is assembled complaints → history → key local
  status → studies → diagnosis. Studies cited are completed board items plus the imaging result the
  doctor typed; planned or pending investigations are never cited. T3 «Ожидаемые технические
  трудности» uses the procedure text only (the "+ local status" part of the spec was not added
  because it would mean inventing how the two combine).
- **EMR prefill (T3)**: a system marked «Норма» shows «Оставить текст EMR»; a changed finding shows
  the new text with «Выделите всё в поле EMR перед вставкой». The epidemiological history keeps
  the EMR text when nothing was recorded.
- **Gating**: T3 needs `labs_core`, `consults` and `anaesthesia` done; `not_applicable` also
  counts, consistent with readiness. T4/T5 are placeholder configs (`awaiting_template`).
- **Outdated detection** compares the stored fields with a fresh render on every read; changed
  fields are highlighted and regeneration keeps the «copied» tick only for fields whose pasted
  value did not change.
- **Copy ticks** are sent to the server one at a time from the browser (and row-locked on
  Postgres) because each one rewrites the document's JSON.
- **Anticoagulant flag**: the intake medication list is the source; saving the form sets
  `case.takes_anticoagulant`, which makes the `anticoag` board item blocking.
- **Offline**: drafts live in IndexedDB (clinical answers only; no name, record number or contact
  data), are pushed every 15 s and on reconnect, each save carrying a client request id (replays
  are applied once). A small case snapshot (birth date, procedure) and the form config are cached
  so the form opens offline; they are cleared on logout, unsynced drafts are kept. The service
  worker caches the app shell only, never API responses. The last signed-in user is remembered in
  localStorage so a ward tablet still opens without a connection.
- **Intake conflicts**: a save based on an older version by a different user returns 409; the form
  offers "load theirs" or "overwrite with mine".
- **Typo guards** on vitals (e.g. pulse 20–250, SpO2 50–100, temperature 30–45) are wide data-entry
  limits, not clinical thresholds.
- **Found by browser tests**: the board sorted bed-less cases first (`"~"` sorts before Cyrillic);
  fixed and covered by a unit test.
