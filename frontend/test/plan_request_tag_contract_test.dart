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
