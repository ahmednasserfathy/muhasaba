# PR-01: catalog and pure scoring

## Scope and decisions

PR-00 was accepted and merged before this branch. PR-01 implements the roadmap's
catalog schema, reference seed, read API and pure Python score fixtures only.
The locked v1.4 blueprint remains authoritative and unchanged.

- Five tables: `categories`, `catalog_releases`, `activities`, `library_entries`,
  and immutable published `adhkar_items` bindings.
- Alembic `0001` creates schema and PostgreSQL publication/immutability guards;
  `0002` inserts the eight categories and 34 reference activities as **DRAFT**.
- The seed preserves the blueprint's provisional weights (74 including fasting,
  69 without it). The 17 groups in `docs/blueprint/seed/adhkar_coverage.csv` remain
  empty ADHKAR_SET drafts. No religious text or synthetic test content is seeded.
- `GET /api/v1/catalog?date=YYYY-MM-DD` returns the latest published release whose
  effective date is on/before the requested local date, with ordered active cards,
  verified official items, source attribution and score eligibility. Dates are
  explicit; no server timezone inference. The fresh seed returns **404**, since
  no release is published. No implicit fallback to a draft or sample content.
- The public catalog contains no private user data and needs no login. Editorial
  reads/writes and publication have **no HTTP endpoint** in this PR. ADMIN-only
  editorial APIs belong to PR-06b after PR-02 authentication. Users never choose
  weights, official eligibility or publication status through an API.
- `users.role` (USER default / ADMIN) and the library's `created_by_admin` foreign
  key are deferred until the users table exists in PR-02. Do not create orphan
  admin UUID columns or an unauthenticated administration endpoint in PR-01.
- Library working entries can change/archive; bindings contain their own text,
  targets and sources. Published releases, activity rows, item rows and referenced
  category definitions cannot be updated/deleted. Inserting/moving rows into a
  published release also fails. Release row locks serialize edits with publication.
- Publication requires active activities; every active ADHKAR_SET needs a verified
  score-eligible item. All bound items must be verified, have nonblank text and
  source/license metadata, and belong to ADHKAR_SET cards. Editorial verification
  is a human responsibility; nonblank metadata is not proof of authenticity.
- Categories remain stable shared definitions in this minimal schema. Renaming or
  reordering a category used by a published release is rejected; introducing
  versioned category labels later requires an explicit schema/product decision.

## Scoring contract

`app/modules/catalog/scoring.py` operates on trusted, complete day-pinned inputs.
It must never receive a list filtered by visibility or a list of only completed
items. It does not read a database or accept user HTTP requests.

- TOGGLE/FASTING: explicit completion earns the fixed parent weight; undo earns 0.
- ADHKAR_SET: fixed weight times the average clamped count/target for OFFICIAL,
  score-eligible entries only. No completion bonus and no direct parent completion.
- Personal entries always earn zero, even if accidentally flagged eligible.
  Visibility and ordering fields have no effect. Duplicate scoring keys and
  empty scored sets are configuration errors.
- Python `Fraction` preserves exact results; `display_percent` rounds half up only
  for display. No rounding while summing daily scores. Zero possible gives null.
- Eligibility is an explicit input. Fasting calendar, user date eligibility,
  journal snapshots, count-write validation and offline sync remain in later PRs.
  Counters are defensively clamped here; future write endpoints reject invalid
  negative/excess counts rather than accepting them.

## Verification commands

From `backend/`:

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -ra
```

Without PostgreSQL, integration tests explicitly skip; this is not a full pass.
With the Compose stack running, from the repository root create a **dedicated**
empty test database once (never point these tests at application/production data):

```bash
docker compose --env-file .env -f infra/compose.yml exec -T db createdb -U postgres -O muhasaba muhasaba_test
cd backend
TEST_DATABASE_URL='postgresql+psycopg://muhasaba:local_app_only@127.0.0.1:5432/muhasaba_test' uv run --locked pytest tests/integration -ra
```

The test database name must end in `_test`. Tests apply real migrations, isolate
ordinary cases in rolled-back transactions, and exercise a downgrade-to-base /
upgrade-to-head roundtrip on that test database. CI runs the same checks.
Tests include seed/coverage parity, 74/69 denominators, publication validation,
immutability and reparenting, historical responses after library edits and new
releases, API ordering/draft exclusion, schema metadata parity and constraints.
The OpenAPI snapshot is `backend/openapi.json` and is checked by pytest.

## Migration and review gate

Apply `alembic upgrade head` manually as documented in the root README. There is
no startup auto-migration. `0002` rollback deletes the reference seed and refuses
when referenced by later data or already published. `0001` rollback removes all
five catalog tables and guard functions: destructive, for disposable test databases
or a separately reviewed restore plan only. Do not run downgrade on live data.

Review this PR and its CI before merging. Stop here: PR-02 accounts/authentication
is the next task, not part of PR-01. Verified religious content is still needed
before a real catalog can be published; the public API intentionally returns 404
until that editorial gate is satisfied.
