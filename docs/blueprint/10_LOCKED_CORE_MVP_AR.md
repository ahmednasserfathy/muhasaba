# 10 | Muhasaba, Locked MVP Core v1.4 (قرار المنتج المعتمد)

**Status:** User-approved core scope, 20 November 2026. This document overrides every conflicting scoring example in v1.3 and earlier. Design/implementation spec, **not proof of exact original website business logic**.

## هدف الـ MVP

Flutter Android-first, FastAPI Python backend واحد, PostgreSQL, SQLite/Drift offline, Arabic RTL. صميم التجربة: 8 مجموعات و34 كارت مرجعي، كروت موزونة، تسجيل وإنهاء وتراجع، أذكار تفصيلية، مكتبة رسمية، محتوى شخصي، صيام، تقارير، إشعارات إيجابية اختيارية، وحسابات أصلية مع قابلية دمج مستقبلي مع مصدر خارجي. الأرقام/الأوزان الأصلية ما زالت تقريبية لحين تحقق مستقل.

## ثلاث مستويات مختلفة لا تختلط

1. **Main Section** مثل الفجر أو الظهر: حاوية تنظيمية، لا تكسب نقاط بذاتها.
2. **Main Activity Card** مثل الجماعة الأولى أو أذكار الصباح: **وحدة النقاط الوحيدة**. لها `activity_code`, `weight`, `kind`, `eligibility` مثبتة في Catalog Release.
3. **Nested Content Items**: الأذكار الرسمية المعتمدة المرتبطة بكارت أذكار، و/أو أدعية وأذكار المستخدم الشخصية. النص/العداد `completed_count/target_count` مختلف تمامًا عن وزن الكارت.

## معادلة الـ Scoring الرسمية

- لكارت `TOGGLE` أو `FASTING`: مكتمل = الوزن كاملًا، غير مكتمل = صفر. كل ضغطة يمكن التراجع عنها بضغطه ثانية، مع استخدام explicit idempotent PUT على الـ API. لا تمنع إكمال صلاة مبكرًا بوقت مفترض بدون مزود مواقيت مؤكد. لا تسمح بإكمال يوم مستقبلي.
- لكارت `ADHKAR_SET`: كل **ذكر رسمي مصدّق ومربوط بالكارت كعنصر score-eligible** يأخذ حصة متساوية من وزن الكارت، ويُحسب `min(completed_count/target_count,1)` لكل ذكر. الإنجاز الجزئي يمنح نقاطًا جزئية فورًا، دون Bonus عند الإكمال ودون شرط إكمال كل الأذكار أولًا.
- فقط عناصر `OFFICIAL & is_score_eligible=true` المحفوظة من Catalog Release اليوم تدخل المعادلة. العناصر `PERSONAL` لها Score Contribution = **ZERO** دائمًا.
- **إخفاء ذكر رسمي من الواجهة أو إعادة ترتيبه لا يغير نقاطه، ولا يحسبه مكتملًا، ولا يحذف واجبه من التقييم**. يجب توفير زر واضح لإظهار العناصر الرسمية المخفية، مع بيان المتبقي في الـ Score.
- إضافة أو تعديل أو حذف دعاء شخصي، حتى مع إتمامه 100%، لا يضيف نقاطًا للكارت ولا يغيّر ممكن الكارت ولا يهبط Score بسبب عدم إكماله. يمكن إظهار تقدمه الشخصي بشكل منفصل.
- `day_earned = SUM(eligible_card.weight * card_fraction)`, `day_possible = SUM(eligible_card.weight)`. `day_percentage = 100 * earned / possible` مع التقريب وقت العرض فقط. الصيام المختار والمستثنى يؤثر على **أهلية كارت الصيام** كاستثناء مستقل، وليس على توزيع الأذكار.
- عند صفر أذكار رسمية score-eligible في Catalog Release لكارت `ADHKAR_SET`, يفشل نشره (Data validation error)؛ لا نسمح بتحويل الكارت إلى 0/0 بسبب تخصيص المستخدم.

## أمثلة Acceptance

| Scenario | Expected weighted score |
|---|---|
| كارت صلاة وزنه 2: لم يُنجز ثم أُنجز ثم أُلغي | 0 → 2 → 0 |
| كارت أذكار وزنه 2، 5 أذكار رسمية، 3/5 مكتملة | 1.2 / 2 |
| إخفاء ذكرين رسميين غير مكتملين، وإضافة 10 أدعية شخصية وإكمالها | **يبقى 1.2 / 2** |
| إكمال الذكرين الرسميين الأخيرين (من شاشة إظهار المخفي) | 2 / 2 |
| ذكر رسمي هدفه 3 تكرارات، إنجاز مرة | ثلث حصة ذلك الذكر فقط |
| ضغطة + ثم - على ذكر، أو مرتين على صلاة | تعود نفس النقاط للحالة السابقة |
| تغيير Admin لمحتوى رسمي في إصدار جديد | النتائج القديمة لا تتغير |
| التخصيص لحساب A | لا يغيّر محتوى أو بيانات حساب B |

## الـ Library Management

- **ADMIN ONLY:** add/edit/review/archive/publish official dhikr/dua with source, Arabic text, title, repetition count, group binding, version. `ARCHIVE` rather than physical delete for referenced content. Preserve historical snapshots. No second CMS server.
- **USER PERSONAL:** add/edit/archive own adhkar/dua, link inside existing group (e.g. أذكار الصباح), hide/unhide and reorder official default items **in personal display only**. User may remove a default from personal view but does not change official library or scoring. No new user-created weighted top-level card in MVP.
- Personal text not public/not endorsed by Admin; all private CRUD scoped to canonical user ID.
- Distinct separate progress for personal added items; user should never think their addition raised the overall score.

## Notifications & motivation

- Encourage immediate partial progress in app without guilt. OS local notifications only after explicit opt-in, gentle reminders to score-eligible remaining visible items and opt-in personal checklist, quiet hours, maximum one unfinished-work summary/day, deep link, cancel/reschedule from locally-known updates.
- Hidden unfinished official items remain eligible for score; do not surface religious private text in lock-screen push. User can reveal them in card detail.

## Identity and architecture

- `users.id` immutable UUID for native or imported users; `registration_source` NATIVE/IMPORTED and separate optional `external_identities`. Do not connect external DB or merge on email alone in MVP.
- FastAPI + SQLAlchemy + Alembic + PostgreSQL, Flutter + Riverpod + Drift + Dio, Docker Compose. No Redis/Celery/Kubernetes/microservices in v1.
- Offline app operations store local state and idempotent outbox mutation atomically; sync must honor last desired state and avoid silently overwriting concurrent edits.
- Fasting Monday/Thursday baseline, confirmed local Ramadan days and user-planned other days. Skipped days not used to pressure users. Reports on canonical fixed-card scores; optional separate personal tracking reports.
- Original website API, video licenses and religious source rights are not assumed; only documented/authorized providers.

## Implementation sequence

1. PR-00 Foundations only; no business logic.
2. PR-01 Catalog and pure scoring fixtures, including customization-is-score-neutral unit tests.
3. PR-02 Native accounts, import-ready schema.
4. PR-03 Daily weighted cards, reversible toggles, official nested counters, offline journal.
5. PR-04 Fasting and Ramadan.
6. PR-05 Reports and sync safety.
7. PR-06 Opt-in local notifications.
8. PR-06b Admin library CRUD, user personal adhkar and hide/reorder display, score isolation tests.
9. PR-07 QA, hardening, Android staging release.

**Scope freeze:** New features are backlog candidates. Fix defects in the core, not a new subsystem per idea. Each PR must pass its acceptance tests before the next.