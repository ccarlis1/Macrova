import 'package:flutter/material.dart';

import '../../providers/meal_plan_provider.dart';
import '../../theme/tokens.dart';
import '../advisory_card.dart';
import '../macrova_chip.dart';
import '../section_header.dart';

/// Curated cuisine chip values (not a tag-registry fetch).
const kCuisineChipValues = [
  'mexican',
  'italian',
  'asian',
  'mediterranean',
];

const kCostLevelChips = [
  ('cheap', 'Cheap'),
  ('standard', 'Standard'),
  ('premium', 'Premium'),
];

const kPrepTimeBucketChips = [
  ('snack', 'Snack'),
  ('quick_meal', 'Quick meal'),
  ('weeknight_meal', 'Weeknight'),
  ('meal_prep', 'Meal prep'),
];

const kDietaryFlagChips = [
  ('vegetarian', 'Vegetarian'),
  ('vegan', 'Vegan'),
  ('gluten_free', 'Gluten-free'),
  ('dairy_free', 'Dairy-free'),
];

/// Pool-level PlanRequest tag filters (hard AND constraints server-side).
class TagPoolFilterSection extends StatelessWidget {
  final MealPlanProvider planProvider;

  const TagPoolFilterSection({super.key, required this.planProvider});

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'Recipe pool filters'),
        Text(
          'Hard filters applied to the recipe pool before planning. '
          'Narrow filters can empty the pool (FM-TAG-EMPTY).',
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
        const SizedBox(height: MacrovaSpacing.md),
        const _FilterRowLabel(label: 'Cuisine'),
        const SizedBox(height: MacrovaSpacing.xs),
        Wrap(
          spacing: MacrovaSpacing.xs,
          runSpacing: MacrovaSpacing.xs,
          children: [
            for (final value in kCuisineChipValues)
              MacrovaChip(
                key: Key('pool_filter_cuisine_$value'),
                label: _titleCase(value),
                selected: planProvider.cuisine.contains(value),
                onTap: () => planProvider.toggleCuisine(value),
              ),
            if (planProvider.cuisine.isNotEmpty)
              MacrovaChip(
                key: const Key('pool_filter_cuisine_clear'),
                label: 'Clear',
                variant: MacrovaChipVariant.removable,
                onRemove: planProvider.clearCuisine,
                onTap: planProvider.clearCuisine,
              ),
          ],
        ),
        const SizedBox(height: MacrovaSpacing.md),
        const _FilterRowLabel(label: 'Cost level'),
        const SizedBox(height: MacrovaSpacing.xs),
        Wrap(
          spacing: MacrovaSpacing.xs,
          runSpacing: MacrovaSpacing.xs,
          children: [
            for (final (value, label) in kCostLevelChips)
              MacrovaChip(
                key: Key('pool_filter_cost_$value'),
                label: label,
                selected: planProvider.costLevel == value,
                onTap: () => planProvider.setCostLevel(value),
              ),
          ],
        ),
        const SizedBox(height: MacrovaSpacing.md),
        const _FilterRowLabel(label: 'Prep time'),
        const SizedBox(height: MacrovaSpacing.xs),
        Wrap(
          spacing: MacrovaSpacing.xs,
          runSpacing: MacrovaSpacing.xs,
          children: [
            for (final (value, label) in kPrepTimeBucketChips)
              MacrovaChip(
                key: Key('pool_filter_prep_$value'),
                label: label,
                selected: planProvider.prepTimeBucket == value,
                onTap: () => planProvider.setPrepTimeBucket(value),
              ),
          ],
        ),
        const SizedBox(height: MacrovaSpacing.md),
        const _FilterRowLabel(label: 'Dietary flags'),
        const SizedBox(height: MacrovaSpacing.xs),
        Wrap(
          spacing: MacrovaSpacing.xs,
          runSpacing: MacrovaSpacing.xs,
          children: [
            for (final (value, label) in kDietaryFlagChips)
              MacrovaChip(
                key: Key('pool_filter_dietary_$value'),
                label: label,
                selected: planProvider.dietaryFlags.contains(value),
                onTap: () => planProvider.toggleDietaryFlag(value),
              ),
          ],
        ),
        if (planProvider.hasActivePoolFilters) ...[
          const SizedBox(height: MacrovaSpacing.md),
          const AdvisoryCard(
            variant: AdvisoryVariant.info,
            title: 'Pool filters are active',
            description:
                'These are hard constraints. If no recipes match, planning '
                'fails with FM-TAG-EMPTY — clear or widen filters and retry.',
          ),
        ],
      ],
    );
  }

  static String _titleCase(String value) {
    if (value.isEmpty) return value;
    return value[0].toUpperCase() + value.substring(1);
  }
}

class _FilterRowLabel extends StatelessWidget {
  final String label;

  const _FilterRowLabel({required this.label});

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    return Text(
      MacrovaTypography.labelCapsText(label),
      style: MacrovaTypography.labelCaps(tokens.inkTertiary),
    );
  }
}
