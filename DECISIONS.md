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

## Phase 3 (workflow)
- **Status flow** (`app/domain/status_flow.py`, pure): forward steps only, plus two reversals
  (cancel a call, revoke an approval) that are head-only and need a reason. Approval is head-only and
  needs a planned date; the call to the OR needs Ready, otherwise the head may override with a
  written reason (shown on the board and case page, stored on the status event for the Phase 4
  KPIs). Emergency cases are not blocked by the checklist. A doctor cannot override, even with a
  reason. Anaesthesiologists and admins never move cases; doctors move only their own patients.
  `in_or` records `operated_on`, which drives the post-op day.
- **Notifications**: every message is built by `case_label()` as «Пал. 3, к. 2 (А. Д.): событие».
  Events: call to OR (treating doctor, all active nurses/head nurses and anaesthesiologists),
  approval, order assigned, result ready, post-op alert, lab expiring before surgery, daily digest
  (each doctor for their cases; head nurse for all), post-op reminder. Each recipient gets an
  in-app row (bell) and, when linked, a Telegram message. Failures are stored in
  `Notification.error` (HTTP status or exception class only; the bot token never appears) and never
  block the action. Order item text is deliberately left out of messages.
- **Telegram**: linking by one-time 8-character code (15 minutes). Webhook requests are authenticated
  by a header secret derived from `SECRET_KEY`; polling runs in a daemon thread for development.
  httpx request logging is set to WARNING because the Bot API URL contains the token.
- **Orders**: only doctors (own patients) and the head create them; nurses and assignees move them
  forward; only a doctor reviews or cancels. A linked order sets the checklist item to `pending`
  and **blocks marking that item done** until every linked order is reviewed or cancelled; it does
  not mark the item done by itself (one reviewed order is not proof the whole item is complete).
  «Мои задачи» = open orders assigned to me, plus results waiting for review on my patients.
  Round mode creates orders with `created_at_round`; its summary lists what the doctor ordered since
  the round started, grouped by patient and by assignee (initials and bed only).
- **Post-op**: entries need the case in returned_to_ward / transferred_icu / post_op and a recorded
  operation date; one entry per calendar day (a second attempt returns the existing id). Only the
  treating doctor or the head records. Day 0 reads «День операции.», later days «N-е сутки после
  операции.». Editing an entry redrafts the note and drops the earlier approval.
- **Notes**: `NoteGenerator` interface with a deterministic template generator (default) and an
  optional LLM generator. The LLM receives only structured values (`llm_safe`: no free text, name,
  birth date or record number; analgesia is reduced to a yes/no); its output must be JSON with
  exactly `general_condition` and `local_status`, within length limits, and the day phrase is
  enforced; anything else falls back to the template text. T6 note fields stay locked (no copy
  button, no clipboard text, server refuses the tick with 409) until the doctor presses
  «Проверено»; approving refreshes an existing T6 document.
- **Alerts**: thresholds in `config/alert_thresholds.yaml` are all null, so nothing alerts until the
  department sets values. An alert notifies the treating doctor once per new alert code per entry.
- **Photos**: raw-body upload (no multipart dependency) validated by size and magic bytes, stored
  through the storage interface (local / S3 / disabled; disabled when `DEMO_MODE=true`). The client
  can never set the photo key. S3 needs the optional `requirements-s3.txt`.
- **Charts** follow the dataviz guidance: one series per chart (title names it, no legend box),
  2 px line, 8 px markers with a surface ring, recessive grid, hover/focus tooltip, table view, and
  the palette's blue (categorical slot 1) with a dark-mode variant. The wound-status series is a
  table because it is categorical per day.
- **Cron limit**: `render-cron.yaml` now has four jobs; deploy it as a second Blueprint when the
  workspace has room (see the earlier note about Render's resource limit).
- **Browser tests** found a header overflow at 360 px and a long-label overflow in the orders panel;
  both fixed and the 360 px check now covers the case page.

## Phase 4 (analytics and polish)
- **KPIs** (head of department and head nurse only), over a period filtered by admission date
  (default: last 90 days):
  - *median admission → Ready*: `first_ready_at − admitted_at` over cases that ever became Ready
    (`first_ready_at` is set the first time readiness holds and never cleared);
  - *most frequent blocking items*: the items currently blocking each active (not discharged) case
    admitted in the period, counted per item;
  - *overrides*: every call to the OR made by the head with a reason, newest first (case label is
    initials and bed only);
  - *not Ready the evening before surgery*: among cases whose planned surgery date has arrived and
    that proceeded to the OR (emergencies excluded), those that were never Ready or only became
    Ready after 18:00 (Asia/Tashkent) on the previous day. This uses `first_ready_at`, so a case
    that was Ready and later lost readiness is not counted; a readiness history table would be
    needed for that.
- **CSV export** contains aggregates only (period, counts, median, per-item blocking counts): no
  patient, bed, initials, case id or override reason. Each export is written to the audit log
  (`export`).
- **QR label**: initials, room/bed, procedure, planned date and a QR code to `/case/<uuid>`; no full
  name and no record number. The QR is drawn as an SVG path from the `qrcode` module matrix (no
  injected HTML). Opening the link without a session goes to the login form and returns to the case
  afterwards (`?next=`, same-site paths only).
- **Audit viewer** (admin and head of department): filter by entity and action, shows who acted.
- **Performance**: route-level code splitting (main chunk 109 KB gzip; each page 1-10 KB),
  gzip for API and static files, immutable caching for fingerprinted assets, no-cache for the shell.
  The board runs a constant number of SQL queries (tested with 6 vs 60 cases); 60 cases serialise to
  well under 20 KB gzipped. Measured with Playwright on a Pixel 5 profile, CPU 4x slower and a
  9 Mbps / 170 ms 4G profile: about 1.0 s cold and warm (budget 1.5 s). This is an emulation on a
  development machine, not a real device.
- **Accessibility**: axe-core (WCAG 2.0/2.1 A and AA, including colour contrast) runs on every
  screen and dialog in the browser suite. It found two real issues (a button whose accessible name
  did not contain its visible text, and an ARIA label on an SVG circle without a role), plus
  list semantics on the document page; all fixed. Status is never colour-only (distinct shapes and
  text labels, unit-tested). Automated checks cannot replace a screen-reader and keyboard review
  with real users.
- **Load data**: `seed_extra_cases()` adds synthetic cases (rooms, beds, checklists) for load and
  performance checks; it is used by the tests and the performance project in `e2e/`.

## OpenAI as the main note model
- `AI_PROVIDER=openai` uses the Chat Completions API (`POST {OPENAI_BASE_URL}/chat/completions`,
  JSON mode, `max_completion_tokens`) with `OPENAI_API_KEY` and `AI_MODEL`; Anthropic remains an
  alternative. It was **not tested against the live OpenAI API** (only against a mocked transport),
  so the first real call should be checked; any HTTP error, bad shape or invalid JSON falls back to
  the template text. The model name is deliberately not hard-coded: set `AI_MODEL`.
- The privacy rules are unchanged and tested for OpenAI too: only `llm_safe()` data is sent (no
  name, birth date, record number or free text), and every draft stays locked until a doctor presses
  «Проверено». Note that this data still leaves the server for a third party; for real patients,
  check the hospital's data-protection requirements and the provider's data-use terms first.
- `DEMO_PASSWORD` (optional, DEMO_MODE only) sets one known password on the seven demo users at each
  deploy, as an alternative to the random passwords printed once in the deploy log.

## Production switch on Render
- `render.yaml` and `render-cron.yaml` now set `DEMO_MODE=false`. The pre-deploy step creates the
  first administrator from `ADMIN_PASSWORD` (never overwriting an existing account), and retires
  the demo users and demo cases only after a real administrator exists, so it cannot lock the
  deployment. Retired demo users are deactivated rather than deleted because audit rows reference them.
- **Not resolved by this switch**: the original requirement that real patient data live on a server
  in Uzbekistan (Render has no such region) and Render's free Postgres expiry (30 days, no backups).
  These are legal and operational decisions for the hospital; DEPLOY.md lists them.

## Floor layout (10th floor)
- `config/floor_plan.yaml` reproduces the 10th-floor evacuation plan (AKFA MEDLINE, 1 December 2025):
  patient rooms 1001-1016 plus the staff room, two procedure rooms, dressing room, two storerooms,
  two toilets, two lifts and two stair exits, with approximate coordinates (a test checks that no
  rooms overlap). It is applied at every deploy (`python -m app.floorplan`, also run by
  `app.predeploy`): rooms are matched by name, positions updated, beds only ever added.
- **One bed per patient room is assumed** (the plan does not show beds). Change `beds:` in the file
  or add beds under «Палаты и койки».
- The board has a «План этажа» view: each patient room shows the bed occupants by initials with
  ✔/✖ (shape and text, not colour alone), free beds as «свободно», and opens the case on click or
  Enter. The demo seed now places its cases in these rooms. The old placeholder ward («Пал. 1-4»)
  stays in existing databases; deactivate its beds if it is not needed.
