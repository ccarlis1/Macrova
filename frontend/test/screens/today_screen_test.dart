import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/today_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/empty_state.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/stat_card.dart';
import 'package:macrova/widgets/sticky_cta.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _goals = {
  'daily_calories': 2000,
  'daily_protein_g': 150.0,
  'daily_fat_g_min': 50.0,
  'daily_fat_g_max': 70.0,
  'daily_carbs_g': 200.0,
};

MealPlan _day1Plan() {
  return MealPlan.fromPlanApiV1Response({
    'success': true,
    'days': 1,
    'daily_plans': [
      {
        'day': 1,
        'meals': [
          {
            'meal_type': 'Breakfast',
            'name': 'Oatmeal Bowl',
            'nutrition': {
              'calories': 400,
              'protein_g': 20,
              'fat_g': 10,
              'carbs_g': 55,
            },
            'busyness_level': 2,
            'ingredients': ['oats'],
          },
          {
            'meal_type': 'Lunch',
            'name': 'Chicken Salad',
            'nutrition': {
              'calories': 500,
              'protein_g': 40,
              'fat_g': 15,
              'carbs_g': 30,
            },
            'busyness_level': 2,
            'ingredients': ['chicken'],
          },
        ],
        'totals': {
          'calories': 900,
          'protein_g': 60,
          'fat_g': 25,
          'carbs_g': 85,
        },
      },
    ],
    'goals': _goals,
    'warnings': <String>[],
  });
}

Widget _wrap({
  required MealPlanProvider mealPlan,
  required ProfileProvider profile,
  required RecipeProvider recipes,
  required LlmConfigProvider llm,
}) {
  return MaterialApp(
    theme: AppTheme.light,
    home: MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<MealPlanProvider>.value(value: mealPlan),
        ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
        ChangeNotifierProvider<LlmConfigProvider>.value(value: llm),
      ],
      child: const Scaffold(body: TodayScreen()),
    ),
  );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TodayScreen', () {
    testWidgets(
      'Given no meal plan, When rendered, Then empty CTA and agent entry are shown',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final profile = ProfileProvider();
        await tester.pumpWidget(
          _wrap(
            mealPlan: MealPlanProvider(),
            profile: profile,
            recipes: RecipeProvider(),
            llm: LlmConfigProvider(profile),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('No meal plan yet. Generate one from the Planner.'),
            findsOneWidget);
        expect(find.byType(EmptyState), findsOneWidget);
        expect(find.text('Open Planner to generate a plan'), findsOneWidget);
        expect(find.text('Plan with words'), findsOneWidget);
        expect(find.text('Set up Agent'), findsOneWidget);
        expect(find.byType(StickyCta), findsOneWidget);
        expect(find.text('Open Planner'), findsWidgets);
      },
    );

    testWidgets(
      'Given a Day 1 plan, When rendered, Then banner stats and meals are shown',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final profile = ProfileProvider();
        final mealPlan = MealPlanProvider()..applyPlanResult(_day1Plan());

        await tester.pumpWidget(
          _wrap(
            mealPlan: mealPlan,
            profile: profile,
            recipes: RecipeProvider(),
            llm: LlmConfigProvider(profile),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Day 1 plan vs targets'), findsOneWidget);
        expect(find.byType(StatCard), findsNWidgets(4));
        expect(find.text('Day 1'), findsOneWidget);
        // First meal appears in Up next and Day 1 list.
        expect(find.text('Oatmeal Bowl'), findsWidgets);
        expect(find.text('Chicken Salad'), findsOneWidget);
        expect(find.byType(MealCard), findsWidgets);
        expect(find.text('Plan ready'), findsOneWidget);
        expect(find.text('Re-generate'), findsOneWidget);
        expect(find.text('Plan with words'), findsOneWidget);
      },
    );

    testWidgets(
      'Given library recipes, When rendered with a plan, Then library carousel is shown',
      (tester) async {
        tester.view.physicalSize = const Size(1000, 1600);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final profile = ProfileProvider();
        final recipes = RecipeProvider(recipeSyncFn: (_) async => []);
        await recipes.addRecipe(
          const Recipe(
            id: 'lib-1',
            name: 'Library Pasta',
            ingredients: [
              RecipeIngredientEntry(
                ingredientId: 'i1',
                ingredientName: 'pasta',
                quantity: 100,
                unit: 'g',
                caloriesPer100g: 350,
                proteinPer100g: 12,
                carbsPer100g: 70,
                fatPer100g: 2,
              ),
            ],
            servings: 1,
          ),
        );

        await tester.pumpWidget(
          _wrap(
            mealPlan: MealPlanProvider()..applyPlanResult(_day1Plan()),
            profile: profile,
            recipes: recipes,
            llm: LlmConfigProvider(profile),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('From your library'), findsOneWidget);
        expect(find.text('Library Pasta'), findsOneWidget);
      },
    );
  });
}
