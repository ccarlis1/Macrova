import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/agent_models.dart';
import 'package:macrova/features/agent/agent_pane_screen.dart';
import 'package:macrova/features/agent/agent_setup_screen.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/advisory_card.dart';
import 'package:macrova/widgets/confidence_chip.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'widget_test_helpers.dart';

class _ReadyLlmGate extends LlmConfigProvider {
  _ReadyLlmGate(super.profile);

  @override
  bool get llmReady => true;

  @override
  void revokeReady(String message) {}
}

Widget _wrapAgentPane({
  required Widget child,
  LlmConfigProvider? gate,
  bool dark = false,
}) {
  final profile = ProfileProvider();
  final llmGate = gate ?? _ReadyLlmGate(profile);
  return MaterialApp(
    theme: AppTheme.light,
    darkTheme: AppTheme.dark,
    themeMode: dark ? ThemeMode.dark : ThemeMode.light,
    home: Scaffold(
      body: MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: profile),
          ChangeNotifierProvider<LlmConfigProvider>.value(value: llmGate),
          ChangeNotifierProvider.value(value: MealPlanProvider()),
          ChangeNotifierProvider.value(
            value: RecipeProvider(recipeSyncFn: (_) async => []),
          ),
        ],
        child: child,
      ),
    ),
  );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AgentSetupScreen', () {
    testWidgets(
      'Given gate closed, When setup screen renders, Then heading and CTA show',
      (tester) async {
        final profile = ProfileProvider();
        final gate = LlmConfigProvider(profile);

        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            home: Scaffold(
              body: ChangeNotifierProvider<LlmConfigProvider>.value(
                value: gate,
                child: AgentSetupScreen(onOpenProfile: () {}),
              ),
            ),
          ),
        );
        await tester.pump();

        expect(find.text('Agent features'), findsOneWidget);
        expect(find.text('Open Profile'), findsOneWidget);
        expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
      },
    );
  });

  group('AgentPaneScreen', () {
    testWidgets(
      'Given LLM ready, When pane renders, Then section headers and inputs show in light and dark',
      (tester) async {
        for (final dark in [false, true]) {
          await tester.pumpWidget(
            _wrapAgentPane(
              dark: dark,
              child: const AgentPaneScreen(),
            ),
          );
          await tester.pump();

          expect(find.text('Agent'), findsOneWidget);
          expect(find.text('Plan from text'), findsOneWidget);
          expect(find.text('Match ingredient names'), findsOneWidget);
          expect(find.text('Generate validated recipes'), findsOneWidget);
          expect(find.byType(TextField), findsNWidgets(4));
        }
      },
    );

    testWidgets(
      'Given gate closed on pane, When pane renders, Then tokenized fallback shows',
      (tester) async {
        final profile = ProfileProvider();
        final gate = LlmConfigProvider(profile);

        await tester.pumpWidget(
          _wrapAgentPane(
            gate: gate,
            child: const AgentPaneScreen(),
          ),
        );
        await tester.pump();

        expect(find.text('LLM gate closed.'), findsOneWidget);
        expect(find.text('Plan from text'), findsNothing);
      },
    );

    testWidgets(
      'Given section error banner, When pane error slot renders, Then AdvisoryCard warn shows message',
      (tester) async {
        await pumpBothThemes(
          tester,
          const AgentSectionErrorBanner(message: 'Server unavailable'),
          assertions: () {
            expect(find.byType(AdvisoryCard), findsOneWidget);
            expect(find.text('Request failed'), findsOneWidget);
            expect(find.text('Server unavailable'), findsOneWidget);
            expect(find.text('INFEASIBLE'), findsNothing);
          },
        );
      },
    );

    testWidgets(
      'Given match results, When results section renders, Then ConfidenceChip is shown',
      (tester) async {
        const result = IngredientMatchResult(
          accepted: [
            IngredientMatchAccepted(
              originalQuery: 'tomato',
              normalizedName: 'Tomatoes, raw',
              confidence: 0.92,
            ),
            IngredientMatchAccepted(
              originalQuery: 'basil',
              normalizedName: 'Basil, fresh',
              confidence: 0.55,
            ),
          ],
          rejected: [
            IngredientMatchRejected(
              originalQuery: 'mystery spice',
              code: 'NO_MATCH',
              message: 'Could not resolve ingredient',
            ),
          ],
        );

        await pumpBothThemes(
          tester,
          const AgentMatchResultsSection(result: result),
          assertions: () {
            expect(find.byType(ConfidenceChip), findsNWidgets(2));
            expect(find.text('92% match'), findsOneWidget);
            expect(find.text('55% match'), findsOneWidget);
            expect(find.text('NO_MATCH: Could not resolve ingredient'),
                findsOneWidget);
          },
        );
      },
    );

    testWidgets(
      'Given generation results with failures, When section renders, Then AdvisoryCard warn surfaces code and message',
      (tester) async {
        const result = RecipeGenerationResult(
          acceptedCount: 1,
          rejectedCount: 1,
          recipeIds: ['recipe-a', 'recipe-b'],
          failures: [
            RecipeGenFailure(
              code: 'VALIDATION_FAILED',
              message: 'Nutrition check failed',
            ),
          ],
        );

        await pumpBothThemes(
          tester,
          const AgentGenerationResultsSection(result: result),
          assertions: () {
            expect(find.byType(AdvisoryCard), findsNWidgets(2));
            expect(find.text('VALIDATION_FAILED'), findsOneWidget);
            expect(find.text('Nutrition check failed'), findsOneWidget);
            expect(find.text('INFEASIBLE'), findsNothing);
            expect(find.byType(SelectableText), findsOneWidget);
            expect(find.text('recipe-a, recipe-b'), findsOneWidget);
          },
        );
      },
    );
  });
}
