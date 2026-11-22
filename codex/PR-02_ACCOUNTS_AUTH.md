# PR-02: accounts and authentication

PR-00 and PR-01 were accepted and merged. This PR implements the roadmap's
account/session foundation and mobile login only; the locked blueprint is unchanged.

## Contract and decisions

- Alembic 0003 adds users, auth_sessions, external_identities and user_settings,
  plus the deferred library_entries.created_by_admin foreign key. USER is the
  default role; registration cannot set role, source or verification flags.
- POST /api/v1/auth/register accepts email, password (12–128 characters), IANA
  timezone and optional trackingStartDate (not in the future in that timezone).
  Email is normalized to lowercase; the default tracking date is today locally.
- POST /api/v1/auth/login accepts email/password. Passwords use Argon2; missing
  accounts still perform password verification against a dummy hash.
- Registration/login return accessToken, refreshToken, expiresIn and user.
  Tokens are random opaque secrets; only SHA-256 token hashes are stored in DB.
  Access lasts 15 minutes, each session at most 30 days from creation.
- POST /api/v1/auth/refresh accepts refreshToken and rotates BOTH tokens under
  a PostgreSQL row lock. Old tokens fail; concurrent refresh has one winner.
  The session's absolute expiry never extends. There is no grace/replay window;
  a lost successful refresh response requires a new login. Clients must not
  blindly retry refresh requests or issue concurrent refreshes.
- POST /api/v1/auth/logout accepts refreshToken and idempotently revokes that
  session, including when access has expired. Other sessions remain valid.
- GET /api/v1/me uses the bearer access token and returns only that account.
  Deleted/inactive imported accounts are denied on login, refresh and access.
  A reusable ADMIN dependency reads current role from DB; no admin API exists yet.
- Auth responses are no-store; validation responses omit submitted secret inputs.
  Bounded in-process IP/account rate limits protect auth endpoints. Multiple
  workers/instances require a shared ingress limiter before production; proxy
  forwarding must be configured only for trusted proxies. No Redis is introduced.
- Imported users can exist without credentials but cannot login before password
  setup AND email verification. External identities are unique by source/subject;
  no email-based linking, import connector or public activation API is introduced.
- Native email verification is explicitly pending: emailVerified remains false
  and the UI says so. Email delivery, reset and activation flows need a mail
  provider and separate implementation before public production onboarding.
- Mobile uses Riverpod/Dio and encrypted storage for one token pair, bound to
  the API URL. Passwords are cleared after submission. Network failure retains
  saved sessions; failed logout retains the account for retry. Debug HTTP is
  limited to local emulator/loopback hosts; release requires configured HTTPS.

## Verification

Run root README backend checks and the dedicated PostgreSQL integration command
in PR-01's document; TEST_DATABASE_URL must end in _test. CI runs all integration
cases, including migration downgrade/reapply and schema parity, on PostgreSQL.

Local: Ruff lint/format and 47 backend tests PASS; 30 PostgreSQL cases NOT_RUN
(Docker unavailable). Flutter analysis PASS. Flutter tests cannot start locally
because objective_c's native build hook cannot resolve the macOS Xcode SDK;
Linux CI must pass the nine client and five widget tests. No Android APK/device
or real keystore verification has been performed; SDK licenses are incomplete.

Auth tests cover account isolation, role restrictions, normalized duplicates,
secret storage, expiry, refresh rotation/replay/concurrency, logout session scope,
soft deletion, imported activation gates, rate limits and external identity uniqueness.
Mobile tests use a fake HTTP adapter and mocked secure-storage platform channel.

## Migration and review gate

Apply alembic upgrade head manually. Downgrading 0003 deletes account/session
and identity/settings data: disposable test databases only, never live data without
an independently reviewed restore plan. No auto-migration or production deployment.

Review this draft and CI before merge. Stop here; PR-03 daily journal is the next
separate task. AWS is unnecessary for this local development stage.
