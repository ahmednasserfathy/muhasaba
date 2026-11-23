import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/reminders/notification_gateway.dart';
import 'package:muhasaba/features/reminders/reminder_policy.dart';
import 'package:muhasaba/features/reminders/reminder_service.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'journal_test_support.dart';

class FakeNotifications extends NotificationGateway {
  bool allowed = true;
  int requests = 0;
  final scheduled = <int, PlannedReminder>{};
  final payloads = <String>[];
  String? launch;
  @override
  bool get supported => true;
  @override
  Future<String?> initialize(void Function(String?) onTap) async => launch;
  @override
  Future<bool> permission({bool request = false}) async {
    if (request) requests++;
    return allowed;
  }

  @override
  Future<void> cancelAll() async => scheduled.clear();
  @override
  Future<void> cancel(int id) async => scheduled.remove(id);
  @override
  Future<void> schedule(PlannedReminder reminder, String payload) async {
    scheduled[reminder.id] = reminder;
    payloads.add(payload);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  tzdata.initializeTimeZones();
  final cairo = tz.getLocation('Africa/Cairo');
  final now = tz.TZDateTime(cairo, 2026, 11, 19, 12);
  test('default off, unknown/completed/excluded days never prompt', () {
    final day = sampleDay();
    expect(
      planReminders(preferences: ReminderPreferences(), now: now, day: day),
      isEmpty,
    );
    final prefs = ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 20 * 60});
    expect(planReminders(preferences: prefs, now: now), isEmpty);
    for (final card in day.cards) {
      card['state'] = 'EXCLUDED';
    }
    expect(planReminders(preferences: prefs, now: now, day: day), isEmpty);
    day.card('dhuhr')['state'] = 'COMPLETED';
    expect(planReminders(preferences: prefs, now: now, day: day), isEmpty);
    day.card('dhuhr')['state'] = 'PENDING';
    expect(planReminders(preferences: prefs, now: now, day: day).length, 1);
  });
  test('quiet hours cross midnight, same-day windows and past times', () {
    final prefs = ReminderPreferences(times: {'DAILY_REVIEW': 23 * 60});
    expect(prefs.quiet(23 * 60), true);
    expect(prefs.quiet(6 * 60), true);
    expect(prefs.quiet(7 * 60), false);
    expect(
      planReminders(preferences: prefs, now: now, day: sampleDay()),
      isEmpty,
    );
    prefs.times['DAILY_REVIEW'] = 11 * 60;
    expect(
      planReminders(preferences: prefs, now: now, day: sampleDay()),
      isEmpty,
    );
    prefs.quietStart = 13 * 60;
    prefs.quietEnd = 15 * 60;
    expect(prefs.quiet(14 * 60), true);
    prefs.quietStart = prefs.quietEnd;
    expect(prefs.quiet(14 * 60), false);
  });
  test(
    'categories need matching remaining card, fasting requires tomorrow plan',
    () {
      final day = sampleDay();
      day.card('set')['code'] = 'fajr_morning_dhikr';
      final prefs = ReminderPreferences(
        times: {
          'MORNING_DHIKR': 13 * 60,
          'EVENING_DHIKR': 14 * 60,
          'FASTING_EVE': 20 * 60,
        },
      );
      final result = planReminders(
        preferences: prefs,
        now: now,
        day: day,
        tomorrowFasting: {'date': '2026-11-20', 'eligible': true},
      );
      expect(result.map((r) => r.kind), ['MORNING_DHIKR', 'FASTING_EVE']);
      expect(result.last.date, '2026-11-20');
      expect(
        planReminders(
          preferences: prefs,
          now: now,
          day: day,
          tomorrowFasting: {'date': '2026-11-20', 'eligible': false},
        ).length,
        1,
      );
    },
  );
  test('timezone and DST gap keep chosen wall time or skip', () {
    final ny = tz.getLocation('America/New_York');
    final prefs = ReminderPreferences(
      times: {'INCOMPLETE_PROGRESS': 150},
      quietStart: 0,
      quietEnd: 0,
    );
    expect(
      planReminders(
        preferences: prefs,
        now: tz.TZDateTime(ny, 2026, 3, 8),
        day: sampleDay('2026-03-08'),
      ),
      isEmpty,
    );
    final plan = planReminders(
      preferences: ReminderPreferences(times: {'DAILY_REVIEW': 20 * 60}),
      now: now,
      day: sampleDay(),
    ).single;
    expect(plan.when.hour, 20);
    expect(plan.when.timeZoneOffset, const Duration(hours: 2));
  });

  late JournalDatabase db;
  late FakeNotifications gateway;
  late ReminderService service;
  late DateTime current;
  setUp(() async {
    db = JournalDatabase(NativeDatabase.memory());
    gateway = FakeNotifications();
    current = now;
    service = ReminderService(
      db,
      'https://example.test/',
      gateway,
      clock: () => current,
    );
    await service.activate(journalAccount);
    await db.saveDay(service.owner!, sampleDay());
  });
  tearDown(() async {
    service.dispose();
    await service.serial;
    await db.close();
  });
  test('permission denial stores no opt-in and makes no schedule', () async {
    gateway.allowed = false;
    await expectLater(
      service.save(ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 1200})),
      throwsA(isA<AuthFailure>()),
    );
    expect((await service.preferences()).times, isEmpty);
    expect(gateway.requests, 1);
    expect(gateway.scheduled, isEmpty);
  });
  test(
    'completion cancels, undo reschedules, consumed slot survives restart',
    () async {
      await service.save(
        ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 1200}),
      );
      expect(gateway.scheduled.length, 1);
      final day = sampleDay();
      for (final card in day.cards) {
        card['state'] = 'EXCLUDED';
      }
      await db.saveDay(service.owner!, day);
      await service.refreshSafely();
      expect(gateway.scheduled, isEmpty);
      await db.saveDay(service.owner!, sampleDay());
      await service.refreshSafely();
      expect(gateway.scheduled.length, 1);
      current = tz.TZDateTime(cairo, 2026, 11, 19, 20, 1);
      service.dispose();
      service = ReminderService(
        db,
        'https://example.test/',
        gateway,
        clock: () => current,
      );
      await service.activate(journalAccount);
      await service.save(
        ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 21 * 60}),
      );
      expect(gateway.scheduled, isEmpty);
    },
  );
  test(
    'opt-out, account switching and deep links preserve isolation',
    () async {
      await service.save(
        ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 1200}),
      );
      final payload = gateway.payloads.single;
      String? opened;
      service.onOpen = (date) => opened = date;
      service.openPayload(payload);
      expect(opened, '2026-11-19');
      opened = null;
      await service.activate(
        const Account(
          id: 'other',
          email: '',
          timezone: 'Africa/Cairo',
          emailVerified: false,
        ),
      );
      expect(gateway.scheduled, isEmpty);
      expect((await service.preferences()).times, isEmpty);
      service.openPayload(payload);
      service.openPayload('invalid');
      expect(opened, isNull);
      await service.activate(journalAccount);
      await service.save(ReminderPreferences());
      expect(gateway.scheduled, isEmpty);
      await service.activate(null);
      expect(gateway.scheduled, isEmpty);
    },
  );
  test('cold-start payload waits for authenticated owner', () async {
    service.dispose();
    gateway.launch = jsonEncode({
      'owner': 'https://example.test/|test-user',
      'date': '2026-11-19',
    });
    service = ReminderService(
      db,
      'https://example.test/',
      gateway,
      clock: () => current,
    );
    String? opened;
    service.onOpen = (date) => opened = date;
    await service.activate(null);
    expect(opened, isNull);
    await service.activate(journalAccount);
    expect(opened, '2026-11-19');
  });
  test(
    'partial official progress still prompts without reading private text',
    () {
      final day = sampleDay();
      DayData.items(day.card('set'))[0]['completedCount'] = 1;
      final result = planReminders(
        preferences: ReminderPreferences(times: {'INCOMPLETE_PROGRESS': 1200}),
        now: now,
        day: day,
      );
      expect(result.length, 1);
      expect(result.single.kind, 'INCOMPLETE_PROGRESS');
    },
  );
  test(
    'v2 database upgrades without losing journal, plan or pending outbox',
    () async {
      final temp = await Directory.systemTemp.createTemp(
        'muhasaba-reminders-test',
      );
      final file = File('${temp.path}/journal.sqlite');
      var disk = JournalDatabase(NativeDatabase(file));
      await disk.saveDay('owner', sampleDay());
      await disk.saveFasting('owner', {
        'date': '2026-11-20',
        'mode': 'ADD',
        'baseReason': 'UNPLANNED',
      });
      await disk.customStatement(
        "INSERT INTO sync_outbox(owner,date,route,payload) VALUES('owner','2026-11-19','test','{}')",
      );
      // Recreate exactly the v2 schema: only reminder tables/version differ.
      await disk.customStatement('DROP TABLE reminder_preferences');
      await disk.customStatement('DROP TABLE reminder_slots');
      await disk.customStatement('PRAGMA user_version = 2');
      await disk.close();
      disk = JournalDatabase(NativeDatabase(file));
      expect(await disk.readDay('owner', '2026-11-19'), isNotNull);
      expect(await disk.readFasting('owner', '2026-11-20'), isNotNull);
      expect((await disk.pending('owner')).length, 1);
      await disk.customStatement(
        "INSERT INTO reminder_preferences(owner,document) VALUES('owner','{}')",
      );
      await disk.customStatement(
        "INSERT INTO reminder_slots(owner,id,fire_at) VALUES('owner',1,'2026-11-19T18:00:00Z')",
      );
      await disk.close();
      await temp.delete(recursive: true);
    },
  );
}
