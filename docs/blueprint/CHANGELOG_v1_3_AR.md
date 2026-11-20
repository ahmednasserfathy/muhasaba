> Historical v1.3 notes, **superseded** where they describe personalized scoring. v1.4 score rules live in `10_LOCKED_CORE_MVP_AR.md`.

# Changelog v1.3 | 20 نوفمبر 2026

## Confirmed directly by product owner

1. إلغاء أي علامة إنجاز بضغطة ثانية، مثل صلاة الظهر المسجلة خطأ؛ احتساب النقاط عكسيًا بشكل فوري.
2. أدعية وأذكار في مكتبة رسمية يديرها الـ ADMIN فقط.
3. المستخدم يمتلك أذكارًا وأدعية شخصية في مجموعات موجودة مثل أذكار الصباح، ويستطيع إخفاء بعض الافتراضيات من خطته وإضافة نصه الخاص.

## New design policies proposed for implementation

- Server uses explicit idempotent `PUT` desired state, Flutter tap toggles locally; server has no toggle action.
- Global `library_entries` editable drafts, immutable catalog-published snapshots. User customization never mutates official content.
- User `user_custom_items` with effective-dated `user_group_plans`; past-day counters/text/targets are frozen at first edit.
- Score calculated on visible items in a personal plan. Group maximum unchanged, and no social leaderboard / cross-user comparison. Empty set NOT_CONFIGURED.
- Plan changes effective next day by default; apply today only if group has no progress. This is a proposal to validate during UAT.
- Future *date* cannot be marked complete; future *prayer time* not gated in MVP because no reliable timing integration yet.

## Delivery impact

- PR-03: undo and decrement tests compulsory.
- PR-06b: small official library admin API + user personalization, once core daily flow stable.
- No additional microservice, standalone CMS frontend, queue, or redis.