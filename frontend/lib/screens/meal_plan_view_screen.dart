import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../widgets/macro_display.dart';
import '../widgets/meal_card.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/section_header.dart';

class MealPlanViewScreen extends StatefulWidget {
  const MealPlanViewScreen({super.key});

  @override
  State<MealPlanViewScreen> createState() => _MealPlanViewScreenState();
}

class _MealPlanViewScreenState extends State<MealPlanViewScreen> {
  bool _showCalendar = false;

  @override
  Widget build(BuildContext context) {
    final planProvider = context.watch<MealPlanProvider>();
    final mealPlan = planProvider.mealPlan;
    final profile = context.watch<ProfileProvider>().profile;

    if (mealPlan == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.view_list_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'Generate a plan from the Planner tab',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      );
    }

    final totalNutrition = mealPlan.totalNutrition;
    final meals = mealPlan.meals;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 800),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // View toggle
              Row(
                children: [
                  Text(
                    'Meal Plan View',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const Spacer(),
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(
                        value: false,
                        label: Text('Daily List'),
                      ),
                      ButtonSegment(
                        value: true,
                        label: Text('Calendar'),
                      ),
                    ],
                    selected: {_showCalendar},
                    onSelectionChanged: (s) =>
                        setState(() => _showCalendar = s.first),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              if (_showCalendar) ...[
                Center(
                  child: Text(
                    'Calendar view coming soon',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: Theme.of(context)
                              .colorScheme
                              .onSurfaceVariant,
                        ),
                  ),
                ),
              ] else ...[
                // Weekly Totals
                _buildWeeklyTotals(context, totalNutrition),
                const SizedBox(height: 16),

                // Weekly Micronutrient Totals
                _buildWeeklyMicronutrients(context, profile),
                const SizedBox(height: 24),

                // Daily Breakdown
                _buildDailyBreakdown(context, meals, totalNutrition),
              ],

              if (mealPlan.warnings.isNotEmpty) ...[
                const SizedBox(height: 24),
                const SectionHeader(title: 'Warnings'),
                ...mealPlan.warnings.map((w) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.warning_amber,
                              size: 16,
                              color: Theme.of(context).colorScheme.error),
                          const SizedBox(width: 8),
                          Expanded(child: Text(w)),
                        ],
                      ),
                    )),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWeeklyTotals(
      BuildContext context, dynamic totalNutrition) {
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
            Text('Daily Totals',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            MacroDisplay(
              calories: totalNutrition.calories,
              proteinG: totalNutrition.proteinG,
              carbsG: totalNutrition.carbsG,
              fatG: totalNutrition.fatG,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeeklyMicronutrients(
      BuildContext context, dynamic profile) {
    final goals = profile.micronutrientGoals;
    final hasGoals = goals.vitaminAUg > 0 ||
        goals.vitaminCMg > 0 ||
        goals.ironMg > 0 ||
        goals.calciumMg > 0 ||
        goals.fiberG > 0 ||
        goals.sodiumMg > 0;

    if (!hasGoals) return const SizedBox.shrink();

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
            Text('Micronutrient Targets',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Based on your profile goals',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 12),
            if (goals.fiberG > 0)
              MicronutrientBar(
                label: 'Fiber',
                value: 0,
                target: goals.fiberG,
                unit: 'g',
              ),
            if (goals.vitaminAUg > 0)
              MicronutrientBar(
                label: 'Vitamin A',
                value: 0,
                target: goals.vitaminAUg,
                unit: 'mcg',
              ),
            if (goals.vitaminCMg > 0)
              MicronutrientBar(
                label: 'Vitamin C',
                value: 0,
                target: goals.vitaminCMg,
                unit: 'mg',
              ),
            if (goals.ironMg > 0)
              MicronutrientBar(
                label: 'Iron',
                value: 0,
                target: goals.ironMg,
                unit: 'mg',
              ),
            if (goals.calciumMg > 0)
              MicronutrientBar(
                label: 'Calcium',
                value: 0,
                target: goals.calciumMg,
                unit: 'mg',
              ),
            if (goals.sodiumMg > 0)
              MicronutrientBar(
                label: 'Sodium',
                value: 0,
                target: goals.sodiumMg,
                unit: 'mg',
                isLimit: true,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildDailyBreakdown(
      BuildContext context, List meals, dynamic totalNutrition) {
    if (meals.isEmpty) {
      return Center(
        child: Text(
          'No meals in this plan',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Day 1',
          action: Text(
            '${totalNutrition.calories.round()} kcal \u2022 '
            '${totalNutrition.proteinG.round()}g P \u2022 '
            '${totalNutrition.carbsG.round()}g C \u2022 '
            '${totalNutrition.fatG.round()}g F',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        ...meals.map((meal) {
          final recipeName =
              meal.recipe['name'] as String? ?? 'Unknown Recipe';
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: MealCard(
              mealType: meal.mealType,
              recipeName: recipeName,
              calories: meal.nutrition.calories,
              proteinG: meal.nutrition.proteinG,
              carbsG: meal.nutrition.carbsG,
              fatG: meal.nutrition.fatG,
            ),
          );
        }),
      ],
    );
  }
}
