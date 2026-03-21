import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('addRecipe calls recipeSyncFn with persisted recipe', () async {
    final syncedBatches = <List<Recipe>>[];
    final provider = RecipeProvider(
      recipeSyncFn: (recipes) async {
        syncedBatches.add(recipes);
        return recipes.map((r) => r.id).toList();
      },
    );
    await provider.load();

    await provider.addRecipe(
      Recipe(
        id: '',
        name: 'Synced Dish',
        ingredients: const [
          RecipeIngredientEntry(
            ingredientId: 'ing',
            ingredientName: 'rice',
            quantity: 100,
            unit: 'g',
          ),
        ],
        servings: 2,
      ),
    );

    expect(syncedBatches, hasLength(1));
    expect(syncedBatches.single.single.name, 'Synced Dish');
    expect(syncedBatches.single.single.id, isNotEmpty);
    expect(provider.recipes.map((r) => r.name), contains('Synced Dish'));
  });

  test('updateRecipe calls recipeSyncFn', () async {
    final syncedBatches = <List<Recipe>>[];
    final provider = RecipeProvider(
      recipeSyncFn: (recipes) async {
        syncedBatches.add(recipes);
        return recipes.map((r) => r.id).toList();
      },
    );
    await provider.load();

    const id = 'fixed-id';
    await provider.addRecipe(
      Recipe(
        id: id,
        name: 'V1',
        ingredients: const [
          RecipeIngredientEntry(
            ingredientId: 'ing',
            ingredientName: 'rice',
            quantity: 100,
            unit: 'g',
          ),
        ],
        servings: 1,
      ),
    );
    syncedBatches.clear();

    await provider.updateRecipe(
      Recipe(
        id: id,
        name: 'V2',
        ingredients: const [
          RecipeIngredientEntry(
            ingredientId: 'ing',
            ingredientName: 'rice',
            quantity: 200,
            unit: 'g',
          ),
        ],
        servings: 1,
      ),
    );

    expect(syncedBatches, hasLength(1));
    expect(syncedBatches.single.single.name, 'V2');
  });
}
