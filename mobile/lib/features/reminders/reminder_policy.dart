import 'package:timezone/timezone.dart' as tz;

import '../daily/day_data.dart';

const reminderLabels = {
  'MORNING_DHIKR': 'أذكار الصباح',
  'EVENING_DHIKR': 'أذكار المساء',
  'BEDTIME': 'قبل النوم',
  'DAILY_REVIEW': 'مراجعة اليوم',
  'FASTING_EVE': 'تذكير الصيام مساء اليوم السابق',
  'INCOMPLETE_PROGRESS': 'ملخص الأعمال المتبقية',
};
const reminderCards = {
  'MORNING_DHIKR': 'fajr_morning_dhikr',
  'EVENING_DHIKR': 'asr_evening_dhikr',
  'BEDTIME': 'dhikr_before_sleep',
};

class ReminderPreferences {
  ReminderPreferences({
    Map<String, int>? times,
    this.quietStart = 22 * 60,
    this.quietEnd = 7 * 60,
  }) : times = times ?? {};
  final Map<String, int> times;
  int quietStart;
  int quietEnd;
  factory ReminderPreferences.fromJson(Map<String, dynamic> value) =>
      ReminderPreferences(
        times: Map<String, int>.from(value['times'] as Map? ?? {}),
        quietStart: value['quietStart'] as int? ?? 1320,
        quietEnd: value['quietEnd'] as int? ?? 420,
      );
  Map<String, dynamic> toJson() => {
    'times': times,
    'quietStart': quietStart,
    'quietEnd': quietEnd,
  };
  bool quiet(int minute) => quietStart == quietEnd
      ? false
      : quietStart < quietEnd
      ? minute >= quietStart && minute < quietEnd
      : minute >= quietStart || minute < quietEnd;
  void validate() {
    if ([
          quietStart,
          quietEnd,
          ...times.values,
        ].any((v) => v < 0 || v >= 1440) ||
        times.keys.any((key) => !reminderLabels.containsKey(key))) {
      throw ArgumentError('Invalid reminder settings');
    }
  }
}

class PlannedReminder {
  const PlannedReminder(this.kind, this.when, this.date);
  final String kind;
  final tz.TZDateTime when;
  final String date;
  int get id =>
      int.parse(when.toIso8601String().split('T').first.replaceAll('-', '')) *
          10 +
      reminderLabels.keys.toList().indexOf(kind);
}

bool remainingCard(Map<String, dynamic> card) =>
    card['eligible'] == true &&
    card['status'] != 'COMPLETED' &&
    (card['possiblePoints'] as num) > 0;

List<PlannedReminder> planReminders({
  required ReminderPreferences preferences,
  required tz.TZDateTime now,
  DayData? day,
  Map<String, dynamic>? tomorrowFasting,
}) {
  preferences.validate();
  day?.recalculate();
  final today = now.toIso8601String().split('T').first;
  final tomorrow = tz.TZDateTime(
    now.location,
    now.year,
    now.month,
    now.day + 1,
  ).toIso8601String().split('T').first;
  final remaining = day?.date == today
      ? day!.cards.where(remainingCard).toList()
      : <Map<String, dynamic>>[];
  final result = <PlannedReminder>[];
  for (final entry in preferences.times.entries) {
    final kind = entry.key;
    final minute = entry.value;
    if (preferences.quiet(minute)) continue;
    final when = tz.TZDateTime(
      now.location,
      now.year,
      now.month,
      now.day,
      minute ~/ 60,
      minute % 60,
    );
    // A DST gap must not silently move a reminder into quiet hours or another time.
    if (!when.isAfter(now) || when.hour * 60 + when.minute != minute) continue;
    final relevant = kind == 'FASTING_EVE'
        ? (tomorrowFasting?['date'] == tomorrow &&
              tomorrowFasting?['eligible'] == true)
        : reminderCards.containsKey(kind)
        ? remaining.any((c) => c['code'] == reminderCards[kind])
        : remaining.isNotEmpty;
    if (relevant) {
      result.add(
        PlannedReminder(kind, when, kind == 'FASTING_EVE' ? tomorrow : today),
      );
    }
  }
  return result;
}
