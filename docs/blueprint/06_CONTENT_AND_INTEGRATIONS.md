# 06 | Adhkar Content, Official Videos, External User Sources

## 1. Dhikr content: verified and attributable

`adhkar_items` is the independent app's editorial catalog of item text, repetition target, ordering, references, review status and release. Items from screenshots are **evidence of UX**, not approval to republish wholesale source text.

Workflow: collect content from an authorized/open source or obtain permission; verify original Arabic text and tashkeel against reliable reference; verify repetition count and usage context; record `source_name`, `source_url`, `license_notes`, reviewer/date; publish in immutable catalog release; cache for offline reading. Do not dynamically scrape the original website's private endpoints.

Existing screenshots show at least two different collections: `dhikr_mosque` and `dhikr_clothes`. A coverage sheet `seed/adhkar_coverage.csv` tracks which set lacks verified content. Until reviewed, use labeled placeholder data in development builds only.

## 2. Video learning content: two distinct scenarios

- **User means official creator videos:** the website offers publicly listed lecture/series pages and an official YouTube channel. For MVP store an approved canonical URL or YouTube video ID per linked topic. Open browser/YouTube app or approved embedded player; the YouTube IFrame Player API is for playback, while YouTube Data API is for metadata/search, which is unnecessary if curated links suffice.
- **User means an API from the reference website:** we have **not verified any public, documented API** at `amgadsamir.com`. Do not invent endpoint URLs, inspect private authenticated APIs or assume permission. Use an `OfficialContentProvider` interface only when provider, published docs, credentials/terms and permission are supplied.

No video content copying or video downloads, no rehosting, no bypassing YouTube embed rules. Videos are useful optional context but do not affect daily score unless explicitly specified in a later PRD.

### Future optional content module

Use `content_resources` with `resource_type` `VIDEO` or `ARTICLE`, `provider` `YOUTUBE`/`OFFICIAL_SITE`, `external_id`, `source_url`, `title_ar`, `related_activity_code`, `verified_at`. For a link-based MVP, a vetted YAML/CSV seed can avoid a whole CMS.

## 3. External user DB, deliberately not coupled to app

### Problem

Some users may already exist in another company's/app's DB, while new users register natively. These aren't two different journal systems. They must share one internal `users.id` identity model.

### Current implementation

- `users.registration_source` is `NATIVE`/`IMPORTED`.
- `external_identities` records `source_system`, `external_subject`, `user_id`, status.
- No external DB connection, no auto-sync scheduler, no separate user service.
- Foreign key in every user-owned table is the app's internal UUID.

### Later when source details exist

1. Confirm **access authorization**, data minimization/consent and data owner approval.
2. Document DB type, host/access (never in mobile), tables or API contract, fields and account IDs.
3. Prefer documented provider API or OIDC over DB reads; if DB access necessary, read-only server credentials with least privilege.
4. Run dry-run CSV/API import with metrics: new users, duplicate external subjects, email conflicts, missing fields, invalid entries.
5. Enforce unique `(source_system,external_subject)` and explicit verified linking if existing native account.
6. Imported user sets app password via verified invite, or authenticates through authorized external OIDC; no copying of external password hashes.
7. Provide rollback (disable/revoke links), audit counts and retry rules. Never overwrite existing journal state.

### Key identity scenario

A native account with `user_id=A` can also be linked to `source_system=B, external_subject=123`; user remains `A`. A different imported person gets user_id `C`. If source B's email matches A, **hold for review**; do not auto-link.

## 4. Verification checklist before any production integration

- Official public API docs/terms? Auth mechanism? Pagination? Rate limits? Retention? Rights? Localization? SLA? Permission from data owner?
- Data fields mapped exactly to local schema, including IDs, state and expiry.
- Staging credentials and sanitized sample responses, never production secrets inside Codex prompts.
- Timeouts, retry policy, circuit-breaker only if real usage justifies it, otherwise bounded HTTP retries.

## v1.3: library management without mixing global and personal data

- Admin publishes **official** Arabic text only after checking source and license. Admin-only actions: add, edit draft, review, archive, assign verified item to one or more existing group cards, and publish a new catalog release.
- A normal user can **hide** a particular default text in their own morning/evening group, not delete it globally, and can add one or more **private** dhikr/dua items into their effective group plan.
- Personal additions may not be sourced or verified; UI must identify them as `شخصي` and must not label them authentic/sunnah by default. No admin review or sharing workflow in MVP.
- Public official library + immutable published group bindings, private user items + effective-dated group plan, daily frozen journal item snapshots: these are three **different** concepts. Resist introducing a generic rule engine or separate CMS server.
- Admin endpoints and OpenAPI suffice initially for content management. A simple visual admin screen can be created later when real editorial workflow warrants it.
- All personal data must be authorized by authenticated internal `users.id`, regardless of whether the account originated as NATIVE or IMPORTED.