import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/ingredient_search.dart';
import '../models/meal_prep_batch.dart';
import '../models/models.dart';
import '../models/nutrition_summary.dart';
import '../models/profile_pin.dart';
import '../models/recipe.dart';
import '../models/recipe_sync_result.dart';
import '../models/tag.dart';

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
          var message = (err['message'] as String?)?.trim().isNotEmpty == true
              ? err['message'] as String
              : 'Request failed';
          final details = err['details'];
          if (details is Map<String, dynamic>) {
            final fe = details['field_errors'];
            if (fe is List && fe.isNotEmpty) {
              message = '$message: ${fe.map((e) => e.toString()).join('; ')}';
            }
            final reason = details['reason'];
            if (reason is String && reason.isNotEmpty) {
              final carbs = details['daily_carbs_g'];
              if (carbs is num) {
                message = '$message ($reason, daily_carbs_g=${carbs.toString()})';
              } else {
                message = '$message ($reason)';
              }
            }
          }
          return ApiException(
            statusCode: status,
            code: (err['code'] as String?)?.trim().isNotEmpty == true
                ? err['code'] as String
                : 'HTTP_ERROR',
            message: message,
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
  ///
  /// HTTP 200 can still reject items: each one is left out of
  /// [RecipeSyncResult.syncedIds] and reported in [RecipeSyncResult.errors]
  /// (BE-19). A whole-request failure throws [ApiException]. [client] is for
  /// tests.
  static Future<RecipeSyncResult> syncRecipes(
    List<Recipe> recipes, {
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/recipes/sync');
    final body = jsonEncode({
      'recipes': recipes.map((r) => r.toSyncPayload()).toList(),
    });
    final res = client == null
        ? await http.post(uri, headers: _jsonHeaders, body: body)
        : await client.post(uri, headers: _jsonHeaders, body: body);

    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body);
      if (decoded is! Map) {
        throw const ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: 'Sync response was not a JSON object',
        );
      }
      try {
        return RecipeSyncResult.fromJson(
          Map<String, dynamic>.from(decoded),
          sent: recipes,
        );
      } on FormatException catch (e) {
        throw ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: e.message,
        );
      }
    }

    throw ApiException.fromResponse(res);
  }

  /// GET /api/v1/llm/status — [enabled] matches server `load_llm_settings().enabled`.
  static Future<bool> fetchLlmServerEnabled() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/llm/status'));
    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body);
      if (decoded is Map<String, dynamic>) {
        return decoded['enabled'] == true;
      }
      throw const ApiException(
        statusCode: 200,
        code: 'INVALID_RESPONSE',
        message: 'LLM status response was not a JSON object',
      );
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
      final decoded = jsonDecode(res.body);
      if (decoded is! Map) {
        throw const ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: 'Plan response was not a JSON object',
        );
      }
      return MealPlan.fromPlanApiV1Response(
        Map<String, dynamic>.from(decoded),
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

  /// GET /api/v1/tags (optionally `?type=context|time|nutrition|constraint`).
  ///
  /// Returns every registry tag; callers offer only [TagMeta.isOfferable] ones.
  /// [client] is for tests.
  static Future<List<TagMeta>> listTags({
    String? type,
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/tags').replace(
      queryParameters: type == null ? null : {'type': type},
    );
    final res = client == null ? await http.get(uri) : await client.get(uri);

    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body);
      if (decoded is! Map) {
        throw const ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: 'Tag list response was not a JSON object',
        );
      }
      try {
        return TagMeta.listFromResponse(Map<String, dynamic>.from(decoded));
      } on FormatException catch (e) {
        throw ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: e.message,
        );
      }
    }

    throw ApiException.fromResponse(res);
  }

  /// GET /api/v1/meal_prep_batches (`?active=false` lists every batch).
  /// [client] is for tests.
  static Future<List<MealPrepBatch>> listMealPrepBatches({
    bool active = true,
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/meal_prep_batches').replace(
      queryParameters: {'active': '$active'},
    );
    final res = client == null ? await http.get(uri) : await client.get(uri);
    if (res.statusCode == 200) {
      return _parseOk(
        res,
        'Meal-prep list response',
        MealPrepBatch.listFromResponse,
      );
    }
    throw ApiException.fromResponse(res);
  }

  /// POST /api/v1/meal_prep_batches. [assignments] are 0-based
  /// `(day_index, slot_index)` plan slots. Structured errors throw
  /// [ApiException] with the server code: `RECIPE_NOT_FOUND` (404),
  /// `RECIPE_NOT_BATCHABLE` (422), `BATCH_CONFLICT` (409, a slot is taken by
  /// another active batch), `BATCH_INVALID` (400). [client] is for tests.
  static Future<MealPrepBatch> createMealPrepBatch({
    required String recipeId,
    required int totalServings,
    required String cookDate,
    required List<MealPrepAssignment> assignments,
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/meal_prep_batches');
    final body = jsonEncode({
      'recipe_id': recipeId,
      'total_servings': totalServings,
      'cook_date': cookDate,
      'assignments': [for (final a in assignments) a.toRequestJson()],
    });
    final res = client == null
        ? await http.post(uri, headers: _jsonHeaders, body: body)
        : await client.post(uri, headers: _jsonHeaders, body: body);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Meal-prep batch response', MealPrepBatch.fromJson);
    }
    throw ApiException.fromResponse(res);
  }

  /// DELETE /api/v1/meal_prep_batches/{id} (cancel). Returns the cancelled id;
  /// an unknown id throws [ApiException] `NOT_FOUND`. [client] is for tests.
  static Future<String> cancelMealPrepBatch(
    String batchId, {
    http.Client? client,
  }) async {
    final uri = Uri.parse(
      '$baseUrl/api/v1/meal_prep_batches/${Uri.encodeComponent(batchId)}',
    );
    final res =
        client == null ? await http.delete(uri) : await client.delete(uri);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Meal-prep cancel response', (json) {
        final id = json['cancelled_id'];
        if (id is! String) {
          throw const FormatException('cancel response has no cancelled_id');
        }
        return id;
      });
    }
    throw ApiException.fromResponse(res);
  }

  /// GET /api/v1/profile/pins. Pins live in the server's profile YAML; an
  /// absent file lists no pins. [client] is for tests.
  static Future<List<ProfilePin>> listPins({http.Client? client}) async {
    final uri = Uri.parse('$baseUrl/api/v1/profile/pins');
    final res = client == null ? await http.get(uri) : await client.get(uri);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Pin list response', ProfilePin.listFromResponse);
    }
    throw ApiException.fromResponse(res);
  }

  /// PUT /api/v1/profile/pins/{day_index}/{slot_index} with `{recipe_id}`.
  /// Indexes are the plan's 0-based slot coordinate. Upsert: re-pinning a slot
  /// replaces its recipe. An unknown recipe throws [ApiException]
  /// `RECIPE_NOT_FOUND` (404). [client] is for tests.
  static Future<ProfilePin> pin(
    int dayIndex,
    int slotIndex,
    String recipeId, {
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/profile/pins/$dayIndex/$slotIndex');
    final body = jsonEncode({'recipe_id': recipeId});
    final res = client == null
        ? await http.put(uri, headers: _jsonHeaders, body: body)
        : await client.put(uri, headers: _jsonHeaders, body: body);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Pin response', (json) {
        final pin = json['pin'];
        if (pin is! Map) throw const FormatException('pin response has no pin');
        return ProfilePin.fromJson(Map<String, dynamic>.from(pin));
      });
    }
    throw ApiException.fromResponse(res);
  }

  /// DELETE /api/v1/profile/pins/{day_index}/{slot_index}. Unpinning an
  /// empty slot is not an error (`deleted: false`). [client] is for tests.
  static Future<ProfilePinDeleteResult> unpin(
    int dayIndex,
    int slotIndex, {
    http.Client? client,
  }) async {
    final uri = Uri.parse('$baseUrl/api/v1/profile/pins/$dayIndex/$slotIndex');
    final res =
        client == null ? await http.delete(uri) : await client.delete(uri);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Unpin response', ProfilePinDeleteResult.fromJson);
    }
    throw ApiException.fromResponse(res);
  }

  /// DELETE /api/v1/profile/pins. Returns `cleared_count`. [client] is for
  /// tests.
  static Future<int> clearPins({http.Client? client}) async {
    final uri = Uri.parse('$baseUrl/api/v1/profile/pins');
    final res =
        client == null ? await http.delete(uri) : await client.delete(uri);
    if (res.statusCode == 200) {
      return _parseOk(res, 'Clear pins response', (json) {
        final n = json['cleared_count'];
        if (n is! num) {
          throw const FormatException('clear response has no cleared_count');
        }
        return n.toInt();
      });
    }
    throw ApiException.fromResponse(res);
  }

  /// Decodes a 200 JSON object with [parse]; a bad shape is `INVALID_RESPONSE`.
  static T _parseOk<T>(
    http.Response res,
    String what,
    T Function(Map<String, dynamic> json) parse,
  ) {
    final Object? decoded;
    try {
      decoded = jsonDecode(res.body);
    } on FormatException {
      throw ApiException(
        statusCode: 200,
        code: 'INVALID_RESPONSE',
        message: '$what was not JSON',
      );
    }
    if (decoded is! Map) {
      throw ApiException(
        statusCode: 200,
        code: 'INVALID_RESPONSE',
        message: '$what was not a JSON object',
      );
    }
    try {
      return parse(Map<String, dynamic>.from(decoded));
    } on FormatException catch (e) {
      throw ApiException(
        statusCode: 200,
        code: 'INVALID_RESPONSE',
        message: e.message,
      );
    }
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
