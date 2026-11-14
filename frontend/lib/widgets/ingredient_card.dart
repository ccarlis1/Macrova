import 'package:flutter/material.dart';

import '../models/ingredient.dart';
import '../theme/tokens.dart';
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

  Color _sourceColor(MacrovaTokens tokens) {
    switch (ingredient.source) {
      case IngredientSource.saved:
        return tokens.semanticSuccess;
      case IngredientSource.api:
        return tokens.macroProtein;
      case IngredientSource.custom:
        return tokens.accent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final sourceColor = _sourceColor(tokens);

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderSm,
        side: selected
            ? BorderSide(color: tokens.accent, width: 2)
            : BorderSide(color: tokens.lineDefault),
      ),
      child: InkWell(
        borderRadius: MacrovaRadius.borderSm,
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      ingredient.name,
                      style: MacrovaTypography.subtitle(tokens.inkPrimary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: MacrovaSpacing.sm - 2,
                      vertical: MacrovaSpacing.xs / 2,
                    ),
                    decoration: BoxDecoration(
                      color: sourceColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(MacrovaRadius.sm / 2),
                    ),
                    child: Text(
                      _sourceLabel,
                      style: MacrovaTypography.caption(sourceColor),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.sm),
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
