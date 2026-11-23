# Muhasaba mobile

Android-first Flutter 3.38.9 / Dart 3.10.8, Arabic RTL. PR-02 implements
register/login, session restoration, account summary and logout with Riverpod,
Dio and flutter_secure_storage. PR-03 adds Arabic daily cards, adhkar detail counters and a Drift SQLite outbox.
Open «المحاسبة اليوم» after login; each date must be loaded online once before
offline editing. The official catalog is still draft; see the guarded synthetic
demo and conflict/retry behavior in `../codex/PR-03_CORE_JOURNAL.md`.

```bash
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter run
```

Start the root Compose stack and apply migrations first (see root README).
Debug defaults to `http://10.0.2.2:8000/api/v1/` for Android emulator access.
For a USB device, run `adb reverse tcp:8000 tcp:8000`, then:

```bash
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1/
```

Debug cleartext is allowed only for localhost, 127.0.0.1 and 10.0.2.2. Release
requires an explicit HTTPS API_BASE_URL; no production backend is deployed yet.
Android backup is disabled. Access and refresh tokens are stored together in one
encrypted value bound to the configured API URL; passwords are never persisted.
Network failures retain the session and offer retry. Logout waits for server
revocation before removing local tokens. Refresh rotates both tokens; a lost
refresh response can require signing in again. No automatic request retries.

Native accounts can currently sign in without email verification; the UI displays
that status. Email delivery, reset and imported-account activation are not built.

Android device/emulator and accepted SDK licenses are needed for device builds.
On this Mac, Flutter tests are blocked by the native objective_c dependency's
Xcode SDK lookup; Linux CI runs the client and widget tests. Secure storage tests
mock the platform channel: real Android keystore behavior still needs device QA.
The generated application ID and signing remain development placeholders.

PR-04 adds fasting ADD (optional type), SKIP and DEFAULT. The date picker includes
the next 365 days for planning only. Load each plan online once before offline
editing; future plans need no published catalog. Drift schema v2 preserves v1
cached days and pending writes. See `../codex/PR-04_FASTING.md`.

PR-05 adds «التقارير» with weekly/monthly navigation, weighted period totals and
explicit «حفظ الفترة دون اتصال» for up to 31 days. Restore preserves pending
local work. Offline totals use cached days and clearly identify missing dates.
Android device testing is deferred to the final release-readiness stage by user
request; automated Flutter tests remain required for every PR.

PR-06 adds «التذكيرات الاختيارية»: all categories default off, account-timezone
wall times, quiet hours and generic private notifications. Only locally loaded
today data and tomorrow fasting plans schedule one-shot reminders. Open daily to
refresh; this is not a background sync service. Preferences remain on this device
and Android permission is requested only through explicit settings interaction.
Drift v3 preserves existing caches/outbox and adds preferences plus daily delivery
reservations. See `../codex/PR-06_REMINDERS.md` for limits and final device QA.
