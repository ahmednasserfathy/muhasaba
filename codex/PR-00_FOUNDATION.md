# Codex task: PR-00, project foundation only

**Suggested branch:** `codex/pr-00-foundation`

> Read root `AGENTS.md`, `docs/blueprint/10_LOCKED_CORE_MVP_AR.md`, `docs/blueprint/02_ARCHITECTURE.md`, and `docs/blueprint/07_DELIVERY_CODEX.md` before touching files. Work only on PR-00. Do not start PR-01 or any application business logic.

## Goal

Prepare a minimal, maintainable monorepo for an Arabic RTL Flutter app and a Python FastAPI/PostgreSQL backend, with reproducible local development and CI. The initial commit currently contains documentation only.

## Deliverables

1. `backend/`: Python project using supported compatible versions of FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg and pytest, Ruff, a minimal app factory or `app/main.py`, GET `/health` returning HTTP 200 + small JSON health status, and one automated API health test.
2. `infra/compose.yml`: local PostgreSQL with named volume and health check, plus FastAPI service if it keeps first-run straightforward; `.env.example` with dummy development values only. All real secrets ignored by Git.
3. Alembic configuration and an empty initial migration mechanism, **no users/catalog/journal tables** yet; document migrations commands and DB connection configuration.
4. `mobile/`: new Flutter Android-first project using standard `flutter create`, configured for Arabic locale/RTL, a minimal home placeholder with the app name "محاسبة", one widget smoke test. Dependencies for Riverpod, Dio, Drift may be installed where appropriate but do not build repositories, auth, offline sync or business screens yet.
5. `.github/workflows/ci.yml`: backend lint/tests and Flutter analysis/tests, using supported official/setup actions and a Flutter setup action. Avoid requiring Android release signing or emulator in foundation CI.
6. Root/local README quickstart, prerequisites, commands, and useful troubleshooting. Keep the authoritative `docs/blueprint/` contents unchanged.

## Non-goals (hard stop)

- No signup/login, password storage, activity models, dhikr content, scoring computation, fasting logic, API contracts implementation, reminders or notifications.
- No Redis, Celery, Kafka, Kubernetes, separate worker, admin frontend, Firebase, new third-party monitoring infrastructure or custom CI services.
- Do not import copyright-protected source content or interact with the reference website's private endpoints.

## Acceptance checks

- `docker compose -f infra/compose.yml up --build -d` works with documented environment configuration; API responds `GET /health` with 200 after startup. If Docker is unavailable, report `NOT_RUN` and provide exact user command.
- In backend: `ruff check .`, `ruff format --check .`, `pytest` work; unit smoke test passes (or explicitly `NOT_RUN` with reason).
- In mobile: `flutter analyze`, `flutter test` work; Arabic RTL smoke test present. If Flutter SDK unavailable, mark `NOT_RUN` rather than claiming success.
- No migration silently runs as destructive reset; no app secrets or real credentials committed.
- CI executes corresponding checks with fixed or appropriately constrained action versions.
- Updated README describes first-run and debugging reliably.

## Final response expected from Codex

1. Brief implementation summary, changed files, and any choices made about versions.
2. Exact PASS/FAIL/NOT_RUN test table with command evidence and reasons.
3. Local run commands, how to stop the compose stack, and migration strategy.
4. Any issues blocking PR review.
5. **Stop. Do not implement PR-01.** Open a draft PR into `main` if the environment supports it; otherwise provide branch/commit details and PR creation instructions.