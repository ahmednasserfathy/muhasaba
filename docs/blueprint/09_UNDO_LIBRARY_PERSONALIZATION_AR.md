# 09 | Approved feature specification, Undo & Library Personalization (v1.4)

## Product intent

Any effort matters; mistaken taps are reversible. Official reviewed adhkar/dua remain admin-controlled, while each user may adapt an existing adhkar card to their own routine, without changing the shared library. The overall score measures completed **fixed-weight main activity cards**, not the user's personal library contents or spiritual merit.

## Decision A: Card undo

| Before | Interaction | After | Score effect |
|---|---|---|---|
| PENDING Dhuhr | Tap | COMPLETED | +activity points |
| COMPLETED Dhuhr | Tap again | PENDING | -exact same points |
| Dhikr `0/1` | Tap | `1/1` | +fractional group points |
| Dhikr `1/1` | Tap again | `0/1` | -fractional group points |
| Dhikr `2/3` | Press `-` | `1/3` | -1/3 of item share |

- Show immediate, accessible visual feedback; green = completed, red/dim = pending, partially completed sets have their own style.
- The same button always permits undo. No irreversible one-way action for journal marks.
- Restrict completed *future calendar dates*, but don't invent prayer-clock restrictions. User can correct an erroneously marked Dhuhr within allowed journal history.
- Use explicit `PUT state=COMPLETED|PENDING` with mutation UUID and expectedVersion. Client double tap must resolve to last desired state, retries cannot toggle twice.

## Decision B: Admin controls the official library

- Admin can add a new source item, edit drafts, choose DHIKR or DUA, set text/tashkeel, target repetitions, source/attribution, status and group bindings.
- Verify source and license/reuse permissions before exposing content as official.
- Admin may archive/remove a published item from **future releases**; no physical deletion of source/history and no mutation of past journal releases.
- Start with protected FastAPI CRUD and OpenAPI docs; design a thin admin UI only when used by real administrators. No independent admin backend.

## Decision C: User personal library

- A user can add private adhkar/dua and attach them to an existing group such as `أذكار الصباح`. A personal item may render as its own **sub-card within that group** or as a row in its modal, but this is a presentation option, not an additional top-level weighted score. A later dedicated `أذكاري الخاصة` display may list all personal items without double-counting.
- Group customization page lists official default texts with eye/show-hide control and own content with add/edit/archive/ordering/repetition controls.
- Hide a default removes it from *this user's active plan*, not the official library and not another user's plan. Restore defaults creates a new plan revision.
- Private text is never sent via shared catalog or marked `verified`; user retains ownership, data deletion/privacy controls apply.
- No user-created new top-level weighted activity or global publishing in the MVP.

## Decision D: Official weighted parent score, separate personal progress (v1.4)

- Only main activity cards own weighted points. For scored ADHKAR_SET, the verified **official score-eligible items** from the pinned catalog release split the parent weight evenly.
- Hiding an official item is a **display preference only**, it does not complete it, award points, remove it from the denominator, or change the other official items' shares. Users can always reveal hidden official remaining items.
- User-written private dhikr/dua items can be ticked and tracked in the same group but are **tracking-only** and award no official score. Completing them is not required for full official points.
- Example: weight=2, five official items, three completed gives `2*3/5 = 1.2`. Hide the other two and add/complete one private dua, still **1.2/2**, not 2/2. Complete the two outstanding official ones => 2/2.
- A scored group with no approved official scoring items must fail catalog publication. Zero visible entries is **not** `NOT_CONFIGURED` and does not remove its main-card points from `possible`.
- Reports show **main card score** and a separate optional private-item progress summary, never a combined score.

## Decision E: History, offline, notifications

- Personal plan versions have an effective date. **Proposed UX**: tomorrow by default; apply today only before any progress in that group today. This is configurable before coding, not claimed as original site behavior.
- On first edit to a day/group, freeze item list, original text, target count and source type in journal day count snapshots. Historical scores don't drift when someone edits/archives an item, restores defaults or admin publishes a new release.
- Local Drift cache/outbox stores user-owned plan + item additions separate from shared cached catalog. All edit writes idempotent; private content must not mix across user IDs upon logout/login.
- Positive local reminders may link to remaining visible unfinished items. Hidden defaults and archived personal items do **not** trigger guilt-based reminders. No extra notification worker/server.

## Minimal database delta from v1.2

1. `library_entries`: global ADMIN-authored reviewed/draft/archived source items.
2. `adhkar_items.library_entry_id` optional: immutable item assignment/snapshot within a catalog release.
3. `user_custom_items`: private owner-authored adhkar/dua.
4. `user_group_plans`: small, effective-dated per-group hide/order/custom item selection.
5. `journal_adhkar_counts` becomes resolved **day-item snapshot** with official/custom FK, text and target snapshot, actual completed count. Same row serves progress and score, avoiding extra event/history tables.
6. `users.role` distinguishes USER from ADMIN; no second user database.

## API delta

- Existing `PUT /days/{date}/activities/{code}` explicitly sets `PENDING` for undo.
- Existing `PUT /days/{date}/adhkar/{item_key}` sets absolute `completedCount` including `0`.
- Admin: `GET/POST/PATCH /admin/library-items`, archive item, and publish catalog release.
- User: `GET/POST/PATCH/DELETE /me/custom-items`, `GET/PUT /me/groups/{code}/plan`, `POST /me/groups/{code}/restore-defaults`.

## Acceptance tests for Codex

1. Dhuhr mark then undo, score returns to original exact value; offline rapid double tap and retry remain stable.
2. Individual adhkar 1/1 undone to 0/1, larger counters decrement, unrelated items unaffected.
3. Private item add/hide defaults changes only the owner, never another user or official library. No cross-user read or write.
4. Three of five official items complete in a weight-2 card equals 1.2/2; hide two pending defaults and complete a newly added private item, official score remains 1.2/2, not 2/2. Custom additions never change max weight or earned points.
5. Plan change and catalog publication don't recalculate earlier dated scores or rewrite old personal item text.
6. Permission matrix: ordinary user cannot publish official library and admin cannot bypass item ownership without explicit approved access workflow.
7. Reminders target eligible visible unfinished official work and/or explicitly opted-in personal items, respect hidden display preferences, opt-out and quiet hours. Hidden official work remains in score and can be revealed from the progress explanation.

## References

- API semantic idempotence for PUT: https://www.rfc-editor.org/rfc/rfc9110.html#name-put
- Flutter offline-first design: https://docs.flutter.dev/app-architecture/design-patterns/offline-first
- FastAPI security guidance: https://fastapi.tiangolo.com/tutorial/security/