import 'package:flutter/material.dart';

import '../models/models.dart';

class MealPlanScreen extends StatelessWidget {
  const MealPlanScreen({super.key});

  Color adherenceColor(double pct) {
    if (pct >= 90) {
      return Colors.green;
    }
    if (pct >= 80) {
      return Colors.amber;
    }
    return Colors.red;
  }

  String _mealTypeLabel(String mealType) {
    if (mealType.isEmpty) {
      return mealType;
    }
    return mealType[0].toUpperCase() + mealType.substring(1);
  }

  Widget _macroCell({
    required BuildContext context,
    required String macro,
    required String actual,
    required String target,
    required double adherence,
  }) {
    final color = adherenceColor(adherence);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(macro, style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 6),
          Text('Actual: $actual'),
          Text('Target: $target'),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              '${adherence.toStringAsFixed(1)}%',
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _mealMacroGrid(Meal meal) {
    final items = <Map<String, String>>[
      {
        'label': 'Calories',
        'value': '${meal.nutrition.calories.toStringAsFixed(0)} kcal',
      },
      {
        'label': 'Protein',
        'value': '${meal.nutrition.proteinG.toStringAsFixed(1)} g',
      },
      {
        'label': 'Fat',
        'value': '${meal.nutrition.fatG.toStringAsFixed(1)} g',
      },
      {
        'label': 'Carbs',
        'value': '${meal.nutrition.carbsG.toStringAsFixed(1)} g',
      },
    ];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: items
          .map(
            (item) => Container(
              width: 148,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.grey.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item['label']!, style: const TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Text(item['value']!),
                ],
              ),
            ),
          )
          .toList(),
    );
  }

  Widget _buildMealCard(BuildContext context, Meal meal) {
    final recipe = meal.recipe;
    final recipeName = recipe['name']?.toString() ?? 'Recipe';
    final cookTime = recipe['cooking_time_minutes']?.toString() ?? '-';
    final ingredients = (recipe['ingredients'] as List<dynamic>? ?? const <dynamic>[]);
    final instructions = (recipe['instructions'] as List<dynamic>? ?? const <dynamic>[]);

    return Card(
      elevation: 1.5,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.restaurant_menu, color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _mealTypeLabel(meal.mealType).toUpperCase(),
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Text('$cookTime min'),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              recipeName,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 12),
            const Divider(),
            const SizedBox(height: 8),
            Text('Ingredients', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 6),
            if (ingredients.isEmpty)
              const Text('No ingredients listed')
            else
              Column(
                children: ingredients
                    .map(
                      (item) => ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Text('•', style: TextStyle(fontSize: 18)),
                        title: Text(item['display']?.toString() ?? ''),
                      ),
                    )
                    .toList(),
              ),
            const SizedBox(height: 8),
            if (instructions.isNotEmpty) ...[
              const Divider(),
              const SizedBox(height: 8),
              Text('Instructions', style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 6),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: List.generate(instructions.length, (index) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text('${index + 1}. ${instructions[index]}'),
                  );
                }),
              ),
            ],
            const SizedBox(height: 12),
            const Divider(),
            const SizedBox(height: 8),
            Text('Per-Meal Macros', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            _mealMacroGrid(meal),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final MealPlan? mealPlan =
        ModalRoute.of(context)?.settings.arguments as MealPlan?;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meal Plan Results'),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final maxWidth = constraints.maxWidth > 700 ? 700.0 : double.infinity;
          if (mealPlan == null) {
            return Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: maxWidth),
                child: const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('No plan loaded'),
                ),
              ),
            );
          }

          final total = mealPlan.totalNutrition;
          final goals = mealPlan.goals;
          final adherence = mealPlan.targetAdherence;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Center(
              child: ConstrainedBox(
                constraints: BoxConstraints(maxWidth: maxWidth),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  mealPlan.meetsGoals
                                      ? Icons.check_circle
                                      : Icons.warning_amber_rounded,
                                  color: mealPlan.meetsGoals
                                      ? Colors.green
                                      : Colors.amber.shade800,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    mealPlan.success
                                        ? 'Daily Summary - Plan Generated'
                                        : 'Daily Summary - Needs Attention',
                                    style: Theme.of(context).textTheme.titleMedium,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            LayoutBuilder(
                              builder: (context, innerConstraints) {
                                final isWide = innerConstraints.maxWidth >= 520;
                                final cellWidth = isWide
                                    ? (innerConstraints.maxWidth - 8) / 2
                                    : innerConstraints.maxWidth;
                                return Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: [
                                    SizedBox(
                                      width: cellWidth,
                                      child: _macroCell(
                                        context: context,
                                        macro: 'Calories',
                                        actual: '${total.calories.toStringAsFixed(0)} kcal',
                                        target: '${goals.calories} kcal',
                                        adherence: adherence['calories'] ?? 0,
                                      ),
                                    ),
                                    SizedBox(
                                      width: cellWidth,
                                      child: _macroCell(
                                        context: context,
                                        macro: 'Protein',
                                        actual: '${total.proteinG.toStringAsFixed(1)} g',
                                        target: '${goals.proteinG.toStringAsFixed(1)} g',
                                        adherence: adherence['protein'] ?? 0,
                                      ),
                                    ),
                                    SizedBox(
                                      width: cellWidth,
                                      child: _macroCell(
                                        context: context,
                                        macro: 'Fat',
                                        actual: '${total.fatG.toStringAsFixed(1)} g',
                                        target:
                                            '${goals.fatGMin.toStringAsFixed(1)}-${goals.fatGMax.toStringAsFixed(1)} g',
                                        adherence: adherence['fat'] ?? 0,
                                      ),
                                    ),
                                    SizedBox(
                                      width: cellWidth,
                                      child: _macroCell(
                                        context: context,
                                        macro: 'Carbs',
                                        actual: '${total.carbsG.toStringAsFixed(1)} g',
                                        target: '${goals.carbsG.toStringAsFixed(1)} g',
                                        adherence: adherence['carbs'] ?? 0,
                                      ),
                                    ),
                                  ],
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                    ),
                    if (mealPlan.warnings.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Card(
                        color: Theme.of(context).colorScheme.errorContainer,
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Text(
                            '⚠️ Warnings: ${mealPlan.warnings.join(' | ')}',
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onErrorContainer,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    ListView.separated(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: mealPlan.meals.length,
                      itemBuilder: (context, index) {
                        return _buildMealCard(context, mealPlan.meals[index]);
                      },
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                    ),
                    const SizedBox(height: 16),
                    LayoutBuilder(
                      builder: (context, innerConstraints) {
                        final useRow = innerConstraints.maxWidth >= 420;
                        if (useRow) {
                          return Row(
                            children: [
                              Expanded(
                                child: ElevatedButton.icon(
                                  onPressed: () => Navigator.pop(context),
                                  icon: const Icon(Icons.refresh),
                                  label: const Text('Re-generate'),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: OutlinedButton.icon(
                                  onPressed: () {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('Share coming soon')),
                                    );
                                  },
                                  icon: const Icon(Icons.share),
                                  label: const Text('Share'),
                                ),
                              ),
                            ],
                          );
                        }

                        return Column(
                          children: [
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                onPressed: () => Navigator.pop(context),
                                icon: const Icon(Icons.refresh),
                                label: const Text('Re-generate'),
                              ),
                            ),
                            const SizedBox(height: 10),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                onPressed: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(content: Text('Share coming soon')),
                                  );
                                },
                                icon: const Icon(Icons.share),
                                label: const Text('Share'),
                              ),
                            ),
                          ],
                        );
                      },
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
