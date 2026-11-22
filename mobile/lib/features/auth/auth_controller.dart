import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'auth_client.dart';

String apiBaseUrl({required bool release, required String configured}) {
  final value = configured.isEmpty && !release
      ? 'http://10.0.2.2:8000/api/v1/'
      : configured;
  final uri = Uri.tryParse(value);
  if (uri == null ||
      !uri.hasAuthority ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      (release
          ? uri.scheme != 'https'
          : !['http', 'https'].contains(uri.scheme))) {
    throw const AuthFailure('إعداد الاتصال غير مكتمل.');
  }
  return value.endsWith('/') ? value : '$value/';
}

final authClientProvider = Provider<AuthClient>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: apiBaseUrl(
        release: kReleaseMode,
        configured: const String.fromEnvironment('API_BASE_URL'),
      ),
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
      sendTimeout: const Duration(seconds: 10),
      followRedirects: false,
    ),
  );
  ref.onDispose(() => dio.close());
  return AuthClient(
    dio,
    TokenStore(
      const FlutterSecureStorage(aOptions: AndroidOptions(resetOnError: false)),
    ),
  );
});

class AuthState {
  const AuthState({
    this.account,
    this.busy = false,
    this.error,
    this.restoreFailed = false,
  });
  final Account? account;
  final bool busy;
  final String? error;
  final bool restoreFailed;
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(
  AuthController.new,
);

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    unawaited(Future<void>.microtask(restore));
    return const AuthState(busy: true);
  }

  Future<void> restore() async {
    if (!ref.mounted) return;
    state = const AuthState(busy: true);
    try {
      final account = await ref.read(authClientProvider).restore();
      if (ref.mounted) state = AuthState(account: account);
    } catch (error) {
      if (ref.mounted) {
        state = AuthState(error: _message(error), restoreFailed: true);
      }
    }
  }

  Future<void> authenticate({
    required String email,
    required String password,
    required bool register,
    String timezone = 'Africa/Cairo',
    String? trackingStartDate,
  }) async {
    if (state.busy) return;
    state = const AuthState(busy: true);
    try {
      final account = await ref
          .read(authClientProvider)
          .authenticate(
            email: email,
            password: password,
            register: register,
            timezone: timezone,
            trackingStartDate: trackingStartDate,
          );
      if (ref.mounted) state = AuthState(account: account);
    } catch (error) {
      if (ref.mounted) state = AuthState(error: _message(error));
    }
  }

  Future<void> logout() async {
    if (state.busy) return;
    final account = state.account;
    state = AuthState(account: account, busy: true);
    try {
      await ref.read(authClientProvider).logout();
      if (ref.mounted) state = const AuthState();
    } catch (error) {
      if (ref.mounted) {
        state = AuthState(account: account, error: _message(error));
      }
    }
  }

  String _message(Object error) => error is AuthFailure
      ? error.message
      : 'تعذر الوصول إلى بيانات الدخول بأمان. حاول مرة أخرى.';
}
