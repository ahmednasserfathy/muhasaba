# PR-03: daily journal and offline counters

PR-02 was accepted and merged before this branch. This vertical slice implements
the locked v1.4 daily cards, official nested counters and atomic local outbox.
No personal library, reports, reminders, Ramadan calendar or fasting-plan API.

## Files and persistence

- `backend/app/modules/journal/`: authenticated daily reads, absolute state/count
  writes, bulk complete/clear, immutable official snapshots and derived scores.
- Alembic `0004`: journal_days, journal_activity_states, journal_adhkar_counts and
  mutation_receipts. First edit snapshots all official items for that day. Reads
  alone create no rows. Snapshot-only counters start at version 0; every explicit
  write increments, including undo. Personal item columns arrive in PR-06b.
- `mobile/lib/features/daily/`: Arabic day/detail UI, exact fraction calculation,
  Drift SQLite cache and persistent ordered outbox. Two local tables store full
  day documents (including catalog definitions) and individual queued operations;
  no redundant normalized cache copies or code generation needed in this slice.
- Auth adds an encrypted account cache for reopening initialized local data during
  transport failures and single-flight refresh for authenticated journal requests.
  A rejected refresh clears credentials; cached identity never authorizes the API.
- OpenAPI snapshot and API/SQLite/widget tests accompany the changes. Blueprint
  source documents remain unchanged. `scripts/journal_demo.py` is test-only tooling.

## API and concurrency

GET `/api/v1/days/{date}` returns full cards/items and weighted summary. The
`/days/today` convenience route uses the user's IANA timezone. Dates are within
trackingStartDate..today; no assumed prayer-clock restrictions. Weekly fasting
uses Monday/Thursday only in PR-03; confirmed Ramadan and ADD/SKIP follow PR-04.
The seed is still DRAFT, so fresh databases return 404 until content is published.

PUT routes: `/days/{date}/activities/{code}`, `/adhkar/{item_key}` and
`/adhkar-sets/{code}`. Bodies include clientMutationId, catalogRelease and
expectedVersion (bulk: exact expectedVersions by child code). The extra release
precondition prevents stale offline first edits silently using a newer catalog.
Parent ADHKAR_SET completion is derived; EXCLUDED/PENDING only can be set there.
Count bounds, membership, account isolation and date rules are server validated.

A PostgreSQL account-row lock serializes first-day creation and mutations across
workers, including bulk updates and per-account mutation receipt keys. GET takes
a shared account lock to avoid mixing concurrent snapshots. Receipt+state commit
atomically. Same ID/body returns its original result; changed body or stale row
version returns 409 without partial edits. No distributed lock service or worker.
The account lock trades same-account parallel throughput for straightforward
correctness at this MVP scale. Receipts have no cleanup yet; PR-05 reviews retention.

## Offline behavior and conflict choice

From the account page, open «المحاسبة اليوم». Bootstrap each date online once;
uncached days explicitly require connection rather than inventing missing history.
Cached days remain editable offline and after restart. The device date uses the
account timezone. State+outbox are written in one Drift transaction, then shown;
rapid taps read the latest persisted value, so two taps undo exactly. Counter
changes use absolute values and queue projected versions. No coalescing of sent
requests; retries reuse the original UUID/body. New days never inherit counts.

Sync runs after edits, on screen open/resume, every 30 seconds while the daily
screen is mounted, and via «مزامنة الآن». It sends one queued write at a time.
Acknowledgements never overwrite newer pending intent; stale concurrent GETs
cannot replace edits already acknowledged. Networking does not hold SQLite locks.
The queue is scoped to API origin/base path plus canonical account ID. Logout
retains isolated local history and unsent work for a later login by the same user;
other accounts never read/send it. Android app-private storage, backup disabled;
SQLite is not separately encrypted. No tokens/passwords in SQLite.

409/422/404 on a write pauses the ordered queue and preserves local data. The UI
shows the affected date. Open that date and «مراجعة التعارض» to compare local/server
states and counters, then retain local work or explicitly adopt the shown server
version and discard that date's pending operations. No automatic overwrite or
force-rebase. Rich per-item merge and bounded multi-device restore remain PR-05.
Network/auth errors retain pending writes. Expired login requires authentication;
local data survives. A lost refresh response can require fresh login as in PR-02.

## Reproducible synthetic demo

Real religious content remains an editorial gate. This optional demo copies all
34 reference cards with clearly labeled **synthetic non-religious test text**,
two official test items per set (targets 1 and 3). It never runs in migrations or
startup and refuses databases whose name does not end in `_test`.

Start the root Compose database and create a separate disposable demo DB once:

```bash
docker compose --env-file .env -f infra/compose.yml up -d db
docker compose --env-file .env -f infra/compose.yml exec -T db createdb -U postgres -O muhasaba muhasaba_demo_test
cd backend
# Dummy local example; match your .env password.
export DATABASE_URL='postgresql+psycopg://muhasaba:local_app_only@127.0.0.1:5432/muhasaba_demo_test'
uv run --locked alembic upgrade head
uv run --locked python -m scripts.journal_demo
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8001
```

In another terminal, from `mobile/`:

```bash
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001/api/v1/
```

For USB: `adb reverse tcp:8001 tcp:8001` and use `http://127.0.0.1:8001/api/v1/`.
Create a test account, open today's journal, tap Dhuhr twice (0→weight→0), open
an adhkar set, increment/decrement and check partial score. Disable networking,
edit, restart the app, reopen the cached day, restore networking and sync. Use
only disposable accounts. Never connect the demo fixture to production data.

## Verification and rollback

Run root README checks and PostgreSQL integration tests with a dedicated *_test
DB. Tests include 34-card 74/69 denominators, GET without writes, day pinning,
partial and bulk undo, duplicate/reused mutations, concurrent first writes,
invalid inputs, timezone bounds and cross-account isolation. Flutter tests use
real SQLite (memory and reopenable file), a fake HTTP adapter and mocked secure
storage; they cover rollback-on-enqueue-failure, restart, retry, rapid taps,
conflicts, stale GETs, exact score fixtures and RTL counters.

Local/CI results are recorded in the PR description after running checks. Android
physical-device, keystore and airplane-mode end-to-end QA remain a release gate.
Migration 0004 downgrade deletes journals and receipts: disposable databases only,
never live history without a reviewed restore plan. Stop for review before PR-04.
