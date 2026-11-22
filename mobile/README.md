# Muhasaba mobile

Android-first Flutter 3.38.9 / Dart 3.10.8, Arabic RTL. PR-02 implements
register/login, session restoration, account summary and logout with Riverpod,
Dio and flutter_secure_storage. Journal and offline sync follow later.

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
