import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;
import 'package:uuid/uuid.dart';

import '../auth/auth_client.dart';
import 'day_data.dart';
import 'journal_database.dart';

class JournalRepository {
  JournalRepository(this.db, this.auth, this.account) {
    tzdata.initializeTimeZones();
  }
  final JournalDatabase db;
  final AuthClient auth;
  final Account account;
  String get owner => '${auth.dio.options.baseUrl}|${account.id}';
  final changes = StreamController<void>.broadcast();
  Future<void> _serial = Future.value();
  bool _syncing = false;
  int _revision = 0;
  bool _disposed = false;
  String? message;
  bool get syncing => _syncing;
  String get today => tz.TZDateTime.now(
    tz.getLocation(account.timezone),
  ).toIso8601String().split('T').first;

  // Serialize local edits and acknowledgements, never hold this across HTTP.
  Future<T> _local<T>(Future<T> Function() task) {
    final result = _serial.then((_) => task());
    _serial = result.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return result;
  }

  void _notify() {
    if (!_disposed) changes.add(null);
  }

  Future<void> dispose() async {
    _disposed = true;
    await changes.close();
  }

  Future<DayData?> read(String date) => db.readDay(owner, date);
  Future<Map<String, dynamic>?> readFasting(String date) =>
      db.readFasting(owner, date);
  Future<int> pendingCount() async => (await db.pending(owner)).length;
  Future<bool> blocked(String date) async =>
      (await db.pending(owner, date)).any((r) => r.read<int>('blocked') == 1);

  Future<void> load(String date) async {
    try {
      await sync();
      if (date.compareTo(today) > 0) {
        await loadFasting(date);
        return;
      }
      final revision = _revision;
      final response = await auth.authorized('GET', 'days/$date', account.id);
      if (_disposed) return;
      final day = DayData(response);
      await _local(
        () => db.transaction(() async {
          // A GET must never overwrite local changes queued during the request.
          if (revision == _revision &&
              (await db.pending(owner, date)).isEmpty) {
            await db.saveDay(owner, day);
            if (day.json['fasting'] != null) {
              await db.saveFasting(
                owner,
                day.json['fasting'] as Map<String, dynamic>,
              );
            }
          }
        }),
      );
      if ((await db.pending(owner)).isEmpty) message = null;
    } catch (error) {
      message = _error(error);
      if (error is DioException && error.response?.statusCode == 404) {
        await loadFasting(date);
      }
    }
    _notify();
  }

  Future<void> edit(
    String date,
    String kind,
    String key, {
    int? delta,
    String? state,
    String? action,
  }) async {
    await _local(
      () => db.transaction(() async {
        final day = await read(date);
        if (day == null) {
          throw const AuthFailure('اتصل بالخادم لتحميل هذا اليوم أولًا.');
        }
        if (date.compareTo(today) > 0 || date.compareTo(day.start) < 0) {
          throw const AuthFailure('التاريخ خارج فترة المتابعة.');
        }
        if (await blocked(date)) {
          throw const AuthFailure('راجع تعارض هذا اليوم أولًا.');
        }
        final payload = <String, dynamic>{
          'catalogRelease': day.release,
          'clientMutationId': const Uuid().v4(),
        };
        late String route;
        if (kind == 'state') {
          final card = day.card(key);
          final desired =
              state ?? (card['state'] == 'COMPLETED' ? 'PENDING' : 'COMPLETED');
          if (card['kind'] == 'ADHKAR_SET' && desired == 'COMPLETED') {
            throw StateError('Derived state');
          }
          if (card['kind'] == 'FASTING' &&
              !DayData.fastingEligible(
                day.json['fasting'] as Map<String, dynamic>?,
                date,
              ) &&
              desired == 'COMPLETED') {
            throw const AuthFailure('الصيام غير مخطط لهذا اليوم.');
          }
          payload.addAll({
            'state': desired,
            'expectedVersion': card['rowVersion'],
          });
          card['state'] = desired;
          card['rowVersion'] = (card['rowVersion'] as int) + 1;
          route = 'activities/${Uri.encodeComponent(key)}';
        } else if (kind == 'count') {
          final card = day.cards.firstWhere(
            (c) => DayData.items(c).any((i) => i['itemKey'] == key),
          );
          final item = DayData.items(
            card,
          ).firstWhere((i) => i['itemKey'] == key);
          final target = item['targetCount'] as int;
          final old = item['completedCount'] as int;
          final count = delta == null
              ? (old == 0 ? target : 0)
              : (old + delta).clamp(0, target);
          if (count == old) return;
          payload.addAll({
            'completedCount': count,
            'expectedVersion': item['rowVersion'],
          });
          item['completedCount'] = count;
          item['rowVersion'] = (item['rowVersion'] as int) + 1;
          route = 'adhkar/${Uri.encodeComponent(key)}';
        } else {
          final items = DayData.items(day.card(key));
          payload.addAll({
            'action': action,
            'expectedVersions': {
              for (final i in items) i['code'] as String: i['rowVersion'],
            },
          });
          for (final i in items) {
            i['completedCount'] = action == 'COMPLETE_ALL'
                ? i['targetCount']
                : 0;
            i['rowVersion'] = (i['rowVersion'] as int) + 1;
          }
          route = 'adhkar-sets/${Uri.encodeComponent(key)}';
        }
        day.recalculate();
        _revision++;
        await db.saveDay(owner, day);
        await db.customStatement(
          'INSERT INTO sync_outbox(owner,date,route,payload) VALUES(?,?,?,?)',
          [owner, date, 'days/$date/$route', jsonEncode(payload)],
        );
      }),
    );
    _notify();
    unawaited(sync());
  }

  Future<void> sync() async {
    if (_syncing || _disposed) return;
    _syncing = true;
    _notify();
    try {
      while (!_disposed) {
        final pending = await db.pending(owner);
        if (pending.isEmpty) {
          message = null;
          break;
        }
        final row = pending.first;
        if (row.read<int>('blocked') == 1) {
          message =
              'تعارض في يوم ${row.read<String>('date')}. تعديلاتك محفوظة؛ راجع نسخة الخادم.';
          break;
        }
        final sequence = row.read<int>('sequence');
        try {
          final response = await auth.authorized(
            'PUT',
            row.read<String>('route'),
            account.id,
            data: jsonDecode(row.read<String>('payload')),
          );
          if (_disposed) return;
          await _local(
            () => db.transaction(() async {
              _revision++;
              await db.customStatement(
                'DELETE FROM sync_outbox WHERE owner=? AND sequence=?',
                [owner, sequence],
              );
              if ((await db.pending(owner, row.read<String>('date'))).isEmpty) {
                if (row.read<String>('route').endsWith('/fasting-plan')) {
                  await db.saveFasting(owner, response);
                } else {
                  await db.saveDay(owner, DayData(response));
                  if (response['fasting'] != null) {
                    await db.saveFasting(
                      owner,
                      response['fasting'] as Map<String, dynamic>,
                    );
                  }
                }
              }
            }),
          );
          _notify();
        } on DioException catch (error) {
          if ([409, 422, 404].contains(error.response?.statusCode)) {
            await _local(
              () => db.customStatement(
                'UPDATE sync_outbox SET blocked=1 WHERE owner=? AND sequence=?',
                [owner, sequence],
              ),
            );
            message =
                'تعذر تطبيق تعديل يوم ${row.read<String>('date')}. تعديلاتك محفوظة؛ راجع نسخة الخادم.';
          } else {
            message = _error(error);
          }
          break;
        }
      }
    } catch (error) {
      message = _error(error);
    } finally {
      _syncing = false;
      _notify();
    }
  }

  Future<DayData> serverDay(String date) async =>
      DayData(await auth.authorized('GET', 'days/$date', account.id));

  // Explicit user choice after comparing local and remote. Clear only this date.
  Future<void> useServer(DayData day) async {
    final date = day.date;
    if (_syncing) throw const AuthFailure('انتظر انتهاء المزامنة.');
    await _local(
      () => db.transaction(() async {
        _revision++;
        await db.customStatement(
          'DELETE FROM sync_outbox WHERE owner=? AND date=?',
          [owner, date],
        );
        await db.saveDay(owner, day);
        if (day.json['fasting'] != null) {
          await db.saveFasting(
            owner,
            day.json['fasting'] as Map<String, dynamic>,
          );
        }
      }),
    );
    message = null;
    _notify();
    unawaited(sync());
  }

  Future<Map<String, dynamic>> serverFasting(String date) async {
    final response = await auth.authorized(
      'GET',
      'fasting/calendar?from=$date&to=$date',
      account.id,
    );
    return (response['days'] as List).single as Map<String, dynamic>;
  }

  Future<void> loadFasting(String date) async {
    final revision = _revision;
    try {
      final plan = await serverFasting(date);
      if (_disposed) return;
      await _local(
        () => db.transaction(() async {
          if (revision == _revision &&
              (await db.pending(owner, date)).isEmpty) {
            await db.saveFasting(owner, plan);
          }
        }),
      );
    } catch (error) {
      message = _error(error);
    }
    _notify();
  }

  Future<void> planFasting(String date, String mode, {String? fastType}) async {
    await _local(
      () => db.transaction(() async {
        final plan = await readFasting(date);
        if (plan == null) {
          throw const AuthFailure('حمّل تقويم هذا اليوم أولًا.');
        }
        if (await blocked(date)) {
          throw const AuthFailure('راجع تعارض اليوم أولًا.');
        }
        if (!['DEFAULT', 'ADD', 'SKIP'].contains(mode) ||
            (mode != 'ADD' && fastType != null)) {
          throw const AuthFailure('خطة صيام غير صالحة.');
        }
        final payload = {
          'clientMutationId': const Uuid().v4(),
          'expectedVersion': plan['rowVersion'],
          'mode': mode,
          'fastType': fastType,
        };
        plan['mode'] = mode;
        plan['fastType'] = fastType;
        plan['rowVersion'] = (plan['rowVersion'] as int) + 1;
        DayData.recalculatePlan(plan);
        _revision++;
        await db.saveFasting(owner, plan);
        await db.customStatement(
          'INSERT INTO sync_outbox(owner,date,route,payload) VALUES(?,?,?,?)',
          [owner, date, 'days/$date/fasting-plan', jsonEncode(payload)],
        );
      }),
    );
    _notify();
    unawaited(sync());
  }

  Future<void> useServerFasting(Map<String, dynamic> plan) async {
    if (_syncing) throw const AuthFailure('انتظر انتهاء المزامنة.');
    final date = plan['date'] as String;
    await _local(
      () => db.transaction(() async {
        final pending = await db.pending(owner, date);
        if (pending.any(
          (r) => !r.read<String>('route').endsWith('/fasting-plan'),
        )) {
          throw const AuthFailure('راجع سجل اليوم كاملًا لحفظ باقي التعديلات.');
        }
        _revision++;
        await db.customStatement(
          'DELETE FROM sync_outbox WHERE owner=? AND date=?',
          [owner, date],
        );
        await db.saveFasting(owner, plan);
      }),
    );
    message = null;
    _notify();
    unawaited(sync());
  }

  Future<int> restoreRange(String from, String to) async {
    validateReportRange(from, to);
    await sync();
    final before = <String, String?>{};
    for (final date in reportDates(from, to)) {
      before[date] = (await read(date))?.encode();
    }
    final revision = _revision;
    final response = await auth.authorized(
      'GET',
      'days?from=$from&to=$to',
      account.id,
    );
    if (_disposed) return 0;
    final restored = await _local(
      () => db.transaction(() async {
        if (revision != _revision) return 0;
        var count = 0;
        for (final value in response['days'] as List) {
          final day = DayData(value as Map<String, dynamic>);
          if (!before.containsKey(day.date) ||
              (await db.pending(owner, day.date)).isNotEmpty ||
              (await read(day.date))?.encode() != before[day.date]) {
            continue;
          }
          await db.saveDay(owner, day);
          count++;
          if (day.json['fasting'] != null) {
            await db.saveFasting(
              owner,
              day.json['fasting'] as Map<String, dynamic>,
            );
          }
        }
        return count;
      }),
    );
    _notify();
    return restored;
  }

  Future<Map<String, dynamic>> localReport(String from, String to) async {
    validateReportRange(from, to);
    final days = <Map<String, dynamic>>[];
    final missing = <String>[];
    var earned = Fraction(0);
    var possible = 0;
    for (final date in reportDates(from, to)) {
      if (date.compareTo(today) > 0 ||
          (account.trackingStartDate != null &&
              date.compareTo(account.trackingStartDate!) < 0)) {
        continue;
      }
      final day = await read(date);
      if (day == null) {
        missing.add(date);
        continue;
      }
      earned = earned + day.recalculate();
      possible += (day.json['summary'] as Map)['possible'] as int;
      days.add({
        'date': date,
        'summary': day.json['summary'],
        'fasting': day.json['fasting'],
      });
    }
    return {
      'days': days,
      'unavailableDates': missing,
      'local': true,
      'summary': {
        'earned': earned.decimal,
        'possible': possible,
        'percent': possible == 0
            ? null
            : earned.times(100).dividedBy(possible).rounded,
      },
    };
  }

  Future<Map<String, dynamic>> report(String from, String to) async {
    validateReportRange(from, to);
    await sync();
    final revision = _revision;
    if ((await db.pending(owner)).isNotEmpty) return localReport(from, to);
    try {
      final result = await auth.authorized(
        'GET',
        'reports/summary?from=$from&to=$to',
        account.id,
      );
      if (revision != _revision || (await db.pending(owner)).isNotEmpty) {
        return localReport(from, to);
      }
      return {...result, 'local': false};
    } catch (_) {
      return localReport(from, to);
    }
  }

  static void validateReportRange(String from, String to) {
    final length = DateTime.parse(
      '${to}T00:00:00Z',
    ).difference(DateTime.parse('${from}T00:00:00Z')).inDays;
    if (length < 0 || length >= 31) {
      throw const AuthFailure('اختر فترة من يوم إلى 31 يومًا.');
    }
  }

  static Iterable<String> reportDates(String from, String to) sync* {
    var date = DateTime.parse('${from}T00:00:00Z');
    final end = DateTime.parse('${to}T00:00:00Z');
    while (!date.isAfter(end)) {
      yield date.toIso8601String().split('T').first;
      date = date.add(const Duration(days: 1));
    }
  }

  String _error(Object error) {
    if (error is AuthFailure) return error.message;
    if (error is DioException) {
      if (error.response?.statusCode == 404) {
        return 'لم يُنشر محتوى معتمد لهذا اليوم بعد.';
      }
      if (error.response?.statusCode == 401) {
        return 'انتهت الجلسة. سجّل الدخول مجددًا؛ تعديلاتك المحلية محفوظة.';
      }
      if (error.response?.statusCode == 422) {
        return 'التاريخ خارج فترة المتابعة.';
      }
    }
    return 'تعذر الاتصال. التعديلات محفوظة على الجهاز وستُرسل عند المزامنة.';
  }
}
