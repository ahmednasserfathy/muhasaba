import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/auth/auth_controller.dart';
import 'package:muhasaba/main.dart';

import 'auth_test_support.dart';

Future<void> pumpApp(WidgetTester tester, AuthClient client) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [authClientProvider.overrideWithValue(client)],
      child: const MuhasabaApp(),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('Arabic RTL login, authenticated account, and logout', (
    tester,
  ) async {
    final paths = <String>[];
    final client = makeClient((request) {
      paths.add(request.path);
      return request.path == 'auth/logout'
          ? jsonResponse(null, 204)
          : jsonResponse(tokensJson);
    });
    await pumpApp(tester, client);
    final context = tester.element(find.text('تسجيل الدخول'));
    expect(Localizations.localeOf(context), const Locale('ar'));
    expect(Directionality.of(context), TextDirection.rtl);
    await tester.enterText(
      find.byKey(const Key('email')),
      'person@example.com',
    );
    await tester.enterText(
      find.byKey(const Key('password')),
      'test-password-123',
    );
    await tester.tap(find.byKey(const Key('submit')));
    await tester.pumpAndSettle();
    expect(find.text('مرحبًا بك في محاسبة'), findsOneWidget);
    expect(find.text('person@example.com'), findsOneWidget);
    await tester.tap(find.text('تسجيل الخروج'));
    await tester.pumpAndSettle();
    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(paths, ['auth/login', 'auth/logout']);
    expect(await client.store.read(), isNull);
    expect(tester.takeException(), isNull);
  });

  testWidgets('registration validates password and submits timezone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(800, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    Map<String, dynamic>? sent;
    final client = makeClient((request) {
      expect(request.path, 'auth/register');
      sent = Map<String, dynamic>.from(request.data as Map);
      return jsonResponse(tokensJson, 201);
    });
    await pumpApp(tester, client);
    await tester.tap(find.text('مستخدم جديد؟ إنشاء حساب'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('email')),
      'person@example.com',
    );
    await tester.enterText(find.byKey(const Key('password')), 'short');
    await tester.tap(find.byKey(const Key('submit')));
    await tester.pumpAndSettle();
    expect(find.text('استخدم 12 حرفًا على الأقل'), findsOneWidget);
    expect(sent, isNull);
    await tester.enterText(
      find.byKey(const Key('password')),
      'test-password-123',
    );
    await tester.tap(find.byKey(const Key('submit')));
    await tester.pumpAndSettle();
    expect(sent!['timezone'], 'Africa/Cairo');
    expect(sent!.containsKey('role'), isFalse);
    expect(find.text('مرحبًا بك في محاسبة'), findsOneWidget);
  });

  testWidgets('failed login shows Arabic error and clears password field', (
    tester,
  ) async {
    await pumpApp(tester, makeClient((_) => jsonResponse({}, 401)));
    await tester.enterText(
      find.byKey(const Key('email')),
      'person@example.com',
    );
    await tester.enterText(find.byKey(const Key('password')), 'wrong-password');
    await tester.tap(find.byKey(const Key('submit')));
    await tester.pumpAndSettle();
    expect(
      find.text('بيانات الدخول غير صحيحة أو انتهت الجلسة.'),
      findsOneWidget,
    );
    expect(
      tester
          .widget<TextFormField>(find.byKey(const Key('password')))
          .controller!
          .text,
      isEmpty,
    );
  });

  testWidgets('startup network failure allows retry without erasing tokens', (
    tester,
  ) async {
    var offline = true;
    final client = makeClient((request) {
      if (offline) {
        throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        );
      }
      return jsonResponse(userJson);
    });
    await client.store.save(
      const SessionTokens('test-access', 'test-refresh', baseUrl),
    );
    await pumpApp(tester, client);
    expect(find.text('إعادة المحاولة'), findsOneWidget);
    expect(await client.store.read(), isNotNull);
    offline = false;
    await tester.tap(find.text('إعادة المحاولة'));
    await tester.pumpAndSettle();
    expect(find.text('مرحبًا بك في محاسبة'), findsOneWidget);
  });

  testWidgets('failed logout keeps account available for retry', (
    tester,
  ) async {
    final client = makeClient(
      (request) =>
          request.path == 'me' ? jsonResponse(userJson) : jsonResponse({}, 503),
    );
    await client.store.save(
      const SessionTokens('test-access', 'test-refresh', baseUrl),
    );
    await pumpApp(tester, client);
    await tester.tap(find.text('تسجيل الخروج'));
    await tester.pumpAndSettle();
    expect(find.text('person@example.com'), findsOneWidget);
    expect(find.text('تسجيل الخروج'), findsOneWidget);
    expect(await client.store.read(), isNotNull);
  });
}
