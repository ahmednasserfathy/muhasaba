import 'dart:convert';

// Exact arithmetic until the display boundary, matching Python Fraction.
class Fraction {
  Fraction(int n, [int d = 1]) : this.big(BigInt.from(n), BigInt.from(d));
  Fraction.big(BigInt n, BigInt d)
    : numerator = n ~/ n.gcd(d),
      denominator = d ~/ n.gcd(d);
  final BigInt numerator;
  final BigInt denominator;
  Fraction operator +(Fraction other) => Fraction.big(
    numerator * other.denominator + other.numerator * denominator,
    denominator * other.denominator,
  );
  Fraction times(int n) =>
      Fraction.big(numerator * BigInt.from(n), denominator);
  Fraction dividedBy(int n) =>
      Fraction.big(numerator, denominator * BigInt.from(n));
  double get decimal => numerator.toDouble() / denominator.toDouble();
  int get rounded =>
      ((numerator * BigInt.two + denominator) ~/ (denominator * BigInt.two))
          .toInt();
}

class DayData {
  DayData(this.json);
  final Map<String, dynamic> json;
  factory DayData.decode(String value) =>
      DayData(jsonDecode(value) as Map<String, dynamic>);
  String encode() => jsonEncode(json);
  String get date => json['date'] as String;
  String get release => json['catalogRelease'] as String;
  String get timezone => json['timezone'] as String;
  String get start => json['trackingStartDate'] as String;
  List<Map<String, dynamic>> get cards =>
      (json['activities'] as List).cast<Map<String, dynamic>>();
  Map<String, dynamic> card(String code) =>
      cards.firstWhere((c) => c['code'] == code);
  static List<Map<String, dynamic>> items(Map<String, dynamic> card) =>
      (card['items'] as List).cast<Map<String, dynamic>>();

  // Only called for a newly saved, not-yet-started group's effective day.
  void applyGroup(Map<String, dynamic> plan) {
    final group = card(plan['activityCode'] as String);
    final hidden = plan['hiddenDefaultCodes'] as List;
    final order = plan['officialOrder'] as List;
    final official = items(
      group,
    ).where((i) => i['sourceType'] == 'OFFICIAL').toList();
    for (var index = 0; index < official.length; index++) {
      final item = official[index];
      item['hidden'] = hidden.contains(item['code']);
      final rank = order.indexOf(item['code']);
      item['sortOrder'] = rank < 0 ? order.length + index : rank;
    }
    official.sort(
      (a, b) => (a['sortOrder'] as int).compareTo(b['sortOrder'] as int),
    );
    group['planVersion'] = plan['rowVersion'];
    group['items'] = <Map<String, dynamic>>[
      ...official,
      for (final item in plan['customItems'] as List)
        {
          'itemKey': 'personal:${item['id']}',
          'code': item['id'],
          'textAr': item['textAr'],
          'targetCount': item['targetCount'],
          'completedCount': 0,
          'rowVersion': 0,
          'sourceType': 'PERSONAL',
          'isScoreEligible': false,
          'hidden': false,
          'sourceName': '',
          'sourceUrl': '',
          'licenseNotes': '',
        },
    ];
    recalculate();
  }

  static bool fastingEligible(Map<String, dynamic>? plan, String date) {
    if (plan == null) return [1, 4].contains(DateTime.parse(date).weekday);
    if (plan['mode'] == 'SKIP') return false;
    if (plan['mode'] == 'ADD') return true;
    return ['RAMADAN', 'WEEKLY'].contains(plan['baseReason']);
  }

  static void recalculatePlan(Map<String, dynamic> plan) {
    plan['reason'] = plan['mode'] == 'SKIP'
        ? 'SKIP'
        : plan['mode'] == 'ADD'
        ? 'ADDED'
        : plan['baseReason'];
    plan['eligible'] = fastingEligible(plan, plan['date'] as String);
  }

  Fraction recalculate() {
    var earned = Fraction(0);
    var possible = 0;
    for (final card in cards) {
      final weight = card['weight'] as int;
      final fasting = card['kind'] == 'FASTING';

      final eligible =
          card['state'] != 'EXCLUDED' &&
          (!fasting ||
              fastingEligible(json['fasting'] as Map<String, dynamic>?, date));
      var fraction = Fraction(0);
      final official = items(card)
          .where(
            (i) =>
                i['sourceType'] == 'OFFICIAL' && i['isScoreEligible'] == true,
          )
          .toList();
      if (card['kind'] == 'ADHKAR_SET') {
        if (official.isEmpty) {
          throw StateError('Missing official scoring items');
        }
        for (final item in official) {
          final target = item['targetCount'] as int;
          fraction =
              fraction +
              Fraction(
                (item['completedCount'] as int).clamp(0, target),
                target,
              );
        }
        fraction = fraction.dividedBy(official.length);
      } else if (card['state'] == 'COMPLETED') {
        fraction = Fraction(1);
      }
      final points = eligible ? fraction.times(weight) : Fraction(0);
      earned = earned + points;
      possible += eligible ? weight : 0;
      card['eligible'] = eligible;
      card['earnedPoints'] = points.decimal;
      card['possiblePoints'] = eligible ? weight : 0;
      card['officialTotal'] = official.length;
      card['officialCompleted'] = official
          .where((i) => i['completedCount'] == i['targetCount'])
          .length;
      card['hiddenOfficialIncomplete'] = official
          .where(
            (i) =>
                i['hidden'] == true && i['completedCount'] != i['targetCount'],
          )
          .length;
      final personal = items(card).where((i) => i['sourceType'] == 'PERSONAL');
      card['personalTotal'] = personal.length;
      card['personalCompleted'] = personal
          .where((i) => i['completedCount'] == i['targetCount'])
          .length;
      card['status'] = !eligible
          ? 'EXCLUDED'
          : fraction.numerator == BigInt.zero
          ? 'PENDING'
          : fraction.numerator == fraction.denominator
          ? 'COMPLETED'
          : 'PARTIAL';
    }
    json['summary'] = {
      'earned': earned.decimal,
      'possible': possible,
      'percent': possible == 0
          ? null
          : earned.times(100).dividedBy(possible).rounded,
    };
    return earned;
  }
}
