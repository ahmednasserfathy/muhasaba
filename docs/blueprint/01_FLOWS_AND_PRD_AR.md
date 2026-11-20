# 01 | User Flows and Functional Requirements

## Navigation (Android-first)

1. `تسجيل الدخول / إنشاء حساب` -> `المحاسبة اليوم`.
2. `المحاسبة اليوم`: date picker, progress bar, 8 category sections, 34 activity tiles, category details via `?`, reset/edit controls, bottom navigation.
3. `نافذة أذكار`: title, vertically scrollable items, Arabic tashkeel-safe text, `(N مرة)` target, `0/N` or `N/N` completed badge, clear completed state, close button and parent progress.
4. `الصيام`: current date, `سُنّة الاثنين والخميس` default or `رمضان` if confirmed period or `تطوع/قضاء/آخر` if user opted in; allow user to add any date.
5. `التقارير`: daily/week/month and completion trend, denominator transparency.
6. `التذكيرات`: local toggles, chosen hours, categories, fasting reminders, quiet hours.
7. `الحساب`: timezone, source label if desired (never stigmatizing), password/profile and data export/delete later.

## Flow A, new user

- Register native account, verify email where available, set locale/timezone (default Arabic / Africa-Cairo), choose a tracking start date (default today).
- Fetch signed/published catalog. Save local cache before journal appears.
- Open current day. All eligible cards are pending. Fasting eligibility depends on date/user planning.
- External-import account is not a separate screen type. Imported users must activate credentials or authenticate through supported external identity integration before app access.

## Flow B, card without details

- Tap `fajr_pre_sunnah`, change PENDING -> COMPLETED -> PENDING. UI turns green/red immediately.
- Save state and client mutation UUID locally in one transaction. Update total weighted points locally. Background sync while network available.
- If explicitly set EXCLUDED, show a neutral disabled style and remove its weight from the day's denominator. No medical-reason field.

## Flow C, card with adhkar (critical)

- Tap `?` next to `dhikr_mosque` to open a modal. UI shows two or more ordered items, their text and their target repetition counts.
- For `required_count=1`, tapping an item toggles `0/1 <-> 1/1`. For `required_count>1`, +1 up to max, with a clear/reduce control.
- Every dhikr item/repetition earns **proportional credit immediately**. Group score is `group_weight * mean(item completed_count/target_count)`, capped at full weight. Status is PENDING (zero), PARTIAL (>0 and <1), COMPLETE (all), or EXCLUDED (explicit override). Individual completed items green; partial parent uses a distinct progress treatment, not a misleading all-green state.
- Main card displays `earned / possible` score, group progress and motivating next action. Display after each tap: "أحسنت، تقدمت خطوة، باقي ... لرفع نقاطك"; no all-or-nothing scoring.
- Parent-card tap on `ADHKAR_SET` opens details by default. Optional explicit `إكمال الكل` button can atomically update all children if retained after usability testing; never silently mark unseen adhkar complete. The question-mark area may also open details.
- On date change, opening the same set reads the selected date's counters. The text can be cached and displayed offline. No new day inherits yesterday's counters.
- If a user sets a group EXCLUDED for that date, its items can remain stored but do not count toward score while excluded; remove exclusion restores derived progress.

## Flow D, fasting days

- Monday/Thursday: fasting is planned/eligible by default as weekly sunnah. User can choose completion or explicitly opt out for a neutral day, depending on agreed product policy.
- Any other day: fasting is not in the denominator unless the user taps `أضف صيام اليوم` or plans it on a calendar. Choice `VOLUNTARY`, `MAKEUP`, or `OTHER` is optional metadata.
- Ramadan: fasting is eligible for configured, confirmed Ramadan period dates for user's selected locale/region. Calendar boundaries must be configurable for moon-sighting differences.
- Allow fasting exemptions without asking for a medical or religious explanation.
- Planning on a future day is allowed, marking a future day as completed is not.
- No pretense to decide religious rulings: these are product reminder/score defaults, user-adjustable where appropriate.

## Flow E, notifications

- User enables a reminder category, sets time in local timezone, grants Android notifications permission.
- App schedules local reminders: morning/evening adhkar, before sleep, end-of-day journal, fasting reminder the evening before a planned fast. Also optional motivational summary when some **eligible** actions remain.
- In-app encouragement updates instantly with the earned partial score, remaining count and gain possible. The optional OS reminder is time-based, at most once/day, not after each tap. Tapping reminder deep-links to relevant outstanding items.
- Quiet hours, category selection and frequency controls; no reminder if disabled or locally known work is completed/excluded. Reschedule/cancel on local state/date/timezone changes and upon device reboot when supported. Handle permission denied gracefully.
- Notifications never reveal private completion scores on locked screen by default; offline local scheduling is not guaranteed to detect concurrent changes on a different device.

## Flow F, imported/external identity (deferred integration)

- Admin-only approved import: read minimal external identity, normalize, insert `users` with `registration_source=IMPORTED`, link `external_identities(source_system,external_subject)`.
- Imported identity receives activation/invitation, or uses a verified external OIDC flow if the provider supports it. Never import plaintext passwords or rely on a database's password hash being compatible.
- If a native user also has external identity, they remain one canonical `user_id`, and `external_identities` records a verified link. Never merge by matching email alone.
- App displays the same journal regardless of account origin. All user records key by canonical `user_id`, not external user ID.

## Flow G, offline and sync

- Day UI remains usable offline after account initialization/catalog bootstrap.
- Every local edit changes SQLite state and adds outbox mutation atomically. Sync when online; retry with idempotency keys, keep unsent operations across restarts.
- In V1 support one primary editing device per account, with protected backup/restore. A second simultaneous editor must not silently overwrite data; version mismatch shows conflict and a user resolution choice.
- No complex infinite retention event log or full real-time device synchronization until multi-device requirement is confirmed.

## UX acceptance requirements

- Arabic RTL and correct Quranic/Arabic diacritics rendering; accessible font scaling and color contrast.
- Independent tap areas for question mark and completion card.
- Scrollable modal with visible completion count, title, close, and safe scrolling in small Android devices.
- Weekly/monthly report explicitly indicates which days count and when fasting was eligible.
- Undo on mistaken taps, past-day editing within user history, current-date header, progress percent deterministic.

## Flow H, accidental completion and undo (v1.3)

1. On a `TOGGLE` card like `dhuhr`, a first tap changes `PENDING -> COMPLETED`, grants configured points and marks the card green. The **same tap again** changes `COMPLETED -> PENDING`, removes those points, and restores its pending appearance. Do not ask for a destructive confirmation on every undo.
2. UI toggles locally before network response. Sync carries the **desired explicit state**, not a server-side `toggle` command; `PUT` and mutation UUID prevent duplicated retries from flipping a state twice.
3. If two taps happen rapidly while offline, local state represents the **last user intent**. Outbox may coalesce unsent changes for one card only if it preserves mutation/revision semantics; never silently discard a server-confirmed remote change.
4. For individual dhikr with `target_count=1`, tap again to undo; for repeated dhikr, show `+1` and `-1`, bounded `0..target_count`. Undo changes only that item, not the whole group.
5. A future *calendar date* cannot be marked complete. A prayer whose clock time has not yet arrived **is not hard blocked** because no prayer-times provider exists in MVP; we will not invent time-of-prayer status. Optional warning requires an independently reviewed time provider and user preference.

## Flow I, my adhkar and dua, personalized morning group (v1.4)

1. From an existing `ADHKAR_SET` (e.g. `morning_adhkar`), user chooses `تخصيص المجموعة`.
2. Show the published default items with `إظهار / إخفاء من خطتي` controls, a `استعادة الافتراضي` action, and personal items below them. Hidden defaults remain in the official library and are not edited globally.
3. `أضف ذكرًا أو دعاءً شخصيًا`: title optional, full Arabic text, `type` (`DHIKR` or `DUA`), repetition target (positive integer), item order. Can add several own items to existing set. Each custom item may appear as a personal sub-card within the group (or a normal detail row) without a new independent score weight. Personal content is private, not reviewed or broadcast to others.
4. User may edit/archive their own items. Once progress exists for an item/date, changes to its text/target are prospective; historical journal snapshots remain readable with original count target.
5. Saving a new plan is effective from next local day **by default**. For a current day with no edits to the affected group, user may choose `تطبيق اليوم`. If progress already exists, apply next day to avoid losing or reinterpreting recorded progress. Communicate the effective date clearly.
- Scores for an `ADHKAR_SET` are based on all **official published score-eligible item snapshots** for the activity, even if some are hidden in the user interface. Personal items are track-only, never score-bearing; their completion is not a condition for earning the full official card weight. Hiding/reordering does not change score or denominator. If there are zero official scoring items, block publication as a scored ADHKAR_SET (configuration error), rather than declaring 0 possible. The UI must clearly expose hidden outstanding official items with a show/restore option.
7. Restore default plan via a new effective-dated plan revision, not a destructive delete. Past dates remain on their originally effective plan.
- The daily percent means **earned weighted main-card points / eligible weighted main-card points**. Custom texts and personal display plans never change this formula. Show a separate optional `تقدم أذكاري الشخصية` summary, not rolled into the official score. Scores are self-tracking feedback and should not be treated as a measure of spiritual value.

## Flow J, official score vs personal tracking (locked v1.4)

1. An ADHKAR_SET card opens a list of official and optional personal items. Each row clearly identifies `رسمي (ضمن نقاط الكارت)` or `شخصي (للمتابعة فقط)` where needed.
2. Official items contribute proportionally to the fixed parent score, regardless of display hiding or item order. Hiding changes visibility only, never record completion or score eligibility.
3. Personal items can be completed, undone, moved or archived; their counts and reminders are private and **do not** change the card score. Completing all official items fills the parent weight even if custom items are unfinished.
4. UI must give a clear unobtrusive route to reveal hidden official items, especially those still pending, to avoid an apparent score that cannot reach 100%.
5. Personal group editing cannot change top-level weights. Existing days remain tied to original catalog snapshots; plan changes do not rewrite them.