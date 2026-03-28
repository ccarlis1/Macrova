import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';

void main() {
  test('availableUnits includes current unit when not in conversions', () {
    const line = RecipeIngredientEntry(
      ingredientId: '1',
      ingredientName: 'x',
      quantity: 1,
      unit: 'tbsp',
      unitConversions: {'cup': 236.588},
    );
    expect(line.availableUnits, containsAll(['g', 'cup', 'tbsp']));
  });

  test('availableUnits deduplicates g if also a conversion key', () {
    const line = RecipeIngredientEntry(
      ingredientId: '1',
      ingredientName: 'x',
      quantity: 1,
      unit: 'g',
      unitConversions: {'g': 1.0, 'oz': 28.35},
    );
    expect(line.availableUnits, ['g', 'oz']);
  });
}
