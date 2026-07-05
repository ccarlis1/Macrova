import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/advisory_card.dart';
import 'package:macrova/widgets/confidence_chip.dart';
import 'package:macrova/widgets/empty_state.dart';
import 'package:macrova/widgets/failure_panel.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:macrova/widgets/meal_card.dart';
import 'package:macrova/widgets/micronutrient_bar.dart';
import 'package:macrova/widgets/num_pill.dart';
import 'package:macrova/widgets/recipe_card.dart';
import 'package:macrova/widgets/section_header.dart';
import 'package:macrova/widgets/segmented_control.dart';
import 'package:macrova/widgets/stat_card.dart';
import 'package:macrova/widgets/macrova_sheet.dart';
import 'package:macrova/widgets/sticky_cta.dart';

import 'widget_test_helpers.dart';

void main() {
  group('SectionHeader', () {
    testWidgets('renders title and optional subtitle/link in light and dark',
        (tester) async {
      await pumpBothThemes(
        tester,
        const SectionHeader(
          title: 'Nutrition Targets',
          subtitle: 'Daily goals',
          linkLabel: 'Edit',
          onLink: _noop,
        ),
        assertions: () {
          expect(find.text('Nutrition Targets'), findsOneWidget);
          expect(find.text('Daily goals'), findsOneWidget);
          expect(find.text('Edit'), findsOneWidget);
        },
      );
    });
  });

  group('RecipeCard variants', () {
    testWidgets('standard constructor preserves existing layout',
        (tester) async {
      await pumpBothThemes(
        tester,
        const RecipeCard(recipe: sampleRecipe, onView: _noop),
        assertions: () {
          expect(find.text('Test Salad'), findsOneWidget);
          expect(find.text('View'), findsOneWidget);
        },
      );
    });

    testWidgets('hero row and mini variants render', (tester) async {
      for (final widget in [
        const RecipeCard.hero(recipe: sampleRecipe, badge: 'Pinned'),
        const RecipeCard.row(recipe: sampleRecipe),
        const RecipeCard.mini(recipe: sampleRecipe),
      ]) {
        await pumpBothThemes(
          tester,
          widget,
          assertions: () {
            expect(find.text('Test Salad'), findsOneWidget);
          },
        );
      }
    });
  });

  group('MealCard slot states', () {
    testWidgets('ok state renders meal content', (tester) async {
      await pumpBothThemes(
        tester,
        const MealCard(
          mealType: 'Breakfast',
          recipeName: 'Oatmeal',
          calories: 350,
          proteinG: 12,
          carbsG: 45,
          fatG: 8,
        ),
        assertions: () {
          expect(find.text('Breakfast'), findsOneWidget);
          expect(find.text('Oatmeal'), findsOneWidget);
        },
      );
    });

    testWidgets('pinned empty warn and workout states render', (tester) async {
      final states = <Widget>[
        const MealCard(
          mealType: 'Lunch',
          recipeName: 'Salad',
          calories: 400,
          proteinG: 20,
          carbsG: 30,
          fatG: 15,
          slotState: MealSlotState.pinned,
        ),
        const MealCard(
          mealType: '',
          recipeName: '+ Add lunch',
          calories: 0,
          proteinG: 0,
          carbsG: 0,
          fatG: 0,
          slotState: MealSlotState.empty,
        ),
        const MealCard(
          mealType: 'Dinner',
          recipeName: 'Stir fry',
          calories: 500,
          proteinG: 25,
          carbsG: 40,
          fatG: 18,
          slotState: MealSlotState.warn,
          warningText: 'High sodium',
        ),
        const MealCard(
          mealType: '',
          recipeName: 'Morning run',
          calories: 0,
          proteinG: 0,
          carbsG: 0,
          fatG: 0,
          slotState: MealSlotState.workout,
          timeLabel: '7:00',
        ),
      ];

      for (final card in states) {
        await pumpBothThemes(
          tester,
          card,
          assertions: () {
            expect(find.byType(MealCard), findsOneWidget);
          },
        );
      }
    });
  });

  group('MicronutrientBar', () {
    testWidgets('micro row uses semantic colors', (tester) async {
      await pumpBothThemes(
        tester,
        const MicronutrientBar(
          label: 'Iron',
          value: 8,
          target: 10,
          unit: 'mg',
        ),
        assertions: () {
          expect(find.text('Iron'), findsOneWidget);
          expect(find.textContaining('80%'), findsOneWidget);
        },
      );
    });

    testWidgets('macro split variant renders legend', (tester) async {
      await pumpBothThemes(
        tester,
        const MicronutrientBar.macroSplit(
          proteinG: 30,
          carbsG: 40,
          fatG: 20,
        ),
        assertions: () {
          expect(find.textContaining('Protein'), findsOneWidget);
          expect(find.textContaining('Carbs'), findsOneWidget);
          expect(find.textContaining('Fat'), findsOneWidget);
        },
      );
    });
  });

  group('MacrovaChip variants', () {
    testWidgets('renders chip variants in light and dark', (tester) async {
      final variants = [
        const MacrovaChip(label: 'Default'),
        const MacrovaChip(label: 'Accent', variant: MacrovaChipVariant.accent),
        const MacrovaChip(label: 'Dark', variant: MacrovaChipVariant.dark),
        const MacrovaChip(label: 'Pinned', variant: MacrovaChipVariant.pinned),
        const MacrovaChip(
          label: 'Add tag',
          variant: MacrovaChipVariant.dashedAdd,
        ),
        const MacrovaChip(
          label: 'Removable',
          variant: MacrovaChipVariant.removable,
          onRemove: _noop,
        ),
      ];

      for (final chip in variants) {
        await pumpBothThemes(
          tester,
          chip,
          assertions: () {
            expect(find.byType(MacrovaChip), findsOneWidget);
          },
        );
      }
    });
  });

  group('ConfidenceChip', () {
    testWidgets('renders hi mid none levels', (tester) async {
      for (final level in ConfidenceLevel.values) {
        await pumpBothThemes(
          tester,
          ConfidenceChip(level: level),
          assertions: () {
            expect(find.byType(ConfidenceChip), findsOneWidget);
          },
        );
      }
    });
  });

  group('FailurePanel', () {
    testWidgets('trace toggles on tap', (tester) async {
      await tester.pumpWidget(
        wrapWidget(
          const FailurePanel(
            terminationCode: 'FM-TAG-EMPTY',
            cause: 'No recipes match required tags.',
            trace: 'search depth=12 backtrack=400',
            fixHint: 'Relax required tags.',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Solver trace'), findsOneWidget);
      expect(find.textContaining('backtrack'), findsNothing);

      await tester.tap(find.text('Solver trace'));
      await tester.pumpAndSettle();

      expect(find.textContaining('backtrack'), findsOneWidget);
    });
  });

  group('EmptyState', () {
    testWidgets('add loading and skeleton variants render', (tester) async {
      for (final widget in [
        const EmptyState(label: '+ Add ingredient'),
        const EmptyState.loading(label: 'Loading…'),
        const EmptyState.skeleton(),
      ]) {
        await pumpBothThemes(
          tester,
          widget,
          assertions: () {
            expect(find.byType(EmptyState), findsOneWidget);
          },
        );
      }
    });
  });

  group('MacrovaSheet', () {
    testWidgets('renders header subtitle progress and sticky CTA', (tester) async {
      Widget sheet() {
        // ignore: prefer_const_constructors
        return SizedBox(
          height: 480,
          // ignore: prefer_const_constructors
          child: MacrovaSheet(
            title: 'Recipe detail',
            subtitle: '2 of 3',
            onClose: _noop,
            progressStep: 2,
            progressTotal: 3,
            body: const Text('Sheet body'),
            cta: const StickyCta(
              label: 'Total',
              detail: '420 kcal',
              actions: [
                StickyCtaAction(label: 'Save', isPrimary: true),
              ],
            ),
          ),
        );
      }

      await pumpBothThemes(
        tester,
        sheet(),
        assertions: () {
          expect(find.text('Recipe detail'), findsOneWidget);
          expect(find.text('2 of 3'), findsOneWidget);
          expect(find.text('Sheet body'), findsOneWidget);
          expect(find.text('Save'), findsOneWidget);
        },
      );
    });

    testWidgets('close button pops modal from show()', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Builder(
            builder: (context) => Scaffold(
              body: Center(
                child: ElevatedButton(
                  onPressed: () => MacrovaSheet.show(
                    context: context,
                    title: 'Planner failure',
                    body: const Text('Failure body'),
                  ),
                  child: const Text('Open sheet'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open sheet'));
      await tester.pumpAndSettle();

      expect(find.text('Planner failure'), findsOneWidget);
      expect(find.text('Failure body'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      expect(find.text('Planner failure'), findsNothing);
      expect(find.text('Open sheet'), findsOneWidget);
    });
  });

  group('StatCard SegmentedControl NumPill StickyCta AdvisoryCard', () {
    testWidgets('primitive widgets render', (tester) async {
      await pumpBothThemes(
        tester,
        Column(
          children: [
            const StatCard(
              label: 'Protein',
              value: '120',
              unit: 'g',
              progress: 0.75,
              variant: StatCardVariant.protein,
            ),
            SegmentedControl<String>(
              options: const [
                SegmentedOption(value: 'a', label: 'A'),
                SegmentedOption(value: 'b', label: 'B'),
              ],
              value: 'a',
              onChanged: (_) {},
            ),
            NumPill(value: 2, onChange: (_) {}),
            const StickyCta(
              label: 'Weekly total',
              detail: '12,400 kcal',
              actions: [
                StickyCtaAction(label: 'Plan', isPrimary: true),
              ],
            ),
            const AdvisoryCard(
              variant: AdvisoryVariant.warn,
              title: 'Sodium note',
              description: 'One meal exceeds daily limit.',
            ),
          ],
        ),
        assertions: () {
          expect(find.text('PROTEIN'), findsOneWidget);
          expect(find.text('A'), findsOneWidget);
          expect(find.text('Plan'), findsOneWidget);
          expect(find.text('Sodium note'), findsOneWidget);
        },
      );
    });
  });
}

void _noop() {}
