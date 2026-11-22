import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/auth/auth_controller.dart';

import 'auth_test_support.dart';

class FailingStore extends TokenStore {
  FailingStore() : super(const FlutterSecureStorage());
  @override
  Future<void> save(SessionTokens tokens) async =>
      throw StateError('storage unavailable');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test(
    'authenticate sends correct fields and persists a single encrypted pair',
    () async {
      final client = makeClient((request) {
        expect(request.path, 'auth/register');
        expect(request.data, {
          'email': 'person@example.com',
          'password': 'test-password-123',
          'timezone': 'Africa/Cairo',
          'trackingStartDate': '2026-11-01',
        });
        return jsonResponse(tokensJson, 201);
      });
      final user = await client.authenticate(
        email: ' person@example.com ',
        password: 'test-password-123',
        register: true,
        trackingStartDate: '2026-11-01',
      );
      expect(user.id, 'test-user');
      final stored = await client.store.read();
      expect(stored!.access, 'test-access');
      expect(stored.refresh, 'test-refresh');
      final values = await const FlutterSecureStorage().readAll();
      expect(values.keys, [TokenStore.key]);
      expect(values.values.single, isNot(contains('test-password-123')));
    },
  );

  test('restore rotates expired access and saves new tokens', () async {
    final paths = <String>[];
    final client = makeClient((request) {
      paths.add(request.path);
      if (request.path == 'me') {
        expect(request.headers['Authorization'], 'Bearer old-access');
        return jsonResponse({}, 401);
      }
      expect(request.data, {'refreshToken': 'old-refresh'});
      return jsonResponse(tokensJson);
    });
    await client.store.save(
      const SessionTokens('old-access', 'old-refresh', baseUrl),
    );
    expect((await client.restore())!.email, 'person@example.com');
    expect(paths, ['me', 'auth/refresh']);
    expect((await client.store.read())!.refresh, 'test-refresh');
  });

  test('restore retains tokens on network failure', () async {
    final client = makeClient(
      (request) => throw DioException(
        requestOptions: request,
        type: DioExceptionType.connectionError,
      ),
    );
    await client.store.save(
      const SessionTokens('old-access', 'old-refresh', baseUrl),
    );
    await expectLater(client.restore(), throwsA(isA<AuthFailure>()));
    expect((await client.store.read())!.refresh, 'old-refresh');
  });

  test(
    'failed refresh clears only an invalid session, not transient failure',
    () async {
      var refreshStatus = 503;
      final client = makeClient(
        (request) =>
            jsonResponse({}, request.path == 'me' ? 401 : refreshStatus),
      );
      await client.store.save(
        const SessionTokens('old-access', 'old-refresh', baseUrl),
      );
      await expectLater(client.restore(), throwsA(isA<AuthFailure>()));
      expect(await client.store.read(), isNotNull);
      refreshStatus = 401;
      expect(await client.restore(), isNull);
      expect(await client.store.read(), isNull);
    },
  );

  test('logout clears storage only after server revocation succeeds', () async {
    var status = 503;
    final client = makeClient((request) {
      expect(request.path, 'auth/logout');
      return jsonResponse(null, status);
    });
    await client.store.save(
      const SessionTokens('old-access', 'old-refresh', baseUrl),
    );
    await expectLater(client.logout(), throwsA(isA<AuthFailure>()));
    expect(await client.store.read(), isNotNull);
    status = 204;
    await client.logout();
    expect(await client.store.read(), isNull);
  });

  test('tokens are never sent to a different configured backend', () async {
    final client = makeClient(
      (_) => throw StateError('must not make a request'),
    );
    await client.store.save(
      const SessionTokens('old-access', 'old-refresh', 'https://other.test/'),
    );
    expect(await client.restore(), isNull);
    expect(await client.store.read(), isNull);
  });

  test('malformed stored session is cleared', () async {
    final client = makeClient(
      (_) => throw StateError('must not make a request'),
    );
    await const FlutterSecureStorage().write(
      key: TokenStore.key,
      value: 'invalid json',
    );
    expect(await client.restore(), isNull);
    expect(await client.store.read(), isNull);
  });

  test(
    'failed secure persistence revokes issued session and reports failure',
    () async {
      final paths = <String>[];
      final client = makeClient((request) {
        paths.add(request.path);
        return request.path == 'auth/logout'
            ? jsonResponse(null, 204)
            : jsonResponse(tokensJson);
      }, store: FailingStore());
      await expectLater(
        client.authenticate(
          email: 'person@example.com',
          password: 'password',
          register: false,
        ),
        throwsA(isA<AuthFailure>()),
      );
      expect(paths, ['auth/login', 'auth/logout']);
    },
  );

  test('release requires an explicit HTTPS endpoint', () {
    for (final value in [
      '',
      'http://example.test/',
      'https://user:pass@example.test/',
    ]) {
      expect(
        () => apiBaseUrl(release: true, configured: value),
        throwsA(isA<AuthFailure>()),
      );
    }
    expect(
      apiBaseUrl(release: true, configured: 'https://example.test/api/v1'),
      baseUrl,
    );
    expect(
      apiBaseUrl(release: false, configured: ''),
      'http://10.0.2.2:8000/api/v1/',
    );
  });
}
