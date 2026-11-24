import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';
import 'package:muhasaba/features/reminders/reminder_policy.dart';
import 'package:timezone/timezone.dart' as tz;

import 'auth_test_support.dart';
import 'journal_repository_test.dart' show idle;
import 'journal_test_support.dart';

Map<String, dynamic> samplePlan(String date) => {
  'activityCode': 'set',
  'date': date,
  'catalogRelease': 'test-release',
  'rowVersion': 0,
  'effectiveFrom': null,
  'hiddenDefaultCodes': <String>[],
  'officialOrder': <String>[],
  'customItems': <Map<String, dynamic>>[],
  'officialItems': DayData.items(sampleDay().card('set')),
};
const personal = {
  'id': '98f1c570-051b-4e45-afde-6771c65e2867',
  'type': 'DUA',
  'textAr': 'نص شخصي للاختبار',
  'targetCount': 1,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late JournalDatabase db;
  late JournalRepository repo;
  late AuthClient auth;
  late JournalServer server;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    db = JournalDatabase(NativeDatabase.memory());
    server = JournalServer(sampleDay())..offline = true;
    auth = makeClient(server.handle);
    await auth.store.save(
      const SessionTokens('access', 'refresh', baseUrl, journalAccount),
    );
    repo = JournalRepository(db, auth, journalAccount);
    await db.saveGroup(repo.owner, samplePlan(repo.tomorrow));
    await db.saveGroup(repo.owner, samplePlan(repo.today));
    await db.saveDay(repo.owner, sampleDay(repo.today));
  });
  tearDown(() async {
    await idle(repo);
    await repo.dispose();
    await db.close();
  });

  test(
    'five official three done stays 1.2 with hidden and personal completion',
    () {
      final day = sampleDay();
      final group = day.card('set');
      final original = DayData.items(group).first;
      group['items'] = [
        for (var i = 0; i < 5; i++)
          {
            ...original,
            'code': '$i',
            'completedCount': i < 3 ? 1 : 0,
            'hidden': i >= 3,
          },
      ];
      DayData.items(group).add({
        ...original,
        'sourceType': 'PERSONAL',
        'completedCount': 1,
        'isScoreEligible': false,
      });
      day.recalculate();
      expect(group['earnedPoints'], 1.2);
      expect(group['possiblePoints'], 2);
      expect(group['hiddenOfficialIncomplete'], 2);
      expect(group['personalCompleted'], 1);
      day.card('dhuhr')['state'] = 'COMPLETED';
      final now = tz.TZDateTime(
        tz.getLocation('Africa/Cairo'),
        2026,
        11,
        19,
        12,
      );
      expect(
        planReminders(
          preferences: ReminderPreferences(
            times: {'INCOMPLETE_PROGRESS': 1200},
          ),
          now: now,
          day: day,
        ),
        isEmpty,
      );
      DayData.items(group).last['completedCount'] = 0;
      expect(
        planReminders(
          preferences: ReminderPreferences(
            times: {'INCOMPLETE_PROGRESS': 1200},
          ),
          now: now,
          day: day,
        ),
        isEmpty,
      );
    },
  );

  test(
    'offline plan and outbox are atomic, owner scoped and versioned',
    () async {
      final plan = (await repo.readGroup('set', repo.tomorrow))!;
      plan['customItems'] = [personal];
      plan['hiddenDefaultCodes'] = ['two'];
      await repo.saveGroup(plan);
      await idle(repo);
      expect((await repo.readGroup('set', repo.tomorrow))!['rowVersion'], 1);
      final row = (await db.pending(repo.owner)).single;
      final payload = jsonDecode(row.read<String>('payload'));
      expect(payload['customItems'], [personal]);
      expect(payload['expectedVersion'], 0);
      expect(await db.readGroup('another-owner', 'set', repo.tomorrow), isNull);
      await expectLater(repo.saveGroup(plan), throwsA(isA<AuthFailure>()));
    },
  );

  test('failed enqueue rolls back the plan and today projection', () async {
    final plan = (await repo.readGroup('set', repo.today))!;
    plan['customItems'] = [personal];
    await db.customStatement(
      "CREATE TRIGGER fail_enqueue BEFORE INSERT ON sync_outbox BEGIN SELECT RAISE(ABORT, 'test'); END",
    );
    await expectLater(repo.saveGroup(plan), throwsA(anything));
    expect((await repo.readGroup('set', repo.today))!['rowVersion'], 0);
    expect((await repo.read(repo.today))!.card('set')['personalTotal'], 0);
    expect(await repo.pendingCount(), 0);
  });

  test(
    'today plan must sync before counters; started groups require tomorrow',
    () async {
      final plan = (await repo.readGroup('set', repo.today))!;
      plan['customItems'] = [personal];
      await repo.saveGroup(plan);
      await idle(repo);
      await expectLater(
        repo.edit(repo.today, 'count', 'personal:${personal['id']}', delta: 1),
        throwsA(isA<AuthFailure>()),
      );
      final projected = (await repo.read(repo.today))!;
      expect(projected.card('set')['planVersion'], 1);
      expect(projected.card('set')['possiblePoints'], 2);
    },
  );

  test('started or undone group cannot be customized today', () async {
    final day = (await repo.read(repo.today))!;
    DayData.items(day.card('set')).first['rowVersion'] = 2;
    await db.saveDay(repo.owner, day);
    await expectLater(
      repo.saveGroup((await repo.readGroup('set', repo.today))!),
      throwsA(isA<AuthFailure>()),
    );
    expect(await repo.pendingCount(), 0);
  });

  test(
    'personal counts use pinned version, bulk updates official only',
    () async {
      final day = sampleDay(repo.today);
      day.applyGroup({
        ...samplePlan(repo.today),
        'rowVersion': 3,
        'customItems': [personal],
      });
      await db.saveDay(repo.owner, day);
      await repo.edit(
        repo.today,
        'count',
        'personal:${personal['id']}',
        delta: 1,
      );
      await idle(repo);
      await repo.edit(repo.today, 'set', 'set', action: 'COMPLETE_ALL');
      await idle(repo);
      final rows = await db.pending(repo.owner);
      expect(
        jsonDecode(rows[0].read<String>('payload'))['expectedPlanVersion'],
        3,
      );
      expect(jsonDecode(rows[1].read<String>('payload'))['expectedVersions'], {
        'one': 0,
        'two': 0,
      });
      final group = (await repo.read(repo.today))!.card('set');
      expect(group['earnedPoints'], 2);
      expect(group['personalCompleted'], 1);
      expect(DayData.items(group).last['rowVersion'], 1);
    },
  );

  test(
    'lost plan response retries same ID, never writes a plan as day data',
    () async {
      Map<String, dynamic>? receipt;
      final ids = <String>[];
      auth.dio.httpClientAdapter = FakeAdapter((request) {
        final data = request.data as Map;
        ids.add(data['clientMutationId'] as String);
        if (receipt != null) return jsonResponse(receipt);
        receipt = {
          ...samplePlan(repo.tomorrow),
          'rowVersion': 1,
          'customItems': data['customItems'],
        };
        return jsonResponse({}, 503);
      });
      final plan = (await repo.readGroup('set', repo.tomorrow))!
        ..['customItems'] = [personal];
      await repo.saveGroup(plan);
      await idle(repo);
      expect(await repo.pendingCount(), 1);
      await repo.sync();
      expect(await repo.pendingCount(), 0);
      expect(ids[0], ids[1]);
      expect(await repo.read(repo.tomorrow), isNull);
      expect((await repo.readGroup('set', repo.tomorrow))!['customItems'], [
        personal,
      ]);
    },
  );

  test(
    'explicit plan conflict resolution preserves unrelated queued journal',
    () async {
      await repo.saveGroup((await repo.readGroup('set', repo.tomorrow))!);
      await idle(repo);
      await repo.edit(repo.today, 'state', 'dhuhr');
      await idle(repo);
      await repo.useServerGroup({
        ...samplePlan(repo.tomorrow),
        'rowVersion': 2,
      });
      await idle(repo);
      final rows = await db.pending(repo.owner);
      expect(rows.length, 1);
      expect(rows.single.read<String>('route'), contains('/activities/dhuhr'));
      expect(
        (await repo.read(repo.today))!.card('dhuhr')['state'],
        'COMPLETED',
      );
    },
  );

  test(
    'v3 migration and restart preserve plan cache and pending mutation',
    () async {
      final temp = await Directory.systemTemp.createTemp('muhasaba-personal-');
      final file = File('${temp.path}/journal.sqlite');
      var disk = JournalDatabase(NativeDatabase(file));
      await disk.saveDay('owner', sampleDay());
      await disk.customStatement('DROP TABLE local_group_plans');
      await disk.customStatement('PRAGMA user_version = 3');
      await disk.close();
      disk = JournalDatabase(NativeDatabase(file));
      expect(await disk.readDay('owner', '2026-11-19'), isNotNull);
      await disk.saveGroup('owner', {
        ...samplePlan(repo.tomorrow),
        'customItems': [personal],
      });
      await disk.customStatement(
        "INSERT INTO sync_outbox(owner,date,route,payload) VALUES('owner',?,'me/groups/set/plan','{}')",
        [repo.tomorrow],
      );
      await disk.close();
      disk = JournalDatabase(NativeDatabase(file));
      expect(
        (await disk.readGroup('owner', 'set', repo.tomorrow))!['customItems'],
        [personal],
      );
      expect((await disk.pending('owner')).length, 1);
      await disk.close();
      await temp.delete(recursive: true);
    },
  );
}
