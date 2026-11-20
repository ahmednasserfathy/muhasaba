# 07 | Execution Roadmap for Codex (small PRs)

**Principle:** One vertical capability per PR. Codex must not generate a complete system in one giant run. Each PR has a demonstrable acceptance criterion and test gate. Developers decide exact compatible package versions, then lock them.

## Milestone map

| PR | Workstream | Deliverables | Gate |
|---|---|---|---|
| PR-00 | Repo + Python skeleton | Monorepo folders, FastAPI `/health`, Docker Compose Postgres, `pyproject.toml`, Alembic config, Flutter app skeleton, CI for lint/test; **no business features** | API starts, tests run, `flutter analyze` works |
| PR-01 | Catalog + score engine | DB migrations for catalog, 34 activity seed, 8 categories, official `library_entries` and immutable group bindings, pure Python scoring, catalog API; coverage tracker | Scoring fixtures, admin-vs-user role boundaries documented, no incorrect published dhikr text |
| PR-02 | Accounts + identity readiness | users, password auth, sessions, external_identities origin mapping; mobile login and secure token store | Native registration/login, imported user remains non-login until verified activation, authz tests |
| PR-03 | Core journal + adhkar | journal tables and API, prayer/toggle **tap-to-complete, tap-again-to-undo**, detailed modal, `0/N` increment/decrement, proportional group score, local Drift states/outbox | Dhuhr `0→weight→0`, 1/2 set earns partial, rapid double tap/retry safe, restart/offline persists |
| PR-04 | Fasting and Ramadan | fasting rules, overrides, calendar_periods, fasting UI, API and tests | Monday/Thu, Wednesday opt-in, Ramadan not duplicated, SKIP removes denominator |
| PR-05 | Reports + sync hardening | weekly/monthly reports, bounded restore, idempotent writes, conflict message, account data isolation | same scores Python/Dart, duplicate mutation safe, conflict never silent |
| PR-06 | Local reminders + approved content | opt-in category reminders, gentle incomplete-progress prompts with deep links, approved dhikr texts and optional approved video links | One prompt max/day, opt-out, quiet hours, cancel/reschedule on completion, permission/timezone cases, attribution checklist |
| PR-06b | Personalized adhkar + admin library management | Minimal admin CRUD/publish, private `user_custom_items`, effective-dated `user_group_plans`, group resolution/snapshots, Flutter customize/restore screen | Hide default is private, add personal dua, versioned history stable, official score unchanged by personalization, cross-user access forbidden |
| PR-07 | Release readiness | end-to-end UAT, backup/restore, error monitoring, signed Android internal build, security audit | staging pass, backup verified, privacy/consent reviewed |

**Optional PR-08 (only on request):** one external DB import/OIDC adapter using source-specific verified mapping, dry run, activation and rollback. Do not implement before exact source constraints are provided.

## Start order and dependencies

- PR-00 then PR-01, tests before mobile pixel tuning.
- PR-02 before authenticated journal API use.
- PR-03 must be end-to-end demonstrable offline.
- PR-04 depends on PR-01 and PR-03.
- PR-05 depends on PR-03, PR-04.
- PR-06 can follow core journal, but don't block local testing on video API.
- PR-07 is a release gate and not a feature dump.

## Codex task protocol for each PR

1. Read `AGENTS.md`, entire relevant Blueprint chapter and upstream PR test status.
2. State scope, assumptions, exact file changes and migrations before coding.
3. Implement small coherent change only. Keep UI and API models aligned.
4. Add unit/API integration/widget tests and update OpenAPI examples/docs if API changes.
5. Run `ruff check`, `ruff format --check`, `pytest`, Alembic upgrade on fresh Postgres. Run `flutter analyze`/`flutter test` when Flutter toolchain available.
6. Report executable commands, PASS/FAIL/NOT_RUN, known gaps and rollback implications.
7. Do not approve your own unverified assumptions about original site/API/content.

## Functional acceptance matrix

| ID | Scenario | Expected |
|---|---|---|
| A01 | Create native user and login | canonical UUID + NATIVE source, protected endpoints |
| A02 | Import-ready identity row | uniqueness and linkage support, no external DB dependency |
| A03 | Enter current day | eligible cards and deterministic score appear |
| A04 | Complete ordinary card | green and score updates without online wait |
| A05 | Open mosque details | separate item list and counters |
| A06 | Complete one of two dhikr items, group weight 2 | parent PARTIAL, earned 1/2, shows remaining 1 item |
| A07 | Complete second item | parent COMPLETE, earned 2/2, never 3/2 |
| A08 | Undo one item | parent PARTIAL, earned returns to 1/2 |
| A08b | Three of five adhkar, group weight 2 | earned 1.2/2, positive in-app encouragement |
| A08c | Opt in to unfinished-work reminder | at most one scheduled summary/day, deep-link to remaining work, suppressed after completion |
| A09 | Monday fasting / Wednesday without plan | Monday eligible; Wednesday excluded from denominator |
| A10 | Add Wednesday fast | Wednesday eligible, still incomplete until marked |
| A11 | Ramadan overlap with Monday | only one fasting item and one weight |
| A12 | Ramadan dates unconfirmed | don't auto-enforce fictional dates |
| A13 | Enable/disable reminder | local scheduled/cleared and OS permission respected |
| A14 | Edit offline then reconnect | same persisted values, no duplicated writes |
| A15 | New device/restore | previous history safe after login, conflicts explicit |
| A16 | No rights for content | no unverifiable text/API launched to production |

## Definition of Done

- Test suite green, docs updated, migrations reviewed, credentials redacted, no hardcoded account details, Arabic RTL accessible, privacy-safe logs, independently reproducible demo.
- If Flutter/Android emulator absent, mark UI tests as NOT_RUN rather than claiming success.
- Codex should not create a custom admin frontend, authentication provider abstraction hierarchy, Kubernetes files or worker queues during core PRs.

## v1.3 sequencing and extra acceptance gates

- Do not put private personalization or an admin SPA into PR-00. PR-01 creates only minimal official library **data model**, permission schema and pure score fixtures. Implement admin editorial endpoints with the dedicated PR-06b after core journal works.
- PR-03 establishes **symmetric reversible toggles** for prayer, ordinary activities and counter decrement, offline atomic outbox and non-flipping idempotent PUT semantics. This is a hard release gate.
- PR-06b creates two user screens: `تخصيص المجموعة` and `إضافة ذكر/دعاء شخصي`. Edit and archive private items are restricted to owner; default hide is override, never global delete. Admin uses protected minimal CRUD endpoints and `publish` action, no separate app.
- Added acceptance: one-tap completes Dhuhr, second tap undoes it including score; offline double tap yields original final state. A morning card with 5 official scoring items keeps the **5-item scoring denominator**, even if two official items are hidden and a custom dua is added. Completing a personal dua never awards points. Historical daily score unchanged after new plan or admin archive. User cannot see another user's private text.
- Future-date completion prohibited; *clock-time prayer* completion is not gated without verified prayer timetable. No GPS permissions for MVP.

## v1.4 MVP lock and Codex gates

- PR-01 scoring engine: implement `earned=parentWeight * avg(normalized_count over OFFICIAL SCORE-ELIGIBLE day-pinned items)`. Assert custom progress and hide/reorder state have no effect on earned or possible.
- PR-03: reversible main card states and official nested counters, live partial progress, 0/N undo, correct 34-card weighted day sum.
- PR-06b: minimal protected Admin official library APIs, user-owned private content, own display customization. Explicit separate personal-progress display. No score recalibration from user plans.
- PR-07 UAT: check score unchanged on hidden defaults/private items, history preservation, no hidden official rows permanently inaccessible, opt-in reminder logic.
- Any new proposal is a backlog item unless it fixes a core acceptance requirement; do not expand scope during PR-00.