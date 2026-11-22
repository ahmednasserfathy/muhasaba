import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Account {
  const Account({
    required this.id,
    required this.email,
    required this.timezone,
    required this.emailVerified,
  });
  final String id;
  final String email;
  final String timezone;
  final bool emailVerified;

  factory Account.fromJson(Map<String, dynamic> json) => Account(
    id: json['id'] as String,
    email: json['email'] as String? ?? '',
    timezone: json['timezone'] as String,
    emailVerified: json['emailVerified'] as bool,
  );
}

class AuthFailure implements Exception {
  const AuthFailure(this.message);
  final String message;
}

class SessionTokens {
  const SessionTokens(this.access, this.refresh, this.baseUrl);
  final String access;
  final String refresh;
  final String baseUrl;
}

class TokenStore {
  TokenStore(this.storage);
  final FlutterSecureStorage storage;
  static const key = 'muhasaba.session.v1';

  Future<SessionTokens?> read() async {
    final value = await storage.read(key: key);
    if (value == null) return null;
    try {
      final json = jsonDecode(value) as Map<String, dynamic>;
      return SessionTokens(
        json['access'] as String,
        json['refresh'] as String,
        json['baseUrl'] as String,
      );
    } on FormatException {
      await clear();
      return null;
    } on TypeError {
      await clear();
      return null;
    }
  }

  Future<void> save(SessionTokens tokens) => storage.write(
    key: key,
    value: jsonEncode({
      'access': tokens.access,
      'refresh': tokens.refresh,
      'baseUrl': tokens.baseUrl,
    }),
  );
  Future<void> clear() => storage.delete(key: key);
}

class AuthClient {
  AuthClient(this.dio, this.store);
  final Dio dio;
  final TokenStore store;

  Future<Account?> restore() async {
    final tokens = await store.read();
    if (tokens == null) return null;
    if (tokens.baseUrl != dio.options.baseUrl) {
      await store.clear();
      return null;
    }
    try {
      final response = await dio.get<Map<String, dynamic>>(
        'me',
        options: Options(headers: {'Authorization': 'Bearer ${tokens.access}'}),
      );
      return Account.fromJson(response.data!);
    } on DioException catch (error) {
      if (error.response?.statusCode != 401) throw _failure(error);
    }
    try {
      final response = await dio.post<Map<String, dynamic>>(
        'auth/refresh',
        data: {'refreshToken': tokens.refresh},
      );
      return await _save(response.data!);
    } on DioException catch (error) {
      if (error.response?.statusCode == 401) {
        await store.clear();
        return null;
      }
      // Do not erase a recoverable session on a transport error or server outage.
      throw _failure(error);
    }
  }

  Future<Account> authenticate({
    required String email,
    required String password,
    required bool register,
    String timezone = 'Africa/Cairo',
    String? trackingStartDate,
  }) async {
    try {
      final response = await dio.post<Map<String, dynamic>>(
        register ? 'auth/register' : 'auth/login',
        data: {
          'email': email.trim(),
          'password': password,
          if (register) 'timezone': timezone.trim(),
          if (register && trackingStartDate != null)
            'trackingStartDate': trackingStartDate,
        },
      );
      return await _save(response.data!);
    } on DioException catch (error) {
      throw _failure(error);
    }
  }

  Future<Account> _save(Map<String, dynamic> data) async {
    final tokens = SessionTokens(
      data['accessToken'] as String,
      data['refreshToken'] as String,
      dio.options.baseUrl,
    );
    final user = Account.fromJson(data['user'] as Map<String, dynamic>);
    try {
      // One encrypted value avoids mismatched access/refresh pairs after restart.
      await store.save(tokens);
    } catch (_) {
      try {
        await dio.post<void>(
          'auth/logout',
          data: {'refreshToken': tokens.refresh},
        );
      } catch (_) {
        // Best effort revocation; no tokens or raw exception details are logged.
      }
      throw const AuthFailure('تعذر حفظ الجلسة بأمان. حاول مرة أخرى.');
    }
    return user;
  }

  Future<void> logout() async {
    final tokens = await store.read();
    if (tokens != null && tokens.baseUrl == dio.options.baseUrl) {
      try {
        await dio.post<void>(
          'auth/logout',
          data: {'refreshToken': tokens.refresh},
        );
      } on DioException catch (error) {
        throw _failure(error);
      }
    }
    await store.clear();
  }

  AuthFailure _failure(DioException error) =>
      AuthFailure(switch (error.response?.statusCode) {
        401 => 'بيانات الدخول غير صحيحة أو انتهت الجلسة.',
        409 => 'تعذر إنشاء الحساب بهذه البيانات. جرّب تسجيل الدخول.',
        422 => 'راجع البريد وكلمة المرور والمنطقة الزمنية وتاريخ البداية.',
        429 => 'محاولات كثيرة. انتظر قليلًا ثم حاول مرة أخرى.',
        _ => 'تعذر الاتصال بالخادم. تحقق من الاتصال وحاول مرة أخرى.',
      });
}
