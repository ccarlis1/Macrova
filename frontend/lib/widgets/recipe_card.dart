import 'package:flutter/material.dart';

import '../models/recipe.dart';
import 'macro_display.dart';

class RecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;

  const RecipeCard({
    super.key,
    required this.recipe,
    this.onView,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Image placeholder
          Container(
            height: 120,
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(12)),
            ),
            child: Center(
              child: Icon(
                Icons.restaurant,
                size: 40,
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  recipe.name,
                  style: Theme.of(context).textTheme.titleSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  '${recipe.servings} servings \u2022 ${recipe.totalCalories.round()} kcal total',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                ),
                const SizedBox(height: 8),
                MacroDisplay(
                  calories: recipe.perServingCalories,
                  proteinG: recipe.perServingProteinG,
                  carbsG: recipe.perServingCarbsG,
                  fatG: recipe.perServingFatG,
                  compact: true,
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: onView,
                    child: const Text('View'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
