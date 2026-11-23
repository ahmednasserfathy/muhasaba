import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';

import 'auth_test_support.dart';
import 'journal_test_support.dart';

Future<void> idle(JournalRepository repo) async {
  for (var i = 0; i < 100; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 5));
    if (!repo.syncing) return;
  }
  fail('Sync did not finish');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late JournalDatabase db;
  late JournalServer server;
  late AuthClient auth;
  late JournalRepository repo;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    db = JournalDatabase(NativeDatabase.memory());
    server = JournalServer(sampleDay());
    auth = makeClient(server.handle);
    await auth.store.save(
      const SessionTokens('access', 'refresh', baseUrl, journalAccount),
    );
    repo = JournalRepository(db, auth, journalAccount);
    await repo.load('2026-11-19');
  });
  tearDown(() async {
    await idle(repo);
    await repo.dispose();
    await db.close();
  });

  test(
    'rapid offline double tap keeps last intent and sequential versions',
    () async {
      server.offline = true;
      await Future.wait([
        repo.edit(server.day.date, 'state', 'dhuhr'),
        repo.edit(server.day.date, 'state', 'dhuhr'),
      ]);
      await idle(repo);
      final local = (await repo.read(server.day.date))!;
      expect(local.card('dhuhr')['state'], 'PENDING');
      expect(local.json['summary']['earned'], 0);
      final outbox = await db.pending(repo.owner);
      expect(outbox.length, 2);
      expect(
        outbox.map(
          (r) => jsonDecode(r.read<String>('payload'))['expectedVersion'],
        ),
        [0, 1],
      );
      server.offline = false;
      await repo.sync();
      expect(await repo.pendingCount(), 0);
      expect(server.day.card('dhuhr')['state'], 'PENDING');
      expect(server.day.card('dhuhr')['rowVersion'], 2);
    },
  );

  test('state and outbox rollback together when enqueue fails', () async {
    await db.customStatement(
      "CREATE TRIGGER fail_enqueue BEFORE INSERT ON sync_outbox BEGIN SELECT RAISE(ABORT, 'test failure'); END",
    );
    await expectLater(
      repo.edit(server.day.date, 'state', 'dhuhr'),
      throwsA(anything),
    );
    expect(
      (await repo.read(server.day.date))!.card('dhuhr')['state'],
      'PENDING',
    );
    expect(await repo.pendingCount(), 0);
  });

  test('lost response retries the same UUID without double-applying', () async {
    server.loseNextResponse = true;
    await repo.edit(server.day.date, 'state', 'dhuhr');
    await idle(repo);
    expect(await repo.pendingCount(), 1);
    expect(server.day.card('dhuhr')['rowVersion'], 1);
    await repo.sync();
    expect(await repo.pendingCount(), 0);
    expect(
      server.payloads[0]['clientMutationId'],
      server.payloads[1]['clientMutationId'],
    );
    expect(server.day.card('dhuhr')['rowVersion'], 1);
  });

  test('counter and bulk undo produce partial score without bonus', () async {
    await repo.edit(server.day.date, 'count', 'official:set:one', delta: 1);
    await idle(repo);
    expect(server.day.card('set')['earnedPoints'], 1);
    await repo.edit(server.day.date, 'set', 'set', action: 'COMPLETE_ALL');
    await idle(repo);
    expect(server.day.card('set')['earnedPoints'], 2);
    await repo.edit(server.day.date, 'count', 'official:set:two', delta: -1);
    await idle(repo);
    expect(server.day.card('set')['earnedPoints'], 1);
    await repo.edit(server.day.date, 'set', 'set', action: 'CLEAR_ALL');
    await idle(repo);
    expect(server.day.card('set')['earnedPoints'], 0);
  });

  test(
    'conflict retains local intent and pauses until explicit server choice',
    () async {
      server.forceConflict = true;
      await repo.edit(server.day.date, 'state', 'dhuhr');
      await idle(repo);
      expect(await repo.blocked(server.day.date), true);
      expect(
        (await repo.read(server.day.date))!.card('dhuhr')['state'],
        'COMPLETED',
      );
      await repo.load(server.day.date);
      expect(
        (await repo.read(server.day.date))!.card('dhuhr')['state'],
        'COMPLETED',
      );
      await expectLater(
        repo.edit(server.day.date, 'state', 'dhuhr'),
        throwsA(isA<AuthFailure>()),
      );
      final remote = await repo.serverDay(server.day.date);
      await repo.useServer(remote);
      await idle(repo);
      expect(await repo.pendingCount(), 0);
      expect(
        (await repo.read(server.day.date))!.card('dhuhr')['state'],
        'PENDING',
      );
    },
  );

  test(
    'cached data and pending writes are isolated by account and backend',
    () async {
      server.offline = true;
      await repo.edit(server.day.date, 'state', 'dhuhr');
      await idle(repo);
      const other = Account(
        id: 'other-user',
        email: '',
        timezone: 'Africa/Cairo',
        emailVerified: false,
      );
      final otherRepo = JournalRepository(db, auth, other);
      expect(await otherRepo.read(server.day.date), isNull);
      expect(await otherRepo.pendingCount(), 0);
      final oldBase = auth.dio.options.baseUrl;
      auth.dio.options.baseUrl = 'https://different.test/';
      expect(await repo.read(server.day.date), isNull);
      auth.dio.options.baseUrl = oldBase;
      await otherRepo.dispose();
    },
  );

  test('new uncached day never inherits yesterday counters', () async {
    await expectLater(
      repo.edit('2026-11-20', 'state', 'dhuhr'),
      throwsA(isA<AuthFailure>()),
    );
    expect(await repo.read('2026-11-20'), isNull);
    expect(await repo.pendingCount(), 0);
  });

  test('an old GET cannot overwrite a completed local write', () async {
    final started = Completer<void>();
    final release = Completer<void>();
    final old = sampleDay();
    auth.dio.httpClientAdapter = FakeAdapter((request) async {
      if (request.method == 'GET') {
        started.complete();
        await release.future;
        return jsonResponse(old.json);
      }
      return server.handle(request);
    });
    final loading = repo.load(server.day.date);
    await started.future;
    await repo.edit(server.day.date, 'state', 'dhuhr');
    await idle(repo);
    release.complete();
    await loading;
    expect(
      (await repo.read(server.day.date))!.card('dhuhr')['state'],
      'COMPLETED',
    );
  });

  test(
    'file database survives restart offline, then drains on reconnect',
    () async {
      final temp = await Directory.systemTemp.createTemp(
        'muhasaba-journal-test',
      );
      final file = File('${temp.path}/journal.sqlite');
      var disk = JournalDatabase(NativeDatabase(file));
      var persisted = JournalRepository(disk, auth, journalAccount);
      await persisted.load(server.day.date);
      server.offline = true;
      await persisted.edit(
        server.day.date,
        'count',
        'official:set:one',
        delta: 1,
      );
      await idle(persisted);
      await persisted.dispose();
      await disk.close();
      disk = JournalDatabase(NativeDatabase(file));
      persisted = JournalRepository(disk, auth, journalAccount);
      await persisted.load(server.day.date);
      expect(
        (await persisted.read(server.day.date))!.card('set')['earnedPoints'],
        1,
      );
      expect(await persisted.pendingCount(), 1);
      server.offline = false;
      await persisted.sync();
      expect(await persisted.pendingCount(), 0);
      expect(server.day.card('set')['earnedPoints'], 1);
      await persisted.dispose();
      await disk.close();
      await temp.delete(recursive: true);
    },
  );

  test(
    'Dart scoring uses exact fractions and ignores personal/non-scoring entries',
    () {
      final day = sampleDay();
      final items = DayData.items(day.card('set'));
      items[0]['completedCount'] = 1;
      items[1]['targetCount'] = 3;
      items[1]['completedCount'] = 1;
      items.add({
        ...items[0],
        'sourceType': 'PERSONAL',
        'isScoreEligible': true,
      });
      day.recalculate();
      expect(day.card('set')['earnedPoints'], closeTo(4 / 3, 1e-12));
      expect(day.json['summary']['percent'], 33);
      expect(Fraction(25, 2).rounded, 13);
      items[1]['completedCount'] = 0;
      day.recalculate();
      expect(day.card('set')['earnedPoints'], 1);
    },
  );
}
