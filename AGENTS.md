# Muhasaba: instructions for Codex and code agents

## Task discipline

- **First read** `docs/blueprint/10_LOCKED_CORE_MVP_AR.md`, then `docs/blueprint/README.md` and any relevant specification chapter. Current task: `codex/PR-01_CATALOG_SCORING.md`. PR-00 is merged; its scope below is historical.
- The v1.4 **locked core overrides any contradictory v1.3 examples**. Do not reinterpret the scoring system.
- Implement only the **requested PR scope**, in small, reviewable changes. Plan briefly, work, test, report PASS/FAIL/NOT_RUN, and stop. Never start the next PR automatically.
- Do not add complex infrastructure or speculative features.

## Locked domain model

- **Main weighted activity cards are the only daily scoring units.** A parent `ADHKAR_SET` card gives proportional credit for **official score-eligible** child items: `earned = parent_weight * mean(clamp(done_i / target_i, 0, 1))`. Never award bonus points in addition to the parent weight.
- User personal adhkar/dua are private, tracking-only and add **zero** points. Hiding/reordering official adhkar changes display only, not scoring membership or denominator. Admin-only official library management; historical snapshots remain stable.
- Ordinary activity tap = set completed, second tap = undo. API operations must use explicit desired state for safe retries; **do not expose a non-idempotent toggle endpoint**.
- User-entered/repeated dhikr count supports increment AND decrement, capped to its target for earning points; partial completion is encouraged, not punished.
- Fasting Monday/Thursday baseline, verified Ramadan calendar plus optional user-planned dates. Imported accounts are future-ready but external DB access is not implemented in PR-00.

## Technical boundaries

- Mobile: **Flutter/Dart**, Arabic RTL, Riverpod, Dio, Drift/SQLite for offline journal.
- Backend: **Python FastAPI** modular monolith, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL. API owns canonical scoring rules. Do not use NestJS/TypeORM as backend.
- Local: Docker Compose with PostgreSQL and API, least-privilege defaults, `.env.example` only. No committed secrets, databases or credentials.
- Tests: pytest, Ruff, Flutter analyze/test, minimal GitHub Actions CI, documented results. Missing SDK means `NOT_RUN`, not fabricated PASS.
- Local date in selected IANA timezone (`Africa/Cairo` default), UTC audit timestamps. Handle Arabic correctly.
- Mobile offline writes must eventually be atomic with a local outbox and idempotent sync, per later PR specs; do not build full sync during foundation.
- Notifications are opt-in and supportive; no shaming. No server push worker for MVP.
- No private or undocumented external API, unauthorized scraping, copied branding/media, or unsourced religious text.

## PR-00 ONLY (completed; historical task boundary)

- Create `backend/`, `mobile/`, `infra/` with minimal working skeletons, API `/health`, Postgres Docker Compose, Alembic scaffolding, tests, lint and CI.
- Do **not** build auth, activity catalog, scoring, database business schema, notification services, video provider, CMS, or actual journal features yet.
- Keep the root docs and v1.4 source of truth intact.
- Summarize commands run, artifacts created, limitations and next review gate before stopping.