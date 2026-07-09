import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/llm_config_provider.dart';
import '../models/models.dart';
import '../models/recipe.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/app_shell.dart';
import '../widgets/macro_display.dart';
import '../widgets/macrova_chip.dart';
import '../widgets/planner/tag_pool_filter_section.dart';
import '../widgets/section_header.dart';
import '../widgets/segmented_control.dart';
import '../widgets/stat_card.dart';
import '../widgets/sticky_cta.dart';

class PlannerConfigScreen extends StatelessWidget {
  const PlannerConfigScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final planProvider = context.watch<MealPlanProvider>();
    final llmGate = context.watch<LlmConfigProvider>();
    final profile = context.watch<ProfileProvider>().profile;
    final recipeProvider = context.watch<RecipeProvider>();
    final recipes = recipeProvider.recipes;
    final remoteIds = recipeProvider.remoteRecipeIds;

    if (!llmGate.llmReady &&
        LlmConfigProvider.isAssistedPlanningMode(planProvider.planningMode)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!context.mounted) return;
        context.read<MealPlanProvider>().setPlanningMode('deterministic');
      });
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Meal Planner Configuration',
                style: MacrovaTypography.headline(tokens.inkPrimary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              Text(
                'Configure your meal plan parameters. The planner will use your recipe pool and nutrition targets to generate an optimized meal plan.',
                style: MacrovaTypography.body(tokens.inkTertiary),
              ),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Planning Duration
              const SectionHeader(title: 'Planning Duration'),
              Text(
                'Number of Days: ${planProvider.days} days',
                style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              _NumberSelector(
                value: planProvider.days,
                min: 1,
                max: 7,
                onChanged: planProvider.setDays,
              ),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Planning mode (assisted requires validated LLM)
              const SectionHeader(title: 'Planner mode'),
              if (llmGate.llmReady) ...[
                Text(
                  'Planning mode',
                  style: MacrovaTypography.titleSm(tokens.inkPrimary),
                ),
                const SizedBox(height: MacrovaSpacing.xs),
                Text(
                  'Assisted modes use the server LLM; deterministic does not.',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
                const SizedBox(height: MacrovaSpacing.sm),
                _TokenDropdown(
                  value: planProvider.planningMode,
                  onChanged: planProvider.setPlanningMode,
                  items: const [
                    DropdownMenuItem(
                      value: 'deterministic',
                      child: Text('Deterministic'),
                    ),
                    DropdownMenuItem(
                      value: 'assisted',
                      child: Text('Assisted'),
                    ),
                    DropdownMenuItem(
                      value: 'assisted_cached',
                      child: Text('Assisted (cache strict)'),
                    ),
                    DropdownMenuItem(
                      value: 'assisted_live',
                      child: Text('Assisted (live)'),
                    ),
                  ],
                ),
              ]
              else
                Text(
                  'LLM-assisted planning appears here after you validate credentials '
                  'on Profile. Using deterministic only.',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Ingredient source (matches POST /api/v1/plan `ingredient_source`)
              const SectionHeader(title: 'Ingredient nutrition source'),
              Text(
                'How the server resolves recipe ingredient nutrition. '
                'Use USDA (API) when your local ingredients file is incomplete — '
                'same as CLI `--ingredient-source api`. Requires USDA_API_KEY on the API server.',
                style: MacrovaTypography.caption(tokens.inkTertiary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              _TokenDropdown(
                value: planProvider.ingredientSource,
                onChanged: planProvider.setIngredientSource,
                items: const [
                  DropdownMenuItem(
                    value: 'local',
                    child: Text('Local JSON (custom_ingredients.json on server)'),
                  ),
                  DropdownMenuItem(
                    value: 'api',
                    child: Text('USDA FoodData Central (API)'),
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Per-day schedule (canonical meals + workout gaps)
              const SectionHeader(title: 'Schedule'),
              Text(
                'For each day: meal count, per-meal busyness (cooking-time band), '
                'and up to two workouts placed between meals.',
                style: MacrovaTypography.caption(tokens.inkTertiary),
              ),
              const SizedBox(height: MacrovaSpacing.md),
              ...List.generate(planProvider.days, (dayIndex) {
                final day = planProvider.scheduleDays[dayIndex];
                return _DayScheduleCard(
                  dayIndex: dayIndex,
                  day: day,
                  onMealCount: planProvider.setMealCountForDay,
                  onBusyness: planProvider.setMealBusyness,
                  onAddWorkout: planProvider.addWorkoutInGap,
                  onRemoveWorkout: planProvider.removeWorkoutAt,
                );
              }),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Recipe Pool
              const SectionHeader(title: 'Recipe Pool'),
              if (recipes.isEmpty)
                Text(
                  'No recipes in your library. Create recipes first.',
                  style: MacrovaTypography.body(tokens.inkTertiary),
                )
              else ...[
                Text(
                  'Select recipes to include in your meal plan:',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
                const SizedBox(height: MacrovaSpacing.sm),
                ...recipes.map((recipe) {
                  final selected =
                      planProvider.selectedRecipeIds.contains(recipe.id);
                  return _RecipePoolRow(
                    recipe: recipe,
                    selected: selected,
                    onToggle: () => planProvider.toggleRecipe(recipe.id),
                  );
                }),
                const SizedBox(height: MacrovaSpacing.xs),
                Text(
                  '${planProvider.selectedRecipeIds.length} recipes selected from your library',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
                if (remoteIds.isNotEmpty) ...[
                  Builder(
                    builder: (context) {
                      final notOnServer = planProvider.selectedRecipeIds
                          .where((id) => !remoteIds.contains(id))
                          .toList();
                      if (notOnServer.isEmpty) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: MacrovaSpacing.md),
                        child: AdvisoryCard(
                          variant: AdvisoryVariant.warn,
                          title:
                              'Some selected recipes are not on the server (${notOnServer.length})',
                          description:
                              'The planner only uses server recipe ids — those '
                              'entries may be ignored until the recipe exists in '
                              'the API pool.',
                        ),
                      );
                    },
                  ),
                ],
              ],
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Recipe pool filters (pool-level PlanRequest tag fields)
              TagPoolFilterSection(planProvider: planProvider),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              // Nutrition Targets
              const SectionHeader(title: 'Your Nutrition Targets'),
              Row(
                children: [
                  Expanded(
                    child: StatCard(
                      label: 'Calories',
                      value: '${profile.calories.round()}',
                      unit: 'kcal',
                    ),
                  ),
                  const SizedBox(width: MacrovaSpacing.md),
                  Expanded(
                    child: StatCard(
                      label: 'Protein',
                      value: '${profile.proteinG.round()}',
                      unit: 'g',
                      variant: StatCardVariant.protein,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.md),
              Row(
                children: [
                  Expanded(
                    child: StatCard(
                      label: 'Carbs',
                      value: '${profile.carbsG.round()}',
                      unit: 'g',
                      variant: StatCardVariant.carb,
                    ),
                  ),
                  const SizedBox(width: MacrovaSpacing.md),
                  Expanded(
                    child: StatCard(
                      label: 'Fat',
                      value: '${profile.fatG.round()}',
                      unit: 'g',
                      variant: StatCardVariant.fat,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              Text(
                'Fat goal: ${profile.fatGMin.round()}–${profile.fatGMax.round()} g · From your Profile settings',
                style: MacrovaTypography.caption(tokens.inkTertiary),
              ),
              const SizedBox(height: MacrovaSpacing.xxl),

              // Generate CTA
              ClipRRect(
                borderRadius: MacrovaRadius.borderMd,
                child: StickyCta(
                  label: 'Meal plan',
                  detail: _ctaDetail(planProvider),
                  actions: [
                    StickyCtaAction(
                      label: planProvider.syncing
                          ? 'Syncing recipes…'
                          : planProvider.loading
                              ? 'Generating...'
                              : 'Generate Meal Plan',
                      isPrimary: true,
                      onPressed: planProvider.loading || planProvider.syncing
                          ? null
                          : () => _generate(context),
                    ),
                  ],
                ),
              ),
              if (planProvider.error != null) ...[
                const SizedBox(height: MacrovaSpacing.md),
                AdvisoryCard(
                  variant: AdvisoryVariant.warn,
                  title: 'Planning error',
                  description: planProvider.error!,
                ),
              ],
              const SizedBox(height: MacrovaSpacing.xlAlt),
              Text(
                'Technical Note: Planner request will be sent to backend with these parameters',
                style: MacrovaTypography.caption(tokens.inkQuaternary)
                    .copyWith(fontStyle: FontStyle.italic),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _generate(BuildContext context) async {
    final profile = context.read<ProfileProvider>().profile;
    final planProvider = context.read<MealPlanProvider>();
    final recipeProvider = context.read<RecipeProvider>();

    final recipeIds = planProvider.selectedRecipeIds.isEmpty
        ? null
        : planProvider.selectedRecipeIds.toList();

    final request = PlanRequest(
      dailyCalories: profile.calories.round(),
      dailyProteinG: profile.proteinG,
      dailyFatGMin: profile.fatGMin,
      dailyFatGMax: profile.fatGMax,
      scheduleDays: planProvider.scheduleDaysForApi(),
      allergies: profile.allergies,
      days: planProvider.days,
      ingredientSource: planProvider.ingredientSource,
      micronutrientGoals: profile.micronutrientGoals.toPlanMicronutrientGoals(),
      micronutrientWeeklyMinFraction: profile.micronutrientWeeklyMinFraction,
      planningMode: planProvider.planningMode,
      recipeIds: recipeIds,
      cuisine: planProvider.cuisine.isEmpty
          ? null
          : List<String>.from(planProvider.cuisine),
      costLevel: planProvider.costLevel,
      prepTimeBucket: planProvider.prepTimeBucket,
      dietaryFlags: planProvider.dietaryFlags.isEmpty
          ? null
          : List<String>.from(planProvider.dietaryFlags),
    );

    final shell = context.findAncestorStateOfType<AppShellState>();

    if (recipeIds != null && recipeIds.isNotEmpty) {
      for (final id in recipeIds) {
        var recipe = recipeProvider.getById(id);
        if (recipe == null) {
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Recipe not found: $id')),
          );
          return;
        }
        if (recipe.ingredients.isEmpty) {
          try {
            recipe = await recipeProvider.fetchRecipeDetail(id);
          } catch (e) {
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  e is ApiException ? e.message : e.toString(),
                ),
              ),
            );
            return;
          }
        }
        if (recipe.ingredients.isEmpty) {
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                'Recipe "${recipe.name}" has no ingredients to sync.',
              ),
            ),
          );
          return;
        }
      }
    }

    // Push every locally stored full recipe to the server before planning so
    // `POST /plan` reads updated lines (not only the selected subset).
    await planProvider.generatePlanWithRecipeSync(
      recipesToSync: recipeProvider.localFullRecipesForSync,
      request: request,
    );
    await recipeProvider.syncSummariesFromApi();

    if (!context.mounted) return;
    if (LlmConfigProvider.isAssistedPlanningMode(request.planningMode) &&
        planProvider.error != null) {
      context.read<LlmConfigProvider>().revokeReady(planProvider.error!);
    }
    if (planProvider.mealPlan != null) {
      shell?.navigateTo(6);
    }
  }

  static String _ctaDetail(MealPlanProvider planProvider) {
    final parts = <String>[
      '${planProvider.days} ${planProvider.days == 1 ? 'day' : 'days'}',
      '${planProvider.selectedRecipeIds.length} selected',
    ];
    final filters = planProvider.activePoolFilterCount;
    if (filters > 0) {
      parts.add('$filters ${filters == 1 ? 'filter' : 'filters'}');
    }
    return parts.join(' · ');
  }
}

/// Token-styled dropdown wrapper (hairline border, no Material underline).
class _TokenDropdown extends StatelessWidget {
  final String value;
  final List<DropdownMenuItem<String>> items;
  final ValueChanged<String> onChanged;

  const _TokenDropdown({
    required this.value,
    required this.items,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: MacrovaSpacing.md),
      decoration: BoxDecoration(
        color: tokens.surfaceTint,
        borderRadius: MacrovaRadius.borderSm,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          isExpanded: true,
          borderRadius: MacrovaRadius.borderSm,
          style: MacrovaTypography.bodyMedium(tokens.inkPrimary),
          items: items,
          onChanged: (v) {
            if (v != null) onChanged(v);
          },
        ),
      ),
    );
  }
}

/// Selectable recipe-pool row (token card). Reuses [MealPlanProvider.toggleRecipe]
/// via [onToggle]; selection state is passed in.
class _RecipePoolRow extends StatelessWidget {
  final Recipe recipe;
  final bool selected;
  final VoidCallback onToggle;

  const _RecipePoolRow({
    required this.recipe,
    required this.selected,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Padding(
      padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onToggle,
          borderRadius: MacrovaRadius.borderSm,
          child: Ink(
            decoration: BoxDecoration(
              color: selected ? tokens.surfaceSoft : Colors.transparent,
              borderRadius: MacrovaRadius.borderSm,
              border: Border.all(
                color: selected ? tokens.lineStrong : tokens.lineDefault,
              ),
            ),
            padding: const EdgeInsets.all(MacrovaSpacing.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  selected
                      ? Icons.check_box_rounded
                      : Icons.check_box_outline_blank_rounded,
                  size: 20,
                  color: selected ? tokens.accent : tokens.inkTertiary,
                ),
                const SizedBox(width: MacrovaSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        recipe.name,
                        style: MacrovaTypography.label(tokens.inkPrimary),
                      ),
                      const SizedBox(height: MacrovaSpacing.xs),
                      MacroDisplay(
                        calories: recipe.perServingCalories,
                        proteinG: recipe.perServingProteinG,
                        carbsG: recipe.perServingCarbsG,
                        fatG: recipe.perServingFatG,
                        compact: true,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// One planning day: meal count, per-meal busyness, optional workouts between meals.
class _DayScheduleCard extends StatelessWidget {
  final int dayIndex;
  final DaySchedule day;
  final void Function(int dayIndex0, int mealCount) onMealCount;
  final void Function(int dayIndex0, int mealIndex0, int busyness) onBusyness;
  final void Function(int dayIndex0, int afterMealIndex) onAddWorkout;
  final void Function(int dayIndex0, int workoutListIndex) onRemoveWorkout;

  const _DayScheduleCard({
    required this.dayIndex,
    required this.day,
    required this.onMealCount,
    required this.onBusyness,
    required this.onAddWorkout,
    required this.onRemoveWorkout,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final n = day.meals.length;
    final gaps = n >= 2 ? List.generate(n - 1, (i) => i + 1) : <int>[];
    final used = {for (final w in day.workouts) w.afterMealIndex};
    final freeGaps = gaps.where((g) => !used.contains(g)).toList();

    return Container(
      margin: const EdgeInsets.only(bottom: MacrovaSpacing.md),
      padding: const EdgeInsets.all(MacrovaSpacing.md),
      decoration: BoxDecoration(
        color: tokens.surfaceTint,
        borderRadius: MacrovaRadius.borderMd,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Day ${day.dayIndex}',
            style: MacrovaTypography.titleSm(tokens.inkPrimary),
          ),
          const SizedBox(height: MacrovaSpacing.sm),
          Text(
            MacrovaTypography.labelCapsText('Meals per day'),
            style: MacrovaTypography.labelCaps(tokens.inkTertiary),
          ),
          const SizedBox(height: MacrovaSpacing.xs),
          Wrap(
            spacing: MacrovaSpacing.xs,
            runSpacing: MacrovaSpacing.xs,
            children: List.generate(8, (i) {
              final v = i + 1;
              final sel = v == n;
              return MacrovaChip(
                label: '$v',
                selected: sel,
                onTap: () => onMealCount(dayIndex, v),
              );
            }),
          ),
          const SizedBox(height: MacrovaSpacing.md),
          ...List.generate(n, (mi) {
            final m = day.meals[mi];
            return Padding(
              padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
              child: Row(
                children: [
                  SizedBox(
                    width: 80,
                    child: Text(
                      'Meal ${m.index}',
                      style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
                    ),
                  ),
                  Expanded(
                    child: SegmentedControl<int>(
                      style: SegmentedControlStyle.busyness,
                      value: m.busynessLevel,
                      onChanged: (v) => onBusyness(dayIndex, mi, v),
                      options: const [
                        SegmentedOption(value: 1, label: '1'),
                        SegmentedOption(value: 2, label: '2'),
                        SegmentedOption(value: 3, label: '3'),
                        SegmentedOption(value: 4, label: '4'),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
          if (n >= 2) ...[
            const SizedBox(height: MacrovaSpacing.sm),
            Text(
              MacrovaTypography.labelCapsText('Workouts (between meals)'),
              style: MacrovaTypography.labelCaps(tokens.inkTertiary),
            ),
            const SizedBox(height: MacrovaSpacing.xs),
            Wrap(
              spacing: MacrovaSpacing.sm,
              runSpacing: MacrovaSpacing.xs,
              children: [
                for (var wi = 0; wi < day.workouts.length; wi++)
                  MacrovaChip(
                    label: 'After meal ${day.workouts[wi].afterMealIndex}',
                    variant: MacrovaChipVariant.removable,
                    onRemove: () => onRemoveWorkout(dayIndex, wi),
                  ),
                if (day.workouts.length < 2 && freeGaps.isNotEmpty)
                  ...freeGaps.map(
                    (g) => MacrovaChip(
                      label: 'After meal $g',
                      variant: MacrovaChipVariant.dashedAdd,
                      onTap: () => onAddWorkout(dayIndex, g),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _NumberSelector extends StatelessWidget {
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  const _NumberSelector({
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: MacrovaSpacing.xs,
      runSpacing: MacrovaSpacing.xs,
      children: List.generate(max - min + 1, (i) {
        final n = min + i;
        final selected = n == value;
        return MacrovaChip(
          label: '$n',
          selected: selected,
          onTap: () => onChanged(n),
        );
      }),
    );
  }
}
