import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

/// Thrown when the API returns a non-success status with a parseable body.
class ApiException implements Exception {
  final int statusCode;
  final String code;
  final String message;

  const ApiException({
    required this.statusCode,
    required this.code,
    required this.message,
  });

  /// Parses `{"error":{"code","message"}}`, FastAPI `detail`, or falls back.
  factory ApiException.fromResponse(http.Response response) {
    final status = response.statusCode;
    final body = response.body;
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final err = decoded['error'];
        if (err is Map<String, dynamic>) {
          return ApiException(
            statusCode: status,
            code: (err['code'] as String?)?.trim().isNotEmpty == true
                ? err['code'] as String
                : 'HTTP_ERROR',
            message: (err['message'] as String?)?.trim().isNotEmpty == true
                ? err['message'] as String
                : 'Request failed',
          );
        }
        final detail = decoded['detail'];
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map<String, dynamic>) {
            final msg = first['msg'] as String?;
            if (msg != null && msg.isNotEmpty) {
              return ApiException(
                statusCode: status,
                code: 'VALIDATION_ERROR',
                message: msg,
              );
            }
          }
        }
      }
    } catch (_) {
      // Non-JSON or unexpected shape — use fallback below.
    }
    final fallback =
        body.isNotEmpty ? body : 'Request failed with status $status';
    return ApiException(
      statusCode: status,
      code: 'HTTP_ERROR',
      message: fallback,
    );
  }

  @override
  String toString() => 'ApiException($statusCode, $code): $message';
}

class ApiService {
  /// Compile-time override: `flutter run --dart-define=API_BASE_URL=https://host:port`
  static const String _baseUrlFromEnvironment = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );

  static const String _defaultBaseUrl = 'http://localhost:8000';

  static String get baseUrl =>
      _baseUrlFromEnvironment.isEmpty
          ? _defaultBaseUrl
          : _baseUrlFromEnvironment;

  static Map<String, String> get _jsonHeaders =>
      const {'Content-Type': 'application/json'};

  /// POST /api/v1/plan
  static Future<MealPlan> plan(PlanRequest body) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/plan'),
      headers: _jsonHeaders,
      body: jsonEncode(body.toJson()),
    );

    if (res.statusCode == 200) {
      return MealPlan.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }

    throw ApiException.fromResponse(res);
  }

  /// GET /api/v1/recipes
  static Future<List<RecipeSummary>> listRecipes() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/recipes'));

    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body) as List<dynamic>;
      return decoded
          .map((item) => RecipeSummary.fromJson(item as Map<String, dynamic>))
          .toList();
    }

    throw ApiException.fromResponse(res);
  }

  /// Prefer [plan]; kept for call sites not yet migrated.
  static Future<MealPlan> generatePlan(PlanRequest profile) => plan(profile);

  /// Prefer [listRecipes]; kept for call sites not yet migrated.
  static Future<List<RecipeSummary>> getRecipes() => listRecipes();
}
