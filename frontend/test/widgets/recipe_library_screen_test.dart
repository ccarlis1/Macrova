import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/recipe_library_screen.dart';
import 'package:macrova/widgets/empty_state.dart';
import 'package:macrova/widgets/advisory_card.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<RecipeBuilderCoordinator> pumpLibrary(
  WidgetTester tester, {
  RecipeProvider? provider,
}) async {
  final recipes = provider ?? RecipeProvider();
  final coordinator = RecipeBuilderCoordinator();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
        ChangeNotifierProvider<RecipeBuilderCoordinator>.value(
          value: coordinator,
        ),
      ],
      child: const MaterialApp(
        home: Scaffold(body: RecipeLibraryScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return coordinator;
}

void main() {
  group('RecipeLibraryScreen', () {
    testWidgets(
      'Given no recipes, When the library renders, Then the EmptyState '
      'offers the starter pack and building a recipe',
      (tester) async {
        await pumpLibrary(tester);

        expect(find.byType(EmptyState), findsNWidgets(2));
        expect(find.text('Start from the starter pack'), findsOneWidget);
        expect(find.text('Build a recipe'), findsOneWidget);
      },
    );

    testWidgets(
      'Given the empty state, When the add affordance is tapped, Then a '
      'pending create action is queued on the coordinator',
      (tester) async {
        final coordinator = await pumpLibrary(tester);

        await tester.tap(find.text('Build a recipe'));
        await tester.pump();

        expect(
          coordinator.takePendingAction(),
          isA<RecipeBuilderPendingCreate>(),
        );
      },
    );

    testWidgets(
      'Given a sync that rejected a recipe, When the library renders, Then an '
      'AdvisoryCard names the recipe and the reason (FE-13)',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        final recipes = RecipeProvider(
          recipeSyncFn: (batch) async => RecipeSyncResult(
            errors: [
              RecipeSyncError.parse(
                "${batch.single.id}: UNIT_NOT_CONVERTIBLE: Ingredient "
                "'almonds' has no gram conversion for unit 'cup'",
                sent: batch,
              ),
            ],
          ),
        );
        await recipes.load();
        await tester.runAsync(
          () => recipes.addRecipe(
            const Recipe(id: 'r-1', name: 'Almond Bowl'),
          ),
        );

        await pumpLibrary(tester, provider: recipes);

        final card = tester.widget<AdvisoryCard>(
          find.byKey(RecipeLibraryScreen.syncRejectionsKey),
        );
        expect(card.variant, AdvisoryVariant.warn);
        expect(card.title, 'A recipe was not saved to the server');
        expect(
          card.description,
          contains(
            "Almond Bowl: Ingredient 'almonds' has no gram conversion for "
            "unit 'cup'",
          ),
        );
      },
    );

    testWidgets(
      'Given no sync rejections, Then no rejection advisory is shown',
      (tester) async {
        await pumpLibrary(tester);

        expect(find.byKey(RecipeLibraryScreen.syncRejectionsKey), findsNothing);
      },
    );
  });
}
