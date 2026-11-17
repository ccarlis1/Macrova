import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/ingredient.dart';
import 'package:macrova/models/recipe.dart';

RecipeIngredientEntry _line(String unit, {double quantity = 2}) =>
    RecipeIngredientEntry(
      ingredientId: 'a',
      ingredientName: 'almonds',
      quantity: quantity,
      unit: unit,
      caloriesPer100g: 600,
      proteinPer100g: 20,
      unitConversions: const {'tbsp': 9},
    );

void main() {
  group('RecipeIngredientEntry strict grams (FE-13)', () {
    test('Given a unit with no conversion, Then nutrition getters throw', () {
      final line = _line('cup');
      expect(line.hasGramWeight, isFalse);
      expect(() => line.calories, throwsA(isA<UnknownUnitException>()));
      expect(
        () => line.scaledMicronutrients,
        throwsA(isA<UnknownUnitException>()),
      );
    });

    test('Given a known unit, Then nutrition uses its grams', () {
      final line = _line('tbsp');
      expect(line.hasGramWeight, isTrue);
      expect(line.calories, closeTo(108, 1e-9)); // 18 g × 6 kcal/g
    });

    test(
        'Given a recipe with an unconvertible line, Then totals leave it out '
        'and it is listed as unresolved', () {
      final recipe = Recipe(
        id: 'r',
        name: 'Mix',
        ingredients: [_line('g', quantity: 100), _line('cup')],
      );
      expect(recipe.totalCalories, closeTo(600, 1e-9));
      expect(recipe.totalProteinG, closeTo(20, 1e-9));
      expect(recipe.linesWithoutGramWeight.single.unit, 'cup');
    });
  });

  group('RecipeIngredientEntry.toApiLine', () {
    test('Given a converted unit, Then grams_per_unit is sent', () {
      expect(_line('tbsp').toApiLine(), {
        'name': 'almonds',
        'quantity': 2.0,
        'unit': 'tbsp',
        'grams_per_unit': 9.0,
      });
    });

    test('Given g or an unconverted unit, Then grams_per_unit is omitted', () {
      expect(_line('g').toApiLine().containsKey('grams_per_unit'), isFalse);
      expect(_line('cup').toApiLine().containsKey('grams_per_unit'), isFalse);
    });
  });
}
