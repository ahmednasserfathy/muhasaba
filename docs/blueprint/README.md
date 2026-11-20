# Muhasaba | Implementation Blueprint v1.3 (Python)

**Status:** Product and technical design, ready for sequential Codex implementation. **Date:** 20 November 2026. This supersedes v1.2 with reversible taps, admin library and personal adhkar plans while retaining partial scoring. It retains the Python backend, fasting, identity and offline-first design. **No app source code.**

**Source evidence:** user video `385726.mp4` and three screenshots `385743.jpg`, `385744.jpg`, `385745.jpg`, plus the public reference `https://www.amgadsamir.com/accountability`. This project is independent of the original website. Its private APIs and permission to reuse its content have not been established.

## Locked design choices

- Flutter Android-first, Arabic RTL, responsive Dark Mode. Riverpod for state, Drift SQLite for offline journal, HTTP client Dio.
- Python FastAPI monolith, SQLAlchemy 2, Alembic migrations, PostgreSQL, Pydantic v2, pytest, Ruff.
- Auth initially app-native email/password. Imported/external identity records are supported in the **schema now**, but no production external DB or federated auth connection before provider details and consent are known.
- 34 reference activity cards, eight sections, provisional weighted scores totaling 74 on a reference Thursday, subject to verified source/product review.
- Some activity cards are `ADHKAR_SET`: text items with independent 0/N counters and **proportional points immediately**, even for unfinished sets. Each item equally shares parent weight; repeated dhikr is normalized within its item. Remaining items encourage progress, not guilt.
- Fasting: Monday/Thursday recurring sunnah; Ramadan period configured per supported region; user can opt in on any other day. Optional days do not reduce a user's score unless explicitly planned.
- On-device configurable reminders first, including one optional gentle unfinished-work prompt per day, with deep link and opt-out. No FCM/backend jobs, prayer-time calculation or external video search in core MVP.
- Videos and the original site's API are an **integration seam**, not an assumed available endpoint; use reviewed official public video links if licensed/permitted, or approved integration later.
- Keep a modular monolith, no Redis, message broker, microservices or complex admin dashboard before need is established. Basic ADMIN editorial APIs are in scope, plus user-owned private adhkar/dua inside existing groups.

## Reading order

1. `00_EXECUTIVE_AR.md` Decisions and scope.
2. `01_FLOWS_AND_PRD_AR.md` User experience and acceptance criteria.
3. `02_ARCHITECTURE.md` Modules, data boundaries, offline policy.
4. `03_DATABASE.md` Logical ERD, table dictionary, indexes, external identities.
5. `04_DOMAIN_RULES.md` Adhkar, scoring, fasting, Ramadan, notifications.
6. `05_API_CONTRACTS.md` Request/response contracts for the Python API.
7. `06_CONTENT_AND_INTEGRATIONS.md` Videos, authorized sources, import strategy.
8. `07_DELIVERY_CODEX.md` PR sequencing, tests, stop gates.
9. `08_RISKS_TESTS_DECISIONS.md` QA, security and open assumptions.
10. `09_UNDO_LIBRARY_PERSONALIZATION_AR.md` Undo, admin library and personal group plans.
11. `AGENTS.md`, `codex/START_HERE.md` Directions and first prompt for Codex.
11. `seed/catalog_reference_34.csv`, `seed/adhkar_coverage.csv` Seeds and text-verification tracker.

## Evidence labels

`OBSERVED` = demonstrated in user screenshots/video. `USER_REQUIREMENT` = now explicitly required by user. `PROPOSED` = our consistent design policy. `UNKNOWN` = unverified, should never be presented as original site behavior.

## Avoid these mistakes

1. Do not mix activity score `2` with an individual dhikr's `1/1` repetition counter.
2. Do not duplicate activity points for multiple adhkar inside a set.
3. Do not score an unplanned voluntary fast as missed on an arbitrary Wednesday.
4. Do not automatically assert Ramadan dates without confirmed region/calendar configuration.
5. Do not treat imported users and native users as different database user IDs for the same verified person, or auto-merge solely by matching email.
6. Do not build a WebView or connect to undocumented/private endpoints of the referenced website.
7. Do not introduce heavy synchronization/event sourcing before cross-device usage is required.

## References

- Reference experience: https://www.amgadsamir.com/accountability
- FastAPI: https://fastapi.tiangolo.com/tutorial/sql-databases/
- Alembic: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- YouTube embed: https://developers.google.com/youtube/iframe_api_reference
- Android notification permission: https://developer.android.com/develop/ui/views/notifications/time-sensitive
- Flutter notifications plugin: https://pub.dev/packages/flutter_local_notifications
- OWASP mobile application verification: https://mas.owasp.org/MASVS/

## New in v1.3

- **Undo by second tap** for any regular activity (including prayers). Explicit set-state REST updates, offline-safe, points revert exactly.
- **Admin-managed official library** of DHIKR/DUA, with review/archive and immutable published catalog snapshots.
- **User personal adhkar/dua** added to existing cards/groups; hide/restore official defaults without global deletion, and retain privacy.
- **Plan-aware score**: original group points unchanged, distributed over a user's effective visible items; history protected with effective date and daily item snapshots; compare progress against own plan rather than other users.
- **Phased delivery**: reversible journal in PR-03 and lightweight customization + admin CRUD in PR-06b. No large CMS or microservices.
- See `09_UNDO_LIBRARY_PERSONALIZATION_AR.md` for the new core spec and `CHANGELOG_v1_3_AR.md` for diffs.