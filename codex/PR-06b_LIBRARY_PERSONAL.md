# PR-06b: official library and private group customization

PR-06 is accepted and merged. This slice implements blueprint chapter 09 using
existing FastAPI auth, PostgreSQL receipts and the Drift journal outbox. No admin
frontend, new scoring units, religious content seed, hosting or Android device
validation. Android acceptance remains deferred to PR-07 at the user's request.

## User flow and history

Daily card details → «تخصيص المجموعة». Choose tomorrow (default), or today before
any recorded edit to that group, including a counter that was subsequently undone.
Add/edit/archive private DHIKR/DUA with 1–1000 repetitions, order private items,
hide/order official defaults, or restore the defaults and save. Maximum 100 private
items per group. Each private UUID belongs to one owner and one group; to use the
same text in another group, add another item. Restore creates a dated revision,
archives omitted items and never deletes historical progress.

Official and private progress appear separately. Hidden official items remain in
the score denominator and can always be revealed in details. Bulk complete/clear
updates official counters only. Private completion never affects official points.
Reminders require visible unfinished official scored items; private notifications
are not enabled in this slice. Reminder messages never include private text.

First journal edit freezes every group's dated plan with text/target snapshots.
A today's unstarted group can replace its snapshot; started groups cannot.
Applying a new today plan after scheduling tomorrow is rejected to avoid silently
reverting to an earlier revision tomorrow. Editing/archiving library or private
sources never rewrites the prior day's stored text, targets, counts or scores.

## API and concurrency

All private routes use the authenticated owner, including ADMIN accounts.
`GET /me/custom-items` lists own active/archived sources (bounded to 1000).
`GET /me/groups/{code}/plan?date=YYYY-MM-DD` defaults to tomorrow and returns the
applicable definition, official texts, catalogRelease and the latest group
rowVersion (the write precondition, not necessarily the day's pinned planVersion).
`PUT` atomically replaces hiddenDefaultCodes, officialOrder and inline customItems
(id, type, textAr, targetCount), with clientMutationId, expectedVersion,
catalogRelease and effectiveFrom. Only today/tomorrow are writable.

POST `/me/custom-items` and PATCH `/me/custom-items/{id}` take an `item` object plus
activityCode and the same dated/version/catalog/mutation context. DELETE at the
item route takes that context in its body and archives from the effective plan.
All return the updated group plan and share group-level concurrency. The mobile
editor uses one aggregate PUT so private text and plan membership commit together.
POST `/me/groups/{code}/restore-defaults` takes the plan write context and clears
all custom selection/hide/order fields in a new revision. Private count keys are
`personal:<uuid>` with expectedPlanVersion plus the existing absolute count and
row version. Official pre-upgrade receipt hashes remain compatible.

Every write locks its owner, records a mutation receipt and commits atomically.
Repeated UUID/body returns the original result; changed-body reuse or stale
versions conflict. Private validation errors redact submitted content and private
responses use no-store. Shared catalog responses contain no private content.

## Editorial API

ADMIN-only GET/POST `/admin/library-items`, PATCH `/{id}`, POST `/{id}/archive`.
Writes include UUID and expectedVersion; new source version is zero. Full source
writes require text, type, target, provenance URL/name and reuse notes. `verified`
records reviewer/time and marks the source ACTIVE; editing without it returns the
source to DRAFT. Archive preserves the source. No role-grant endpoint is exposed.

GET/POST `/admin/catalog-releases` lists or clones an existing release's fixed
cards/bindings into a future draft (baseReleaseId, code, effectiveFrom, version 0).
PUT `/{id}/groups/{code}/items` replaces a draft group's bindings from active,
reviewed library sources and copies immutable text/provenance snapshots. POST
`/{id}/publish` publishes the future draft after database validation. All draft
edits/publication use the release version. Empty/unverified scoring groups fail.
Editing/archiving a source does not change previously copied bindings; administrators
must explicitly replace a future draft's bindings before publication. Published
releases cannot be edited. Real source/license/editor review is still required;
there is no automatic factual verification of religious content.

## Persistence and offline limits

Alembic 0006 adds private items/plans, nullable custom snapshot links, source/XOR
constraints, frozen group plans and editorial versions/reviewer metadata. Existing
journal days are backfilled with empty plans; official history is unchanged.
Downgrade deletes private plan/count data: never run on live data as a rollback.
Use backups and a reviewed forward migration instead.

Drift v4 adds owner/backend-scoped local_group_plans separate from shared catalog
and journal documents. Plan cache, optional today's projection and outbox insert
are one SQLite transaction. One pending plan per group is allowed; synchronize
or resolve it before editing that group again. Today's projected plan must sync
before recording the day's counters. Tomorrow plans can be saved offline after
the configuration has been loaded once. This conservative limit avoids rebasing
private counters against a rejected plan. An old pending effective date is still
accessible for explicit conflict comparison/discard after midnight.

A failed/stale plan pauses the existing ordered outbox. Compare local/server plan
and explicitly retain it or adopt the server version; unrelated queued edits are
preserved. A failed write never silently migrates its effective date. Daily journal
conflict resolution cannot discard a queued plan. Older GETs cannot overwrite
queued edits. Content typed but not saved in the editor is a transient draft.

## Verification

- Local PASS: Ruff lint/format, OpenAPI snapshot, 66 backend unit tests, Flutter
  analysis/format. Real PostgreSQL integration checks require CI (no local Docker).
- Local NOT_RUN: Flutter tests are blocked before test execution by the existing
  objective_c native build hook / missing macOS SDK. Linux CI runs the suite.
- Tests cover five official/three complete = 1.2/2 despite hiding two and completing
  personal text, owner/admin isolation, history/archives, expected versions and
  old receipt compatibility, publication guards, atomic offline rollback/retry,
  personal counters, v3/v4 persistence, reminder filtering and Arabic customization.
- Device/emulator/APK and production deployment: NOT_RUN, deferred.

Stop for PR review before PR-07 final integration and Android work.
