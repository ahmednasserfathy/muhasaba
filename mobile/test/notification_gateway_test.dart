import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:muhasaba/features/reminders/notification_gateway.dart';
import 'package:muhasaba/features/reminders/reminder_policy.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class AndroidGateway extends NotificationGateway {
  @override
  bool get supported => true;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'Android plugin bridge requests permission, schedules privately and cancels',
    () async {
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      AndroidFlutterLocalNotificationsPlugin.registerWith();
      addTearDown(() => debugDefaultTargetPlatformOverride = null);
      const channel = MethodChannel(
        'dexterous.com/flutter/local_notifications',
      );
      final calls = <MethodCall>[];
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            calls.add(call);
            if (call.method == 'getNotificationAppLaunchDetails') {
              return {'notificationLaunchedApp': false};
            }
            return true;
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );
      final gateway = AndroidGateway();
      await gateway.initialize((_) {});
      expect(
        calls.any((c) => c.method == 'requestNotificationsPermission'),
        false,
      );
      expect(await gateway.permission(request: true), true);
      tzdata.initializeTimeZones();
      await gateway.schedule(
        PlannedReminder(
          'INCOMPLETE_PROGRESS',
          tz.TZDateTime.now(
            tz.getLocation('Africa/Cairo'),
          ).add(const Duration(days: 1)),
          '2026-11-19',
        ),
        'opaque-test',
      );
      final args =
          calls.singleWhere((c) => c.method == 'zonedSchedule').arguments
              as Map;
      expect(args['payload'], 'opaque-test');
      expect(args['title'], 'محاسبة');
      expect(args['body'], isNot(contains('نقطة')));
      expect(args['matchDateTimeComponents'], isNull);
      final platform = args['platformSpecifics'] as Map;
      expect(platform['scheduleMode'], 'inexactAllowWhileIdle');
      expect(platform['playSound'], false);
      expect(platform['enableVibration'], false);
      await gateway.cancel(1);
      await gateway.cancelAll();
      expect(calls.any((c) => c.method == 'cancelAll'), true);
    },
  );
}
