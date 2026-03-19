import 'package:flutter/material.dart';

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

  static const _micronutrientUnits = {
    'vitamin_a_ug': 'mcg',
    'vitamin_c_mg': 'mg',
    'iron_mg': 'mg',
    'calcium_mg': 'mg',
    'fiber_g': 'g',
    'sodium_mg': 'mg',
  };

  static const _micronutrientLabels = {
    'vitamin_a_ug': 'Vitamin A',
    'vitamin_c_mg': 'Vitamin C',
    'iron_mg': 'Iron',
    'calcium_mg': 'Calcium',
    'fiber_g': 'Fiber',
    'sodium_mg': 'Sodium',
  };

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            MacroDisplay(
              calories: calories,
              proteinG: proteinG,
              carbsG: carbsG,
              fatG: fatG,
            ),
            if (perServingCalories != null && servings != null) ...[
              const Divider(height: 24),
              Text(
                'Per Serving ($servings servings)',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              _labeledRow(context, 'Calories:', '${perServingCalories!.round()} kcal'),
              _labeledRow(context, 'Protein:', '${perServingProteinG!.round()}g'),
              _labeledRow(context, 'Carbs:', '${perServingCarbsG!.round()}g'),
              _labeledRow(context, 'Fat:', '${perServingFatG!.round()}g'),
            ],
            if (micronutrients.isNotEmpty) ...[
              const Divider(height: 24),
              Text(
                'Micronutrients (Total)',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              ...micronutrients.entries.map((e) {
                final target = micronutrientTargets[e.key] ?? 0;
                final unit = _micronutrientUnits[e.key] ?? '';
                final label = _micronutrientLabels[e.key] ?? e.key;
                final isLimit = e.key == 'sodium_mg';
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

  Widget _labeledRow(BuildContext context, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          Text(
            value,
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
