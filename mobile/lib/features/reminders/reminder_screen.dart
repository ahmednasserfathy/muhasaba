import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_client.dart';
import 'reminder_policy.dart';
import 'reminder_service.dart';

class ReminderScreen extends ConsumerStatefulWidget {
  const ReminderScreen({super.key});
  @override
  ConsumerState<ReminderScreen> createState() => _ReminderScreenState();
}

class _ReminderScreenState extends ConsumerState<ReminderScreen> {
  ReminderPreferences? preferences;
  bool busy = false;
  String? message;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final prefs = await ref.read(reminderServiceProvider).preferences();
      if (mounted) setState(() => preferences = prefs);
    } catch (_) {
      if (mounted) setState(() => message = 'تعذر قراءة إعدادات التذكير.');
    }
  }

  Future<int?> pick(int minute) async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: minute ~/ 60, minute: minute % 60),
    );
    return time == null ? null : time.hour * 60 + time.minute;
  }

  Future<void> save(ReminderPreferences next) async {
    setState(() {
      busy = true;
      message = null;
    });
    try {
      await ref.read(reminderServiceProvider).save(next);
      if (mounted) {
        setState(() {
          preferences = next;
          message = 'تم حفظ الإعدادات على هذا الجهاز.';
        });
      }
    } catch (error) {
      if (mounted) {
        setState(
          () => message = error is AuthFailure
              ? error.message
              : 'تعذر حفظ التذكيرات. أعد المحاولة.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  ReminderPreferences copy() =>
      ReminderPreferences.fromJson(preferences!.toJson());
  String time(int minute) =>
      '${(minute ~/ 60).toString().padLeft(2, '0')}:${(minute % 60).toString().padLeft(2, '0')}';
  @override
  Widget build(BuildContext context) {
    final service = ref.read(reminderServiceProvider);
    final prefs = preferences;
    return Scaffold(
      appBar: AppBar(title: const Text('التذكيرات الاختيارية')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'كل التذكيرات مقفولة افتراضيًا. اختر الوقت المناسب لك. لن تظهر درجاتك أو نصوصك الخاصة في الإشعار.',
          ),
          Text('المنطقة الزمنية: ${service.account?.timezone ?? '—'}'),
          const Text(
            'نستخدم اليوم المحمّل على الجهاز وخطة صيام الغد المحمّلة. افتح التطبيق يوميًا لتحديث الجدولة؛ لا نعرف تعديلات الأجهزة الأخرى أثناء إغلاقه.',
          ),
          const Text(
            'ملخص المتبقي مرة واحدة كحد أقصى يوميًا. التوقيت تقريبي حسب نظام الجهاز. أوقات الصمت تُتخطّى ولا تؤجَّل.',
          ),
          if (!service.gateway.supported)
            const Text('إشعارات النظام متاحة على Android فقط.'),
          if (message != null) Text(message!),
          if (service.error != null) Text(service.error!),
          if (busy) const LinearProgressIndicator(),
          if (prefs != null) ...[
            for (final entry in reminderLabels.entries)
              SwitchListTile(
                title: Text(entry.value),
                subtitle: Text(
                  prefs.times[entry.key] == null
                      ? 'متوقف'
                      : time(prefs.times[entry.key]!),
                ),
                value: prefs.times.containsKey(entry.key),
                onChanged: busy || !service.gateway.supported
                    ? null
                    : (enabled) async {
                        final next = copy();
                        if (enabled) {
                          final chosen = await pick(20 * 60);
                          if (chosen == null || !mounted) return;
                          next.times[entry.key] = chosen;
                        } else {
                          next.times.remove(entry.key);
                        }
                        await save(next);
                      },
                secondary: prefs.times.containsKey(entry.key)
                    ? IconButton(
                        tooltip: 'تغيير الوقت',
                        icon: const Icon(Icons.schedule),
                        onPressed: busy
                            ? null
                            : () async {
                                final chosen = await pick(
                                  prefs.times[entry.key]!,
                                );
                                if (chosen == null || !mounted) return;
                                final next = copy();
                                next.times[entry.key] = chosen;
                                await save(next);
                              },
                      )
                    : null,
              ),
            ListTile(
              title: const Text('بداية ساعات الصمت'),
              subtitle: Text(time(prefs.quietStart)),
              onTap: busy
                  ? null
                  : () async {
                      final chosen = await pick(prefs.quietStart);
                      if (chosen == null || !mounted) return;
                      final next = copy();
                      next.quietStart = chosen;
                      await save(next);
                    },
            ),
            ListTile(
              title: const Text('نهاية ساعات الصمت'),
              subtitle: Text(time(prefs.quietEnd)),
              onTap: busy
                  ? null
                  : () async {
                      final chosen = await pick(prefs.quietEnd);
                      if (chosen == null || !mounted) return;
                      final next = copy();
                      next.quietEnd = chosen;
                      await save(next);
                    },
            ),
            const Text('اختيار نفس وقت البداية والنهاية يلغي ساعات الصمت.'),
            OutlinedButton(
              onPressed: busy
                  ? null
                  : () {
                      final next = copy();
                      next.times.clear();
                      save(next);
                    },
              child: const Text('إيقاف كل التذكيرات'),
            ),
          ],
        ],
      ),
    );
  }
}
