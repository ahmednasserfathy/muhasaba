import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/auth/auth_controller.dart';
import 'package:muhasaba/features/daily/daily_screen.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';

import 'auth_test_support.dart';
import 'journal_test_support.dart';

Future<void> settleJournal(WidgetTester tester) async {
  for (var i = 0; i < 12; i++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 15)),
    );
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets(
    'Arabic journal toggles, details and counter undo persist offline',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      final db = JournalDatabase(NativeDatabase.memory());
      final auth = makeClient((_) => jsonResponse({}, 503));
      await auth.store.save(
        const SessionTokens('access', 'refresh', baseUrl, journalAccount),
      );
      final repo = JournalRepository(db, auth, journalAccount);
      await tester.runAsync(
        () => db.saveDay(repo.owner, sampleDay(repo.today)),
      );
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authClientProvider.overrideWithValue(auth),
            journalDatabaseProvider.overrideWithValue(db),
          ],
          child: MaterialApp(
            locale: const Locale('ar'),
            supportedLocales: const [Locale('ar')],
            localizationsDelegates: GlobalMaterialLocalizations.delegates,
            home: const DailyScreen(account: journalAccount),
          ),
        ),
      );
      await settleJournal(tester);
      expect(
        Directionality.of(tester.element(find.text('المحاسبة اليوم'))),
        TextDirection.rtl,
      );
      await tester.tap(find.byKey(const Key('card-dhuhr')));
      await settleJournal(tester);
      expect(find.text('إنجاز الأعمال الأساسية: 50٪'), findsOneWidget);
      await tester.tap(find.byKey(const Key('card-dhuhr')));
      await settleJournal(tester);
      expect(find.text('إنجاز الأعمال الأساسية: 0٪'), findsOneWidget);
      await tester.tap(find.byTooltip('تفاصيل الأذكار'));
      await settleJournal(tester);
      await tester.tap(find.byKey(const Key('plus-one')));
      await settleJournal(tester);
      expect(find.text('1/1'), findsOneWidget);
      expect(find.text('1.0 / 2 نقطة — 1/2 مكتمل'), findsOneWidget);
      await tester.tap(find.byKey(const Key('minus-one')));
      await settleJournal(tester);
      expect(find.text('0.0 / 2 نقطة — 0/2 مكتمل'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.tap(find.byTooltip('إغلاق'));
      await settleJournal(tester);
      await tester.pumpWidget(const SizedBox());
      await tester.runAsync(() async {
        await repo.dispose();
        await db.close();
      });
    },
  );
}
