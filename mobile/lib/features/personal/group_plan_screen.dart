import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../auth/auth_client.dart';
import '../daily/journal_repository.dart';

class GroupPlanScreen extends StatefulWidget {
  const GroupPlanScreen({
    super.key,
    required this.repository,
    required this.code,
  });
  final JournalRepository repository;
  final String code;
  @override
  State<GroupPlanScreen> createState() => _GroupPlanScreenState();
}

class _GroupPlanScreenState extends State<GroupPlanScreen> {
  late String date;
  Map<String, dynamic>? plan;
  String? message;
  bool busy = false;
  bool pending = false;
  String? pendingDate;
  JournalRepository get repo => widget.repository;
  List get custom => plan!['customItems'] as List;
  List get hidden => plan!['hiddenDefaultCodes'] as List;

  @override
  void initState() {
    super.initState();
    date = repo.tomorrow;
    _load();
  }

  Future<void> _load() async {
    setState(() => busy = true);
    try {
      pendingDate = await repo.pendingGroupDate(widget.code);
      if (pendingDate != null) date = pendingDate!;
      await repo.loadGroup(widget.code, date);
      final loaded = await repo.readGroup(widget.code, date);
      final queued = await repo.groupPending(widget.code);
      if (mounted) {
        setState(() {
          plan = loaded;
          pending = queued;
          message = loaded == null
              ? 'اتصل بالخادم لتحميل تخصيص هذه المجموعة أولًا.'
              : repo.message;
        });
      }
    } catch (_) {
      if (mounted)
        setState(() => message = 'تعذر قراءة التخصيص المحفوظ. حاول مرة أخرى.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _save() async {
    setState(() => busy = true);
    try {
      await repo.saveGroup(plan!);
      final saved = await repo.readGroup(widget.code, date);
      if (mounted) {
        setState(() {
          plan = saved;
          pending = true;
          message = 'تم الحفظ على الجهاز. اضغط مزامنة للتأكد من وصوله للخادم.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => message = e is AuthFailure ? e.message : 'تعذر حفظ التخصيص.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _edit([Map<String, dynamic>? item]) async {
    final text = TextEditingController(text: item?['textAr'] as String? ?? '');
    final target = TextEditingController(text: '${item?['targetCount'] ?? 1}');
    var type = item?['type'] as String? ?? 'DHIKR';
    final form = GlobalKey<FormState>();
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('محتوى شخصي — بدون نقاط'),
          content: SingleChildScrollView(
            child: Form(
              key: form,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButton<String>(
                    value: type,
                    items: const [
                      DropdownMenuItem(value: 'DHIKR', child: Text('ذكر')),
                      DropdownMenuItem(value: 'DUA', child: Text('دعاء')),
                    ],
                    onChanged: (v) => update(() => type = v!),
                  ),
                  TextFormField(
                    controller: text,
                    maxLines: 4,
                    maxLength: 10000,
                    decoration: const InputDecoration(labelText: 'النص الشخصي'),
                    validator: (v) =>
                        v == null || v.trim().isEmpty ? 'اكتب النص' : null,
                  ),
                  TextFormField(
                    controller: target,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'عدد التكرار'),
                    validator: (v) {
                      final n = int.tryParse(v ?? '');
                      return n == null || n < 1 || n > 1000
                          ? 'اختر عددًا من 1 إلى 1000'
                          : null;
                    },
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إلغاء'),
            ),
            FilledButton(
              onPressed: () {
                if (form.currentState!.validate()) {
                  Navigator.pop(context, <String, dynamic>{
                    'id': item?['id'] ?? const Uuid().v4(),
                    'type': type,
                    'textAr': text.text,
                    'targetCount': int.parse(target.text),
                  });
                }
              },
              child: const Text('إضافة للتخصيص'),
            ),
          ],
        ),
      ),
    );
    // Dialog route's closing animation may still reference its controllers.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    text.dispose();
    target.dispose();
    if (result != null && mounted) {
      setState(() {
        if (item == null) {
          custom.add(result);
        } else {
          custom[custom.indexOf(item)] = result;
        }
      });
    }
  }

  List<Map<String, dynamic>> get official {
    final values = (plan!['officialItems'] as List)
        .cast<Map<String, dynamic>>()
        .toList();
    final order = plan!['officialOrder'] as List;
    final original = values.map((i) => i['code']).toList();
    int rank(Map i) => order.contains(i['code'])
        ? order.indexOf(i['code'])
        : order.length + original.indexOf(i['code']);
    values.sort((a, b) => rank(a).compareTo(rank(b)));
    return values;
  }

  Future<void> _compare() async {
    setState(() => busy = true);
    try {
      final remote = await repo.serverGroup(widget.code, date);
      if (!mounted) return;
      String describe(Map<String, dynamic> p) =>
          'مخفي: ${(p['hiddenDefaultCodes'] as List).join(', ')}\nالترتيب: ${(p['officialOrder'] as List).join(', ')}\n${(p['customItems'] as List).map((i) => '${i['textAr']} — ${i['targetCount']}').join('\n')}';
      final accept = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('مراجعة تخصيص المجموعة'),
          content: SingleChildScrollView(
            child: Text(
              'الجهاز:\n${describe(plan!)}\n\nالخادم:\n${describe(remote)}\n\nاعتماد الخادم يلغي تخصيص هذه المجموعة المعلّق فقط.',
            ),
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
      if (accept == true) {
        await repo.useServerGroup(remote);
        await _load();
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => message = e is AuthFailure
              ? e.message
              : 'تعذر تحميل نسخة الخادم. تعديلاتك محفوظة.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final enabled = !busy && !pending && plan != null;
    final items = plan == null ? <Map<String, dynamic>>[] : official;
    return Scaffold(
      appBar: AppBar(title: const Text('تخصيص المجموعة')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'التخصيص من الغد افتراضيًا. تطبيقه اليوم متاح قبل أي تسجيل بالمجموعة. إخفاء الرسمي لا يغيّر النقاط؛ المحتوى الشخصي للمتابعة فقط.',
          ),
          DropdownButton<String>(
            value: date,
            items: [
              for (final d in {repo.today, repo.tomorrow, date})
                DropdownMenuItem(
                  value: d,
                  child: Text(
                    d == repo.today
                        ? 'اليوم — $d'
                        : d == repo.tomorrow
                        ? 'الغد — $d'
                        : 'تخصيص معلّق — $d',
                  ),
                ),
            ],
            onChanged: busy
                ? null
                : (v) {
                    date = v!;
                    plan = null;
                    _load();
                  },
          ),
          if (busy) const LinearProgressIndicator(),
          if (message != null) Text(message!),
          Wrap(
            spacing: 8,
            children: [
              TextButton(
                onPressed: busy ? null : _load,
                child: const Text('مزامنة'),
              ),
              if (pending && plan != null)
                TextButton(
                  onPressed: busy ? null : _compare,
                  child: const Text('مراجعة نسخة الخادم'),
                ),
            ],
          ),
          if (plan != null) ...[
            const Text('المحتوى الرسمي'),
            for (var index = 0; index < items.length; index++)
              ListTile(
                title: Text(items[index]['textAr'] as String),
                subtitle: Text('التكرار: ${items[index]['targetCount']}'),
                leading: IconButton(
                  tooltip: 'إظهار أو إخفاء',
                  icon: Icon(
                    hidden.contains(items[index]['code'])
                        ? Icons.visibility_off
                        : Icons.visibility,
                  ),
                  onPressed: !enabled
                      ? null
                      : () => setState(() {
                          final code = items[index]['code'];
                          hidden.contains(code)
                              ? hidden.remove(code)
                              : hidden.add(code);
                        }),
                ),
                trailing: IconButton(
                  tooltip: 'تحريك لأعلى',
                  icon: const Icon(Icons.arrow_upward),
                  onPressed: !enabled || index == 0
                      ? null
                      : () => setState(() {
                          final order = items.map((i) => i['code']).toList();
                          final code = order.removeAt(index);
                          order.insert(index - 1, code);
                          plan!['officialOrder'] = order;
                        }),
                ),
              ),
            const Text('المحتوى الشخصي — خاص بك وبدون نقاط'),
            for (var index = 0; index < custom.length; index++)
              ListTile(
                title: Text(custom[index]['textAr'] as String),
                subtitle: Text('التكرار: ${custom[index]['targetCount']}'),
                onTap: enabled
                    ? () => _edit(custom[index] as Map<String, dynamic>)
                    : null,
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      tooltip: 'تحريك لأعلى',
                      onPressed: !enabled || index == 0
                          ? null
                          : () => setState(() {
                              final item = custom.removeAt(index);
                              custom.insert(index - 1, item);
                            }),
                      icon: const Icon(Icons.arrow_upward),
                    ),
                    IconButton(
                      tooltip: 'أرشفة من الخطة الجديدة',
                      onPressed: !enabled
                          ? null
                          : () => setState(() => custom.removeAt(index)),
                      icon: const Icon(Icons.archive_outlined),
                    ),
                  ],
                ),
              ),
            TextButton(
              onPressed: enabled && custom.length < 100 ? () => _edit() : null,
              child: const Text('إضافة ذكر أو دعاء شخصي'),
            ),
            TextButton(
              onPressed: !enabled
                  ? null
                  : () => setState(() {
                      plan =
                          jsonDecode(jsonEncode(plan)) as Map<String, dynamic>;
                      plan!['hiddenDefaultCodes'] = [];
                      plan!['officialOrder'] = [];
                      plan!['customItems'] = [];
                    }),
              child: const Text('استعادة الافتراضي في الخطة الجديدة'),
            ),
            FilledButton(
              onPressed: enabled ? _save : null,
              child: const Text('حفظ التخصيص'),
            ),
          ],
        ],
      ),
    );
  }
}
