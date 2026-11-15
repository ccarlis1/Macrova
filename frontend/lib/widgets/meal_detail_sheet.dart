import 'package:flutter/material.dart';

import '../models/meal_prep_batch.dart';
import '../models/models.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';
import 'macrova_chip.dart';
import 'macrova_sheet.dart';
import 'sticky_cta.dart';

/// Meal-slot detail sheet: summary + local Mark cooked CTA only.
///
/// Explicitly omits Pin and Swap (out of scope for PR14).
class MealDetailSheet {
  MealDetailSheet._();

  /// Batch variant (FE-14): shown when `meal.source == meal_prep_batch`.
  static const mealPrepKey = Key('meal_detail_meal_prep');

  static Future<void> show({
    required BuildContext context,
    required Meal meal,
    required int day,
    required int mealIndex,
    required bool isCooked,
    required VoidCallback onToggleCooked,
  }) {
    final recipeName = meal.recipe['name'] as String? ?? 'Unknown Recipe';
    final cookedLabel = isCooked ? 'Mark not cooked' : 'Mark cooked';

    return MacrovaSheet.show(
      context: context,
      title: meal.mealType,
      subtitle: 'Day $day',
      body: _MealDetailBody(meal: meal, recipeName: recipeName),
      cta: StickyCta(
        label: 'This device only',
        detail: isCooked ? 'Marked cooked' : 'Not marked cooked',
        actions: [
          StickyCtaAction(
            label: cookedLabel,
            isPrimary: true,
            onPressed: () {
              onToggleCooked();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
    );
  }
}

class _MealDetailBody extends StatelessWidget {
  final Meal meal;
  final String recipeName;

  const _MealDetailBody({
    required this.meal,
    required this.recipeName,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return ListView(
      padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
      children: [
        Text(
          recipeName,
          style: MacrovaTypography.subtitle(tokens.inkPrimary),
        ),
        if (meal.isMealPrepBatch) ...[
          const SizedBox(height: MacrovaSpacing.sm),
          Row(
            key: MealDetailSheet.mealPrepKey,
            children: [
              const MacrovaChip(
                label: 'Meal prep',
                variant: MacrovaChipVariant.accent,
                leadingIcon: Icons.kitchen_outlined,
              ),
              const SizedBox(width: MacrovaSpacing.sm),
              Expanded(
                child: Text(
                  meal.servings == null
                      ? 'From a meal-prep batch'
                      : 'From a meal-prep batch · '
                          '${servingsLabel(meal.servings!)}',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: MacrovaSpacing.md),
        MacroDisplay(
          calories: meal.nutrition.calories,
          proteinG: meal.nutrition.proteinG,
          carbsG: meal.nutrition.carbsG,
          fatG: meal.nutrition.fatG,
        ),
        const SizedBox(height: MacrovaSpacing.xl),
        Text(
          'Cooked status is saved on this device only. '
          'It is not sent to the planner.',
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
      ],
    );
  }
}
