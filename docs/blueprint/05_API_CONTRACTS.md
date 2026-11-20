# 05 | FastAPI REST Contracts v1.1

**Base:** `/api/v1`, HTTPS+JSON UTF-8. All date params are ISO local `YYYY-MM-DD`. Bearer access token except public register/login. API derives user ID from token; never accepts another user's ID as authority.

## Endpoint matrix

| Method | Endpoint | Purpose | Phase |
|---|---|---|---|
| POST | `/auth/register` | Native account creation, password hash, email activation flow | PR-02 |
| POST | `/auth/login` | Return access/rotating refresh tokens | PR-02 |
| POST | `/auth/refresh` | Rotate refresh token | PR-02 |
| POST | `/auth/logout` | Revoke session | PR-02 |
| GET | `/me` | Canonical account and registrationSource | PR-02 |
| GET | `/catalog?date=...` | Versioned categories, activities, verified adhkar items | PR-01 |
| GET | `/days/{date}` | Daily statuses, counters, fasting eligibility, percent | PR-03 |
| PUT | `/days/{date}/activities/{code}` | Set PENDING/COMPLETED/EXCLUDED for TOGGLE/FASTING, or EXCLUDED/PENDING for ADHKAR_SET | PR-03 |
| PUT | `/days/{date}/adhkar/{item_code}` | Set individual item's counter | PR-03 |
| PUT | `/days/{date}/adhkar-sets/{activity_code}` | Atomic bulk-complete/clear verified set | PR-03 |
| PUT | `/days/{date}/fasting-plan` | Override ADD/SKIP/DEFAULT, optional type | PR-04 |
| GET | `/fasting/calendar?from=&to=` | Eligible/added skipped fasting dates and Ramadan info | PR-04 |
| GET | `/days?from=&to=` | Bounded day summaries for restore and reports | PR-05 |
| GET | `/reports/summary?from=&to=` | Earned, possible, percent, per-day timeline | PR-05 |
| GET/PATCH | `/settings` | Portable reminder preferences and timezone | PR-06 |
| GET | `/resources?activityCode=...` | Reviewed official video references only, when built | Phase 2 |

**Not in MVP:** `/admin/import/users` live endpoint, external password sharing, unknown official site proxy, push-notification campaigns.

## Contract: catalog

`GET /api/v1/catalog?date=2026-11-19`

```json
{
  "release": "reference-2026-11-19",
  "categories": [
    {
      "code": "DHIKR", "titleAr": "أذكار متنوعة", "sortOrder": 8,
      "activities": [
        {
          "code": "dhikr_mosque", "titleAr": "المسجد دخول وخروج",
          "points": 2, "kind": "ADHKAR_SET", "showDetails": true,
          "items": [
            {"code": "mosque_entry", "sortOrder": 1, "targetCount": 1,
             "textAr": "[النص المعتمد بعد المراجعة]", "reviewStatus": "DRAFT"}
          ]
        }
      ]
    }
  ]
}
```

The object is illustrative, **not a production seed**. Do not expose `DRAFT` text as authoritative in released catalog; production returns only verified items. Client caches by immutable release ID.

## Contract: daily state

`GET /api/v1/days/2026-11-19`

```json
{
  "date": "2026-11-19",
  "catalogRelease": "reference-2026-11-19",
  "fasting": {"eligible": true, "reason": "WEEKLY", "override": null},
  "activities": [
    {"code": "dhikr_mosque", "kind": "ADHKAR_SET", "status": "PARTIAL",
     "completedItems": 1, "totalItems": 2, "progressFraction": 0.5, "earnedPoints": 1, "possiblePoints": 2},
    {"code": "night_witr", "kind": "TOGGLE", "status": "COMPLETED", "earnedPoints": 1, "possiblePoints": 1}
  ],
  "adhkarCounts": [
    {"itemCode": "mosque_entry", "completedCount": 1, "targetCount": 1, "rowVersion": 1},
    {"itemCode": "mosque_exit", "completedCount": 0, "targetCount": 1, "rowVersion": 0}
  ],
  "summary": {"earned": 2, "possible": 74, "percent": 3}
}
```

Only examples: the response is abbreviated, `summary` corresponds to the two shown activity earnings (1 partial dhikr + 1 witr) and 74 possible. Day's real percent is calculated from **all 34 eligible catalog items**, whether omitted from this example or not. Values are decimals; clients should not accumulate individually rounded percentages.

## Contracts: write mutations

All writes include `clientMutationId` UUID (stored in `mutation_receipts`) and `expectedVersion` (0 if never written). The API returns new row version, canonical state, updated day score. A stale version yields `409 CONFLICT`; same mutation ID and payload returns original result. Same mutation ID with different payload yields `409 IDEMPOTENCY_KEY_REUSE`.

### Change regular card

`PUT /days/2026-11-19/activities/night_witr`

```json
{
  "state": "COMPLETED",
  "expectedVersion": 0,
  "clientMutationId": "5e3f5e34-c5a8-4114-8e55-6126b1781e54"
}
```

Never allow `COMPLETED` or `PARTIAL` to be written directly on an `ADHKAR_SET`: both are derived from its counters. Allow `EXCLUDED` for an adhkar parent via this route.

### Update one dhikr counter

`PUT /days/2026-11-19/adhkar/official:dhikr_mosque:mosque_entry`

```json
{
  "completedCount": 1,
  "expectedVersion": 0,
  "clientMutationId": "cb65d00f-23c2-497c-9b2f-55e5eb37a1af"
}
```

Returns a new item version, parent status, and daily score. Validate `0 <= completedCount <= targetCount`, item is verified and associated with the pinned catalog release.

### Bulk-complete all dhikr children

`PUT /days/2026-11-19/adhkar-sets/dhikr_mosque`

```json
{
  "action": "COMPLETE_ALL",
  "expectedVersions": {"mosque_entry": 1, "mosque_exit": 0},
  "clientMutationId": "41161258-8c46-47ee-9073-8f9576814e99"
}
```

Actions `COMPLETE_ALL` and `CLEAR_ALL`, transactionally updates each verified child; all-or-nothing if any expected version stale. In local Offline mode this is one logical outbox operation.

### Fasting plan override

`PUT /days/2026-11-18/fasting-plan`

```json
{
  "mode": "ADD", "fastType": "VOLUNTARY",
  "expectedVersion": 0,
  "clientMutationId": "17f58922-3e62-4994-a32e-de6622d97982"
}
```

`mode`: `DEFAULT`, `ADD`, `SKIP`. `DEFAULT` restores scheduled policy. For sync versioning, `fasting_overrides` should retain row and version when cleared, or use a documented per-date concurrency token. **Implementation decision:** add `row_version INT NOT NULL DEFAULT 1` and `mode='DEFAULT'` as stored state once edited, so versions are never reset (see database migration note).

## Conflict, auth and errors

```json
{"error": {"code":"CONFLICT", "messageAr":"تم تغيير البيانات على جهاز آخر", "requestId":"...", "canonical":{"value":1,"version":3}}}
```

Relevant statuses: `200` success, `201` created, `400/422` validation, `401` invalid/expired authentication, `403` forbidden, `404` missing activity/unknown date, `409` idempotency or concurrency, `429` rate limit, `503` transient backend failure (local outbox remains pending).

## Import contract (future, no live route yet)

Define `ExternalIdentitySource` with `source_system`, `external_subject`, optional verified email, optional display name and activation state. Use admin-only batch import with dry-run report and conflicts before any write. Future external login through OIDC if available, otherwise invitation/reset flow. Never connect Flutter directly to an external database.

## OpenAPI deliverables

FastAPI generates `/openapi.json` and `/docs` for review. Commit schema snapshots to repo and check route response examples with integration tests. All operations validate ownership, date, release membership and item target counts server-side.

## v1.3 endpoints: undo, official library, and private plans

### Idempotent undo already supported by existing journal endpoint

`PUT /api/v1/days/{date}/activities/dhuhr` with `{ "state": "PENDING", "expectedVersion": 2, "clientMutationId": "<uuid>" }` removes a mistaken completion. Flutter tap sends explicit intended state, never `POST /toggle`; repeated delivery of the same mutation cannot re-complete the prayer. Date D may be today or a past date in account history, not a future completed date.

`PUT /api/v1/days/{date}/adhkar/{item_key}` sets absolute `completedCount` including zero. For personalized groups, `item_key` is a **stable, namespaced, day-resolved item key** returned by `GET /days/{date}` (e.g. `official:dhikr_mosque:mosque_entry` or `personal:<uuid>`), preventing collisions. Keys are resolvable even before the first count row is created; the first write atomically materializes the day/group snapshots. Response includes `source=OFFICIAL|PERSONAL`, per-item target, parent `PARTIAL|COMPLETE|PENDING|EXCLUDED` and updated score. Scored official groups cannot be published without at least one verified score-eligible official item.

### Official admin content (protected `ADMIN` role)

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/admin/library-items` | List/search drafts, verified, archived |
| POST | `/admin/library-items` | Draft new `DHIKR` or `DUA`, with text, default target and source |
| PATCH | `/admin/library-items/{id}` | Edit working draft; editing published text requires next release |
| POST | `/admin/library-items/{id}/archive` | Soft archive, never delete referenced released content |
| POST | `/admin/catalog-releases/{id}/publish` | Validate reviewed items and publish immutable release |

A minimal protected API is sufficient for first implementation, without a complex admin UI. Admin endpoints must validate `role=ADMIN`, never trust client-supplied roles.

### User-owned content and customization

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/me/custom-items` | Return only the authenticated user's content |
| POST | `/me/custom-items` | Add private dhikr/dua (`type`, `textAr`, `targetCount`, optional title) |
| PATCH | `/me/custom-items/{id}` | Edit own draft/prospective item; create revision where already tracked |
| DELETE | `/me/custom-items/{id}` | Soft archive own item; retain historical journal snapshots |
| GET | `/me/groups/{activityCode}/plan?date=...` | Effective visible official and personal items, including source/targets |
| PUT | `/me/groups/{activityCode}/plan` | Save replacement effective-dated plan, with hidden default item codes and ordered custom item IDs; client mutation ID and concurrency guard |
| POST | `/me/groups/{activityCode}/restore-defaults` | Create new effective-dated plan restoring official defaults |

Illustrative plan write (not a copy of the original site):

```json
{
  "effectiveFrom": "2026-11-21",
  "hiddenDefaultCodes": ["morning_item_b", "morning_item_d"],
  "customItems": [{"customItemId": "<own-uuid>", "sortOrder": 6}],
  "expectedVersion": 0,
  "clientMutationId": "<uuid>"
}
```

- Backend verifies every `customItemId` belongs to user, validates that official codes belong to specified group, stores ordered plan revision, and never changes official catalog.
- `effectiveFrom` defaults to user's next local date. `today` permitted only while that group/day has no progress, including locally-pending edits once reconciled; client warns if offline cannot confirm latest server progress.
- Read response for official `GET /catalog` is **public/shared only**; authenticated `GET /me/groups/.../plan` resolves private overrides. Keep authorization and caching separate to avoid leaking private text.
- Business errors: `400/422` invalid targets/source, `403` role or user ownership, `409` stale plan/version or active-day edits, `404` unknown group/item, `200/201` success. All write actions use request UUID to support retry.

## v1.4 API score/display contract

- `GET /api/v1/days/{date}` and dhikr count updates must return main-card `weight`, `earnedPoints`, `possiblePoints`, `officialCompleted`, `officialTotal`, and item-level `sourceType` and `isScoreEligible`. Personal items have `isScoreEligible=false`.
- Updating `PUT /api/v1/days/{date}/adhkar/{item_key}` for a `personal:<uuid>` changes private progress and optional personal tracking UI only; **dayScore and parent earnedPoints remain exactly unchanged**.
- `PUT /api/v1/me/groups/{activityCode}/plan` hide/unhide/reorder/add operations update the user-visible plan only; do **not** recalculate the score. A response should include a visibility note when hidden official entries remain incomplete.
- Official score eligibility is determined from day-pinned catalog snapshots, not `hiddenDefaultCodes` or `customItems`; no user API to set official score eligibility, points or total possible.
- `GET /api/v1/days/{date}` can supply `hiddenOfficialCount` and `hiddenOfficialIncompleteCount` plus `showHiddenDefaults` UI hook to avoid a confusing partially scored card.