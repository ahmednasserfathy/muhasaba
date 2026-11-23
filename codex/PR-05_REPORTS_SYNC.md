# PR-05: reports and bounded restore

PR-04 is accepted and merged. This slice adds weekly/monthly reports and safe
history restoration; no migrations, new dependencies or scoring-rule changes.
Android device testing is deferred to PR-07 per user request; automated Flutter
analysis and tests continue in every PR.

## API and score contracts

Authenticated GET `/api/v1/reports/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`
returns daily summaries, fasting details, period summary and unavailableDates.
GET `/api/v1/days?from=YYYY-MM-DD&to=YYYY-MM-DD` returns complete DayViews for
restoring counters, versions, catalog definitions and fasting plans on a device.
Both accept inclusive ranges of 1–31 days. Longer/reversed ranges return 422.
Requested boundaries are returned as fromDate/toDate. Only dates between the
account tracking start and its timezone-local today are included. Empty windows
return no days and a null percentage, never 100%.

Days with no published catalog are explicitly listed in unavailableDates; totals
cover available days only and the UI labels them incomplete. Unedited days with
available content have zero earned and the normal eligible denominator. This
avoids pretending unknown catalog weights are zero. No reads materialize journals.
Pinned releases and fasting baselines use the same resolution as the daily API.

Period percentage is sum(earned)/sum(possible), rounded half up at display only,
not an average of daily percentages. The existing journal calculation now exposes
its exact Fraction score alongside DayView so reports cannot accumulate rounded
float values. Dart also retains Fraction through period aggregation. The shared
account read lock prevents journal/fasting writes interleaving across the window.
Responses are private/no-store and never accept a user ID as authority.

## Mobile and sync

Account → «التقارير» opens an Arabic RTL weekly view (Monday–Sunday), with calendar
month selection and previous/next navigation. Future and pre-tracking dates never
contribute. The timeline shows each available day's earned/possible and fasting
plan status; unavailable dates have a separate explicit label.

Reports synchronize existing outbox work before requesting the canonical server
summary. If work remains pending, or a local revision changes during the request,
they use local exact totals instead. Connection failures also use local totals,
clearly labeled as device data that may be incomplete or unsynchronized.

«حفظ الفترة دون اتصال» retrieves at most 31 full days in one request and stores
them atomically using existing SQLite tables, scoped to API base URL and account.
It never deletes outbox work. Dates with pending edits are skipped. A changed
local revision during the request discards the stale response, and per-date
cache comparisons guard changes from another repository instance. Unavailable
dates do not erase previously cached history. Restore can be repeated and older
months restored separately; no whole-account unbounded download or background job.

Existing same-UUID replay, conflict pause and explicit server-adoption flow remain
in the daily screen. Mutation receipts remain retained without pruning: expiring
them could break long-offline retries. No forced conflict merge or silent rebase.

## Verification and limits

Run root README checks. Regression coverage includes weighted denominators,
partial progress, missing catalogs, tracking/today bounds, exclusions, pinned
releases, authorization, account isolation, atomic restore rollback and stale
restore responses after an acknowledged edit. Flutter tests include the Arabic
weekly/monthly controls and offline saving.

CI runs real PostgreSQL/Compose migrations and Flutter on Linux. Local macOS
Flutter native-assets setup remains blocked by Xcode; device/keystore/airplane-mode
QA is NOT_RUN and deferred to PR-07. Final test counts are recorded in the PR.
No schema rollback is needed; revert application changes to remove this feature.
Stop for review before PR-06.
