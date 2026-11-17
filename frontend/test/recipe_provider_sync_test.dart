import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
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
        return RecipeSyncResult(syncedIds: recipes.map((r) => r.id).toList());
      },
    );
    await provider.load();

    await provider.addRecipe(
      const Recipe(
        id: '',
        name: 'Synced Dish',
        ingredients: [
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

  test(
      'Given the sync rejects the recipe, Then the provider keeps the error '
      'until a later sync stores it (FE-13)', () async {
    var reject = true;
    final provider = RecipeProvider(
      recipeSyncFn: (recipes) async => reject
          ? RecipeSyncResult(
              errors: [
                RecipeSyncError.parse(
                  "${recipes.single.id}: UNIT_NOT_CONVERTIBLE: Ingredient "
                  "'almonds' has no gram conversion for unit 'cup'",
                  sent: recipes,
                ),
              ],
            )
          : RecipeSyncResult(syncedIds: [for (final r in recipes) r.id]),
    );
    await provider.load();
    const recipe = Recipe(
      id: 'bad',
      name: 'Almond Bowl',
      ingredients: [
        RecipeIngredientEntry(
          ingredientId: 'a',
          ingredientName: 'almonds',
          quantity: 2,
          unit: 'cup',
        ),
      ],
    );

    final result = await provider.addRecipe(recipe);

    expect(result.errors, hasLength(1));
    expect(provider.recipeSyncErrors, hasLength(1));
    expect(provider.recipeSyncErrors.single.recipeName, 'Almond Bowl');
    expect(provider.recipeSyncErrors.single.code, 'UNIT_NOT_CONVERTIBLE');
    // Still saved on the device.
    expect(provider.recipes.map((r) => r.id), contains('bad'));

    reject = false;
    await provider.updateRecipe(recipe);
    expect(provider.recipeSyncErrors, isEmpty);
  });

  test('Given a rejected recipe is deleted, Then its error is dropped',
      () async {
    final provider = RecipeProvider(
      recipeSyncFn: (recipes) async => RecipeSyncResult(
        errors: [
          RecipeSyncError.parse(
            '${recipes.single.id}: INGREDIENT_UNRESOLVED: nope',
            sent: recipes,
          ),
        ],
      ),
    );
    await provider.load();
    await provider.addRecipe(const Recipe(id: 'gone', name: 'Gone'));
    expect(provider.recipeSyncErrors, hasLength(1));

    await provider.deleteRecipe('gone');

    expect(provider.recipeSyncErrors, isEmpty);
  });

  test('updateRecipe calls recipeSyncFn', () async {
    final syncedBatches = <List<Recipe>>[];
    final provider = RecipeProvider(
      recipeSyncFn: (recipes) async {
        syncedBatches.add(recipes);
        return RecipeSyncResult(syncedIds: recipes.map((r) => r.id).toList());
      },
    );
    await provider.load();

    const id = 'fixed-id';
    await provider.addRecipe(
      const Recipe(
        id: id,
        name: 'V1',
        ingredients: [
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
      const Recipe(
        id: id,
        name: 'V2',
        ingredients: [
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
