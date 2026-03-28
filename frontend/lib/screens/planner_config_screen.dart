import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/llm_config_provider.dart';
import '../models/models.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../widgets/app_shell.dart';
import '../widgets/macro_display.dart';
import '../widgets/section_header.dart';

class PlannerConfigScreen extends StatelessWidget {
  const PlannerConfigScreen({super.key});

  @override
  Widget build(BuildContext context) {
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
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Meal Planner Configuration',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 8),
              Text(
                'Configure your meal plan parameters. The planner will use your recipe pool and nutrition targets to generate an optimized meal plan.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 24),

              // Planning Duration
              const SectionHeader(title: 'Planning Duration'),
              Text('Number of Days: ${planProvider.days} days'),
              const SizedBox(height: 8),
              _NumberSelector(
                value: planProvider.days,
                min: 1,
                max: 7,
                onChanged: planProvider.setDays,
              ),
              const SizedBox(height: 24),

              // Planning mode (assisted requires validated LLM)
              const SectionHeader(title: 'Planner mode'),
              if (llmGate.llmReady) ...[
                Text(
                  'Planning mode',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 4),
                Text(
                  'Assisted modes use the server LLM; deterministic does not.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
                const SizedBox(height: 8),
                DropdownButton<String>(
                  value: planProvider.planningMode,
                  isExpanded: true,
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
                  onChanged: (v) {
                    if (v != null) {
                      planProvider.setPlanningMode(v);
                    }
                  },
                ),
              ]
              else
                Text(
                  'LLM-assisted planning appears here after you validate credentials '
                  'on Profile. Using deterministic only.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              const SizedBox(height: 24),

              // Ingredient source (matches POST /api/v1/plan `ingredient_source`)
              const SectionHeader(title: 'Ingredient nutrition source'),
              Text(
                'How the server resolves recipe ingredient nutrition. '
                'Use USDA (API) when your local ingredients file is incomplete — '
                'same as CLI `--ingredient-source api`. Requires USDA_API_KEY on the API server.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 8),
              DropdownButton<String>(
                value: planProvider.ingredientSource,
                isExpanded: true,
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
                onChanged: (v) {
                  if (v != null) {
                    planProvider.setIngredientSource(v);
                  }
                },
              ),
              const SizedBox(height: 24),

              // Per-day schedule (canonical meals + workout gaps)
              const SectionHeader(title: 'Schedule'),
              Text(
                'For each day: meal count, per-meal busyness (cooking-time band), '
                'and up to two workouts placed between meals.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 12),
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
              const SizedBox(height: 24),

              // Recipe Pool
              const SectionHeader(title: 'Recipe Pool'),
              if (recipes.isEmpty)
                Text(
                  'No recipes in your library. Create recipes first.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color:
                            Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                )
              else ...[
                Text(
                  'Select recipes to include in your meal plan:',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 8),
                ...recipes.map((recipe) {
                  final selected =
                      planProvider.selectedRecipeIds.contains(recipe.id);
                  return CheckboxListTile(
                    value: selected,
                    onChanged: (_) => planProvider.toggleRecipe(recipe.id),
                    title: Text(recipe.name),
                    subtitle: MacroDisplay(
                      calories: recipe.perServingCalories,
                      proteinG: recipe.perServingProteinG,
                      carbsG: recipe.perServingCarbsG,
                      fatG: recipe.perServingFatG,
                      compact: true,
                    ),
                    contentPadding: EdgeInsets.zero,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  );
                }),
                const SizedBox(height: 4),
                Text(
                  '${planProvider.selectedRecipeIds.length} recipes selected from your library',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color:
                            Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
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
                        padding: const EdgeInsets.only(top: 12),
                        child: Material(
                          color: Theme.of(context)
                              .colorScheme
                              .errorContainer
                              .withValues(alpha: 0.35),
                          borderRadius: BorderRadius.circular(8),
                          child: Padding(
                            padding: const EdgeInsets.all(12),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(
                                  Icons.warning_amber_rounded,
                                  color: Theme.of(context).colorScheme.error,
                                  size: 22,
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'Some selected recipes are not on the server '
                                    '(${notOnServer.length}). The planner only uses '
                                    'server recipe ids — those entries may be ignored '
                                    'until the recipe exists in the API pool.',
                                    style:
                                        Theme.of(context).textTheme.bodySmall,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ],
              ],
              const SizedBox(height: 24),

              // Nutrition Targets
              const SectionHeader(title: 'Your Nutrition Targets'),
              Card(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                  side: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Daily Target',
                          style: Theme.of(context).textTheme.titleSmall),
                      const SizedBox(height: 8),
                      MacroDisplay(
                        calories: profile.calories,
                        proteinG: profile.proteinG,
                        carbsG: profile.carbsG,
                        fatG: profile.fatG,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Fat goal: ${profile.fatGMin.round()}–${profile.fatGMax.round()} g',
                        style:
                            Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'From your Profile settings',
                        style:
                            Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurfaceVariant,
                                ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),

              // Generate button
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: planProvider.loading || planProvider.syncing
                      ? null
                      : () => _generate(context),
                  icon: planProvider.loading || planProvider.syncing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.arrow_forward),
                  label: Text(
                    planProvider.syncing
                        ? 'Syncing recipes…'
                        : planProvider.loading
                            ? 'Generating...'
                            : 'Generate Meal Plan',
                  ),
                ),
              ),
              if (planProvider.error != null) ...[
                const SizedBox(height: 12),
                Text(
                  'Error: ${planProvider.error}',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
              const SizedBox(height: 24),
              Text(
                'Technical Note: Planner request will be sent to backend with these parameters',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontStyle: FontStyle.italic,
                    ),
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
      shell?.navigateTo(5);
    }
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
    final n = day.meals.length;
    final gaps = n >= 2 ? List.generate(n - 1, (i) => i + 1) : <int>[];
    final used = {for (final w in day.workouts) w.afterMealIndex};
    final freeGaps = gaps.where((g) => !used.contains(g)).toList();

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Day ${day.dayIndex}',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            Text('Meals per day', style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 4),
            Wrap(
              spacing: 4,
              children: List.generate(8, (i) {
                final v = i + 1;
                final sel = v == n;
                return ChoiceChip(
                  label: Text('$v'),
                  selected: sel,
                  onSelected: (_) => onMealCount(dayIndex, v),
                );
              }),
            ),
            const SizedBox(height: 8),
            ...List.generate(n, (mi) {
              final m = day.meals[mi];
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 80,
                      child: Text('Meal ${m.index}'),
                    ),
                    Expanded(
                      child: SegmentedButton<int>(
                        segments: const [
                          ButtonSegment(value: 1, label: Text('1')),
                          ButtonSegment(value: 2, label: Text('2')),
                          ButtonSegment(value: 3, label: Text('3')),
                          ButtonSegment(value: 4, label: Text('4')),
                        ],
                        emptySelectionAllowed: false,
                        selected: {m.busynessLevel},
                        onSelectionChanged: (s) {
                          if (s.isEmpty) return;
                          onBusyness(dayIndex, mi, s.first);
                        },
                      ),
                    ),
                  ],
                ),
              );
            }),
            if (n >= 2) ...[
              const SizedBox(height: 8),
              Text(
                'Workouts (between meals)',
                style: Theme.of(context).textTheme.labelSmall,
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  for (var wi = 0; wi < day.workouts.length; wi++)
                    InputChip(
                      label: Text('After meal ${day.workouts[wi].afterMealIndex}'),
                      onDeleted: () => onRemoveWorkout(dayIndex, wi),
                    ),
                  if (day.workouts.length < 2 && freeGaps.isNotEmpty)
                    ...freeGaps.map(
                      (g) => TextButton(
                        onPressed: () => onAddWorkout(dayIndex, g),
                        child: Text('+ After meal $g'),
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
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
      spacing: 4,
      children: List.generate(max - min + 1, (i) {
        final n = min + i;
        final selected = n == value;
        return ChoiceChip(
          label: Text('$n'),
          selected: selected,
          onSelected: (_) => onChanged(n),
        );
      }),
    );
  }
}
