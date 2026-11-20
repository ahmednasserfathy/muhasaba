> Historical v1.2 notes. Current authoritative scope and scoring: `10_LOCKED_CORE_MVP_AR.md`.

# التغيير من v1.1 إلى v1.2

**قرار المستخدم المعتمد:** الإنجاز الجزئي للأذكار يُحتسب في الـ score، مع تشجيع إيجابي وإشعارات اختيارية بالأعمال المتبقية.

- ألغينا سياسة `all-or-nothing` من Domain Rules وPRD والـ API examples وCodex instructions والـ acceptance tests.
- صيغة مقترحة قابلة للاختبار: `set_weight * average(min(done_i,target_i)/target_i)`؛ ذكر واحد من 2 في مجموعة وزنها 2 = نقطة، و3 من 5 في مجموعة وزنها 2 = 1.2 نقطة.
- أضفنا Derived state اسمها `PARTIAL`، لا تخزن كحالة أبوية قابلة للتعديل.
- تشجيع فوري داخل التطبيق لكل تحسن، وإشعار ملخص اختياري بحد أقصى مرة يوميًا خارج أوقات الهدوء.
- للخصوصية لا نعرض تفاصيل العبادة والنقاط على شاشة قفل الجهاز افتراضيًا.
- باقي الـ Stack كما هو: Flutter/SQLite/Drift، Python/FastAPI، PostgreSQL، Offline-first، External Identity مستقبلًا.

**قرار مفتوح للتجربة لاحقًا:** هل توزيع نقاط مجموعة الأذكار يكون بالتساوي على كل ذكر أم بأوزان مختلفة؟ الافتراضي الحالي بالتساوي لأنه أبسط وأكثر إنصافًا في التكرارات.