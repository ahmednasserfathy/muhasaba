# First Codex Task: PR-00 (copy into Codex)

Read `AGENTS.md`, `README.md`, all product, architecture, database and roadmap docs. We are building an Arabic offline-first Flutter religious activity tracker with a PYTHON FastAPI backend, NOT NestJS. Implement **PR-00 only**:

1. Create a single monorepo `backend/`, `mobile/`, `infra/`, `docs/` with a coherent README and `.env.example`. No business code yet.
2. Python backend: `pyproject.toml`, FastAPI `app.main`, `/api/v1/health/live`, DB connection configuration, SQLAlchemy session pattern, Alembic config and migration scaffolding, pytest smoke tests, Ruff formatting/lint configuration.
3. Docker Compose local PostgreSQL and backend, health checks and volume, only local environment secrets in `.env` ignored by git. No production credentials.
4. Flutter mobile skeleton in Arabic RTL Dark Mode with an empty daily screen and navigation placeholders, Riverpod bootstrap, `flutter analyze` and widget smoke test. No unauthorized content copied from original website.
5. CI steps for Python tests/lint and Flutter analyze/tests when toolchain exists. Pin dependency versions reasonably and commit lockfiles where appropriate.
6. Document exact commands for local start, database connection/migrations, tests and teardown.
7. Report files, commands executed, passing/failing/not run checks and blockers. STOP. Do not implement real users, schema tables, cards, scores, content or integrations until PR-01/02.

**Acceptance:** Fresh clone + documented commands starts a Python API and Postgres, `/api/v1/health/live` responds, automated smoke test passes. The Flutter skeleton builds/analyzes in a configured Flutter environment, Arabic RTL works. No NestJS or unnecessary extra services. If any SDK/tool is unavailable, state the missing test explicitly.

### Next task after review (NOT in PR-00)

PR-01: Implement categories/releases/activities/adhkar item models, Alembic migration, seed 34 reference activity codes, source verification tracker and pure Python scoring with Thursday regression fixtures. Must maintain distinction `points != target_count`. No invented unverified adhkar texts.

### v1.3 constraints (read before PR-00, do not implement yet)

- Upcoming PR-03 must support reversible completion and explicit state-setting API; no ambiguous `/toggle` endpoint.
- PR-06b will deliver admin official library CRUD, private custom adhkar/dua and hide/restore defaults with effective dates, daily snapshots and fixed official-score-only model. No new top-level weighted user activities in v1.
- These requirements are described in `09_UNDO_LIBRARY_PERSONALIZATION_AR.md`. PR-00 scope **unchanged**: foundation only.

## Version 1.4 mandatory

Before PR-00, read `10_LOCKED_CORE_MVP_AR.md`. Do not implement scoring based on the user's visible/custom adhkar. Only score official pinned items within weighted main cards; private content is track-only. PR-00 remains infrastructure only.
