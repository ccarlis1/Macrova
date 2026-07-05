import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/agent_pane_screen.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/main.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';

const _wideSize = Size(1200, 800);
/// Below the 760px shell breakpoint but wide enough for screen content in tests.
const _narrowSize = Size(720, 800);

const _editRecipe = Recipe(
  id: 'r1',
  name: 'Temp',
  ingredients: [
    RecipeIngredientEntry(
      ingredientId: 'i1',
      ingredientName: 'oats',
      quantity: 50,
      unit: 'g',
    ),
  ],
  servings: 1,
);

Future<RecipeBuilderCoordinator> pumpAppShell(
  WidgetTester tester, {
  RecipeBuilderCoordinator? recipeBuilderCoordinator,
}) async {
  final profile = ProfileProvider();
  final coordinator = recipeBuilderCoordinator ?? RecipeBuilderCoordinator();
  await tester.pumpWidget(
    MacrovaApp(
      profile: profile,
      llmGate: LlmConfigProvider(profile),
      ingredients: IngredientProvider(),
      recipes: RecipeProvider(),
      recipeBuilderCoordinator: coordinator,
      mealPlan: MealPlanProvider(),
    ),
  );
  await tester.pumpAndSettle();
  return coordinator;
}

Future<void> tapRecipeBuilderTab(WidgetTester tester, {required bool wide}) async {
  if (wide) {
    await tester.tap(find.text('Recipe Builder'));
  } else {
    await tester.tap(find.byIcon(Icons.build_outlined));
  }
  await tester.pumpAndSettle();
}

Future<void> tapAgentTab(WidgetTester tester, {required bool wide}) async {
  if (wide) {
    await tester.tap(find.text('Agent Pane'));
  } else {
    await tester.tap(find.byIcon(Icons.smart_toy_outlined));
  }
  await tester.pumpAndSettle();
}

void main() {
  group('AppShell responsive layout', () {
    testWidgets(
      'Given wide viewport, When AppShell renders, Then NavigationRail is shown',
      (tester) async {
        tester.view.physicalSize = _wideSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);

        expect(find.byType(NavigationRail), findsOneWidget);
        expect(find.byType(NavigationBar), findsNothing);
        expect(find.text('Macrova'), findsOneWidget);
      },
    );

    testWidgets(
      'Given narrow viewport, When AppShell renders, Then NavigationBar is shown',
      (tester) async {
        tester.view.physicalSize = _narrowSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);

        expect(find.byType(NavigationBar), findsOneWidget);
        expect(find.byType(NavigationRail), findsNothing);
        expect(find.text('Macrova'), findsNothing);
      },
    );

    testWidgets(
      'Given narrow viewport, When Ingredients is selected, Then IndexedStack shows Ingredients',
      (tester) async {
        tester.view.physicalSize = _narrowSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);

        expect(find.text('Editable Nutrition Targets'), findsOneWidget);

        await tester.tap(find.byIcon(Icons.egg_outlined));
        await tester.pumpAndSettle();

        expect(find.text('Editable Nutrition Targets'), findsNothing);
        expect(find.text('Search for ingredients...'), findsOneWidget);
      },
    );

    testWidgets(
      'Given wide viewport, When Ingredients is selected, Then IndexedStack shows Ingredients',
      (tester) async {
        tester.view.physicalSize = _wideSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);

        expect(find.text('Editable Nutrition Targets'), findsOneWidget);

        await tester.tap(find.text('Ingredients'));
        await tester.pumpAndSettle();

        expect(find.text('Editable Nutrition Targets'), findsNothing);
        expect(find.text('Search for ingredients...'), findsOneWidget);
      },
    );

    testWidgets(
      'Given selected index, When viewport crosses breakpoint, Then selection is preserved',
      (tester) async {
        tester.view.physicalSize = _narrowSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);

        await tester.tap(find.byIcon(Icons.egg_outlined));
        await tester.pumpAndSettle();
        expect(find.text('Search for ingredients...'), findsOneWidget);

        tester.view.physicalSize = _wideSize;
        await tester.pumpAndSettle();

        expect(find.byType(NavigationRail), findsOneWidget);
        expect(find.text('Search for ingredients...'), findsOneWidget);
      },
    );

    testWidgets(
      'Given narrow viewport and edit mode, When Recipe Builder is reselected, Then startCreate clears builder',
      (tester) async {
        tester.view.physicalSize = _narrowSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final coordinator = await pumpAppShell(tester);
        await tapRecipeBuilderTab(tester, wide: false);

        coordinator.openForEdit(_editRecipe);
        await tester.pump();
        expect(find.text('Edit Recipe'), findsOneWidget);
        expect(find.text('Temp'), findsOneWidget);

        await tester.tap(find.byIcon(Icons.egg_outlined));
        await tester.pumpAndSettle();
        await tapRecipeBuilderTab(tester, wide: false);

        expect(find.text('Create Recipe'), findsOneWidget);
        expect(find.text('Temp'), findsNothing);
      },
    );

    testWidgets(
      'Given wide viewport and edit mode, When Recipe Builder is reselected, Then startCreate clears builder',
      (tester) async {
        tester.view.physicalSize = _wideSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        final coordinator = await pumpAppShell(tester);
        await tapRecipeBuilderTab(tester, wide: true);

        coordinator.openForEdit(_editRecipe);
        await tester.pump();
        expect(find.text('Edit Recipe'), findsOneWidget);
        expect(find.text('Temp'), findsOneWidget);

        await tester.tap(find.text('Ingredients'));
        await tester.pumpAndSettle();
        await tapRecipeBuilderTab(tester, wide: true);

        expect(find.text('Create Recipe'), findsOneWidget);
        expect(find.text('Temp'), findsNothing);
      },
    );

    testWidgets(
      'Given LLM not ready, When Agent tab is selected on narrow viewport, Then AgentSetupScreen is shown',
      (tester) async {
        tester.view.physicalSize = _narrowSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);
        await tapAgentTab(tester, wide: false);

        expect(find.text('Agent features'), findsOneWidget);
        expect(find.byType(AgentPaneScreen), findsNothing);
      },
    );

    testWidgets(
      'Given LLM not ready, When Agent tab is selected on wide viewport, Then AgentSetupScreen is shown',
      (tester) async {
        tester.view.physicalSize = _wideSize;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await pumpAppShell(tester);
        await tapAgentTab(tester, wide: true);

        expect(find.text('Agent features'), findsOneWidget);
        expect(find.byType(AgentPaneScreen), findsNothing);
      },
    );
  });
}
