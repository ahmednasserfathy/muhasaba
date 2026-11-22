import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'features/auth/auth_screen.dart';

void main() {
  runApp(const ProviderScope(child: MuhasabaApp()));
}

class MuhasabaApp extends StatelessWidget {
  const MuhasabaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'محاسبة',
      locale: const Locale('ar'),
      supportedLocales: const [Locale('ar')],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      theme: ThemeData(colorSchemeSeed: Colors.teal),
      home: const AuthScreen(),
    );
  }
}
