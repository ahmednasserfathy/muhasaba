import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_client.dart';
import '../auth/auth_controller.dart';
import '../daily/daily_screen.dart';
import '../daily/journal_repository.dart';

class ReportsScreen extends ConsumerStatefulWidget {
  const ReportsScreen({super.key, required this.account});
  final Account account;
  @override
  ConsumerState<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends ConsumerState<ReportsScreen> {
  late final JournalRepository repository;
  late DateTime anchor;
  bool month = false;
  bool busy = false;
  String? message;
  Map<String, dynamic>? report;

  String iso(DateTime date) => date.toIso8601String().split('T').first;
  DateTime get start => month
      ? DateTime.utc(anchor.year, anchor.month)
      : anchor.subtract(Duration(days: anchor.weekday - 1));
  DateTime get end => month
      ? DateTime.utc(anchor.year, anchor.month + 1, 0)
      : start.add(const Duration(days: 6));

  @override
  void initState() {
    super.initState();
    repository = JournalRepository(
      ref.read(journalDatabaseProvider),
      ref.read(authClientProvider),
      widget.account,
    );
    anchor = DateTime.parse('${repository.today}T00:00:00Z');
    unawaited(load());
  }

  @override
  void dispose() {
    unawaited(repository.dispose());
    super.dispose();
  }

  Future<void> load({bool restore = false}) async {
    setState(() {
      busy = true;
      message = null;
      report = null;
    });
    try {
      var restored = 0;
      if (restore) {
        restored = await repository.restoreRange(iso(start), iso(end));
      }
      final value = await repository.report(iso(start), iso(end));
      if (mounted) {
        setState(() {
          report = value;
          if (restore) {
            message =
                'حُفظت $restored أيام؛ التعديلات المعلقة محفوظة دون استبدال.';
          }
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => message =
              'تعذر تحميل الفترة. أعد المحاولة؛ بيانات الجهاز محفوظة.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void move(int direction) {
    setState(
      () => anchor = month
          ? DateTime.utc(anchor.year, anchor.month + direction, 1)
          : anchor.add(Duration(days: 7 * direction)),
    );
    unawaited(load());
  }

  @override
  Widget build(BuildContext context) {
    final summary = report?['summary'] as Map?;
    final days = (report?['days'] as List?) ?? [];
    final missing = (report?['unavailableDates'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('التقارير')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Wrap(
            spacing: 12,
            children: [
              ChoiceChip(
                label: const Text('أسبوعي'),
                selected: !month,
                onSelected: busy
                    ? null
                    : (_) {
                        setState(() => month = false);
                        unawaited(load());
                      },
              ),
              ChoiceChip(
                label: const Text('شهري'),
                selected: month,
                onSelected: busy
                    ? null
                    : (_) {
                        setState(() => month = true);
                        unawaited(load());
                      },
              ),
              TextButton(
                onPressed: busy ? null : () => move(-1),
                child: const Text('السابق'),
              ),
              TextButton(
                onPressed:
                    busy ||
                        !end.isBefore(
                          DateTime.parse('${repository.today}T00:00:00Z'),
                        )
                    ? null
                    : () => move(1),
                child: const Text('التالي'),
              ),
            ],
          ),
          Text('${iso(start)} — ${iso(end)}', textDirection: TextDirection.ltr),
          const Text(
            'النسبة = مجموع النقاط المكتسبة ÷ مجموع النقاط الممكنة. المستقبل وما قبل بداية المتابعة خارج الحساب.',
          ),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: busy ? null : () => load(),
                child: const Text('تحديث'),
              ),
              OutlinedButton(
                onPressed: busy ? null : () => load(restore: true),
                child: const Text('حفظ الفترة دون اتصال'),
              ),
            ],
          ),
          if (busy) const LinearProgressIndicator(),
          if (message != null) Text(message!),
          if (report != null) ...[
            Text(
              report!['local'] == true
                  ? 'من بيانات الجهاز — قد توجد تعديلات لم تُزامن أو أيام لم تُحمّل.'
                  : 'من البيانات المحفوظة على الخادم.',
            ),
            if (missing.isNotEmpty)
              Text(
                'تقرير غير مكتمل: ${missing.length} يومًا غير متاح. النسبة تخص الأيام المتاحة فقط.',
              ),
            if (days.isEmpty) const Text('لا توجد أيام متاحة في هذه الفترة.'),
            Text(
              'إنجاز الفترة: ${summary?['percent'] ?? '—'}٪',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(
              '${(summary?['earned'] as num?)?.toStringAsFixed(1) ?? '0'} / ${summary?['possible'] ?? 0} نقطة',
            ),
            for (final day in days)
              Card(
                child: ListTile(
                  title: Text(day['date'] as String),
                  subtitle: Text(
                    '${(day['summary']['earned'] as num).toStringAsFixed(1)} / ${day['summary']['possible']} نقطة'
                    '${day['fasting'] == null
                        ? ''
                        : day['fasting']['eligible'] == true
                        ? ' • الصيام مخطط'
                        : ' • الصيام خارج الخطة'}',
                  ),
                  trailing: Text('${day['summary']['percent'] ?? '—'}٪'),
                ),
              ),
            for (final date in missing)
              ListTile(
                title: Text(date as String),
                subtitle: const Text('غير متاح — لم يدخل في النسبة'),
              ),
          ],
        ],
      ),
    );
  }
}
