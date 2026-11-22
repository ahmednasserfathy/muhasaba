import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/main.dart';

void main() {
  testWidgets('Home displays Arabic content in RTL', (tester) async {
    await tester.pumpWidget(const MuhasabaApp());
    await tester.pumpAndSettle();

    expect(find.text('محاسبة'), findsOneWidget);
    final greeting = find.text('مرحبًا بك في محاسبة');
    expect(greeting, findsOneWidget);
    final context = tester.element(greeting);
    expect(Localizations.localeOf(context), const Locale('ar'));
    expect(Directionality.of(context), TextDirection.rtl);
    expect(tester.takeException(), isNull);
  });
}
