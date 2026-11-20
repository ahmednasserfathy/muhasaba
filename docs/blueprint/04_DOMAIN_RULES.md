# 04 | Domain Logic: Dhikr, Weighted Score, Fasting, Ramadan, Reminders

## 1. Distinct units: `points` vs `target_count`

- In screenshot, main tile numeric badge `2` is **proposed** to mean weight `points=2`.
- In detail modal, badge `0/1` or `1/1` is **observed** item completion, not points.
- **Confirmed product requirement:** an `ADHKAR_SET` awards partial points as individual items/repetitions are completed, even if the whole set is unfinished. No all-or-nothing scoring.
- Each **official score-eligible item**, and only such an item, contributes an **equal share of the fixed parent activity weight**. Its fraction is `clamp(completed_count / target_count, 0, 1)`. Personal user-authored items and hidden/reordered UI state do not join the scoring set. Official scoring membership comes from the pinned published catalog, and never from the personalized view. `target_count` must be positive.
- Example: five items, each target 1, parent worth 2 points; three completed => `(3/5)*2 = 1.2` points, not zero. Two items, targets 1 and 3, at 1/1 and 1/3 => `(1 + 1/3)/2 * 2 = 1.333333...` points, not 0 and not 2.
- Do **not** award the parent score in addition to its item-derived fractional score. A complete set earns exactly its configured weight; progress/score is derived and never stored as a contradictory parent completion flag.
- Keep the full rational/Decimal precision in canonical scoring; round only for display, e.g. 1 decimal for points and integer percent for day score. Avoid incrementally adding rounded fractions.
- A published set has at least one verified item. If content remains unverified, do not publish it as a partial set and artificially inflate score. Never infer completion of an empty set.

## 2. Stable scoring definitions

For a given user/date/catalog release:

```
eligible(activity, date, user) =
    activity.active_in_release
    AND date >= user.tracking_start_date
    AND date <= today_in_user_timezone
    AND (activity is not FASTING OR fasting_is_planned(date, user))
    AND (activity is not EXCLUDED for that day)

fraction(activity, date, user) =
    if activity.kind in (TOGGLE, FASTING):
        1 if activity_state==COMPLETED else 0
    if activity.kind==ADHKAR_SET:
        mean(clamp(item.completed_count/item.target_count,0,1)
             for item in day_pinned_official_score_eligible_items)
        # exclude private custom items; ignore display hide/reorder overrides

possible = sum(points of eligible activities)
earned = sum(points * fraction(activity) for eligible activities)
percent = round_half_up(100*earned/possible) or null if possible=0
# For a partial set, UI status PARTIAL is derived. COMPLETE when fraction == 1;
# PENDING when fraction == 0; EXCLUDED when overridden for the day.
```

The original 34-card proposed seed has **74 reference points on Thursday**. Without fasting on an ordinary non-Monday/Thursday, denominator is **69** unless explicit added fast or Ramadan. 2/74 displays 3%; 8/74 is 11%; 12/74 is 16%; 24/74 is 32%. These are regression fixtures for the provisional weighting model, **not proof** of original implementation.

Do not store percentage as mutable canonical user state; compute on query and in app pure domain library. Compare API and Dart fixtures to guarantee parity.

## 3. Fasting precedence (specific)

1. If per-user override mode is SKIP, fasting is ineligible.
2. Else if override ADD, fasting is eligible, even on Wednesday.
3. Else if a CONFIRMED regional Ramadan interval covers date, fasting is eligible with default label `رمضان`.
4. Else if ISO weekday 1 or 4, fasting is eligible with default label `سنة الاثنين والخميس`.
5. Else not eligible; do not count as missed, but allow user to add it.

`fast_type` is display/planning metadata only and has no special weight. This priority is a product decision. Users may set exclusions without recording reasons or sensitive health data. During Ramadan on Monday/Thursday, the fast appears **once**, not duplicated as sunnah+Ramadan.

If Ramadan period is provisional/unavailable, default weekly rule still works, with clear in-app configuration/confirmation flow; do not falsely assert religious calendar authority.

## 4. Notifications (on device, opt-in)

- `MORNING_DHIKR`, `EVENING_DHIKR`, `BEDTIME`, `DAILY_REVIEW`, `FASTING_EVE`, and opt-in `INCOMPLETE_PROGRESS` motivational summary (maximum one summary per day, not one per tap or item).
- Defaults **off** until user opts in, chooses local time and Android permission is granted. Use IANA timezone, initial Africa/Cairo. Fast reminder scheduled previous evening for default/added fast, revise on plan changes.
- Offer **in-app encouragement** immediately after any completion: earned score, next attainable gain, a short non-judgmental message. This is in-app feedback, not an OS push notification.
- Opted-in motivational reminder uses latest **locally known** incomplete eligible work when scheduled; whenever local journal state changes, cancel/reschedule or suppress now-irrelevant pending reminders. Tapping opens remaining items/date (deep link). Never promise an exact fresh-completion check if the app is closed and edits happened on another device; local scheduled notifications are not a live server query.
- No reminders for excluded, ineligible fasting, future unconfirmed work, or completed groups; no guilt, streak pressure, public ranking or punitive text. Provide quiet hours, frequency settings and one-tap opt-out.
- No backend notification workers, FCM or job queue in MVP. Preferences optionally backed up as user settings.
- Re-schedule at boot and timezone shifts where supported. Exact alarms permission only when justified; approximate reminders are okay. Android 13+ runtime POST_NOTIFICATIONS permission required. Hide sensitive progress/score and religious activity detail on lock screen by default.

## 5. Content rules

- `ADHKAR_SET` needs approved complete item list. Do not convert reference screenshot text to full authoritative religious corpus.
- Store full Arabic text with diacritics in Unicode, source/reference, number of repetitions, editor review state and catalog version.
- If a user completes a set before some text is approved, do not misrepresent missing items as completed; seed only reviewed sets or temporarily keep reference card as TOGGLE with an `info_available=false` message (explicitly marked non-parity).
- Test layout for long lines, font scaling and scroll. Text direction RTL and punctuation should remain accessible.

## 6. Date, history and privacy

- Activity entries are tied to an ISO local DATE, not a timestamp-derived implicit date. User-selected date must be passed explicitly.
- `today` computed from user's configured timezone for eligibility; UTC timestamps for audits.
- Report: weighted period ratio `sum earned/sum possible` over days in account tracking window, inclusive today. Unedited past days after start are zero completed; future days omitted.
- Do not store reasons for menstruation, illness or fast exemption. No public scores, social ranking, or unconsented behavioral analytics.

## 7. Key acceptance tests

1. Mosque set with 2 equal items worth 2 points: `[1/1,0/1]` = PARTIAL and **1 point**, `[1/1,1/1]` = COMPLETE and **2 points**.
2. Five-item set with three complete and weight 2: **1.2 earned**. Undo one item => **0.8**, never a second full parent reward.
3. Mixed repetitions `[1/1,1/3]` in a 2-point two-item set => **1.333333...** earned; each item equal share, each repetition fraction bounded to 1.
4. Parent quick-complete atomically marks all verified items; undo individual returns to PARTIAL without erasing other counters.
5. `target_count=3`: counter 0/3 -> 1/3 -> 2/3 -> 3/3, attempt 4 rejected.
6. Notification enabled: schedule at most one incomplete-progress summary per day, suppress/reschedule when last remaining item completed, honor quiet hours and opt-out. No notification on every item tap.
7. Monday fast planned, Tuesday unplanned, Tuesday after ADD, Ramadan Thursday not counted twice, SKIP removes denominator.
8. Original 74-point Thursday regression and dynamic 69-point non-fasting Friday regression.
9. Older catalog release snapshot never changes when later content/points are published.
10. Disabled notification, permission denied, timezone change and offline mode produce safe behavior.

## 8. v1.3: Toggle undo and user-customized plans

### Set/undo behavior

- Normal `TOGGLE` activities (e.g., Dhuhr) and fasting can be marked `COMPLETED` or explicitly set back to `PENDING`. The *client* click is a toggle; the server receives the **absolute intended state** via idempotent `PUT`. Every undo removes the earned fraction from the total. The user must be able to re-complete normally.
- `ADHKAR_SET` child counts can increment and decrement. A child with target 1 toggles `0/1 ↔ 1/1`; with target N supports explicit `+` and `-`. Its parent progress is always recomputed; completed items are never silently cleared when another item is undone.
- Calendar future dates cannot be completed; no clock-time validation for current-day prayer tiles in MVP. No unverified prayer timetable is used to block a legitimate correction.

### Resolve immutable scoring membership and personalized display (v1.4)

1. Select the catalog release pinned to date D; get **all official score-eligible items** in each scored ADHKAR_SET card. This is the fixed scoring set for that day.
2. Resolve the user's effective hide/order/custom plan **only for UI/tracking**. Hidden official rows are not removed from scoring.
3. Freeze official scoring item text, target and membership for the day; freeze personal tracked items separately (marked `is_score_eligible=false`). Historical scoring must not drift after admin edits or user changes.
4. Group score = `weight * mean(clamp(count / target, 0, 1) for pinned_official_scoring_items)`. A custom item counts as zero score contribution even when complete. There is no extra completion bonus.
5. If all official scoring entries are hidden visually, show an explanation + control `إظهار الأذكار الرسمية المخفية`. The set still has its published main-card weight; it does not silently become `NOT_CONFIGURED` or disappear from `possible`.
6. Reject publication of a scored ADHKAR_SET without at least one official score-eligible entry, rather than divide by zero.

Example: 2 point card with 5 official entries. Three official entries complete => 1.2 points. Hide two unfinished defaults and add 10 custom entries and complete them all => **still 1.2/2**, not 2/2; restore hidden entries and finish them to earn the remaining 0.8.


### Plan effective date UX policy (proposed)

- New customizations take effect **tomorrow by default**. Offer `Apply today` only if that day's affected group has no recorded progress; if there is progress, show why the change starts tomorrow. Keep prior recorded counts. Users can always undo a tap on existing day's pinned plan.
- Review/target changes to personal items do not mutate prior snapshots. Revert to defaults creates a new effective revision rather than deleting earlier plans.
- `user_custom_items` are private, non-editorially-reviewed notes; make source/verification label clear. Content from users is never copied into the global verified library.

### Additional acceptance tests

1. Dhuhr `false -> true -> false`: points `0 -> weight -> 0`, UI `red -> green -> red`, no double counting; works offline, with eventual final state preserved after retry.
2. Rapid double tap and duplicate network retry never accidentally turn `PENDING` into `COMPLETED` again; server PUT is set-state, not toggle.
3. Existing morning set of five OFFICIAL items with three completed: 1.2/2. Hide two pending official defaults, add/complete one private item: still 1.2/2; another user retains original five official items.
4. User with zero visible default items: official group still has its configured weight in possible; score from pinned official items, with show-hidden option. Never auto award 100% or exclude the group simply because items are hidden.
5. Re-enabling a hidden default is a UI visibility change, with zero scoring effect on current or historical days. Catalog release changes are prospective, historical scores remain stable.
6. Unauthorized account reading another user's custom text returns 404/403; unauthorized publishing official content returns 403.
7. Admin archives official source after publishing release A; past journals on release A remain stable; release B can omit/update item following review.
8. Create/edit/archive user personal prayer, target counts and order; historical snapshots remain unchanged; no publish to another user.