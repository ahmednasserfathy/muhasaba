# 08 | Decisions, Risks, Quality, Security

## Signed-off user requirements vs product choices

| ID | Question | Evidence | Our default | Status |
|---|---|---|---|---|
| D01 | Backend language | Explicit user preference | Python/FastAPI | CONFIRMED |
| D02 | Adhkar detail | Screenshot shows `0/1` and `1/1`; user explicitly requires credit for partial completion | Per-item counter, proportional group points immediately, derived PARTIAL/COMPLETE state | USER REQUIREMENT CONFIRMED; exact formula PROPOSED |
| D03 | Activity tile numbers | Reference video with 74-point fit | Use numeric badge as score weight | INFERRED, verify before public claim |
| D04 | Native notifications | User explicitly requests nudges to finish outstanding items | Gentle opt-in locally scheduled progress reminder, once/day max, deep-link to remaining work; in-app feedback immediate | USER REQUIREMENT CONFIRMED; frequency PROPOSED |
| D05 | Fasting patterns | Explicit user preference | Mon/Thu default, any day opt-in, Ramadan calendar configured | CONFIRMED UX, exceptions proposed |
| D06 | Ramadan dates | Dates vary by locale/sighting | Confirmed region calendar, manual override/skip | PROPOSED |
| D07 | External users | User says integration probable | Internal UUID + origin + optional linked identity; adapter later | CONFIRMED READINESS, provider unknown |
| D08 | Videos / official API | User wants official integration | Official public video links first; only use documented/authorized API | OPEN PROVIDER / RIGHTS |
| D09 | Notifications prayer-time relative | Not specified | Fixed user times, no GPS/adhan API | PROPOSED |
| D10 | Detailed dhikr completion | User rejects all-or-nothing and requests encouragement | Each item has equal share of parent weight, fractions within multi-repeat item, no double count | PARTIAL SCORING CONFIRMED; precise allocation PROPOSED |
| D11 | Imported login | External DB not described | Invite-based activation or OIDC if supported; no reused password hashes | PROPOSED |
| D12 | Multiple devices | Not explicitly required | Primary-device editing initially; version conflicts protected | PROPOSED |
| D13 | Religious texts and license | No full authoritative corpus provided | Verified and licensed content required before launch | BLOCKER for corresponding collections |

## Security basics, proportionate to this product

- TLS everywhere, token verification and rotation, secure mobile storage; never log Authorization headers, refresh token, personal journal or religious activity labels with user IDs.
- Rate limit auth and sensitive endpoints; verify email ownership before linking accounts. Password hashing via modern vetted library (Argon2id preferred), secure reset/activation.
- `user_id` always derived from authenticated token in server queries. Test cross-account data leaks on all daily, report and adhkar endpoints.
- Postgres backups with at least one restore drill. Restrict production DB network. Least-privilege role and no migration auto-run from mobile.
- Preserve offline journal in app encrypted at rest if threat model warrants it; at minimum OS protected storage, prevent cross-user cached-data exposure on logout/user switch.
- Clear deletion/retention policy: allow account deletion, revoke external identity links and purge journal data based on stated retention.
- Avoid storing medical reasons for exclusions; period toggles should be neutral and private, not a diagnosis record.
- Third-party video embeds may collect viewing activity; disclose and use user-initiated playback. Do not infer personal spiritual beliefs or advertise against them.

## Test strategy

1. **Pure Python pytest:** score, date eligibility, Ramadan priority, percent rounding, adhkar target counts, catalog immutability.
2. **FastAPI integration against real test PostgreSQL:** Alembic migration upgrade; FK/unique constraints; cross-user authz; idempotent replay; stale expectedVersion conflict; no duplicate child counts.
3. **Flutter unit/widget:** modal RTL layout, long tashkeel, large text scale, separate help tap vs complete, live score on update, undo, empty calendar.
4. **Offline e2e:** force airplane mode, record several dhikr, restart app, reconnect, verify exact original counts and latest score.
5. **Notification QA:** Android permission denied, reschedule when local zone/date changes, planned Wednesday fast reminder, quiet hours, max one motivational reminder/day, cancel on locally known completion/exclusion, deep link to remaining work, no private text on lock screen.
6. **External identity QA (Phase 2):** duplicate source subject, same email across two users, import retry, unauthorized connector, link revoke, dry run.

## Pre-production gates

- Real staging backend with TLS, migration applied, clean sample accounts, fresh/install upgrade tests.
- Validated Arabic texts and licensed video links, or hide unfinished screens until approved.
- Users can view scoring explanation (`why denominator changed`) and control reminders/exclusions.
- Monitor error rates, DB health, 401/409 rates, offline outbox pending count without private journal content.
- Recovery guide and tested DB restore. Publish privacy policy, support contact, account/data deletion request flow before broader release.

## Minimalism guardrails

- The schema may contain an unused `external_identities` table now, but NO direct external connector until its source format is known.
- No scheduled server notification workers while local notifications meet the requirement.
- No video API integration when a reviewed official video URL already solves playback.
- Support user-authored adhkar/dua inside existing group cards as PR-06b, **after** core 34 activities and reversible journal work. No arbitrary new weighted top-level activities or complex CMS frontend in MVP.
- No heavy sync feed, distributed locks or event-sourcing; use idempotent mutations plus row versions. Revisit if true multi-device editing is needed.

## v1.3 new decisions and tests

| ID | Area | Rule | Evidence |
|---|---|---|---|
| D14 | Accidental tap | Any normal completed card can be tapped again to revert to pending and reduce score | USER REQUIREMENT CONFIRMED |
| D15 | Prayer clock-time | Do not falsely block Dhuhr based on missing/guessed prayer times; only block future date journal completion | PROPOSED safe MVP policy |
| D16 | Official Library | Admin-only create/edit/verify/archive/publish, immutable published snapshots | USER REQUIREMENT CONFIRMED; storage policy PROPOSED |
| D17 | Private dua/adhkar | Users add their own private content to an existing group, hide defaults only from their own plan, restore later | USER REQUIREMENT CONFIRMED |
| D18 | Main-card score isolation | Only official score-eligible items can earn a fixed ADHKAR_SET parent card's points; private additions and hide/reorder changes never alter earned/possible points | USER REQUIREMENT CONFIRMED, v1.4 |
| D19 | Effective date | Plan changes default to next day; allow same day only before that group's progress starts | PROPOSED to protect history |

### Additional tests

- Tap to complete then tap to undo regular activity; score reverses exactly, even after offline retry.
- Decrement multi-repeat dhikr and toggle a target-one dhikr; parent goes COMPLETE -> PARTIAL -> PENDING as appropriate.
- Admin adds an approved official item and publishes new release. Old users' dated activity remains on old release. Editing a draft cannot mutate published content.
- User A hides default item in group; user B still sees it; official group unchanged. User A adds own dua to morning group, and cannot access B's personal content by guessing IDs.
- Under five official score-bearing items and weight=2, 3/5 complete => 1.2 earned. Hiding pending official items, adding private items and completing private ones leaves score at 1.2/2. Hiding all defaults still leaves original possible points; never grants free score.
- User modifies plan in a new effective revision; historical snapshots, texts, repetition targets, score and daily reports do not change.
- Personal text never appears in shared/public catalog endpoints, other user reports or sensitive system logs; custom text on lock-screen notifications disabled by default.