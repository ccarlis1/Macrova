import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';

void main() {
  test('takePendingAction clears without notifying', () {
    final c = RecipeBuilderCoordinator();
    var notifies = 0;
    c.addListener(() => notifies++);

    expect(c.takePendingAction(), isNull);

    c.openForEdit(
      const Recipe(
        id: 'a',
        name: 'N',
        ingredients: [
          RecipeIngredientEntry(
            ingredientId: 'i',
            ingredientName: 'x',
            quantity: 1,
            unit: 'g',
          ),
        ],
        servings: 1,
      ),
    );
    expect(notifies, 1);

    final p = c.takePendingAction();
    expect(p, isA<RecipeBuilderPendingEdit>());
    expect(c.takePendingAction(), isNull);
    expect(notifies, 1);
  });

  test('startCreate yields RecipeBuilderPendingCreate', () {
    final c = RecipeBuilderCoordinator();
    c.startCreate();
    final p = c.takePendingAction();
    expect(p, isA<RecipeBuilderPendingCreate>());
  });
}
