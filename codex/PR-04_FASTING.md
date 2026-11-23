# PR-04: fasting plans and regional Ramadan calendars

PR-03 is merged. This scope adds fasting eligibility, planning and its offline UI;
reports, reminders and personal libraries remain later PRs.

## Rules and persistence

Precedence is SKIP, ADD, confirmed regional Ramadan, Monday/Thursday, unplanned.
Only one fasting card weight applies when reasons overlap. Optional fastType is
VOLUNTARY, MAKEUP or OTHER and is accepted only with ADD. SKIP excludes fasting
from possible/earned points without deleting completion; DEFAULT restores the
baseline. No medical reasons are collected. Legacy card-level EXCLUDED remains
independent and can be restored through the card's existing action.

Migration 0005 adds fasting_overrides, calendar_periods and a journal baseline.
First journal edit pins the regional baseline so later calendar corrections do
not rewrite saved scores. Existing PR-03 journals retain weekly-only baselines.
Reading or planning alone does not create a journal or pin its baseline.
Downgrading 0005 deletes plans, calendars and baselines: disposable databases only.

## API and offline behavior

- GET `/api/v1/fasting/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD`: inclusive 1–366
  days, starting no earlier than trackingStartDate. Returns source, confirmation,
  baseline, effective eligibility, override version and whether baseline is pinned.
- PUT `/api/v1/days/{date}/fasting-plan`: clientMutationId, expectedVersion,
  mode and optional fastType. Returns the fasting view, independently of catalog.
- Day GET includes the same fasting view and derives the score from eligibility.

Planning future dates is allowed; completing future activities is still rejected.
Account locks, atomic mutation receipts and optimistic versions follow PR-03.
Same ID/body replays the original result; stale versions or reused IDs return 409.
DEFAULT retains a versioned row to prevent stale clients recreating removed plans.

Flutter exposes planning through the next 365 days. Drift v2 adds local_fasting
without deleting v1 days/outbox. Cached plans and outbox writes commit atomically,
then synchronize in order alongside journal writes. Planning updates local scores
without changing completion. Network failures preserve pending work. Conflict UI
requires explicit adoption of server state; a plan-only resolution cannot discard
pending journal edits. Each date must first be loaded online; future plan bootstrap
works without an official catalog. Previous mutation receipts lacking fasting
remain readable for migration compatibility.

## Operator calendar setup

No real Ramadan dates are seeded or inferred. PROVISIONAL dates are displayed but
never activate Ramadan scoring. CONFIRMED requires a reviewed HTTPS source URL.
The account's regionKey is used (currently defaults to EG). Run on the host from
backend with an explicitly configured DATABASE_URL and reviewed values:

```bash
uv run --locked python -m scripts.ramadan_calendar \
  --region "$REGION_KEY" --start "$REVIEWED_START" --end "$REVIEWED_END" \
  --status CONFIRMED --source-url "$REVIEWED_SOURCE_URL"
```

Start/end are inclusive ISO dates. The command accepts at most 31 days, serializes
operator edits, rejects overlaps and updates an existing region/start entry.
Use PROVISIONAL without source-url for unconfirmed dates. No public calendar
administration endpoint or automatic external fetch is introduced.

## Verification

Local: 66 backend tests PASS, Ruff PASS, Flutter analysis/format PASS. The 55
PostgreSQL cases need a dedicated *_test database and run in CI; macOS Flutter
tests remain blocked by native-assets/Xcode setup and run on Linux CI instead.
The PR records final CI results. New cases cover precedence, one-weight overlap,
future planning, replay/conflict, account isolation, calendar correction, migration
backfill, SQLite v1 upgrade, transaction rollback, restart and Arabic controls.
Android device/keystore/airplane-mode QA remains NOT_RUN. Stop for review before PR-05.
