import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/daily/journal_repository.dart';
import 'package:muhasaba/features/personal/group_plan_screen.dart';

import 'auth_test_support.dart';
import 'daily_widget_test.dart' show settleJournal;
import 'journal_test_support.dart';
import 'personal_test.dart' show samplePlan;

void main() {
  testWidgets(
    'Arabic customization adds private text hides default and queues tomorrow',
    (tester) async {
      FlutterSecureStorage.setMockInitialValues({});
      final db = JournalDatabase(NativeDatabase.memory());
      final auth = makeClient((_) => jsonResponse({}, 503));
      await auth.store.save(
        const SessionTokens('access', 'refresh', baseUrl, journalAccount),
      );
      final repo = JournalRepository(db, auth, journalAccount);
      await tester.runAsync(
        () => db.saveGroup(repo.owner, samplePlan(repo.tomorrow)),
      );
      tester.view.physicalSize = const Size(900, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('ar'),
          supportedLocales: const [Locale('ar')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: GroupPlanScreen(repository: repo, code: 'set'),
        ),
      );
      await settleJournal(tester);
      expect(find.text('الغد — ${repo.tomorrow}'), findsOneWidget);
      await tester.tap(find.byTooltip('إظهار أو إخفاء').first);
      await tester.tap(find.text('إضافة ذكر أو دعاء شخصي'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.widgetWithText(TextFormField, 'النص الشخصي'),
        'نص خاص للاختبار',
      );
      await tester.tap(find.text('إضافة للتخصيص'));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(milliseconds: 400));
      expect(find.text('نص خاص للاختبار'), findsOneWidget);
      await tester.tap(find.text('حفظ التخصيص'));
      await settleJournal(tester);
      await tester.runAsync(() async {
        final plan = (await repo.readGroup('set', repo.tomorrow))!;
        expect(plan['hiddenDefaultCodes'], ['one']);
        expect(
          (plan['customItems'] as List).single['textAr'],
          'نص خاص للاختبار',
        );
        expect(await repo.pendingCount(), 1);
      });
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.runAsync(() async {
        await repo.dispose();
        await db.close();
      });
    },
  );
}
