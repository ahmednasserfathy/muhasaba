# PR-06: opt-in local reminders

PR-05 is accepted and merged. This slice implements local Android reminders and
Arabic settings. No backend worker, push service, prayer timetable, new API or
server migration. Optional server backup of preferences is deferred; device
opt-in is never silently enabled by another device. No new religious texts or
video links are published: source/license/editor review remains a content gate.

## Behavior

Account → «التذكيرات الاختيارية» enables each category after choosing its time:
morning adhkar, evening adhkar, bedtime, daily review, fasting eve or incomplete
progress. All are off initially. Defaults for quiet hours are 22:00–07:00;
equal boundaries disable quiet hours. Times inside quiet hours are skipped,
not moved to another hour. The user's account IANA timezone is used; the UI
shows it. DST nonexistent wall times are skipped. No GPS or exact-alarm permission.

Today reminders require locally cached eligible incomplete cards. Category
bindings use the existing reference activity codes. Completed/excluded cards do
not trigger reminders. Partial official progress remains eligible. Fasting eve
requires tomorrow's locally cached eligible plan, and opens that planning date.
Unknown/unloaded days never imply incomplete work. No future completion assumed.

Notifications have generic supportive text, no private text/count/score, no sound
or vibration and secret lock-screen visibility. Taps validate the account/backend
payload and open the specific day with remaining-card filtering. Initial launch
payload waits for account restoration. Logout/account change cancels notifications.

Reconciliation runs after successful local journal/fasting changes and sync,
on account activation/resume, and every minute while the app is running. It
cancels obsolete reminders and replaces the same per-date/category notification.
One incomplete summary at most per account-local date: a persisted reservation
whose scheduled time has passed is consumed, even if the OS delayed or failed
delivery. Changing time, restarting or toggling preferences cannot produce a
second summary. Future canceled slots can be reused after undo. Reservation before
dispatch deliberately favors missed delivery over duplicate delivery on crash.

## Persistence and platform integration

Drift v3 adds reminder_preferences(owner,document) and
reminder_slots(owner,id,fire_at); owner includes API base URL and account UUID.
Existing days, fasting plans and mutation outbox survive upgrade from v1/v2.
Notification IDs combine local date and stable category index. Do not reorder
category keys without migrating outstanding IDs. Reservations are not pruned.
Settings persist locally; no notifications are enabled by default on a new device.

flutter_local_notifications is pinned to 21.0.0, compatible with Flutter 3.38.9.
Android uses inexactAllowWhileIdle one-shot scheduling, POST_NOTIFICATIONS,
RECEIVE_BOOT_COMPLETED and the plugin's scheduled/boot receivers. Java 17,
AGP 8.11.1 and SDK 36 match existing build configuration; desugaring 2.1.4 is added.
A drawable notification icon is retained through resource shrinking.

Primary integration reference:
https://pub.dev/packages/flutter_local_notifications/versions/21.0.0

## Explicit limits and verification

Only the remaining times today are scheduled, plus fasting-eve today for tomorrow.
Open the app daily and load the relevant journal/calendar to extend scheduling.
No claim of fresh server state while closed or across devices. Boot restores
already scheduled alarms through the plugin; it does not download another day.
Account-timezone changes are reconciled on resume/activation. Device timezone
changes do not change the selected account timezone. Approximate Android alarms
may be delayed/suppressed by power management; quiet hours govern requested wall
schedule, not a guarantee against OS-delayed delivery. Reopening after due time
may cancel a delayed reminder instead of issuing another.

Tests cover default off, partial/completed/excluded work, fasting plans, quiet
hours, permission rejection, DST gaps, category targeting, cancel/undo, daily
quota across service restart, owner-scoped links and cold launch. Android method
channel tests exercise the real plugin bridge with mocked OS calls; widget tests
exercise Arabic opt-in/time picker/disable. Existing v1 migration and journal
regressions remain in CI. Ruff, backend, Flutter analysis/tests and Compose results
are recorded in the PR. Local macOS Flutter native-assets remain blocked by Xcode.

Per user request, actual Android permission dialogs, notifications while closed,
reboot behavior, manufacturer battery policy, deep-link cold start, release icon
retention and final signed APK/device testing are deferred to PR-07, NOT_RUN here.
This feature is not claimed device-validated. Downgrading the app does not remove
SQLite v3 tables; use a compatible forward migration, never clear user history.
Stop for review before PR-06b library/personalization.
