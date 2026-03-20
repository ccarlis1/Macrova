import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/main.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';

void main() {
  testWidgets('App boots with Macrova shell', (WidgetTester tester) async {
    final profile = ProfileProvider();
    await tester.pumpWidget(
      MacrovaApp(
        profile: profile,
        llmGate: LlmConfigProvider(profile),
        ingredients: IngredientProvider(),
        recipes: RecipeProvider(),
        mealPlan: MealPlanProvider(),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Macrova'), findsOneWidget);
  });
}
