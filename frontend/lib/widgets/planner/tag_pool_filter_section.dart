import 'package:flutter/material.dart';

import '../../models/recipe.dart';
import '../../models/tag.dart';
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

  /// Recipes the plan will draw from (the selected ones, or the whole library
  /// when none is selected); used for the missing-value warnings.
  final List<Recipe> poolRecipes;

  const TagPoolFilterSection({
    super.key,
    required this.planProvider,
    this.poolRecipes = const [],
  });

  static const cuisineGapKey = Key('pool_filter_cuisine_gap');
  static const costGapKey = Key('pool_filter_cost_gap');

  /// Pool recipes with no cuisine the app knows of (never set in the Recipe
  /// Builder, or set to `unknown`). The recipe detail doesn't return the stored
  /// cuisine, so this is the app's own record, not the server's.
  static int countMissingCuisine(Iterable<Recipe> pool) => pool
      .where((r) => r.cuisine == null || r.cuisine == kCuisineUnknown)
      .length;

  /// Pool recipes with no cost the app knows of (the server stores them as
  /// `standard`). Same caveat as [countMissingCuisine].
  static int countMissingCost(Iterable<Recipe> pool) =>
      pool.where((r) => r.costLevel == null).length;

  static String _recipesHave(int n) =>
      n == 1 ? '1 recipe has' : '$n recipes have';

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
        ..._gapWarnings(),
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

  List<Widget> _gapWarnings() {
    final out = <Widget>[];
    if (planProvider.cuisine.isNotEmpty) {
      final n = countMissingCuisine(poolRecipes);
      if (n > 0) {
        out.add(
          AdvisoryCard(
            key: cuisineGapKey,
            variant: AdvisoryVariant.warn,
            title: '${_recipesHave(n)} no cuisine set and will be left out.',
            description:
                'A cuisine filter drops recipes without a cuisine. Set one in '
                'the Recipe Builder to keep them. Counted from cuisines set in '
                'this app; the server doesn\'t report stored cuisines yet.',
          ),
        );
      }
    }
    final cost = planProvider.costLevel;
    if (cost != null && cost != kCostLevelDefault) {
      final n = countMissingCost(poolRecipes);
      if (n > 0) {
        out.add(
          AdvisoryCard(
            key: costGapKey,
            variant: AdvisoryVariant.warn,
            title: '${_recipesHave(n)} no cost set and will be left out.',
            description:
                'Recipes without a cost are stored as Standard, so the '
                '${tagValueLabel(cost)} filter drops them. Set a cost in the '
                'Recipe Builder to keep them. Counted from costs set in this '
                'app; the server doesn\'t report stored costs yet.',
          ),
        );
      }
    }
    if (out.isEmpty) return out;
    return [
      for (final w in out) ...[
        const SizedBox(height: MacrovaSpacing.md),
        w,
      ],
    ];
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
