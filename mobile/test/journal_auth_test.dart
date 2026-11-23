import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';

import 'auth_test_support.dart';
import 'journal_test_support.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test(
    'initialized account can reopen local journal during network outage',
    () async {
      final client = makeClient(
        (request) => throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        ),
      );
      await client.store.save(
        const SessionTokens('a', 'r', baseUrl, journalAccount),
      );
      expect((await client.restore())!.id, journalAccount.id);
      expect(await client.store.read(), isNotNull);
    },
  );

  test('revoked refresh never falls back to cached identity', () async {
    final client = makeClient((_) => jsonResponse({}, 401));
    await client.store.save(
      const SessionTokens('a', 'r', baseUrl, journalAccount),
    );
    expect(await client.restore(), isNull);
    expect(await client.store.read(), isNull);
  });

  test('concurrent journal requests share one token refresh', () async {
    var refreshes = 0;
    final started = Completer<void>();
    final release = Completer<void>();
    final client = makeClient((request) async {
      if (request.path == 'auth/refresh') {
        refreshes++;
        started.complete();
        await release.future;
        return jsonResponse(tokensJson);
      }
      if (request.headers['Authorization'] == 'Bearer old') {
        return jsonResponse({}, 401);
      }
      return jsonResponse({'ok': true});
    });
    await client.store.save(
      const SessionTokens('old', 'r', baseUrl, journalAccount),
    );
    final a = client.authorized('GET', 'days/a', journalAccount.id);
    final b = client.authorized('GET', 'days/b', journalAccount.id);
    await started.future;
    await Future<void>.delayed(const Duration(milliseconds: 10));
    release.complete();
    expect(await Future.wait([a, b]), [
      {'ok': true},
      {'ok': true},
    ]);
    expect(refreshes, 1);
  });

  test('journal request cannot send another account tokens', () async {
    final client = makeClient((_) => throw StateError('must not send'));
    await client.store.save(
      const SessionTokens('a', 'r', baseUrl, journalAccount),
    );
    await expectLater(
      client.authorized('GET', 'days/a', 'other'),
      throwsA(isA<AuthFailure>()),
    );
  });
}
