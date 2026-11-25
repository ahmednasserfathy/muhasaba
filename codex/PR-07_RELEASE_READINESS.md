# PR-07: release readiness, recovery and private operations

Update, 25 November 2026: the owner supplied an AWS host and authorized replacing
the temporary domain's existing site. See `infra/STAGING.md` for the verified
deployment checkpoint: public HTTPS and certificate renewal checks now pass with
a dedicated web security group. The original preparation
scope and deferred-release gates below remain historical context.

PR-06b is accepted and merged. This is release preparation, not a production
launch. The user explicitly deferred AWS; Android work comes after backend/mobile
checks. No deployed HTTPS service, production content or persistent signing key
is assumed. No new product features or external service subscriptions.

## Scope and validation

- `/health` remains process liveness. `/ready` executes `SELECT 1` and returns
  503 on missing/unavailable database. It does not assert migration/content state.
  PostgreSQL connections and pool acquisition have three-second timeouts; this is
  not a global SQL execution or HTTP deadline.
- Request events contain generated request ID, allowlisted method, route template,
  status and elapsed milliseconds. Never log request/response bodies, tokens,
  email, user IDs, IP, raw URL/query or private exception text. Unhandled errors
  return a generic 500 with the request ID. Normal 401/409/422 behavior is preserved.
- Container Uvicorn disables its raw access log. For host runs use `--no-access-log`.
  SQLAlchemy hides bound parameters. Compose PostgreSQL omits routine failing SQL
  statements and verbose row details; administrators must retain the same policy
  in managed infrastructure. This reduces diagnostic detail intentionally, and is
  not a promise to sanitize arbitrary administrator SQL or external proxy logs.
- CI runs the existing API/integration and Flutter suites, then the real database
  backup/restore drill described below, then Android release compilation/signature
  verification. CI is the authoritative runtime check on this Mac, where Docker
  is unavailable and Flutter test native hooks require unfinished Xcode setup.

## Local Compose backup and recovery drill

Apply migrations first using the existing README. From repository root:

```bash
infra/scripts/backup.sh /SAFE_DIRECTORY/muhasaba.dump
infra/scripts/restore-check.sh /SAFE_DIRECTORY/muhasaba.dump rehearsal_restore_test
```

Use a directory you control on protected storage. Backup uses PostgreSQL's custom
archive format and app DB role; the file is mode 0600, created through a temporary
file then an atomic non-overwriting link. Failures remove the temporary file.
Existing backup destinations are refused. The database name may be an optional
second argument to backup.sh. Scripts use the root `.env` and Compose service.

Restore accepts only a new `*_restore_test` database, creates it owned by the app
role, then restores in one transaction with stop-on-error. It never drops a database
or restores over production. A failure may leave a newly created empty database;
inspect it before any manual cleanup. A dump is trusted SQL: only restore archives
from an authorized, authenticated backup source. Do not expose rehearsal databases.

CI uses isolated recovery_source_test and recovery_restore_test databases. A guarded
Python probe creates synthetic 34-card catalog/account data through the API, hides
an official item, records official and private progress and saves expected results.
After dump/restore it logs in again and checks the complete day, private text,
reports and replay of the original mutation receipt without another state change.
This verifies schema/functions/triggers, auth and journal data together. The probe
refuses non-PostgreSQL or non-`*_test` targets. Expectations contain synthetic data,
no bearer/refresh tokens; they and the dump are removed and never uploaded.

For a real restore, first isolate a new database, verify schema/head, counts and
sample histories with authorized access, then plan a maintenance window and an
explicit application connection cutover. Preserve the old database until acceptance.
This PR performs no real cutover and sets no recovery-time/recovery-point guarantee.
Schedule encrypted backups, retention and periodic restore drills with the future
AWS owner. Archives include private text, hashes and live session records: never
commit or send them through chat. No cloud storage or encryption key was created.

## Monitoring and incident triage

Future staging monitoring should probe `/health` and `/ready`, aggregate route/status
counts and latency (especially 5xx, 401 and 409), and alert on sustained readiness
failure. Request IDs identify failures without tying them to user identities.
Local pending-outbox counts remain visible in the app; no user telemetry is sent.
No external monitoring service is connected. Configure log access/retention and
proxy redaction when AWS is provisioned. Reproduce failures with synthetic inputs;
do not turn on payload logging to debug a private production journal.

## Android build and device gates

Release Gradle tasks fail when signing settings are missing; no fallback to debug
signing. Supply ANDROID_KEYSTORE_PATH, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS
and ANDROID_KEY_PASSWORD outside source control. The existing package name is
provisional until the owner chooses a publishing identity.

The final CI job depends on backend/mobile success, creates an ephemeral CI-only
certificate, compiles release with `https://staging.invalid/api/v1/`, verifies the
APK signature and deletes APK/key. It proves compilation/signing integration only;
it is deliberately not an installable service-connected release candidate.

On the local Mac, Android licenses are incomplete and no Android device is connected;
Xcode also has unaccepted terms/missing components. No licenses are accepted by the
agent. Actual Android keystore, offline/restart/reconnect, notification permission,
quiet hours, cold launch, reboot, battery restrictions, large Arabic text and signed
upgrade testing remain NOT_RUN. Run them last after the operator supplies the test
environment and reviews tooling licenses. A production signing key must be backed
up independently; never use or retain the disposable CI certificate for distribution.

## UAT and release gate matrix

| Gate | Evidence / remaining work |
| --- | --- |
| Registration/session/isolation | Existing API + Flutter tests; actual Android secure storage still required |
| Exact scoring/undo/private score neutrality | Python/PostgreSQL/Flutter suites; five official/three complete remains 1.2/2 |
| Hidden rows reachable and Arabic customization | Flutter widget tests; large-text/device walkthrough pending |
| Versioned history, conflicts, retry, restart | Integration and file-backed Flutter tests; airplane-mode device UAT pending |
| DB backup/recovery | Real pg_dump/pg_restore plus API probe in CI |
| Private operations | Allowlisted logging/readiness tests, no payload capture |
| Security review | Bounded static auth/ownership/editorial/cache/operations review; not an independent penetration test or dependency audit |
| Android build | CI ephemeral release signing/verification; persistent internal release + device UAT pending |
| Staging | AWS/TLS and renewal checks passed; dedicated web ingress, edge limits and server secrets configured; external backup retention and monitoring remain open |
| Content | Official Arabic source/reuse approval and regional Ramadan confirmation remain operator gates |
| Privacy/support | Publish actual policy/contact and deletion/retention workflow before broader release; no policy or SLA invented here |

Review this PR before treating any preparation item as a release approval. A green
CI run does not close the staging, privacy, content or actual-device gates.

## References

- [PostgreSQL log controls](https://www.postgresql.org/docs/16/runtime-config-logging.html)
- [Android signing configuration](https://developer.android.com/build/build-variants)
- [Keytool password environment inputs](https://docs.oracle.com/en/java/javase/12/tools/keytool.html)
