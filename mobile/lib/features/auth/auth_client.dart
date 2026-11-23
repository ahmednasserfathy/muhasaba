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

  Map<String, dynamic> toJson() => {
    'id': id,
    'email': email,
    'timezone': timezone,
    'emailVerified': emailVerified,
  };

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
  const SessionTokens(this.access, this.refresh, this.baseUrl, [this.account]);
  final Account? account;
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
        json['account'] == null
            ? null
            : Account.fromJson(json['account'] as Map<String, dynamic>),
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
      if (tokens.account != null) 'account': tokens.account!.toJson(),
    }),
  );
  Future<void> clear() => storage.delete(key: key);
}

class AuthClient {
  AuthClient(this.dio, this.store);
  final Dio dio;
  final TokenStore store;
  int _sessionEpoch = 0;

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
      final account = Account.fromJson(response.data!);
      await store.save(
        SessionTokens(tokens.access, tokens.refresh, tokens.baseUrl, account),
      );
      return account;
    } on DioException catch (error) {
      if (error.response?.statusCode != 401) {
        if (_transient(error) && tokens.account != null) return tokens.account;
        throw _failure(error);
      }
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
      if (_transient(error) && tokens.account != null) return tokens.account;
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
      Account.fromJson(data['user'] as Map<String, dynamic>),
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

  Future<void>? _refreshing;
  bool _transient(DioException error) =>
      error.response == null || (error.response!.statusCode ?? 0) >= 500;

  Future<void> _refresh(SessionTokens old) async {
    final epoch = _sessionEpoch;
    try {
      final response = await dio.post<Map<String, dynamic>>(
        'auth/refresh',
        data: {'refreshToken': old.refresh},
      );
      if (epoch != _sessionEpoch) {
        try {
          await dio.post<void>(
            'auth/logout',
            data: {'refreshToken': response.data!['refreshToken']},
          );
        } catch (_) {}
        throw const AuthFailure('تغيّرت الجلسة. أعد تسجيل الدخول.');
      }
      await _save(response.data!);
    } on DioException catch (error) {
      if (error.response?.statusCode == 401) await store.clear();
      rethrow;
    }
  }

  Future<Map<String, dynamic>> authorized(
    String method,
    String path,
    String userId, {
    Object? data,
  }) async {
    Future<SessionTokens> checkedTokens() async {
      final tokens = await store.read();
      if (tokens == null ||
          tokens.baseUrl != dio.options.baseUrl ||
          tokens.account?.id != userId) {
        throw const AuthFailure(
          'سجّل الدخول مجددًا؛ التعديلات المحلية محفوظة.',
        );
      }
      return tokens;
    }

    var tokens = await checkedTokens();
    Future<Response<Map<String, dynamic>>> send() =>
        dio.request<Map<String, dynamic>>(
          path,
          data: data,
          options: Options(
            method: method,
            headers: {'Authorization': 'Bearer ${tokens.access}'},
          ),
        );
    try {
      return (await send()).data!;
    } on DioException catch (error) {
      if (error.response?.statusCode != 401) rethrow;
    }
    final latest = await checkedTokens();
    if (latest.access == tokens.access) {
      final refresh = _refreshing ??= _refresh(latest);
      try {
        await refresh;
      } finally {
        if (identical(_refreshing, refresh)) _refreshing = null;
      }
    }
    tokens = await checkedTokens();
    return (await send()).data!;
  }

  Future<void> logout() async {
    _sessionEpoch++;
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
