import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:muhasaba/features/auth/auth_client.dart';

const baseUrl = 'https://example.test/api/v1/';
const userJson = <String, dynamic>{
  'id': 'test-user',
  'email': 'person@example.com',
  'timezone': 'Africa/Cairo',
  'emailVerified': false,
};
const tokensJson = <String, dynamic>{
  'accessToken': 'test-access',
  'refreshToken': 'test-refresh',
  'user': userJson,
  'tokenType': 'bearer',
  'expiresIn': 900,
};

ResponseBody jsonResponse(Object? data, [int status = 200]) =>
    ResponseBody.fromString(
      jsonEncode(data),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );

class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);
  final FutureOr<ResponseBody> Function(RequestOptions) handler;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async => handler(options);
  @override
  void close({bool force = false}) {}
}

AuthClient makeClient(
  FutureOr<ResponseBody> Function(RequestOptions) handler, {
  TokenStore? store,
}) {
  final dio = Dio(BaseOptions(baseUrl: baseUrl, followRedirects: false));
  dio.httpClientAdapter = FakeAdapter(handler);
  return AuthClient(dio, store ?? TokenStore(const FlutterSecureStorage()));
}
