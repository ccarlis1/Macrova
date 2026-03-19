import 'package:flutter/material.dart';

import '../models/ingredient.dart';
import 'macro_display.dart';

class IngredientCard extends StatelessWidget {
  final Ingredient ingredient;
  final bool selected;
  final VoidCallback? onTap;

  const IngredientCard({
    super.key,
    required this.ingredient,
    this.selected = false,
    this.onTap,
  });

  String get _sourceLabel {
    switch (ingredient.source) {
      case IngredientSource.saved:
        return 'Saved';
      case IngredientSource.api:
        return 'API';
      case IngredientSource.custom:
        return 'Custom';
    }
  }

  Color _sourceColor(BuildContext context) {
    switch (ingredient.source) {
      case IngredientSource.saved:
        return Colors.green;
      case IngredientSource.api:
        return Colors.blue;
      case IngredientSource.custom:
        return Colors.purple;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: selected
            ? BorderSide(color: colorScheme.primary, width: 2)
            : BorderSide(color: colorScheme.outlineVariant),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      ingredient.name,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: _sourceColor(context).withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _sourceLabel,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: _sourceColor(context),
                          ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              MacroDisplay(
                calories: ingredient.caloriesPer100g,
                proteinG: ingredient.proteinPer100g,
                carbsG: ingredient.carbsPer100g,
                fatG: ingredient.fatPer100g,
                compact: true,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
