import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/ingredient_search.dart';
import '../models/models.dart';
import '../models/nutrition_summary.dart';
import '../models/recipe.dart';

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

  /// POST /api/v1/recipes/sync
  static Future<List<String>> syncRecipes(List<Recipe> recipes) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/recipes/sync'),
      headers: _jsonHeaders,
      body: jsonEncode({
        'recipes': recipes.map((r) => r.toSyncPayload()).toList(),
      }),
    );

    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body) as Map<String, dynamic>;
      final raw = decoded['synced_ids'];
      if (raw is! List) {
        throw const ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: 'Missing synced_ids in sync response',
        );
      }
      return raw.map((e) => e.toString()).toList();
    }

    throw ApiException.fromResponse(res);
  }

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

  /// GET /api/v1/recipes/{id}
  static Future<Recipe> getRecipe(String recipeId) async {
    final encoded = Uri.encodeComponent(recipeId);
    final res = await http.get(
      Uri.parse('$baseUrl/api/v1/recipes/$encoded'),
    );

    if (res.statusCode == 200) {
      return Recipe.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }

    throw ApiException.fromResponse(res);
  }

  /// GET /api/v1/ingredients/search
  static Future<IngredientSearchResponse> searchIngredients({
    required String q,
    int page = 1,
    int pageSize = 25,
    String dataTypes = 'all',
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/ingredients/search').replace(
      queryParameters: {
        'q': q,
        'page': '$page',
        'page_size': '$pageSize',
        'data_types': dataTypes,
      },
    );
    final res = await http.get(uri);

    if (res.statusCode == 200) {
      return IngredientSearchResponse.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }

    throw ApiException.fromResponse(res);
  }

  /// POST /api/v1/ingredients/resolve with [fdcId] only (USDA detail path).
  static Future<Map<String, dynamic>> resolveIngredientJson({
    required int fdcId,
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/ingredients/resolve'),
      headers: _jsonHeaders,
      body: jsonEncode({'fdc_id': fdcId}),
    );

    if (res.statusCode == 200) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }

    throw ApiException.fromResponse(res);
  }

  /// POST /api/v1/nutrition/summary
  static Future<NutritionSummary> nutritionSummary({
    required int servings,
    required List<Map<String, dynamic>> ingredientLines,
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/nutrition/summary'),
      headers: _jsonHeaders,
      body: jsonEncode({
        'servings': servings,
        'ingredients': ingredientLines,
      }),
    );

    if (res.statusCode == 200) {
      return NutritionSummary.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }

    throw ApiException.fromResponse(res);
  }

  /// Prefer [plan]; kept for call sites not yet migrated.
  static Future<MealPlan> generatePlan(PlanRequest profile) => plan(profile);

  /// Prefer [listRecipes]; kept for call sites not yet migrated.
  static Future<List<RecipeSummary>> getRecipes() => listRecipes();
}
