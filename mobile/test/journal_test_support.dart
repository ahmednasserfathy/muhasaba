import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:muhasaba/features/auth/auth_client.dart';
import 'package:muhasaba/features/daily/day_data.dart';

import 'auth_test_support.dart';

const journalAccount = Account(
  id: 'test-user',
  email: 'person@example.com',
  timezone: 'Africa/Cairo',
  emailVerified: false,
);

DayData sampleDay([String date = '2026-11-19']) {
  Map<String, dynamic> card(
    String code,
    String kind,
    List<Map<String, dynamic>> items,
  ) => {
    'code': code,
    'categoryCode': 'TEST',
    'categoryTitleAr': 'قسم اختبار',
    'titleAr': code == 'dhuhr' ? 'الظهر' : 'مجموعة اختبار',
    'kind': kind,
    'weight': 2,
    'state': 'PENDING',
    'status': 'PENDING',
    'rowVersion': 0,
    'eligible': true,
    'earnedPoints': 0,
    'possiblePoints': 2,
    'officialCompleted': 0,
    'officialTotal': items.length,
    'items': items,
  };
  final day = DayData({
    'date': date,
    'today': date,
    'trackingStartDate': '2026-01-01',
    'timezone': 'Africa/Cairo',
    'catalogRelease': 'test-release',
    'activities': [
      card('dhuhr', 'TOGGLE', []),
      card('set', 'ADHKAR_SET', [
        for (final code in ['one', 'two'])
          {
            'itemKey': 'official:set:$code',
            'code': code,
            'textAr': 'نَصٌّ لاختبار الواجهة فقط',
            'targetCount': 1,
            'completedCount': 0,
            'rowVersion': 0,
            'sourceType': 'OFFICIAL',
            'isScoreEligible': true,
            'sourceName': 'بيانات اختبار',
            'sourceUrl': 'https://example.test',
            'licenseNotes': 'اختبار فقط',
          },
      ]),
    ],
    'summary': {'earned': 0, 'possible': 4, 'percent': 0},
  });
  day.recalculate();
  return day;
}

class JournalServer {
  JournalServer(this.day);
  DayData day;
  bool offline = false;
  bool loseNextResponse = false;
  bool forceConflict = false;
  final receipts = <String, Map<String, dynamic>>{};
  final payloads = <Map<String, dynamic>>[];
  ResponseBody handle(RequestOptions request) {
    if (offline) {
      throw DioException(
        requestOptions: request,
        type: DioExceptionType.connectionError,
      );
    }
    if (request.method == 'GET') return jsonResponse(day.json);
    final payload = Map<String, dynamic>.from(request.data as Map);
    payloads.add(payload);
    final id = payload['clientMutationId'] as String;
    if (receipts.containsKey(id)) return jsonResponse(receipts[id]);
    if (forceConflict) {
      return jsonResponse({
        'detail': {'code': 'CONFLICT'},
      }, 409);
    }
    final path = Uri.decodeComponent(request.path);
    if (path.contains('/activities/')) {
      final card = day.card(path.split('/').last);
      if (card['rowVersion'] != payload['expectedVersion']) {
        return jsonResponse({}, 409);
      }
      card['state'] = payload['state'];
      card['rowVersion'] = (card['rowVersion'] as int) + 1;
    } else if (path.contains('/adhkar/')) {
      final item = day.cards
          .expand(DayData.items)
          .firstWhere((i) => i['itemKey'] == path.split('/').last);
      if (item['rowVersion'] != payload['expectedVersion']) {
        return jsonResponse({}, 409);
      }
      item['completedCount'] = payload['completedCount'];
      item['rowVersion'] = (item['rowVersion'] as int) + 1;
    } else {
      final items = DayData.items(day.card(path.split('/').last));
      for (final item in items) {
        if (item['rowVersion'] != payload['expectedVersions'][item['code']]) {
          return jsonResponse({}, 409);
        }
      }
      for (final item in items) {
        item['completedCount'] = payload['action'] == 'COMPLETE_ALL'
            ? item['targetCount']
            : 0;
        item['rowVersion'] = (item['rowVersion'] as int) + 1;
      }
    }
    day.recalculate();
    receipts[id] = jsonDecode(day.encode()) as Map<String, dynamic>;
    if (loseNextResponse) {
      loseNextResponse = false;
      throw DioException(
        requestOptions: request,
        type: DioExceptionType.receiveTimeout,
      );
    }
    return jsonResponse(day.json);
  }
}
