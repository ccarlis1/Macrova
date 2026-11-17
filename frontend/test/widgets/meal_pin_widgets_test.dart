import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/profile_pin.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/meal_detail_sheet.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../pin_test_helpers.dart';
import 'widget_test_helpers.dart';

// FE-15: pin badge on MealCard and the Pin/Unpin action in MealDetailSheet.

MealCard _card(Meal m, {bool hasPin = false}) => MealCard(
      mealType: m.mealType,
      recipeName: m.recipe['name'] as String,
      calories: m.nutrition.calories,
      proteinG: m.nutrition.proteinG,
      carbsG: m.nutrition.carbsG,
      fatG: m.nutrition.fatG,
      source: m.source,
      servings: m.servings,
      hasPin: hasPin,
    );

String _pinBadgeLabel(WidgetTester tester) =>
    tester.widget<MacrovaChip>(find.byKey(MealCard.pinBadgeKey)).label;

/// Opens the sheet for [meal] as day [day]'s [mealIndex]th meal, under
/// [plan]. Returns once the sheet's pin fetch has settled.
Future<void> _openSheet(
  WidgetTester tester,
  MealPlanProvider plan,
  Meal meal, {
  int day = 1,
  int mealIndex = 1,
}) async {
  tester.view.physicalSize = const Size(800, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    ChangeNotifierProvider<MealPlanProvider>.value(
      value: plan,
      child: MaterialApp(
        theme: AppTheme.light,
        home: Builder(
          builder: (context) => Scaffold(
            body: TextButton(
              onPressed: () => MealDetailSheet.show(
                context: context,
                meal: meal,
                day: day,
                mealIndex: mealIndex,
                isCooked: false,
                onToggleCooked: () {},
              ),
              child: const Text('Open'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();
}

String _actionLabel(WidgetTester tester) {
  final button =
      tester.widget<OutlinedButton>(find.byKey(MealDetailSheet.pinActionKey));
  return (button.child! as Text).data!;
}

bool _actionEnabled(WidgetTester tester) => tester
    .widget<OutlinedButton>(find.byKey(MealDetailSheet.pinActionKey))
    .enabled;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('MealCard pin badge', () {
    testWidgets('Given source pinned_assignment, Then it shows "Pinned"',
        (tester) async {
      await tester.pumpWidget(
        wrapWidget(_card(plannedMeal(source: Meal.sourcePinnedAssignment))),
      );

      expect(find.byKey(MealCard.pinBadgeKey), findsOneWidget);
      expect(_pinBadgeLabel(tester), 'Pinned');
    });

    testWidgets(
        'Given a planner meal whose slot was pinned after the plan, Then it '
        'shows "Pinned · next plan"', (tester) async {
      await tester.pumpWidget(wrapWidget(_card(plannedMeal(), hasPin: true)));

      expect(find.byKey(MealCard.pinBadgeKey), findsOneWidget);
      expect(_pinBadgeLabel(tester), 'Pinned · next plan');
    });

    testWidgets('Given a planner meal without a pin, Then no pin badge',
        (tester) async {
      await tester.pumpWidget(wrapWidget(_card(plannedMeal())));

      expect(find.byKey(MealCard.pinBadgeKey), findsNothing);
    });

    testWidgets(
        'Given a meal-prep batch meal on a pinned slot, Then the batch badge '
        'shows and the pin badge does not (meal prep beats pins)',
        (tester) async {
      await tester.pumpWidget(
        wrapWidget(
          _card(
            plannedMeal(
              source: Meal.sourceMealPrepBatch,
              batchId: 'b1',
              servings: 1,
            ),
            hasPin: true,
          ),
        ),
      );

      expect(find.byKey(MealCard.mealPrepBadgeKey), findsOneWidget);
      expect(find.byKey(MealCard.pinBadgeKey), findsNothing);
    });
  });

  group('MealDetailSheet pin action', () {
    testWidgets(
        'Given an unpinned slot, When Pin is tapped, Then it PUTs the plan '
        "slot's own (day_index, slot_index), re-fetches pins, shows Unpin, "
        'and does not re-run the plan', (tester) async {
      final server = FakePinServer();
      final plan = server.provider();
      // Day 2's second meal, slot_index 1 → pin coordinate (1, 1).
      await _openSheet(tester, plan, plannedMeal(), day: 2, mealIndex: 1);

      expect(server.listCalls, 1, reason: 'the sheet fetches pins once');
      expect(_actionLabel(tester), 'Pin');
      expect(_actionEnabled(tester), isTrue);
      expect(find.text('Not pinned'), findsOneWidget);
      expect(find.text('Applies next time you plan'), findsOneWidget);

      await tester.tap(find.byKey(MealDetailSheet.pinActionKey));
      await tester.pumpAndSettle();

      expect(server.upserts, [(1, 1, 'recipe_001')]);
      expect(server.listCalls, 2);
      expect(_actionLabel(tester), 'Unpin');
      expect(find.text('Pinned to this slot'), findsOneWidget);
      expect(server.planRequests, isEmpty);
    });

    testWidgets(
        'Given a pinned slot, When Unpin is tapped, Then it DELETEs that slot '
        'and shows Pin again', (tester) async {
      final server = FakePinServer(pins: const [
        ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'recipe_001'),
      ]);
      final plan = server.provider();
      await plan.loadPins();
      await _openSheet(
        tester,
        plan,
        plannedMeal(source: Meal.sourcePinnedAssignment),
      );

      expect(find.byKey(MealDetailSheet.pinnedKey), findsOneWidget);
      expect(_actionLabel(tester), 'Unpin');

      await tester.tap(find.byKey(MealDetailSheet.pinActionKey));
      await tester.pumpAndSettle();

      expect(server.deletes, [(0, 1)]);
      expect(_actionLabel(tester), 'Pin');
      expect(server.planRequests, isEmpty);
    });

    testWidgets(
        'Given RECIPE_NOT_FOUND, When Pin is tapped, Then the server code shows '
        'and the slot stays unpinned', (tester) async {
      final server = FakePinServer()..knownRecipeIds = {'other'};
      final plan = server.provider();
      await _openSheet(tester, plan, plannedMeal());

      await tester.tap(find.byKey(MealDetailSheet.pinActionKey));
      await tester.pumpAndSettle();

      expect(find.byKey(MealDetailSheet.pinErrorKey), findsOneWidget);
      expect(find.textContaining('RECIPE_NOT_FOUND'), findsOneWidget);
      expect(_actionLabel(tester), 'Pin');
    });

    testWidgets(
        'Given a meal-prep batch slot, Then Pin is disabled with "Meal prep '
        'overrides pins for this meal"', (tester) async {
      final server = FakePinServer();
      final plan = server.provider();
      await _openSheet(
        tester,
        plan,
        plannedMeal(source: Meal.sourceMealPrepBatch, batchId: 'b1', servings: 1),
      );

      expect(_actionLabel(tester), 'Pin');
      expect(_actionEnabled(tester), isFalse);
      expect(
        tester
            .widget<Text>(find.byKey(MealDetailSheet.pinPrecedenceKey))
            .data,
        'Meal prep overrides pins for this meal',
      );

      await tester.tap(find.byKey(MealDetailSheet.pinActionKey));
      await tester.pumpAndSettle();
      expect(server.upserts, isEmpty);
    });

    testWidgets('Without a MealPlanProvider, Then no pin action is shown',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Builder(
            builder: (context) => Scaffold(
              body: TextButton(
                onPressed: () => MealDetailSheet.show(
                  context: context,
                  meal: plannedMeal(),
                  day: 1,
                  mealIndex: 0,
                  isCooked: false,
                  onToggleCooked: () {},
                ),
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.byKey(MealDetailSheet.pinActionKey), findsNothing);
    });
  });
}
