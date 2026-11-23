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
import 'daily_widget_test.dart' show settleJournal;
import 'fasting_test.dart' show samplePlan;
import 'journal_test_support.dart';

void main() {
  testWidgets(
    'Arabic fasting panel adds a type and excludes without a reason',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      final db = JournalDatabase(NativeDatabase.memory());
      final auth = makeClient((_) => jsonResponse({}, 503));
      await auth.store.save(
        const SessionTokens('a', 'r', baseUrl, journalAccount),
      );
      final repo = JournalRepository(db, auth, journalAccount);
      await tester.runAsync(
        () => db.saveFasting(repo.owner, samplePlan(repo.today)),
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
      expect(find.textContaining('لا توجد تواريخ رمضان مؤكدة'), findsOneWidget);
      await tester.tap(find.text('أضف صيام اليوم'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('قضاء'));
      await settleJournal(tester);
      expect(find.text('خطة الصيام: صيام أضفته'), findsOneWidget);
      expect(find.text('النوع: قضاء'), findsOneWidget);
      await tester.tap(find.text('استثناء الصيام'));
      await settleJournal(tester);
      expect(find.text('خطة الصيام: مستثنى من النقاط'), findsOneWidget);
      await tester.tap(find.text('الجدول الافتراضي'));
      await settleJournal(tester);
      expect(find.text('خطة الصيام: غير مخطط'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.runAsync(() async {
        await repo.dispose();
        await db.close();
      });
    },
  );
}
