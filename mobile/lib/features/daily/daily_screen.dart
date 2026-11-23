import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_client.dart';
import '../auth/auth_controller.dart';
import 'day_data.dart';
import 'journal_database.dart';
import 'journal_repository.dart';

final journalDatabaseProvider = Provider<JournalDatabase>((ref) {
  final db = JournalDatabase.open();
  ref.onDispose(() => unawaited(db.close()));
  return db;
});

class DailyScreen extends ConsumerStatefulWidget {
  const DailyScreen({super.key, required this.account});
  final Account account;
  @override
  ConsumerState<DailyScreen> createState() => _DailyScreenState();
}

class _DailyScreenState extends ConsumerState<DailyScreen>
    with WidgetsBindingObserver {
  late final JournalRepository repository;
  late String date;
  DayData? day;
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
    date = repository.today;
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
      final count = await repository.pendingCount();
      final conflict = await repository.blocked(selected);
      if (mounted && selected == date) {
        setState(() {
          day = loaded;
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
      lastDate: DateTime.parse(repository.today),
    );
    if (selected != null && mounted) {
      setState(() {
        date = selected.toIso8601String().split('T').first;
        day = null;
        error = null;
      });
      await _open();
    }
  }

  Future<void> _resolve() async {
    final selected = date;
    try {
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
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => StreamBuilder<void>(
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
                            : () => _edit('set', code, action: 'COMPLETE_ALL'),
                        child: const Text('إكمال الكل'),
                      ),
                      TextButton(
                        onPressed: blocked
                            ? null
                            : () => _edit('set', code, action: 'CLEAR_ALL'),
                        child: const Text('مسح الكل'),
                      ),
                    ],
                  ),
                  for (final item in DayData.items(card))
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
                              item['isScoreEligible'] == true
                                  ? 'رسمي — ضمن نقاط الكارت'
                                  : 'رسمي — للمتابعة فقط',
                            ),
                            Text('المصدر: ${item['sourceName']}'),
                            SelectableText(item['sourceUrl'] as String),
                            Text(item['licenseNotes'] as String),
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
                                  onPressed: blocked || item['targetCount'] != 1
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
    );
  }

  String _points(dynamic value) => (value as num).toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final summary = day?.json['summary'] as Map<String, dynamic>?;
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
            if (day == null)
              const Text(
                'حمّل اليوم من الخادم مرة واحدة لتتمكن من استخدامه بدون اتصال.',
              ),
            if (day != null)
              for (final category
                  in day!.cards.map((c) => c['categoryCode']).toSet()) ...[
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
                for (final card in day!.cards.where(
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
            const Text(
              'الصيام هنا حسب الاثنين والخميس فقط؛ تخطيط الصيام ورمضان في المرحلة التالية.',
            ),
          ],
        ),
      ),
    );
  }

  String _status(String value) => switch (value) {
    'COMPLETED' => 'مكتمل',
    'PARTIAL' => 'إنجاز جزئي',
    'EXCLUDED' => 'مستثنى',
    _ => 'لم يكتمل بعد',
  };
}
