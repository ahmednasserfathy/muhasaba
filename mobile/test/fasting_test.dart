import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:drift/drift.dart' show MigrationStrategy;
import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';

import 'auth_test_support.dart';
import 'journal_test_support.dart';
import 'journal_repository_test.dart' show idle;

Map<String, dynamic> samplePlan(String date, {String baseline = 'UNPLANNED'}) =>
    {
      'date': date,
      'regionKey': 'EG',
      'mode': 'DEFAULT',
      'fastType': null,
      'rowVersion': 0,
      'eligible': baseline != 'UNPLANNED',
      'reason': baseline,
      'baseReason': baseline,
      'calendarStatus': baseline == 'RAMADAN' ? 'CONFIRMED' : 'UNAVAILABLE',
      'sourceUrl': null,
      'pinned': false,
    };

class FastingServer extends JournalServer {
  FastingServer(super.day) {
    plan = samplePlan(day.date);
    day.json['fasting'] = plan;
    day.cards.add({
      ...day.card('dhuhr'),
      'code': 'fast',
      'titleAr': 'الصيام',
      'kind': 'FASTING',
      'weight': 5,
    });
    day.recalculate();
  }
  late Map<String, dynamic> plan;
  @override
  ResponseBody handle(RequestOptions request) {
    if (offline) {
      throw DioException(
        requestOptions: request,
        type: DioExceptionType.connectionError,
      );
    }
    if (request.path.startsWith('fasting/calendar')) {
      return jsonResponse({
        'days': [plan],
      });
    }
    if (request.path.endsWith('/fasting-plan')) {
      final data = Map<String, dynamic>.from(request.data as Map);
      final id = data['clientMutationId'] as String;
      payloads.add(data);
      if (receipts.containsKey(id)) return jsonResponse(receipts[id]);
      if (forceConflict || data['expectedVersion'] != plan['rowVersion']) {
        return jsonResponse({}, 409);
      }
      plan['mode'] = data['mode'];
      plan['fastType'] = data['fastType'];
      plan['rowVersion'] = (plan['rowVersion'] as int) + 1;
      DayData.recalculatePlan(plan);
      day.recalculate();
      receipts[id] = jsonDecode(jsonEncode(plan)) as Map<String, dynamic>;
      if (loseNextResponse) {
        loseNextResponse = false;
        throw DioException(
          requestOptions: request,
          type: DioExceptionType.receiveTimeout,
        );
      }
      return jsonResponse(plan);
    }
    return super.handle(request);
  }
}

// Actual v1 SQL fixture to verify non-destructive migration to the new cache.
class LegacyDatabase extends JournalDatabase {
  LegacyDatabase(super.executor);
  @override
  int get schemaVersion => 1;
  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (_) async {
      await customStatement(
        'CREATE TABLE local_days (owner TEXT NOT NULL, date TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(owner,date))',
      );
      await customStatement(
        'CREATE TABLE sync_outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, date TEXT NOT NULL, route TEXT NOT NULL, payload TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0)',
      );
      await customStatement(
        'CREATE INDEX outbox_owner ON sync_outbox(owner,sequence)',
      );
    },
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late JournalDatabase db;
  late FastingServer server;
  late AuthClient auth;
  late JournalRepository repo;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    db = JournalDatabase(NativeDatabase.memory());
    server = FastingServer(sampleDay('2026-11-18'));
    auth = makeClient(server.handle);
    await auth.store.save(
      const SessionTokens('access', 'refresh', baseUrl, journalAccount),
    );
    repo = JournalRepository(db, auth, journalAccount);
    await repo.load(server.day.date);
  });
  tearDown(() async {
    await idle(repo);
    await repo.dispose();
    await db.close();
  });

  test(
    'offline ADD, complete, SKIP and DEFAULT keep ordered intent and score',
    () async {
      server.offline = true;
      await repo.planFasting(server.day.date, 'ADD', fastType: 'MAKEUP');
      await idle(repo);
      expect(
        (await repo.read(server.day.date))!.json['summary']['possible'],
        9,
      );
      expect((await repo.read(server.day.date))!.json['summary']['earned'], 0);
      await repo.edit(server.day.date, 'state', 'fast');
      await idle(repo);
      expect((await repo.read(server.day.date))!.json['summary']['earned'], 5);
      await repo.planFasting(server.day.date, 'SKIP');
      await idle(repo);
      expect(
        (await repo.read(server.day.date))!.json['summary']['possible'],
        4,
      );
      expect((await repo.read(server.day.date))!.json['summary']['earned'], 0);
      await repo.planFasting(server.day.date, 'DEFAULT');
      await idle(repo);
      server.offline = false;
      await repo.sync();
      expect(await repo.pendingCount(), 0);
      expect(server.plan['rowVersion'], 3);
      expect(server.plan['reason'], 'UNPLANNED');
      expect(server.day.card('fast')['state'], 'COMPLETED');
      expect(server.day.json['summary']['earned'], 0);
    },
  );

  test(
    'Ramadan and weekly do not duplicate weight; SKIP restores saved completion',
    () {
      final day = server.day;
      day.json['date'] = '2026-11-19';
      day.json['fasting'] = samplePlan('2026-11-19', baseline: 'RAMADAN');
      day.card('fast')['state'] = 'COMPLETED';
      day.recalculate();
      expect(day.json['summary']['possible'], 9);
      expect(day.json['summary']['earned'], 5);
      day.json['fasting']['mode'] = 'SKIP';
      day.recalculate();
      expect(day.json['summary']['possible'], 4);
      day.json['fasting']['mode'] = 'DEFAULT';
      day.recalculate();
      expect(day.json['summary']['earned'], 5);
    },
  );

  test('plan enqueue failure rolls back cache and daily score', () async {
    await db.customStatement(
      "CREATE TRIGGER fail_plan BEFORE INSERT ON sync_outbox BEGIN SELECT RAISE(ABORT,'failure'); END",
    );
    await expectLater(
      repo.planFasting(server.day.date, 'ADD'),
      throwsA(anything),
    );
    expect((await repo.readFasting(server.day.date))!['rowVersion'], 0);
    expect((await repo.read(server.day.date))!.json['summary']['possible'], 4);
  });

  test(
    'lost plan response replays same UUID without resetting version',
    () async {
      server.loseNextResponse = true;
      await repo.planFasting(server.day.date, 'ADD');
      await idle(repo);
      expect(await repo.pendingCount(), 1);
      await repo.sync();
      expect(server.plan['rowVersion'], 1);
      expect(await repo.pendingCount(), 0);
      expect(
        server.payloads[0]['clientMutationId'],
        server.payloads[1]['clientMutationId'],
      );
    },
  );

  test(
    'future plan survives reopen; future completion remains forbidden',
    () async {
      final future = DateTime.parse(
        repo.today,
      ).add(const Duration(days: 10)).toIso8601String().split('T').first;
      server.plan = samplePlan(future);
      final directory = await Directory.systemTemp.createTemp('fasting-test');
      final file = File('${directory.path}/cache.sqlite');
      var disk = JournalDatabase(NativeDatabase(file));
      var local = JournalRepository(disk, auth, journalAccount);
      await local.load(future);
      server.offline = true;
      await local.planFasting(future, 'ADD');
      await idle(local);
      await expectLater(
        local.edit(future, 'state', 'fast'),
        throwsA(isA<AuthFailure>()),
      );
      expect(await local.read(future), isNull);
      await local.dispose();
      await disk.close();
      disk = JournalDatabase(NativeDatabase(file));
      local = JournalRepository(disk, auth, journalAccount);
      expect((await local.readFasting(future))!['mode'], 'ADD');
      server.offline = false;
      await local.sync();
      expect(await local.pendingCount(), 0);
      await local.dispose();
      await disk.close();
      await directory.delete(recursive: true);
    },
  );

  test(
    'future plan conflict preserves local choice until explicit adoption',
    () async {
      final future = DateTime.parse(
        repo.today,
      ).add(const Duration(days: 10)).toIso8601String().split('T').first;
      server.plan = samplePlan(future);
      await repo.load(future);
      server.forceConflict = true;
      await repo.planFasting(future, 'ADD');
      await idle(repo);
      expect(await repo.blocked(future), true);
      expect((await repo.readFasting(future))!['mode'], 'ADD');
      await repo.useServerFasting(await repo.serverFasting(future));
      await idle(repo);
      expect((await repo.readFasting(future))!['mode'], 'DEFAULT');
      expect(await repo.pendingCount(), 0);
    },
  );

  test(
    'v1 upgrade retains days and outbox while adding isolated fasting cache',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'fasting-migration',
      );
      final file = File('${directory.path}/legacy.sqlite');
      final legacy = LegacyDatabase(NativeDatabase(file));
      await legacy.saveDay(repo.owner, sampleDay());
      await legacy.customStatement(
        'INSERT INTO sync_outbox(owner,date,route,payload) VALUES(?,?,?,?)',
        [repo.owner, '2026-11-19', 'days/2026-11-19/activities/dhuhr', '{}'],
      );
      await legacy.close();
      final upgraded = JournalDatabase(NativeDatabase(file));
      expect(await upgraded.readDay(repo.owner, '2026-11-19'), isNotNull);
      expect((await upgraded.pending(repo.owner)).length, 1);
      await upgraded.saveFasting(repo.owner, samplePlan('2026-11-19'));
      expect(
        await upgraded.readFasting('another-account', '2026-11-19'),
        isNull,
      );
      expect(await upgraded.readFasting(repo.owner, '2026-11-19'), isNotNull);
      await upgraded.close();
      await directory.delete(recursive: true);
    },
  );
}
