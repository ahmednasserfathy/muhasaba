import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/daily/journal_database.dart';
import 'package:muhasaba/features/reminders/reminder_screen.dart';
import 'package:muhasaba/features/reminders/reminder_service.dart';
import 'package:timezone/timezone.dart' as tz;

import 'daily_widget_test.dart' show settleJournal;
import 'journal_test_support.dart';
import 'reminders_test.dart' show FakeNotifications;

void main() {
  testWidgets('Arabic opt-in chooses time and all-off cancels', (tester) async {
    final db = JournalDatabase(NativeDatabase.memory());
    final gateway = FakeNotifications();
    final service = ReminderService(
      db,
      'https://example.test/',
      gateway,
      clock: () =>
          tz.TZDateTime(tz.getLocation('Africa/Cairo'), 2026, 11, 19, 12),
    );
    await tester.runAsync(() async {
      await service.activate(journalAccount);
      await db.saveDay(service.owner!, sampleDay());
    });
    tester.view.physicalSize = const Size(800, 1400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [reminderServiceProvider.overrideWithValue(service)],
        child: const MaterialApp(
          locale: Locale('ar'),
          supportedLocales: [Locale('ar')],
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          home: ReminderScreen(),
        ),
      ),
    );
    await settleJournal(tester);
    expect(gateway.requests, 0);
    expect(
      Directionality.of(tester.element(find.text('التذكيرات الاختيارية'))),
      TextDirection.rtl,
    );
    await tester.tap(find.text('ملخص الأعمال المتبقية'));
    await tester.pumpAndSettle();
    // Confirm the time selected in the Material time picker.
    final context = tester.element(find.byType(TimePickerDialog));
    await tester.tap(
      find.text(MaterialLocalizations.of(context).okButtonLabel),
    );
    await settleJournal(tester);
    expect(gateway.requests, 1);
    expect(gateway.scheduled.length, 1);
    await tester.ensureVisible(find.text('إيقاف كل التذكيرات'));
    await tester.tap(find.text('إيقاف كل التذكيرات'));
    await settleJournal(tester);
    expect(gateway.scheduled, isEmpty);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
    service.dispose();
    await tester.runAsync(db.close);
  });
}
