import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/meal_prep_batch.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/meal_plan_view_screen.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/create_batch_sheet.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/meal_prep_tray.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'meal_prep_test_helpers.dart';

// FE-14: create-batch sheet (overflow guard, success refresh, conflict).

bool _selected(WidgetTester tester, Key key) =>
    tester.widget<MacrovaChip>(find.byKey(key)).selected;

bool _enabled(WidgetTester tester, Key key) =>
    tester.widget<MacrovaChip>(find.byKey(key)).onTap != null;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  void bigView(WidgetTester tester) {
    tester.view.physicalSize = const Size(1000, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  }

  /// Plan provider holding the 2-day plan from [planRequest].
  Future<MealPlanProvider> plannedProvider(FakeMealPrepServer server) async {
    final plan = server.provider();
    await plan.generatePlan(planRequest);
    server.planRequests.clear();
    return plan;
  }

  Future<void> openSheet(
    WidgetTester tester, {
    required MealPlanProvider plan,
    required RecipeProvider recipes,
  }) async {
    await tester.pumpWidget(
      wrapWithProviders(
        Builder(
          builder: (context) => TextButton(
            onPressed: () => CreateBatchSheet.show(
              context,
              today: DateTime(2026, 11, 14),
            ),
            child: const Text('open'),
          ),
        ),
        plan: plan,
        recipes: recipes,
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
  }

  Future<void> tapKey(WidgetTester tester, Key key) async {
    await tester.ensureVisible(find.byKey(key));
    await tester.tap(find.byKey(key));
    await tester.pumpAndSettle();
  }

  testWidgets(
      'Given recipes, Then only meal-prep capable ones are offered, the cook '
      'date defaults to today, and slots come from the current plan',
      (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer();
    await openSheet(
      tester,
      plan: await plannedProvider(server),
      recipes: await recipeProviderWith([capableRecipe, plainRecipe]),
    );

    expect(find.byKey(CreateBatchSheet.recipeKey(capableRecipe.id)),
        findsOneWidget);
    expect(find.byKey(CreateBatchSheet.recipeKey(plainRecipe.id)), findsNothing);
    expect(
      tester.widget<MacrovaChip>(find.byKey(CreateBatchSheet.cookDateKey)).label,
      '2026-11-14',
    );
    for (final (d, s) in [(0, 0), (0, 1), (1, 0), (1, 1)]) {
      expect(find.byKey(CreateBatchSheet.slotKey(d, s)), findsOneWidget);
    }
    expect(find.textContaining('fixed assignments, not preferences'),
        findsOneWidget);
  });

  testWidgets(
      'Given no capable recipe, Then the sheet says to mark one in the Recipe '
      'Builder', (tester) async {
    bigView(tester);
    await openSheet(
      tester,
      plan: await plannedProvider(FakeMealPrepServer()),
      recipes: await recipeProviderWith([plainRecipe]),
    );

    expect(find.byKey(CreateBatchSheet.noRecipesKey), findsOneWidget);
    expect(
      find.textContaining('Mark a recipe meal-prep capable in the Recipe Builder'),
      findsOneWidget,
    );
  });

  testWidgets(
      'Given 2 servings, When 2 slots are picked, Then no more can be picked '
      'until servings go up, servings cannot drop below the picked slots, and '
      'a second slot on the same day is blocked', (tester) async {
    bigView(tester);
    await openSheet(
      tester,
      plan: await plannedProvider(FakeMealPrepServer()),
      recipes: await recipeProviderWith([capableRecipe]),
    );

    await tapKey(tester, CreateBatchSheet.slotKey(0, 0));
    // Same day: blocked (the planner never repeats a recipe within a day).
    expect(_enabled(tester, CreateBatchSheet.slotKey(0, 1)), isFalse);

    await tapKey(tester, CreateBatchSheet.slotKey(1, 1));
    expect(_selected(tester, CreateBatchSheet.slotKey(1, 1)), isTrue);
    expect(find.byKey(CreateBatchSheet.slotsFullKey), findsOneWidget);
    expect(_enabled(tester, CreateBatchSheet.slotKey(1, 0)), isFalse);
    expect(find.text('2 of 2 servings assigned'), findsOneWidget);

    // The stepper can't go below the 2 picked slots (nor below 2).
    final dec = find.descendant(
      of: find.byKey(CreateBatchSheet.servingsKey),
      matching: find.byIcon(Icons.remove),
    );
    await tester.tap(dec);
    await tester.pumpAndSettle();
    expect(find.text('2 of 2 servings assigned'), findsOneWidget);

    // Unpicking frees a slot again.
    await tapKey(tester, CreateBatchSheet.slotKey(1, 1));
    expect(find.byKey(CreateBatchSheet.slotsFullKey), findsNothing);
    expect(_enabled(tester, CreateBatchSheet.slotKey(1, 0)), isTrue);
  });

  testWidgets(
      'Given a filled sheet on Meal Plan View, When submitted, Then it POSTs '
      'the 0-based slots, closes, refreshes the tray and re-runs the plan',
      (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer();
    final plan = await plannedProvider(server);
    final recipes = await recipeProviderWith([capableRecipe]);
    final profile = ProfileProvider();
    // Providers inside `home`, as on the real screen tests: the sheet's modal
    // route must still find them.
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: MultiProvider(
          providers: [
            ChangeNotifierProvider<ProfileProvider>.value(value: profile),
            ChangeNotifierProvider<LlmConfigProvider>.value(
              value: LlmConfigProvider(profile),
            ),
            ChangeNotifierProvider<MealPlanProvider>.value(value: plan),
            ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
          ],
          child: const Scaffold(body: MealPlanViewScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final listsBefore = server.listCalls;

    await tapKey(tester, MealPrepTray.emptyKey);
    await tapKey(tester, CreateBatchSheet.recipeKey(capableRecipe.id));
    await tester.tap(find.descendant(
      of: find.byKey(CreateBatchSheet.servingsKey),
      matching: find.byIcon(Icons.add),
    ));
    await tester.pumpAndSettle();
    await tapKey(tester, CreateBatchSheet.slotKey(1, 0));
    await tapKey(tester, CreateBatchSheet.slotKey(0, 0));
    await tester.tap(find.text('Create batch'));
    await tester.pumpAndSettle();

    expect(server.created.single['recipe_id'], capableRecipe.id);
    expect(server.created.single['total_servings'], 3);
    expect(server.created.single['assignments'], [
      {'day_index': 0, 'slot_index': 0, 'servings': 1.0},
      {'day_index': 1, 'slot_index': 0, 'servings': 1.0},
    ]);
    expect(find.byType(CreateBatchSheet), findsNothing);
    expect(server.listCalls, listsBefore + 1);
    expect(server.planRequests.single.toJson(), planRequest.toJson());
    expect(find.byKey(MealPrepTray.batchKey('b1')), findsOneWidget);
    expect(find.textContaining('The plan was re-run'), findsOneWidget);
    expect(plan.mealPrepBatches.single.recipeId, capableRecipe.id);
  });

  testWidgets(
      'Given BATCH_CONFLICT, When submitted, Then the sheet stays open with the '
      'server message', (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer()
      ..createError = const ApiException(
        statusCode: 409,
        code: 'BATCH_CONFLICT',
        message: 'Slot conflict at day_index=0, slot_index=0',
      );
    final plan = await plannedProvider(server);
    await openSheet(
      tester,
      plan: plan,
      recipes: await recipeProviderWith([capableRecipe]),
    );

    await tapKey(tester, CreateBatchSheet.recipeKey(capableRecipe.id));
    await tapKey(tester, CreateBatchSheet.slotKey(0, 0));
    await tester.tap(find.text('Create batch'));
    await tester.pumpAndSettle();

    expect(find.byType(CreateBatchSheet), findsOneWidget);
    expect(find.byKey(CreateBatchSheet.errorKey), findsOneWidget);
    expect(
      find.text('A slot is already taken by another batch (BATCH_CONFLICT)'),
      findsOneWidget,
    );
    expect(
      find.textContaining('Slot conflict at day_index=0, slot_index=0'),
      findsOneWidget,
    );
    expect(server.planRequests, isEmpty);
    expect(plan.mealPrepBatches, isEmpty);
  });

  testWidgets(
      'Given RECIPE_NOT_BATCHABLE, When submitted, Then the fix is shown',
      (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer()
      ..createError = const ApiException(
        statusCode: 422,
        code: 'RECIPE_NOT_BATCHABLE',
        message: "Recipe 'fe14-oat-bowl' is not meal-prep capable.",
      );
    await openSheet(
      tester,
      plan: await plannedProvider(server),
      recipes: await recipeProviderWith([capableRecipe]),
    );

    await tapKey(tester, CreateBatchSheet.recipeKey(capableRecipe.id));
    await tapKey(tester, CreateBatchSheet.slotKey(0, 0));
    await tester.tap(find.text('Create batch'));
    await tester.pumpAndSettle();

    expect(find.byType(CreateBatchSheet), findsOneWidget);
    expect(find.text("This recipe can't be batched (RECIPE_NOT_BATCHABLE)"),
        findsOneWidget);
    expect(find.textContaining('switch on "Meal-prep capable"'), findsOneWidget);
  });

  testWidgets(
      'Given the plan used a selected pool without the recipe, Then the sheet '
      'warns the slots would fail', (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer();
    final plan = server.provider();
    await plan.generatePlan(const PlanRequest(
      dailyCalories: 2000,
      dailyProteinG: 150,
      dailyFatGMin: 50,
      dailyFatGMax: 70,
      days: 2,
      recipeIds: ['other'],
    ));
    await openSheet(
      tester,
      plan: plan,
      recipes: await recipeProviderWith([capableRecipe]),
    );

    expect(find.byKey(CreateBatchSheet.poolWarningKey), findsNothing);
    await tapKey(tester, CreateBatchSheet.recipeKey(capableRecipe.id));
    expect(find.byKey(CreateBatchSheet.poolWarningKey), findsOneWidget);
  });

  testWidgets(
      'Given the re-run plan places the batch, Then Meal Plan View shows the '
      'batch card variant', (tester) async {
    bigView(tester);
    final server = FakeMealPrepServer();
    final plan = server.provider(
      planResult: () => MealPlan.fromPlanApiV1Response(
        fixtureJson('plan_with_meal_prep_batch.json'),
      ),
    );
    await plan.generatePlan(planRequest);
    final recipes = await recipeProviderWith([capableRecipe]);
    final profile = ProfileProvider();
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<ProfileProvider>.value(value: profile),
          ChangeNotifierProvider<LlmConfigProvider>.value(
            value: LlmConfigProvider(profile),
          ),
          ChangeNotifierProvider<MealPlanProvider>.value(value: plan),
          ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const Scaffold(body: MealPlanViewScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Captured plan: the (0,0) and (1,0) batch slots, one serving each.
    expect(find.byKey(MealCard.mealPrepBadgeKey), findsNWidgets(2));
    expect(find.byKey(MealCard.mealPrepServingsKey), findsNWidgets(2));
    expect(find.text('1 serving'), findsNWidgets(2));
    expect(isoDate(DateTime(2026, 1, 5)), '2026-01-05');
  });
}
