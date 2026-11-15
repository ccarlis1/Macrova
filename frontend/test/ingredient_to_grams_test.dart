import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/ingredient.dart';
import 'package:macrova/models/recipe.dart';

const _almonds = Ingredient(
  id: 'a',
  name: 'almonds',
  caloriesPer100g: 600,
  proteinPer100g: 20,
  unitConversions: {'tbsp': 9},
);

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
  group('Ingredient.toGrams (FE-13)', () {
    test('Given g, Then the quantity is grams', () {
      expect(_almonds.toGrams(50, 'g'), 50);
    });

    test('Given a unit with a conversion, Then it is scaled', () {
      expect(_almonds.toGrams(2, 'tbsp'), 18);
    });

    test('Given oz, Then the mass conversion is used', () {
      expect(_almonds.toGrams(2, 'oz'), closeTo(56.7, 1e-9));
    });

    test('Given to taste, Then it weighs nothing', () {
      expect(_almonds.toGrams(1, 'to taste'), 0);
    });

    test(
        'Given a unit with no conversion, Then UnknownUnitException is thrown '
        '(not the quantity as grams)', () {
      expect(
        () => _almonds.toGrams(2, 'cup'),
        throwsA(
          isA<UnknownUnitException>()
              .having((e) => e.unit, 'unit', 'cup')
              .having((e) => e.ingredientName, 'ingredientName', 'almonds'),
        ),
      );
    });

    test('Given a zero conversion, Then the unit is unknown', () {
      const ing = Ingredient(id: 'x', name: 'x', unitConversions: {'cup': 0});
      expect(() => ing.toGrams(1, 'cup'), throwsA(isA<UnknownUnitException>()));
    });
  });

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
