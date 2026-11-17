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

  /// Pool recipes whose stored cuisine / cost were loaded from
  /// `GET /api/v1/recipes/{id}` this session ([RecipeProvider.hasServerTags]).
  /// Only these are counted; the others are reported as not checked.
  final Set<String> checkedRecipeIds;

  /// True when [poolRecipes] is an explicit selection (details are fetched
  /// for it); false when it is the whole library (no details are fetched).
  final bool poolIsSelection;

  /// True while the selected pool's details are loading.
  final bool checkingTags;

  const TagPoolFilterSection({
    super.key,
    required this.planProvider,
    this.poolRecipes = const [],
    this.checkedRecipeIds = const {},
    this.poolIsSelection = false,
    this.checkingTags = false,
  });

  static const cuisineGapKey = Key('pool_filter_cuisine_gap');
  static const costGapKey = Key('pool_filter_cost_gap');
  static const uncheckedKey = Key('pool_filter_tags_unchecked');

  /// Checked pool recipes with no stored cuisine: no tag entry (null) or the
  /// server's `unknown`. A cuisine filter drops them.
  static int countMissingCuisine(
    Iterable<Recipe> pool,
    Set<String> checkedIds,
  ) =>
      pool
          .where((r) => checkedIds.contains(r.id))
          .where((r) => r.cuisine == null || r.cuisine == kCuisineUnknown)
          .length;

  /// Checked pool recipes a Cheap / Premium filter drops for want of a cost:
  /// no tag entry (null), or `standard`, which is what the server stores when
  /// no cost was set (an explicit Standard can't be told apart).
  static int countMissingCost(
    Iterable<Recipe> pool,
    Set<String> checkedIds,
  ) =>
      pool
          .where((r) => checkedIds.contains(r.id))
          .where((r) => r.costLevel == null || r.costLevel == kCostLevelDefault)
          .length;

  /// Whether a filter is on that the warnings check (cuisine, Cheap/Premium).
  static bool needsTagCheck(MealPlanProvider planProvider) =>
      planProvider.cuisine.isNotEmpty ||
      (planProvider.costLevel != null &&
          planProvider.costLevel != kCostLevelDefault);

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
      final n = countMissingCuisine(poolRecipes, checkedRecipeIds);
      if (n > 0) {
        out.add(
          AdvisoryCard(
            key: cuisineGapKey,
            variant: AdvisoryVariant.warn,
            title: '${_recipesHave(n)} no cuisine set and will be left out.',
            description:
                'A cuisine filter drops recipes without a cuisine. Set one in '
                'the Recipe Builder to keep them. Counted from each recipe\'s '
                'stored cuisine on the server.',
          ),
        );
      }
    }
    final cost = planProvider.costLevel;
    if (cost != null && cost != kCostLevelDefault) {
      final n = countMissingCost(poolRecipes, checkedRecipeIds);
      if (n > 0) {
        out.add(
          AdvisoryCard(
            key: costGapKey,
            variant: AdvisoryVariant.warn,
            title: n == 1
                ? '1 recipe is Standard or has no cost set and will be left '
                    'out.'
                : '$n recipes are Standard or have no cost set and will be '
                    'left out.',
            description:
                'Recipes without a cost are stored as Standard, so the '
                '${tagValueLabel(cost)} filter drops them. Set a cost in the '
                'Recipe Builder to keep them. Counted from each recipe\'s '
                'stored cost on the server.',
          ),
        );
      }
    }
    if (needsTagCheck(planProvider)) {
      final unchecked =
          poolRecipes.where((r) => !checkedRecipeIds.contains(r.id)).length;
      if (unchecked > 0) {
        out.add(
          AdvisoryCard(
            key: uncheckedKey,
            variant: AdvisoryVariant.info,
            title: checkingTags
                ? 'Checking stored cuisine and cost…'
                : 'Stored cuisine and cost not checked for $unchecked '
                    '${unchecked == 1 ? 'recipe' : 'recipes'}',
            description: !poolIsSelection
                ? 'Select recipes in the pool to check which ones this filter '
                    'will leave out. The whole library isn\'t loaded.'
                : checkingTags
                    ? 'Loading the selected recipes from the server.'
                    : 'They couldn\'t be loaded from the server (recipes '
                        'saved only on this device can\'t be checked).',
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
