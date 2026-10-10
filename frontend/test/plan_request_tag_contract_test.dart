import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';

void main() {
  test('Given tag fields, When PlanRequest serializes, Then backend keys match', () {
    const request = PlanRequest(
      dailyCalories: 2400,
      dailyProteinG: 150,
      dailyFatGMin: 50,
      dailyFatGMax: 100,
      schedule: {'07:00': 2},
      cuisine: ['mexican'],
      costLevel: 'cheap',
      prepTimeBucket: 'quick_meal',
      dietaryFlags: ['vegan'],
      recipeTagsPath: 'data/recipes/recipe_tags.json',
    );

    final json = request.toJson();

    expect(json['cuisine'], ['mexican']);
    expect(json['cost_level'], 'cheap');
    expect(json['prep_time_bucket'], 'quick_meal');
    expect(json['dietary_flags'], ['vegan']);
    expect(json['recipe_tags_path'], 'data/recipes/recipe_tags.json');
  });

  test('Given maxDailyCalories set, When PlanRequest serializes, Then max_daily_calories is included', () {
    const request = PlanRequest(
      dailyCalories: 2000,
      dailyProteinG: 130,
      dailyFatGMin: 50,
      dailyFatGMax: 70,
      schedule: {'07:00': 3},
      maxDailyCalories: 1700,
    );

    final json = request.toJson();

    expect(json['max_daily_calories'], 1700);
  });

  test('Given maxDailyCalories null, When PlanRequest serializes, Then max_daily_calories is omitted', () {
    const request = PlanRequest(
      dailyCalories: 2000,
      dailyProteinG: 130,
      dailyFatGMin: 50,
      dailyFatGMax: 70,
      schedule: {'07:00': 3},
    );

    final json = request.toJson();

    expect(json.containsKey('max_daily_calories'), isFalse);
  });

  test('Given openapi snapshot, When PlanRequest schema is checked, Then max_daily_calories is a property', () {
    final openapiFile = File('../openapi/openapi.json');
    expect(openapiFile.existsSync(), isTrue, reason: 'openapi/openapi.json missing');
    final schema = jsonDecode(openapiFile.readAsStringSync()) as Map<String, dynamic>;
    final components = schema['components'] as Map<String, dynamic>;
    final schemas = components['schemas'] as Map<String, dynamic>;
    final planRequest = schemas['PlanRequest'] as Map<String, dynamic>;
    final props = planRequest['properties'] as Map<String, dynamic>;
    expect(props.containsKey('max_daily_calories'), isTrue);
  });

  test('Given slot tag fields, When MealSlot serializes, Then backend keys match', () {
    const slot = MealSlot(
      index: 1,
      busynessLevel: 2,
      requiredTagSlugs: ['high-fiber'],
      preferredTagSlugs: ['high-protein'],
    );

    final json = slot.toJson();

    expect(json['required_tag_slugs'], ['high-fiber']);
    expect(json['preferred_tag_slugs'], ['high-protein']);
  });
}
