import 'dart:async';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';

import 'auth_test_support.dart';
import 'journal_repository_test.dart' show idle;
import 'journal_test_support.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late JournalDatabase db;
  late AuthClient auth;
  late JournalRepository repo;
  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    db = JournalDatabase(NativeDatabase.memory());
    auth = makeClient((_) => jsonResponse({}, 503));
    await auth.store.save(
      const SessionTokens('a', 'r', baseUrl, journalAccount),
    );
    repo = JournalRepository(db, auth, journalAccount);
  });
  tearDown(() async {
    await idle(repo);
    await repo.dispose();
    await db.close();
  });

  test('period uses exact weighted sums, with missing days explicit', () async {
    final day = sampleDay('2026-11-18');
    final items = DayData.items(day.card('set'));
    items[0]['targetCount'] = 3;
    items[0]['completedCount'] = 1;
    await db.saveDay(repo.owner, day);
    final second = sampleDay('2026-11-19');
    second.card('dhuhr')['state'] = 'EXCLUDED';
    second.card('set')['weight'] = 4;
    DayData.items(second.card('set'))[0]['completedCount'] = 1;
    await db.saveDay(repo.owner, second);
    final result = await repo.localReport('2026-11-17', '2026-11-19');
    expect(result['unavailableDates'], ['2026-11-17']);
    expect(result['summary']['earned'], closeTo(7 / 3, 1e-12));
    expect(result['summary']['possible'], 8);
    expect(result['summary']['percent'], 29);
  });

  test(
    'restore preserves blocked work and imports other days for offline reports',
    () async {
      await db.saveDay(repo.owner, sampleDay());
      await repo.edit('2026-11-19', 'state', 'dhuhr');
      await idle(repo);
      auth.dio.httpClientAdapter = FakeAdapter(
        (request) => request.method == 'PUT'
            ? jsonResponse({}, 409)
            : jsonResponse({
                'days': [sampleDay('2026-11-18').json, sampleDay().json],
              }),
      );
      await repo.restoreRange('2026-11-18', '2026-11-19');
      expect(await repo.blocked('2026-11-19'), true);
      expect(await repo.pendingCount(), 1);
      expect(
        (await repo.read('2026-11-19'))!.card('dhuhr')['state'],
        'COMPLETED',
      );
      expect(await repo.read('2026-11-18'), isNotNull);
      final result = await repo.report('2026-11-18', '2026-11-19');
      expect(result['local'], true);
      expect(result['summary']['percent'], 25);
    },
  );

  test(
    'in-flight restore cannot overwrite an edit already acknowledged',
    () async {
      final server = JournalServer(sampleDay());
      await db.saveDay(repo.owner, sampleDay());
      final started = Completer<void>();
      final release = Completer<void>();
      auth.dio.httpClientAdapter = FakeAdapter((request) async {
        if (request.method == 'GET') {
          started.complete();
          await release.future;
          return jsonResponse({
            'days': [sampleDay().json],
          });
        }
        return server.handle(request);
      });
      final loading = repo.restoreRange('2026-11-19', '2026-11-19');
      await started.future;
      await repo.edit('2026-11-19', 'state', 'dhuhr');
      await idle(repo);
      expect(await repo.pendingCount(), 0);
      release.complete();
      await loading;
      expect(
        (await repo.read('2026-11-19'))!.card('dhuhr')['state'],
        'COMPLETED',
      );
    },
  );

  test('restore is atomic and scoped, range is bounded', () async {
    auth.dio.httpClientAdapter = FakeAdapter(
      (_) => jsonResponse({
        'days': [sampleDay('2026-11-18').json, sampleDay().json],
      }),
    );
    await db.customStatement(
      "CREATE TRIGGER fail_restore BEFORE INSERT ON local_days WHEN NEW.date='2026-11-19' BEGIN SELECT RAISE(ABORT, 'test'); END",
    );
    await expectLater(
      repo.restoreRange('2026-11-18', '2026-11-19'),
      throwsA(anything),
    );
    expect(await repo.read('2026-11-18'), isNull);
    await expectLater(
      repo.restoreRange('2026-10-01', '2026-11-01'),
      throwsA(isA<AuthFailure>()),
    );
    await db.customStatement('DROP TRIGGER fail_restore');
    await repo.restoreRange('2026-11-18', '2026-11-19');
    final other = JournalRepository(
      db,
      auth,
      const Account(
        id: 'other',
        email: '',
        timezone: 'Africa/Cairo',
        emailVerified: false,
      ),
    );
    final result = await other.localReport('2026-11-18', '2026-11-19');
    expect(result['days'], isEmpty);
    expect(result['summary']['percent'], isNull);
    await other.dispose();
  });

  test('canonical report is used online, cache fallback is labelled', () async {
    auth.dio.httpClientAdapter = FakeAdapter((request) {
      expect(request.path, contains('reports/summary'));
      return jsonResponse({
        'days': [],
        'unavailableDates': [],
        'summary': {'earned': 0, 'possible': 0, 'percent': null},
      });
    });
    expect((await repo.report('2026-11-19', '2026-11-19'))['local'], false);
    auth.dio.httpClientAdapter = FakeAdapter((_) => jsonResponse({}, 503));
    expect((await repo.report('2026-11-19', '2026-11-19'))['local'], true);
  });
}
