import 'package:flutter/material.dart';

import '../models/micronutrient_metadata.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';
import 'micronutrient_bar.dart';

class NutritionTotalsPanel extends StatelessWidget {
  final String title;
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final double? perServingCalories;
  final double? perServingProteinG;
  final double? perServingCarbsG;
  final double? perServingFatG;
  final int? servings;
  final Map<String, double> micronutrients;
  final Map<String, double> micronutrientTargets;

  const NutritionTotalsPanel({
    super.key,
    this.title = 'Nutrition Totals',
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.perServingCalories,
    this.perServingProteinG,
    this.perServingCarbsG,
    this.perServingFatG,
    this.servings,
    this.micronutrients = const {},
    this.micronutrientTargets = const {},
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderMd,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: Padding(
        padding: const EdgeInsets.all(MacrovaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: MacrovaTypography.subtitle(tokens.inkPrimary),
            ),
            const SizedBox(height: MacrovaSpacing.md),
            MacroDisplay(
              calories: calories,
              proteinG: proteinG,
              carbsG: carbsG,
              fatG: fatG,
            ),
            if (perServingCalories != null && servings != null) ...[
              Divider(height: MacrovaSpacing.xlAlt, color: tokens.lineSoft),
              Text(
                'Per Serving ($servings servings)',
                style: MacrovaTypography.label(tokens.inkPrimary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              _labeledRow(
                tokens,
                'Calories:',
                '${perServingCalories!.round()} kcal',
              ),
              _labeledRow(
                tokens,
                'Protein:',
                '${perServingProteinG!.round()}g',
              ),
              _labeledRow(
                tokens,
                'Carbs:',
                '${perServingCarbsG!.round()}g',
              ),
              _labeledRow(
                tokens,
                'Fat:',
                '${perServingFatG!.round()}g',
              ),
            ],
            if (micronutrients.isNotEmpty) ...[
              Divider(height: MacrovaSpacing.xlAlt, color: tokens.lineSoft),
              Text(
                'Micronutrients (Total)',
                style: MacrovaTypography.label(tokens.inkPrimary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              ...micronutrients.entries.map((e) {
                final target = micronutrientTargets[e.key] ?? 0;
                final unit = micronutrientUnitForKey(e.key);
                final label = micronutrientLabelForKey(e.key);
                final isLimit = micronutrientIsLimitKey(e.key);
                return MicronutrientBar(
                  label: label,
                  value: e.value,
                  target: target,
                  unit: unit,
                  isLimit: isLimit,
                );
              }),
            ],
          ],
        ),
      ),
    );
  }

  Widget _labeledRow(MacrovaTokens tokens, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.xs / 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: MacrovaTypography.body(tokens.inkSecondary)),
          Text(
            value,
            style: MacrovaTypography.body(tokens.inkPrimary).copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
