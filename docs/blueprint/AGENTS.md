# Codex instructions for Muhasaba implementation v1.4

**Must read:** `README.md`, `00_EXECUTIVE_AR.md`, `01_FLOWS_AND_PRD_AR.md`, `02_ARCHITECTURE.md`, `03_DATABASE.md`, `04_DOMAIN_RULES.md`, `05_API_CONTRACTS.md`, `06_CONTENT_AND_INTEGRATIONS.md`, `07_DELIVERY_CODEX.md`, `08_RISKS_TESTS_DECISIONS.md`, `09_UNDO_LIBRARY_PERSONALIZATION_AR.md`, **`10_LOCKED_CORE_MVP_AR.md`**, `seed/`, then `codex/START_HERE.md`.

## Technology boundaries

- Flutter/Dart Android-first, Riverpod, SQLite/Drift, Dio; Python FastAPI + SQLAlchemy 2 + Alembic + Pydantic + PostgreSQL. Do **not** generate NestJS, TypeORM, or TypeScript backend.
- Modular monolith; no Kubernetes, Redis, Celery, event bus or unnecessary new apps/services. Work on only requested PR.
- Do not use original amgadsamir.com authenticated/private endpoints, logo, copied artwork, or scrape/rehost content. Public official video link integration only after documented rights and review.

## Mandatory invariants

- Main activity `points` and dhikr `target_count` are different. NEVER use all-or-nothing for `ADHKAR_SET`. Fractional parent score = `points * mean(clamp(done/target,0,1) for each OFFICIAL score-eligible item pinned to that day)`; no second reward on group completion. Support derived PARTIAL state and undo.
- Main `ADHKAR_SET` state must be derived; bulk complete/clear updates child rows atomically. `EXCLUDED` is a distinct parent/day override. User-owned custom items are tracking-only (0 score). Hidden defaults remain score-eligible even when hidden from view. A scored official set with no verified scoring items is an invalid catalog publication.
- Use 34 reference activity codes/8 sections and provisional Thursday 74 point fixtures. Treat actual original site's weighting as inferred, not guaranteed.
- Fasting eligible on Mon/Thu or confirmed region Ramadan or explicit opt-in, unless SKIP. Never count same fast twice; future plans allowed, future completion forbidden.
- One internal UUID user ID; account `registration_source` and external identities separate. Never merge accounts on email match alone.
- User-owned operations authenticate and authorize on server. Journals private; no medical reasons in DB.
- Published catalog immutable, historical days pinned; personalized group plans effective-dated and journal member snapshots frozen. Official scoring membership is separate from personal display and custom-item tracking. All migrations via Alembic.
- Source texts of adhkar require verification and attribution before production; do not hallucinate canonical text/repetition counts.
- Dates ISO local with IANA timezone, UTC audit timestamps; tests cover Cairo and calendar boundaries.
- Offline local state plus outbox must change atomically; retries idempotent and conflicts visible.
- Scheduled local notifications are opt-in and privacy-preserving. Encourage partial progress without guilt. Instant feedback happens in-app; OS unfinished-work notifications max once/day, quiet hours, cancel/reschedule on relevant locally-known progress, deep link to remaining items. No push worker in MVP.

## Delivery protocol

1. State requested PR scope and proposed changes before coding.
2. Make only necessary files, write pytest/Flutter tests, avoid speculative abstractions.
3. Run available format/lint/tests, report results literally. Do not assert Flutter SDK build if unavailable.
4. Explain how to run, migrate and roll back changes; flag unresolved product decisions.
5. STOP after requested PR for review, do not execute next PR unasked.

## First execution

See `codex/START_HERE.md`. First task PR-00 only, no business features.

## v1.4 must-follow constraints

- Standard activity cards (including Dhuhr): tap marks complete; tap again undoes it, fully reversing earned points. Server receives explicit `PUT` state (not non-idempotent `toggle`), using mutation ID and row version. Allow past and current dates, never completion of future calendar dates. No unsupported prayer clock-time gating.
- Official content library is administered only by ADMIN and published through reviewed immutable catalog versions. `users.role` must be checked on server. No rich CMS UI in initial foundation.
- User can add/edit/archive **private** adhkar/dua and hide official default items in their own existing group. These operations never delete official records and never affect other accounts. Custom content is never automatically claimed to be verified.
- Resolve active official+personal items from effective-dated `user_group_plans`, snapshot per day on first edit, award fractional group points over **official score-eligible** items only; fixed group weight, no double bonus, custom items/hidden display do not change score. Scores are private encouragement metrics, not user leaderboards. Personal plan settings do not change score.
- New features belong to PR-06b after reversible journal core PR-03; do not implement content customization in PR-00.

## Mandatory v1.4 correction, higher priority than previous v1.3 examples

Read `10_LOCKED_CORE_MVP_AR.md` first. `user_group_plans` custom items, hide flags and ordering are NOT input to the scoring denominator or numerator. No personal dhikr can award extra points. The main activity card is the only unit of weighted score and official nested adhkar earn partial credit inside it. A hide operation is display-only and must not be treated as exclusion or achievement. Do not implement a personalized scoring engine or old 4-visible-item denominator examples from earlier files. Keep MVP limited and stop after each Codex PR.