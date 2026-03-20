import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../models/models.dart';
import '../../services/api_service.dart';
import 'agent_models.dart';

/// LLM / agent-only endpoints. Import only from agent UI and gated call sites.
class AgentApi {
  static Map<String, String> get _headers =>
      const {'Content-Type': 'application/json'};

  static Future<MealPlan> planFromText(Map<String, dynamic> body) async {
    final res = await http.post(
      Uri.parse('${ApiService.baseUrl}/api/v1/plan-from-text'),
      headers: _headers,
      body: jsonEncode(body),
    );
    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body);
      if (decoded is! Map) {
        throw const ApiException(
          statusCode: 200,
          code: 'INVALID_RESPONSE',
          message: 'Plan-from-text response was not a JSON object',
        );
      }
      return MealPlan.fromPlanApiV1Response(
        Map<String, dynamic>.from(decoded),
      );
    }
    throw ApiException.fromResponse(res);
  }

  static Future<IngredientMatchResult> matchIngredients(
    List<String> queries,
  ) async {
    final res = await http.post(
      Uri.parse('${ApiService.baseUrl}/api/v1/ingredients/match'),
      headers: _headers,
      body: jsonEncode({'queries': queries}),
    );
    if (res.statusCode == 200) {
      return IngredientMatchResult.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }
    throw ApiException.fromResponse(res);
  }

  static Future<RecipeGenerationResult> generateValidatedRecipes({
    required int count,
    required Map<String, dynamic> context,
  }) async {
    final res = await http.post(
      Uri.parse('${ApiService.baseUrl}/api/v1/recipes/generate-validated'),
      headers: _headers,
      body: jsonEncode({'count': count, 'context': context}),
    );
    if (res.statusCode == 200) {
      return RecipeGenerationResult.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }
    throw ApiException.fromResponse(res);
  }
}
