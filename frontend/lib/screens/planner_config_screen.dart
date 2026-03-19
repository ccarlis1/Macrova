import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../widgets/app_shell.dart';
import '../widgets/macro_display.dart';
import '../widgets/section_header.dart';

class PlannerConfigScreen extends StatelessWidget {
  const PlannerConfigScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final planProvider = context.watch<MealPlanProvider>();
    final profile = context.watch<ProfileProvider>().profile;
    final recipes = context.watch<RecipeProvider>().recipes;

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

              // Meals Per Day
              const SectionHeader(title: 'Meals Per Day'),
              Text('Number of Meals: ${planProvider.mealsPerDay} meals/day'),
              const SizedBox(height: 8),
              _NumberSelector(
                value: planProvider.mealsPerDay,
                min: 1,
                max: 8,
                onChanged: planProvider.setMealsPerDay,
              ),
              const SizedBox(height: 4),
              Text(
                'Example: 3 meals = Breakfast, Lunch, Dinner',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 24),

              // Workout Schedule
              const SectionHeader(title: 'Workout Schedule'),
              Text(
                'Select which days you\'ll workout and when during the day:',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 8),
              ...List.generate(planProvider.days, (i) {
                final timing = planProvider.workoutSchedule[i];
                final isWorkout = timing != null;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 80,
                        child: Text('Day ${i + 1}'),
                      ),
                      Expanded(
                        child: SegmentedButton<String?>(
                          segments: const [
                            ButtonSegment(
                              value: null,
                              label: Text('Rest day'),
                            ),
                            ButtonSegment(
                              value: 'morning',
                              label: Text('AM'),
                            ),
                            ButtonSegment(
                              value: 'afternoon',
                              label: Text('PM'),
                            ),
                          ],
                          selected: {isWorkout ? timing : null},
                          onSelectionChanged: (s) {
                            planProvider.setWorkoutDay(i, s.first);
                          },
                        ),
                      ),
                    ],
                  ),
                );
              }),
              const SizedBox(height: 4),
              Text(
                'Note: Workout timing affects calorie distribution in your meal plan',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
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
                  onPressed: planProvider.loading
                      ? null
                      : () => _generate(context),
                  icon: planProvider.loading
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                          ),
                        )
                      : const Icon(Icons.arrow_forward),
                  label: Text(planProvider.loading
                      ? 'Generating...'
                      : 'Generate Meal Plan'),
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

  void _generate(BuildContext context) {
    final profile = context.read<ProfileProvider>().profile;
    final planProvider = context.read<MealPlanProvider>();

    // Build schedule from meals per day
    final schedule = <String, int>{};
    final mealTimes = ['08:00', '12:00', '15:00', '18:00', '20:00', '22:00', '07:00', '10:00'];
    for (int i = 0; i < planProvider.mealsPerDay && i < mealTimes.length; i++) {
      schedule[mealTimes[i]] = 3; // default busyness
    }

    final request = PlanRequest(
      dailyCalories: profile.calories.round(),
      dailyProteinG: profile.proteinG,
      dailyFatGMin: profile.fatG * 0.9,
      dailyFatGMax: profile.fatG * 1.1,
      schedule: schedule,
      allergies: profile.allergies,
    );

    final shell = context.findAncestorStateOfType<AppShellState>();
    planProvider.generatePlan(request).then((_) {
      if (planProvider.mealPlan != null) {
        shell?.navigateTo(5);
      }
    });
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
