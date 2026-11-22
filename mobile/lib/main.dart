import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  runApp(const MuhasabaApp());
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
      home: Scaffold(
        appBar: AppBar(title: const Text('محاسبة')),
        body: const SafeArea(child: Center(child: Text('مرحبًا بك في محاسبة'))),
      ),
    );
  }
}
