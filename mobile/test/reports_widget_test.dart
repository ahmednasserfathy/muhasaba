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
import 'package:muhasaba/features/reports/reports_screen.dart';

import 'auth_test_support.dart';
import 'daily_widget_test.dart' show settleJournal;
import 'journal_test_support.dart';

void main() {
  testWidgets('Arabic weekly/monthly report and explicit bounded restore', (
    tester,
  ) async {
    FlutterSecureStorage.setMockInitialValues({});
    final db = JournalDatabase(NativeDatabase.memory());
    var restores = 0;
    final auth = makeClient((request) {
      if (request.path.startsWith('days?')) {
        restores++;
        return jsonResponse({'days': []});
      }
      return jsonResponse({
        'days': [],
        'unavailableDates': ['2026-11-18'],
        'summary': {'earned': 2, 'possible': 13, 'percent': 15},
      });
    });
    await auth.store.save(
      const SessionTokens('a', 'r', baseUrl, journalAccount),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authClientProvider.overrideWithValue(auth),
          journalDatabaseProvider.overrideWithValue(db),
        ],
        child: const MaterialApp(
          locale: Locale('ar'),
          supportedLocales: [Locale('ar')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: ReportsScreen(account: journalAccount),
        ),
      ),
    );
    await settleJournal(tester);
    expect(
      Directionality.of(tester.element(find.text('التقارير'))),
      TextDirection.rtl,
    );
    expect(find.text('إنجاز الفترة: 15٪'), findsOneWidget);
    expect(find.textContaining('تقرير غير مكتمل'), findsOneWidget);
    await tester.tap(find.text('شهري'));
    await settleJournal(tester);
    await tester.tap(find.text('حفظ الفترة دون اتصال'));
    await settleJournal(tester);
    expect(restores, 1);
    expect(find.textContaining('حُفظت 0 أيام'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    await tester.runAsync(db.close);
  });
}
