import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/planner_config_screen.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../widgets/widget_test_helpers.dart';

Future<void> _pumpScreen(
  WidgetTester tester, {
  ProfileProvider? profile,
  MealPlanProvider? mealPlan,
  RecipeProvider? recipes,
}) async {
  final p = profile ?? ProfileProvider();
  final mp = mealPlan ?? MealPlanProvider();
  final rp = recipes ?? RecipeProvider();

  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: p),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: LlmConfigProvider(p),
        ),
        ChangeNotifierProvider<RecipeProvider>.value(value: rp),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mp),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: PlannerConfigScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('PlannerConfigScreen', () {
    testWidgets(
      'Given the day-count selector, When a day chip is tapped, '
      'Then MealPlanProvider.days updates',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 2400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        expect(mealPlan.days, 7);

        await _pumpScreen(tester, mealPlan: mealPlan);

        // The first seven MacrovaChips are the day-count selector (1..7);
        // index 2 corresponds to day 3.
        await tester.tap(find.byType(MacrovaChip).at(2));
        await tester.pumpAndSettle();

        expect(mealPlan.days, 3);
      },
    );

    testWidgets(
      'Given a recipe in the pool, When its row is tapped, '
      'Then it becomes selected',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 2400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final mealPlan = MealPlanProvider();
        mealPlan.setDays(1);
        final recipes = RecipeProvider();
        await StorageService.saveRecipes([sampleRecipe]);
        await recipes.load();

        await _pumpScreen(tester, mealPlan: mealPlan, recipes: recipes);

        expect(find.text('Test Salad'), findsOneWidget);
        expect(mealPlan.selectedRecipeIds, isEmpty);
        expect(
          find.text('0 recipes selected from your library'),
          findsOneWidget,
        );

        await tester.tap(find.text('Test Salad'));
        await tester.pumpAndSettle();

        expect(mealPlan.selectedRecipeIds, contains('r1'));
        expect(
          find.text('1 recipes selected from your library'),
          findsOneWidget,
        );
      },
    );
  });
}
