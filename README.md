# Muhasaba | محاسبة النفس

Android-first Arabic RTL Flutter application with a Python FastAPI backend and
PostgreSQL. PR-00 provides the foundation; PR-01 adds the catalog and scoring.
**PR-04 adds offline fasting plans and sourced regional Ramadan calendars.**
See [`PR-04 contracts and setup`](codex/PR-04_FASTING.md).
See [`PR-03 scope, API and demo`](codex/PR-03_CORE_JOURNAL.md).

## Product baseline

- Implementation Blueprint v1.4, approved 20 November 2026.
- Read [`AGENTS.md`](AGENTS.md), then the authoritative
  [`Locked Core v1.4`](docs/blueprint/10_LOCKED_CORE_MVP_AR.md).
- [`Blueprint index`](docs/blueprint/README.md),
  [`delivery roadmap`](docs/blueprint/07_DELIVERY_CODEX.md),
  [`PR-00 scope`](codex/PR-00_FOUNDATION.md),
  [`review workflow`](codex/WORKFLOW.md).
- Arabic RTL; selected IANA timezone defaults to `Africa/Cairo` in later domain
  work, with UTC audit timestamps.
- Modular monolith: no queues, Redis, Kubernetes or external identity connection.

## Non-negotiable score rule

Only the weighted **main daily accountability cards** determine daily score.
Official, score-eligible nested adhkar share points **inside their fixed parent
card**, granting partial credit as their repetitions are completed. Custom user
dua/adhkar and hiding/reordering official defaults **never** add points or change
the parent's point budget. Support exact undo and preserve scores from previous
days. PR-01 tests this rule in the pure Python scoring engine; journal integration
and Flutter scoring are later work.

## Structure

```text
backend/           FastAPI, SQLAlchemy metadata, Alembic and pytest
mobile/            Flutter Arabic authentication UI and secure session storage
infra/             Local PostgreSQL/API Compose stack and dummy env example
.github/workflows/ Backend, Compose and Flutter checks
codex/             PR scope and review workflow
docs/blueprint/    Authoritative product specifications (unchanged)
```

## Prerequisites

- Python 3.13 managed by [uv](https://docs.astral.sh/uv/); commands and Docker use
  uv 0.10.8. `uv.lock` pins the resolved backend dependencies.
- Flutter **3.38.9**, Dart **3.10.8** (the same version used in CI), and Android
  SDK/device/emulator for running the app. `pubspec.lock` is committed.
- Docker with Compose v2 for the full API/database stack. No AWS account or
  production credentials are needed for foundation development.

## Local API without Docker

From the repository root:

```bash
cd backend
uv python install 3.13
uv sync --locked
uv run --locked uvicorn app.main:app --reload
```

In another terminal:

```bash
curl --fail http://127.0.0.1:8000/health
```

Expected: HTTP 200 and `{"status":"ok"}`. OpenAPI is at
<http://127.0.0.1:8000/docs>. `/health` checks process liveness only, not database
readiness. It runs without `DATABASE_URL`. Stop the development server with Ctrl+C.

## Local API and PostgreSQL with Compose

Run from the repository root. Pass the root `.env` explicitly so loading does
not depend on Compose's project-directory defaults:

```bash
cp infra/.env.example .env
docker compose --env-file .env -f infra/compose.yml up --build -d --wait
curl --fail http://127.0.0.1:8000/health
docker compose --env-file .env -f infra/compose.yml exec -T api alembic upgrade head
```

Copy the example only on first setup; do not overwrite an existing `.env`.
The example passwords are dummy local values. The API uses a non-superuser
`muhasaba` database role with schema creation privileges for migrations; bootstrap
uses a separate PostgreSQL administrator. Both published ports bind to localhost.
The API container runs as a non-root OS user.

```bash
docker compose --env-file .env -f infra/compose.yml logs api db
docker compose --env-file .env -f infra/compose.yml down
```

`down` preserves the named database volume. No automatic migration or database
reset runs during API startup. PostgreSQL initialization runs only on a fresh
volume; editing passwords in `.env` does not change existing database passwords.
These Compose settings are for local development, not a production deployment.
Use URL-safe local `APP_DB_PASSWORD` values: Compose interpolates that value into
`DATABASE_URL` without URL encoding.

## Migrations

`alembic upgrade head` applies `0001` (five catalog/library tables plus publication
and immutability guards) and `0002` (eight categories, 34 draft reference cards), then `0003` (users,
sessions, external identity placeholders, settings and library author FK), then
`0004` (daily journals, official snapshots and mutation receipts), then
`0005` (fasting overrides, regional calendars and preserved daily baselines).
There are no seeded religious texts or published releases.

`GET /api/v1/catalog?date=2026-11-19` intentionally returns 404 on a fresh database.
Only published, verified official catalogs are exposed. The contract is also
available in `/docs` and the checked `backend/openapi.json` snapshot. Missing DB
configuration/connection returns 503; `/health` remains independent.

For migration commands on the host with the Compose database running:

```bash
cd backend
# Dummy example only; match the app password in your root .env.
export DATABASE_URL='postgresql+psycopg://muhasaba:local_app_only@127.0.0.1:5432/muhasaba'
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic heads
```

Later PRs add their model imports to Alembic metadata and create revisions with
`uv run --locked alembic revision --autogenerate -m "describe schema change"`.
Review generated upgrade/downgrade operations before applying them. PR-01
downgrades remove seed data and catalog tables; they are destructive and must not
be run against live data without a reviewed restore plan. Published/referenced
seed data is protected from the seed downgrade. Do not use `create_all()` or
destructive resets as a migration strategy.

## Mobile

```bash
cd mobile
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter run
```

The app supports registration, login, session restoration and logout using
Riverpod, Dio and encrypted token storage. The default debug URL targets the
Android emulator at `http://10.0.2.2:8000/api/v1/`; start the Compose backend and
apply migrations first. See [`mobile setup`](mobile/README.md) for device and
release configuration. Open «المحاسبة اليوم» from the account page for cached daily tracking and sync.
Published content is required; a guarded synthetic 34-card demo is documented in
[PR-03](codex/PR-03_CORE_JOURNAL.md). Fasting plans also work without a published catalog; reports follow in PR-05.

## Checks

From `backend/`:

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

From `mobile/`:

```bash
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
```

CI runs these checks plus a fresh Compose stack, live `/health` request and
`alembic upgrade head`/`current` through the application database role. PR-01 also
runs PostgreSQL integration tests on a dedicated `muhasaba_test` database, including
migration rollback/reapply and schema parity. See the PR-01 scope document for
commands. Without `TEST_DATABASE_URL`, those integration tests explicitly skip.

### PR-00 local verification (22 November 2026, historical baseline)

| Check | Result | Evidence / limitation |
|---|---|---|
| `uv sync --locked` | PASS | Python 3.13.12, dependency lock resolved |
| `uv run --locked ruff check .` | PASS | No lint findings |
| `uv run --locked ruff format --check .` | PASS | Six Python files formatted |
| `uv run --locked pytest` | PASS | API health smoke test |
| Live Uvicorn `GET /health` | PASS | HTTP 200 and expected JSON on local port 18000 |
| `alembic upgrade head --sql`, `alembic heads` | PASS | Offline scaffold loads; no revisions |
| `flutter pub get --enforce-lockfile` | PASS | Locked dependency resolution |
| Dart format check, `flutter analyze` | PASS | No formatting/analyzer issues |
| `flutter test` | PASS | Arabic locale, app text and RTL smoke test |
| Compose build/start, online migrations | NOT_RUN locally | Docker unavailable; included in CI |
| Android device run / APK build | NOT_RUN | Android licenses incomplete; not required for widget tests |

PR-03 local checks: 54 backend tests pass; 46 PostgreSQL integration cases
require CI or a dedicated database. Flutter analysis passes; local Flutter tests
are blocked by the macOS native-assets/Xcode SDK setup. See the PR-03 document
and current GitHub Actions results for full verification.

## Troubleshooting

- Run `flutter doctor` to inspect Android tooling. Review/accept required Android
  licenses with `flutter doctor --android-licenses` before device builds.
- On macOS, `/usr/bin/python3` can be blocked by Xcode's license. Use the uv-managed
  interpreter above. iOS/macOS builds and their Xcode/CocoaPods setup are outside
  this Android foundation task.
- If Docker is unavailable, use the standalone API and Flutter checks; the real
  PostgreSQL/Compose checks still need Docker or CI before merge.
- If port 8000 is busy, stop the host Uvicorn process before starting Compose.
  If 5432 is busy, stop the conflicting local database or explicitly adjust the
  Compose host mapping and host `DATABASE_URL` together.
- Alembic requires an explicit `DATABASE_URL`; it does not automatically load
  `.env`. Compose supplies its internal URL using hostname `db`; host commands use
  `127.0.0.1`. Missing configuration fails instead of choosing a production database.

## Content rights and source verification

Screenshots and the public reference site are functional references, not
permission to reuse private APIs, copyrighted assets or unverified Arabic texts.
Proposed weights are product fixtures, not proof of the original site's internal
calculations. Verified religious content is a later catalog/release gate.

## Tooling references

- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [setup-uv action](https://github.com/astral-sh/setup-uv)
- [Flutter setup action](https://github.com/subosito/flutter-action)
