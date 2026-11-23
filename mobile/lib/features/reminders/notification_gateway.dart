import 'dart:io';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'reminder_policy.dart';

class NotificationGateway {
  final plugin = FlutterLocalNotificationsPlugin();
  bool get supported => Platform.isAndroid;
  Future<String?> initialize(void Function(String?) onTap) async {
    if (!supported) return null;
    await plugin.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('ic_reminder'),
      ),
      onDidReceiveNotificationResponse: (response) => onTap(response.payload),
    );
    final launch = await plugin.getNotificationAppLaunchDetails();
    return launch?.didNotificationLaunchApp == true
        ? launch?.notificationResponse?.payload
        : null;
  }

  Future<bool> permission({bool request = false}) async {
    if (!supported) return false;
    final android = plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()!;
    return (request
            ? await android.requestNotificationsPermission()
            : await android.areNotificationsEnabled()) ??
        false;
  }

  Future<void> cancelAll() async {
    if (supported) await plugin.cancelAll();
  }

  Future<void> cancel(int id) async {
    if (supported) await plugin.cancel(id: id);
  }

  Future<void> schedule(PlannedReminder reminder, String payload) async {
    if (!supported) return;
    await plugin.zonedSchedule(
      id: reminder.id,
      title: 'محاسبة',
      body: 'خطوة بسيطة على قدر استطاعتك. افتح التطبيق عندما يناسبك.',
      scheduledDate: reminder.when,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails(
          'gentle_reminders',
          'تذكيرات اختيارية',
          importance: Importance.defaultImportance,
          priority: Priority.defaultPriority,
          visibility: NotificationVisibility.secret,
          playSound: false,
          enableVibration: false,
        ),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      payload: payload,
    );
  }
}
