import 'dart:io';
import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';

import 'day_data.dart';

final journalDatabaseProvider = Provider<JournalDatabase>((ref) {
  final db = JournalDatabase.open();
  ref.onDispose(() => unawaited(db.close()));
  return db;
});

// SQL tables managed by Drift migrations/transactions. The complete
// day document includes the pinned catalog, counters and projected row versions.
class JournalDatabase extends GeneratedDatabase {
  JournalDatabase(super.executor);
  factory JournalDatabase.open() => JournalDatabase(
    LazyDatabase(() async {
      final directory = await getApplicationSupportDirectory();
      return NativeDatabase.createInBackground(
        File('${directory.path}/journal.sqlite'),
      );
    }),
  );

  @override
  int get schemaVersion => 4;
  final changes = StreamController<void>.broadcast();
  @override
  Future<void> close() async {
    await changes.close();
    await super.close();
  }

  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const [];
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => const [];
  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (_) async {
      await _createFasting();
      await _createReminders();
      await _createGroups();
      await customStatement(
        'CREATE TABLE local_days (owner TEXT NOT NULL, date TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(owner, date))',
      );
      await customStatement(
        'CREATE TABLE sync_outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, date TEXT NOT NULL, route TEXT NOT NULL, payload TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0)',
      );
      await customStatement(
        'CREATE INDEX outbox_owner ON sync_outbox(owner, sequence)',
      );
    },
    onUpgrade: (_, from, to) async {
      if (from < 2) await _createFasting();
      if (from < 3) await _createReminders();
      if (from < 4) await _createGroups();
    },
  );

  Future<void> _createGroups() => customStatement(
    'CREATE TABLE local_group_plans (owner TEXT NOT NULL, code TEXT NOT NULL, date TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(owner,code,date))',
  );
  Future<Map<String, dynamic>?> readGroup(
    String owner,
    String code,
    String date,
  ) async {
    final rows = await customSelect(
      'SELECT document FROM local_group_plans WHERE owner=? AND code=? AND date=?',
      variables: [Variable(owner), Variable(code), Variable(date)],
    ).get();
    return rows.isEmpty
        ? null
        : jsonDecode(rows.single.read<String>('document'))
              as Map<String, dynamic>;
  }

  Future<void> saveGroup(
    String owner,
    Map<String, dynamic> plan,
  ) => customStatement(
    'INSERT INTO local_group_plans(owner,code,date,document) VALUES(?,?,?,?) ON CONFLICT(owner,code,date) DO UPDATE SET document=excluded.document',
    [owner, plan['activityCode'], plan['date'], jsonEncode(plan)],
  );

  Future<void> _createReminders() async {
    await customStatement(
      'CREATE TABLE reminder_preferences (owner TEXT PRIMARY KEY, document TEXT NOT NULL)',
    );
    await customStatement(
      'CREATE TABLE reminder_slots (owner TEXT NOT NULL, id INTEGER NOT NULL, fire_at TEXT NOT NULL, PRIMARY KEY(owner,id))',
    );
  }

  Future<void> _createFasting() => customStatement(
    'CREATE TABLE local_fasting (owner TEXT NOT NULL, date TEXT NOT NULL, document TEXT NOT NULL, PRIMARY KEY(owner,date))',
  );
  Future<Map<String, dynamic>?> readFasting(String owner, String date) async {
    final rows = await customSelect(
      'SELECT document FROM local_fasting WHERE owner=? AND date=?',
      variables: [Variable(owner), Variable(date)],
    ).get();
    return rows.isEmpty
        ? null
        : jsonDecode(rows.single.read<String>('document'))
              as Map<String, dynamic>;
  }

  Future<void> saveFasting(String owner, Map<String, dynamic> plan) async {
    await customStatement(
      'INSERT INTO local_fasting(owner,date,document) VALUES(?,?,?) ON CONFLICT(owner,date) DO UPDATE SET document=excluded.document',
      [owner, plan['date'], jsonEncode(plan)],
    );
    final day = await readDay(owner, plan['date'] as String);
    if (day != null) {
      day.json['fasting'] = plan;
      day.recalculate();
      await saveDay(owner, day);
    }
  }

  Future<DayData?> readDay(String owner, String date) async {
    final rows = await customSelect(
      'SELECT document FROM local_days WHERE owner = ? AND date = ?',
      variables: [Variable(owner), Variable(date)],
    ).get();
    return rows.isEmpty
        ? null
        : DayData.decode(rows.single.read<String>('document'));
  }

  Future<void> saveDay(String owner, DayData day) => customStatement(
    'INSERT INTO local_days(owner,date,document) VALUES(?,?,?) ON CONFLICT(owner,date) DO UPDATE SET document=excluded.document',
    [owner, day.date, day.encode()],
  );
  Future<List<QueryRow>> pending(String owner, [String? date]) => customSelect(
    'SELECT * FROM sync_outbox WHERE owner = ?${date == null ? '' : ' AND date = ?'} ORDER BY sequence',
    variables: [Variable(owner), if (date != null) Variable(date)],
  ).get();
}
