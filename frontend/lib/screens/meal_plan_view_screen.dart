import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/micronutrient_metadata.dart';
import '../models/models.dart';
import '../models/user_profile.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../services/grocery_optimize_payload.dart';
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
  bool _groceryBusy = false;

  @override
  Widget build(BuildContext context) {
    final planProvider = context.watch<MealPlanProvider>();
    final mealPlan = planProvider.mealPlan;
    final profile = context.watch<ProfileProvider>().profile;
    final recipeProvider = context.watch<RecipeProvider>();

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
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton.tonalIcon(
                  onPressed: _groceryBusy
                      ? null
                      : () => _runGroceryOptimize(mealPlan, recipeProvider),
                  icon: _groceryBusy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.shopping_cart_outlined),
                  label: Text(_groceryBusy ? 'Building cart…' : 'Create optimal grocery cart'),
                ),
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
                // Plan-wide macro totals (whole horizon; multi-day = sum or weekly_totals)
                _buildWeeklyTotals(context, mealPlan.days, totalNutrition),
                const SizedBox(height: 16),

                // Plan micronutrients vs profile targets (daily × plan length)
                _buildWeeklyMicronutrients(context, profile, mealPlan),
                const SizedBox(height: 24),

                // Per-day breakdown from API daily_plans
                _buildDailyBreakdown(context, mealPlan),
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
      BuildContext context, int planDays, dynamic totalNutrition) {
    final title = planDays > 1 ? 'Plan totals' : 'Daily totals';
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
    BuildContext context,
    UserProfile profile,
    MealPlan mealPlan,
  ) {
    final goals = profile.micronutrientGoals;
    final microJson = goals.toJson();
    final hasGoals = microJson.values.any((v) => (v as num) > 0);

    if (!hasGoals) return const SizedBox.shrink();

    final actual = mealPlan.totalNutrition.micronutrients;
    final periodDays = mealPlan.days.clamp(1, 7);

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
              'Plan totals vs daily profile goals × $periodDays day(s)',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 12),
            for (final meta in kMicronutrientsInDisplayOrder) ...[
              if (((microJson[meta.key] as num?)?.toDouble() ?? 0) > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: MicronutrientBar(
                    label: meta.label,
                    value: actual[meta.key] ?? 0,
                    target:
                        (microJson[meta.key] as num).toDouble() * periodDays,
                    unit: meta.unit,
                    isLimit: meta.isLimit,
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildDailyBreakdown(BuildContext context, MealPlan mealPlan) {
    final days = mealPlan.dailyPlans;
    if (days.isEmpty ||
        days.every((d) => d.meals.isEmpty)) {
      return Center(
        child: Text(
          'No meals in this plan',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }

    final blocks = <Widget>[];
    for (final d in days) {
      if (d.meals.isEmpty) continue;
      blocks.add(
        SectionHeader(
          title: 'Day ${d.day}',
          action: Text(
            '${d.dayTotals.calories.round()} kcal \u2022 '
            '${d.dayTotals.proteinG.round()}g P \u2022 '
            '${d.dayTotals.carbsG.round()}g C \u2022 '
            '${d.dayTotals.fatG.round()}g F',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      );
      for (final meal in d.meals) {
        final recipeName =
            meal.recipe['name'] as String? ?? 'Unknown Recipe';
        blocks.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: MealCard(
              mealType: meal.mealType,
              recipeName: recipeName,
              calories: meal.nutrition.calories,
              proteinG: meal.nutrition.proteinG,
              carbsG: meal.nutrition.carbsG,
              fatG: meal.nutrition.fatG,
            ),
          ),
        );
      }
      blocks.add(const SizedBox(height: 16));
    }
    if (blocks.isNotEmpty) {
      blocks.removeLast();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: blocks,
    );
  }

  /// POST `/api/v1/grocery/optimize` via [ApiService.groceryOptimize] (multi-minute
  /// runs; client timeout and [ApiException] surfaced with [SnackBar]).
  Future<void> _runGroceryOptimize(
    MealPlan mealPlan,
    RecipeProvider recipes,
  ) async {
    final body = buildGroceryOptimizeRequestBody(
      mealPlan: mealPlan,
      recipes: recipes,
    );
    if (body == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not build a cart: ensure meals include recipe IDs and recipes have ingredients.',
          ),
        ),
      );
      return;
    }

    setState(() => _groceryBusy = true);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Searching stores for your ingredients — this can take a few minutes.',
          ),
          duration: Duration(seconds: 5),
        ),
      );
    }
    try {
      final res = await ApiService.groceryOptimize(body);
      if (!mounted) return;
      if (res['ok'] == true) {
        final r = res['result'];
        if (r is! Map<String, dynamic>) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Unexpected response shape.')),
          );
          return;
        }
        final ms = r['multiStoreOptimization'];
        final cost = ms is Map<String, dynamic> ? ms['totalCost'] : null;
        final cart = r['cartPlan'];
        final lines =
            cart is Map<String, dynamic> ? cart['lines'] as List<dynamic>? : null;
        final nLines = lines?.length ?? 0;
        await showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Grocery cart'),
            content: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'Estimated total: '
                    '${cost != null ? "\$${cost.toString()}" : "—"}',
                    style: Theme.of(ctx).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 8),
                  Text('$nLines cart line(s)'),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('OK'),
              ),
            ],
          ),
        );
      } else {
        final err = res['error'];
        final msg = err is Map && err['message'] is String
            ? err['message'] as String
            : 'Grocery optimizer failed';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(msg)),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _groceryBusy = false);
      }
    }
  }
}
