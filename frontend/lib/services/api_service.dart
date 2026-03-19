import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/models.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000';

  static Future<MealPlan> generatePlan(PlanRequest profile) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/plan'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode(profile.toJson()),
    );

    if (res.statusCode == 200) {
      return MealPlan.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>,
      );
    }

    throw Exception(
      'Failed: ${res.statusCode}',
    );
  }

  static Future<List<RecipeSummary>> getRecipes() async {
    final res = await http.get(Uri.parse('$baseUrl/api/recipes'));

    if (res.statusCode == 200) {
      final decoded = jsonDecode(res.body) as List<dynamic>;
      return decoded
          .map((item) => RecipeSummary.fromJson(item as Map<String, dynamic>))
          .toList();
    }

    throw Exception(
      'Failed: ${res.statusCode}',
    );
  }
}
