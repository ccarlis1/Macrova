import 'package:flutter/material.dart';

import '../models/models.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';
import 'macrova_sheet.dart';
import 'sticky_cta.dart';

/// Meal-slot detail sheet: summary + local Mark cooked CTA only.
///
/// Explicitly omits Pin and Swap (out of scope for PR14).
class MealDetailSheet {
  MealDetailSheet._();

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
