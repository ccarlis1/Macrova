import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';

// Sprint 2 BE-21: recipe detail lines carry an additive `resolved` flag.
void main() {
  Map<String, dynamic> line([Map<String, dynamic> extra = const {}]) => {
        'ingredient_id': 'r:line:0',
        'ingredient_name': 'almonds',
        'quantity': 1,
        'unit': 'cup',
        ...extra,
      };

  test('resolved defaults to true when the server omits it', () {
    expect(RecipeIngredientEntry.fromJson(line()).resolved, isTrue);
  });

  test('resolved: false is read from the detail payload', () {
    final entry = RecipeIngredientEntry.fromJson(line({'resolved': false}));
    expect(entry.resolved, isFalse);
    expect(entry.caloriesPer100g, 0);
  });

  test('resolved survives toJson / fromJson and copyWith', () {
    final entry = RecipeIngredientEntry.fromJson(line({'resolved': false}));
    expect(RecipeIngredientEntry.fromJson(entry.toJson()).resolved, isFalse);
    expect(entry.copyWith(quantity: 2).resolved, isFalse);
  });
}
