import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_client.dart';
import '../auth/auth_controller.dart';
import '../personal/group_plan_screen.dart';
import 'day_data.dart';
import 'journal_database.dart';
import 'journal_repository.dart';

export 'journal_database.dart' show journalDatabaseProvider;

class DailyScreen extends ConsumerStatefulWidget {
  const DailyScreen({
    super.key,
    required this.account,
    this.initialDate,
    this.showRemaining = false,
  });
  final String? initialDate;
  final bool showRemaining;
  final Account account;
  @override
  ConsumerState<DailyScreen> createState() => _DailyScreenState();
}

class _DailyScreenState extends ConsumerState<DailyScreen>
    with WidgetsBindingObserver {
  late final JournalRepository repository;
  late String date;
  bool remainingOnly = false;
  DayData? day;
  Map<String, dynamic>? fasting;
  int pending = 0;
  bool blocked = false;
  String? error;
  StreamSubscription<void>? subscription;
  Timer? timer;

  @override
  void initState() {
    super.initState();
    repository = JournalRepository(
      ref.read(journalDatabaseProvider),
      ref.read(authClientProvider),
      widget.account,
    );
    date = widget.initialDate ?? repository.today;
    remainingOnly = widget.showRemaining;
    WidgetsBinding.instance.addObserver(this);
    subscription = repository.changes.stream.listen((_) => unawaited(_read()));
    timer = Timer.periodic(
      const Duration(seconds: 30),
      (_) => unawaited(repository.sync()),
    );
    unawaited(_open());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) unawaited(repository.load(date));
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    timer?.cancel();
    unawaited(subscription?.cancel());
    unawaited(repository.dispose());
    super.dispose();
  }

  Future<void> _read() async {
    final selected = date;
    try {
      final loaded = await repository.read(selected);
      final plan = await repository.readFasting(selected);
      final count = await repository.pendingCount();
      final conflict = await repository.blocked(selected);
      if (mounted && selected == date) {
        setState(() {
          day = loaded;
          fasting = plan;
          pending = count;
          blocked = conflict;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'تعذر فتح سجل الجهاز. لم يتم حفظ أي تعديل جديد.',
        );
      }
    }
  }

  Future<void> _open() async {
    await _read();
    await repository.load(date);
  }

  Future<void> _edit(
    String kind,
    String key, {
    int? delta,
    String? state,
    String? action,
  }) async {
    try {
      await repository.edit(
        date,
        kind,
        key,
        delta: delta,
        state: state,
        action: action,
      );
      if (mounted) setState(() => error = null);
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is AuthFailure
              ? e.message
              : 'تعذر حفظ التعديل على الجهاز. حاول مرة أخرى.',
        );
      }
    }
  }

  Future<void> _chooseDate() async {
    final selected = await showDatePicker(
      context: context,
      initialDate: DateTime.parse(date),
      firstDate: DateTime.parse(
        day?.start ?? widget.account.trackingStartDate ?? '1900-01-01',
      ),
      lastDate: DateTime.parse(repository.today).add(const Duration(days: 365)),
    );
    if (selected != null && mounted) {
      setState(() {
        date = selected.toIso8601String().split('T').first;
        day = null;
        fasting = null;
        error = null;
      });
      await _open();
    }
  }

  Future<void> _resolve() async {
    final selected = date;
    try {
      if (day == null) {
        final remote = await repository.serverFasting(selected);
        if (!mounted) return;
        final accept = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('مراجعة خطة الصيام'),
            content: Text(
              'الجهاز: ${_fastingReason(fasting?['reason'])}\nالخادم: ${_fastingReason(remote['reason'])}\nاعتماد الخادم يلغي تعديلات الخطة المعلقة لهذا اليوم.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('احتفظ بتعديلاتي'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('اعتماد الخادم'),
              ),
            ],
          ),
        );
        if (accept == true) await repository.useServerFasting(remote);
        return;
      }
      final remote = await repository.serverDay(selected);
      if (!mounted) return;
      final accept = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('مراجعة التعارض'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'تعديلات الجهاز ما زالت محفوظة. اعتماد الخادم يلغي التعديلات المعلقة لهذا اليوم فقط. يمكنك الاحتفاظ بها والعودة لاحقًا.',
                ),
                Text(
                  'خطة الصيام — الجهاز: ${_fastingReason(fasting?['reason'])}، الخادم: ${_fastingReason(remote.json['fasting']?['reason'])}',
                ),
                for (final c in remote.cards) ...[
                  Text(
                    '${c['titleAr']} — الجهاز: ${_localStatus(c['code'] as String)}، الخادم: ${_status(c['status'] as String)}',
                  ),
                  for (final i in DayData.items(c))
                    Text(
                      '${i['textAr']}\nالجهاز: ${_localCount(i['itemKey'] as String)} — الخادم: ${i['completedCount']}/${i['targetCount']}',
                    ),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('احتفظ بتعديلاتي'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('اعتماد الخادم وإلغاء المعلّق'),
            ),
          ],
        ),
      );
      if (accept == true) await repository.useServer(remote);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'تعذر تحميل نسخة الخادم. تعديلاتك محفوظة.');
      }
    }
  }

  String _localStatus(String code) {
    final cards = day?.cards.where((c) => c['code'] == code).toList() ?? [];
    return cards.isEmpty
        ? 'غير موجود'
        : _status(cards.first['status'] as String);
  }

  String _localCount(String key) {
    final items =
        day?.cards
            .expand(DayData.items)
            .where((i) => i['itemKey'] == key)
            .toList() ??
        [];
    return items.isEmpty
        ? 'غير موجود'
        : '${items.first['completedCount']}/${items.first['targetCount']}';
  }

  void _details(String code) {
    var showHidden = false;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => StreamBuilder<void>(
          stream: repository.changes.stream,
          builder: (context, _) => FutureBuilder<DayData?>(
            future: repository.read(date),
            builder: (context, snapshot) {
              final card = snapshot.data?.card(code) ?? day!.card(code);
              return DraggableScrollableSheet(
                expand: false,
                initialChildSize: 0.8,
                minChildSize: 0.4,
                builder: (context, scroll) => ListView(
                  controller: scroll,
                  padding: const EdgeInsets.all(20),
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            card['titleAr'] as String,
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                        ),
                        IconButton(
                          tooltip: 'إغلاق',
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close),
                        ),
                      ],
                    ),
                    Text(
                      '${_points(card['earnedPoints'])} / ${card['possiblePoints']} نقطة — ${card['officialCompleted']}/${card['officialTotal']} مكتمل',
                    ),
                    const Text(
                      'كل خطوة تُحسب. يمكنك التراجع أو تقليل العدد في أي وقت.',
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton(
                          onPressed: blocked
                              ? null
                              : () =>
                                    _edit('set', code, action: 'COMPLETE_ALL'),
                          child: const Text('إكمال الرسمي كله'),
                        ),
                        TextButton(
                          onPressed: blocked
                              ? null
                              : () => _edit('set', code, action: 'CLEAR_ALL'),
                          child: const Text('مسح الرسمي كله'),
                        ),
                      ],
                    ),
                    Text(
                      'الشخصي: ${card['personalCompleted'] ?? 0}/${card['personalTotal'] ?? 0} — بدون نقاط',
                    ),
                    TextButton(
                      onPressed: () {
                        Navigator.pop(context);
                        Navigator.of(this.context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => GroupPlanScreen(
                              repository: repository,
                              code: code,
                            ),
                          ),
                        );
                      },
                      child: const Text('تخصيص المجموعة'),
                    ),
                    if (DayData.items(card).any((i) => i['hidden'] == true))
                      TextButton(
                        onPressed: () => update(() => showHidden = !showHidden),
                        child: Text(
                          showHidden
                              ? 'إخفاء العناصر المخفية'
                              : 'إظهار المخفي — ${card['hiddenOfficialIncomplete'] ?? 0} رسمي متبقٍ ضمن النقاط',
                        ),
                      ),
                    for (final item in DayData.items(
                      card,
                    ).where((i) => showHidden || i['hidden'] != true))
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                item['textAr'] as String,
                                textDirection: TextDirection.rtl,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              Text(
                                item['sourceType'] == 'PERSONAL'
                                    ? 'شخصي — للمتابعة فقط وبدون نقاط'
                                    : item['isScoreEligible'] == true
                                    ? 'رسمي — ضمن نقاط الكارت'
                                    : 'رسمي — للمتابعة فقط',
                              ),
                              if (item['sourceType'] == 'OFFICIAL') ...[
                                Text('المصدر: ${item['sourceName']}'),
                                SelectableText(item['sourceUrl'] as String),
                                Text(item['licenseNotes'] as String),
                              ],
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  IconButton(
                                    key: Key('minus-${item['code']}'),
                                    tooltip: 'تقليل العدد',
                                    onPressed: blocked
                                        ? null
                                        : () => _edit(
                                            'count',
                                            item['itemKey'] as String,
                                            delta: -1,
                                          ),
                                    icon: const Icon(Icons.remove),
                                  ),
                                  TextButton(
                                    key: Key('count-${item['code']}'),
                                    onPressed:
                                        blocked || item['targetCount'] != 1
                                        ? null
                                        : () => _edit(
                                            'count',
                                            item['itemKey'] as String,
                                          ),
                                    child: Text(
                                      '${item['completedCount']}/${item['targetCount']}',
                                    ),
                                  ),
                                  IconButton(
                                    key: Key('plus-${item['code']}'),
                                    tooltip: 'زيادة العدد',
                                    onPressed: blocked
                                        ? null
                                        : () => _edit(
                                            'count',
                                            item['itemKey'] as String,
                                            delta: 1,
                                          ),
                                    icon: const Icon(Icons.add),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  String _points(dynamic value) => (value as num).toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final summary = day?.json['summary'] as Map<String, dynamic>?;
    final visibleCards =
        day?.cards
            .where(
              (c) =>
                  !remainingOnly ||
                  (c['eligible'] == true && c['status'] != 'COMPLETED'),
            )
            .toList() ??
        <Map<String, dynamic>>[];
    return Scaffold(
      appBar: AppBar(
        title: const Text('المحاسبة اليوم'),
        actions: [
          IconButton(
            tooltip: 'اختيار اليوم',
            onPressed: _chooseDate,
            icon: const Icon(Icons.calendar_month),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(date, style: Theme.of(context).textTheme.headlineSmall),
            Text('إنجاز الأعمال الأساسية: ${summary?['percent'] ?? '—'}٪'),
            if (summary != null)
              Text(
                '${_points(summary['earned'])} / ${summary['possible']} نقطة',
              ),
            if (summary != null)
              LinearProgressIndicator(
                value: ((summary['percent'] as int?) ?? 0) / 100,
              ),
            Text(
              pending == 0
                  ? 'لا توجد تعديلات معلقة'
                  : '$pending تعديل محفوظ على الجهاز ينتظر المزامنة',
            ),
            if (repository.message != null) Text(repository.message!),
            if (error != null)
              Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            Wrap(
              spacing: 8,
              children: [
                TextButton(
                  onPressed: repository.syncing
                      ? null
                      : () => repository.load(date),
                  child: const Text('مزامنة الآن'),
                ),
                if (blocked)
                  TextButton(
                    onPressed: repository.syncing ? null : _resolve,
                    child: const Text('مراجعة التعارض'),
                  ),
              ],
            ),
            SwitchListTile(
              title: const Text('عرض الأعمال المتبقية فقط'),
              value: remainingOnly,
              onChanged: (value) => setState(() => remainingOnly = value),
            ),
            if (fasting != null) _fastingPanel(),
            if (date.compareTo(repository.today) > 0)
              const Text('تخطيط فقط — تسجيل الإنجاز متاح في يومه.'),
            if (day == null && date.compareTo(repository.today) <= 0)
              const Text(
                'حمّل اليوم من الخادم مرة واحدة لتتمكن من استخدامه بدون اتصال.',
              ),
            if (day != null)
              for (final category
                  in visibleCards.map((c) => c['categoryCode']).toSet()) ...[
                Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: Text(
                    day!.cards.firstWhere(
                          (c) => c['categoryCode'] == category,
                        )['categoryTitleAr']
                        as String,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                for (final card in visibleCards.where(
                  (c) => c['categoryCode'] == category,
                ))
                  Card(
                    color: card['status'] == 'COMPLETED'
                        ? Colors.green.withValues(alpha: 0.2)
                        : card['status'] == 'PARTIAL'
                        ? Colors.amber.withValues(alpha: 0.15)
                        : null,
                    child: Column(
                      children: [
                        ListTile(
                          key: Key('card-${card['code']}'),
                          title: Text(card['titleAr'] as String),
                          subtitle: Text(
                            '${_points(card['earnedPoints'])} / ${card['possiblePoints']} نقطة — ${_status(card['status'] as String)}',
                          ),
                          leading: Icon(
                            card['status'] == 'COMPLETED'
                                ? Icons.check_circle
                                : card['status'] == 'PARTIAL'
                                ? Icons.pie_chart
                                : Icons.circle_outlined,
                          ),
                          onTap: blocked
                              ? null
                              : card['kind'] == 'ADHKAR_SET'
                              ? () => _details(card['code'] as String)
                              : card['eligible'] == true
                              ? () => _edit('state', card['code'] as String)
                              : null,
                          trailing: card['kind'] == 'ADHKAR_SET'
                              ? IconButton(
                                  tooltip: 'تفاصيل الأذكار',
                                  onPressed: () =>
                                      _details(card['code'] as String),
                                  icon: const Icon(Icons.help_outline),
                                )
                              : null,
                        ),
                        if (card['kind'] != 'FASTING' ||
                            card['state'] == 'EXCLUDED')
                          TextButton(
                            onPressed: blocked
                                ? null
                                : () => _edit(
                                    'state',
                                    card['code'] as String,
                                    state: card['state'] == 'EXCLUDED'
                                        ? 'PENDING'
                                        : 'EXCLUDED',
                                  ),
                            child: Text(
                              card['state'] == 'EXCLUDED'
                                  ? 'إعادة إدراج اليوم'
                                  : 'استثناء من هذا اليوم',
                            ),
                          ),
                      ],
                    ),
                  ),
              ],
          ],
        ),
      ),
    );
  }

  Future<void> _plan(String mode, [String? type]) async {
    try {
      await repository.planFasting(date, mode, fastType: type);
      if (mounted) setState(() => error = null);
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is AuthFailure ? e.message : 'تعذر حفظ خطة الصيام.',
        );
      }
    }
  }

  String _fastingReason(dynamic reason) => switch (reason) {
    'SKIP' => 'مستثنى من النقاط',
    'ADDED' => 'صيام أضفته',
    'RAMADAN' => 'رمضان — تواريخ مؤكدة',
    'WEEKLY' => 'الاثنين والخميس',
    _ => 'غير مخطط',
  };
  String _fastType(dynamic type) => switch (type) {
    'VOLUNTARY' => 'تطوع',
    'MAKEUP' => 'قضاء',
    'OTHER' => 'آخر',
    _ => 'بدون تصنيف',
  };

  Widget _fastingPanel() => Card(
    child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'خطة الصيام: ${_fastingReason(fasting!['reason'])}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text('المنطقة: ${fasting!['regionKey']}'),
          if (fasting!['fastType'] != null)
            Text('النوع: ${_fastType(fasting!['fastType'])}'),
          if (fasting!['calendarStatus'] != 'CONFIRMED')
            const Text(
              'لا توجد تواريخ رمضان مؤكدة لهذا اليوم في منطقتك. يمكنك إضافة اليوم يدويًا؛ تأكيد التقويم من مصدر موثوق مسؤولية الإدارة.',
            ),
          if (fasting!['sourceUrl'] != null)
            SelectableText('مصدر التقويم: ${fasting!['sourceUrl']}'),
          if (fasting!['pinned'] == true)
            const Text('قاعدة التقويم مثبتة مع سجل هذا اليوم.'),
          const Text(
            'التخطيط لا يسجل إتمام الصيام. الاستثناء يزيل نقاطه الممكنة دون طلب سبب.',
          ),
          Wrap(
            spacing: 8,
            children: [
              PopupMenuButton<String>(
                enabled: !blocked,
                tooltip: 'إضافة صيام',
                onSelected: (value) =>
                    _plan('ADD', value == 'NONE' ? null : value),
                itemBuilder: (_) => [
                  const PopupMenuItem(value: 'NONE', child: Text('بدون تصنيف')),
                  const PopupMenuItem(value: 'VOLUNTARY', child: Text('تطوع')),
                  const PopupMenuItem(value: 'MAKEUP', child: Text('قضاء')),
                  const PopupMenuItem(value: 'OTHER', child: Text('آخر')),
                ],
                child: const Padding(
                  padding: EdgeInsets.all(12),
                  child: Text('أضف صيام اليوم'),
                ),
              ),
              TextButton(
                onPressed: blocked ? null : () => _plan('SKIP'),
                child: const Text('استثناء الصيام'),
              ),
              TextButton(
                onPressed: blocked ? null : () => _plan('DEFAULT'),
                child: const Text('الجدول الافتراضي'),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  String _status(String value) => switch (value) {
    'COMPLETED' => 'مكتمل',
    'PARTIAL' => 'إنجاز جزئي',
    'EXCLUDED' => 'مستثنى',
    _ => 'لم يكتمل بعد',
  };
}
