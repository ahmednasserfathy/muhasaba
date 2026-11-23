import 'dart:async';
import 'dart:convert';

import 'package:drift/drift.dart' show Variable;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../auth/auth_client.dart';
import '../auth/auth_controller.dart';
import '../daily/journal_database.dart';
import 'notification_gateway.dart';
import 'reminder_policy.dart';

final reminderServiceProvider = Provider<ReminderService>((ref) {
  final service = ReminderService(
    ref.read(journalDatabaseProvider),
    ref.read(authClientProvider).dio.options.baseUrl,
    NotificationGateway(),
  );
  ref.onDispose(service.dispose);
  return service;
});

class ReminderService {
  ReminderService(
    this.db,
    this.baseUrl,
    this.gateway, {
    DateTime Function()? clock,
  }) : clock = clock ?? DateTime.now {
    tzdata.initializeTimeZones();
    subscription = db.changes.stream.listen((_) => unawaited(refreshSafely()));
  }
  final JournalDatabase db;
  final String baseUrl;
  final NotificationGateway gateway;
  final DateTime Function() clock;
  late final StreamSubscription<void> subscription;
  Account? account;
  String? get owner => account == null ? null : '$baseUrl|${account!.id}';
  String? error;
  void Function(String date)? onOpen;
  String? pendingPayload;
  Future<void>? initialization;
  Future<void> serial = Future.value();
  bool disposed = false;

  Future<T> _queue<T>(Future<T> Function() task) {
    final result = serial.then((_) => task());
    serial = result.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return result;
  }

  Future<void> initialize() => initialization ??= () async {
    pendingPayload = await gateway.initialize(openPayload);
  }();

  void openPayload(String? payload) {
    if (payload == null) return;
    if (account == null) {
      pendingPayload = payload;
      return;
    }
    try {
      final value = jsonDecode(payload) as Map;
      if (value['owner'] != owner) return;
      final date = value['date'] as String;
      if (DateTime.tryParse(date) == null ||
          !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(date)) {
        return;
      }
      if (account!.trackingStartDate != null &&
          date.compareTo(account!.trackingStartDate!) < 0) {
        return;
      }
      onOpen?.call(date);
    } catch (_) {
      /* Ignore stale or malformed notification payloads. */
    }
  }

  Future<void> activate(Account? next) async {
    final changed =
        account?.id != next?.id || account?.timezone != next?.timezone;
    account = next;
    if (!gateway.supported) return;
    await _queue(() async {
      await initialize();
      if (changed || next == null) await gateway.cancelAll();
      await _refresh();
      final payload = pendingPayload;
      if (account != null) {
        pendingPayload = null;
        openPayload(payload);
      }
    });
  }

  Future<ReminderPreferences> preferences() async {
    if (owner == null) return ReminderPreferences();
    final rows = await db
        .customSelect(
          'SELECT document FROM reminder_preferences WHERE owner=?',
          variables: [Variable(owner!)],
        )
        .get();
    return rows.isEmpty
        ? ReminderPreferences()
        : ReminderPreferences.fromJson(
            jsonDecode(rows.single.read<String>('document'))
                as Map<String, dynamic>,
          );
  }

  Future<void> save(ReminderPreferences preferences) async {
    preferences.validate();
    final expectedOwner = owner;
    final document = jsonEncode(preferences.toJson());
    await _queue(() async {
      if (expectedOwner == null ||
          owner != expectedOwner ||
          !gateway.supported) {
        throw const AuthFailure('التذكيرات متاحة لحساب مسجل على Android.');
      }
      await initialize();
      if (preferences.times.isNotEmpty &&
          !await gateway.permission(request: true)) {
        await gateway.cancelAll();
        throw const AuthFailure(
          'لم يُسمح بالإشعارات. يمكنك السماح بها من إعدادات الجهاز ثم المحاولة.',
        );
      }
      await db.customStatement(
        'INSERT INTO reminder_preferences(owner,document) VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET document=excluded.document',
        [expectedOwner, document],
      );
      await _refresh();
    });
  }

  Future<void> refreshSafely() async {
    if (disposed || !gateway.supported) return;
    try {
      await _queue(() async {
        await initialize();
        await _refresh();
      });
      error = null;
    } catch (_) {
      error = 'تعذر تحديث التذكيرات. افتح إعداداتها وأعد المحاولة.';
    }
  }

  Future<void> _refresh() async {
    final user = account;
    final key = owner;
    if (disposed || user == null || key == null) return;
    final prefs = await preferences();
    if (prefs.times.isEmpty || !await gateway.permission()) {
      await gateway.cancelAll();
      return;
    }
    final now = tz.TZDateTime.from(clock(), tz.getLocation(user.timezone));
    final today = now.toIso8601String().split('T').first;
    final tomorrow = tz.TZDateTime(
      now.location,
      now.year,
      now.month,
      now.day + 1,
    ).toIso8601String().split('T').first;
    final day = await db.readDay(key, today);
    final fasting = await db.readFasting(key, tomorrow);
    final planned = planReminders(
      preferences: prefs,
      now: now,
      day: day,
      tomorrowFasting: fasting,
    );
    for (final kind in reminderLabels.keys) {
      if (disposed || owner != key) return;
      final id = PlannedReminder(kind, now, today).id;
      final rows = await db
          .customSelect(
            'SELECT fire_at FROM reminder_slots WHERE owner=? AND id=?',
            variables: [Variable(key), Variable(id)],
          )
          .get();
      final previous = rows.isEmpty
          ? null
          : DateTime.parse(rows.single.read<String>('fire_at'));
      // Once a scheduled time passes, never issue a second notification for that
      // account/category/date, including after restart or changing the chosen time.
      if (previous != null && !previous.isAfter(now)) {
        await gateway.cancel(id);
        continue;
      }
      final candidates = planned.where((p) => p.kind == kind);
      if (candidates.isEmpty) {
        await gateway.cancel(id);
        await db.customStatement(
          'DELETE FROM reminder_slots WHERE owner=? AND id=?',
          [key, id],
        );
        continue;
      }
      final reminder = candidates.single;
      // Persist the reservation before dispatch; a failed dispatch may suppress
      // that day's reminder rather than risk duplicate delivery after a crash.
      await db.customStatement(
        'INSERT INTO reminder_slots(owner,id,fire_at) VALUES(?,?,?) ON CONFLICT(owner,id) DO UPDATE SET fire_at=excluded.fire_at',
        [key, id, reminder.when.toUtc().toIso8601String()],
      );
      await gateway.schedule(
        reminder,
        jsonEncode({'owner': key, 'date': reminder.date}),
      );
    }
  }

  void dispose() {
    disposed = true;
    unawaited(subscription.cancel());
  }
}
