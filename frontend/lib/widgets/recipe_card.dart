import 'package:flutter/material.dart';

import '../models/recipe.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';

enum RecipeCardVariant { standard, hero, row, mini }

class RecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;
  final RecipeCardVariant variant;
  final String? badge;

  /// Local UI only until backend-contract-auditor confirms a favorites tag
  /// write path (see redesign plan PR14).
  final bool isFavorite;
  final VoidCallback? onFavorite;

  /// Caller-supplied URL only — [Recipe] has no image field yet; use gradient
  /// fallback when null/empty until backend confirms an image contract.
  final String? imageUrl;
  final String? subtitle;
  final String? description;

  const RecipeCard({
    super.key,
    required this.recipe,
    this.onView,
  })  : variant = RecipeCardVariant.standard,
        badge = null,
        isFavorite = false,
        onFavorite = null,
        imageUrl = null,
        subtitle = null,
        description = null;

  const RecipeCard.hero({
    super.key,
    required this.recipe,
    this.onView,
    this.badge,
    this.isFavorite = false,
    this.onFavorite,
    this.imageUrl,
    this.subtitle,
    this.description,
  }) : variant = RecipeCardVariant.hero;

  const RecipeCard.row({
    super.key,
    required this.recipe,
    this.onView,
    this.imageUrl,
    this.subtitle,
  })  : variant = RecipeCardVariant.row,
        badge = null,
        isFavorite = false,
        onFavorite = null,
        description = null;

  const RecipeCard.mini({
    super.key,
    required this.recipe,
    this.onView,
    this.imageUrl,
    this.subtitle,
  })  : variant = RecipeCardVariant.mini,
        badge = null,
        isFavorite = false,
        onFavorite = null,
        description = null;

  @override
  Widget build(BuildContext context) {
    return switch (variant) {
      RecipeCardVariant.standard => _StandardRecipeCard(
          recipe: recipe,
          onView: onView,
        ),
      RecipeCardVariant.hero => _HeroRecipeCard(
          recipe: recipe,
          onView: onView,
          badge: badge,
          isFavorite: isFavorite,
          onFavorite: onFavorite,
          imageUrl: imageUrl,
          subtitle: subtitle,
          description: description,
        ),
      RecipeCardVariant.row => _RowRecipeCard(
          recipe: recipe,
          onView: onView,
          imageUrl: imageUrl,
          subtitle: subtitle,
        ),
      RecipeCardVariant.mini => _MiniRecipeCard(
          recipe: recipe,
          onView: onView,
          imageUrl: imageUrl,
          subtitle: subtitle,
        ),
    };
  }
}

class _RecipeThumbnail extends StatelessWidget {
  final MacrovaTokens tokens;
  final String? imageUrl;
  final double? width;
  final double height;
  final BorderRadius borderRadius;

  const _RecipeThumbnail({
    required this.tokens,
    this.imageUrl,
    this.width,
    required this.height,
    required this.borderRadius,
  });

  @override
  Widget build(BuildContext context) {
    final gradient = LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        tokens.accentTint,
        tokens.accent.withValues(alpha: 0.55),
      ],
    );

    Widget child;
    if (imageUrl != null && imageUrl!.isNotEmpty) {
      child = Image.network(
        imageUrl!,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => _fallbackIcon(),
      );
    } else {
      child = _fallbackIcon();
    }

    return Container(
      width: width,
      height: height,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        gradient: imageUrl == null || imageUrl!.isEmpty ? gradient : null,
        borderRadius: borderRadius,
      ),
      child: child,
    );
  }

  Widget _fallbackIcon() {
    final iconSize = height.isFinite ? (height * 0.35).clamp(20.0, 48.0) : 32.0;
    return Center(
      child: Icon(
        Icons.restaurant,
        size: iconSize,
        color: tokens.inkQuaternary,
      ),
    );
  }
}

class _StandardRecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;

  const _StandardRecipeCard({
    required this.recipe,
    required this.onView,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderMd,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _RecipeThumbnail(
            tokens: tokens,
            height: 120,
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(MacrovaRadius.md),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(MacrovaSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  recipe.name,
                  style: Theme.of(context).textTheme.titleSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: MacrovaSpacing.xs),
                Text(
                  recipe.ingredients.isEmpty
                      ? 'No local nutrition data — add ingredients in the builder'
                      : '${recipe.servings} servings \u2022 ${recipe.totalCalories.round()} kcal total',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: tokens.inkTertiary,
                      ),
                ),
                const SizedBox(height: MacrovaSpacing.sm),
                if (recipe.ingredients.isEmpty)
                  Text(
                    'Server or draft recipe',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: tokens.inkQuaternary,
                        ),
                  )
                else
                  MacroDisplay(
                    calories: recipe.perServingCalories,
                    proteinG: recipe.perServingProteinG,
                    carbsG: recipe.perServingCarbsG,
                    fatG: recipe.perServingFatG,
                    compact: true,
                  ),
                const SizedBox(height: MacrovaSpacing.sm),
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

class _HeroRecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;
  final String? badge;
  final bool isFavorite;
  final VoidCallback? onFavorite;
  final String? imageUrl;
  final String? subtitle;
  final String? description;

  const _HeroRecipeCard({
    required this.recipe,
    required this.onView,
    required this.badge,
    required this.isFavorite,
    required this.onFavorite,
    required this.imageUrl,
    required this.subtitle,
    required this.description,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final meta = subtitle ??
        '${recipe.servings} servings \u2022 ${recipe.perServingCalories.round()} kcal';

    return Card(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderMd,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: InkWell(
        onTap: onView,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AspectRatio(
              aspectRatio: 16 / 10,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  _RecipeThumbnail(
                    tokens: tokens,
                    imageUrl: imageUrl,
                    height: double.infinity,
                    borderRadius: BorderRadius.zero,
                  ),
                  if (badge != null)
                    Positioned(
                      top: MacrovaSpacing.md,
                      left: MacrovaSpacing.md,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: MacrovaSpacing.sm,
                          vertical: MacrovaSpacing.xs,
                        ),
                        decoration: BoxDecoration(
                          color: tokens.inkPrimary.withValues(alpha: 0.75),
                          borderRadius: MacrovaRadius.borderPill,
                        ),
                        child: Text(
                          badge!,
                          style: MacrovaTypography.caption(MacrovaColors.onDarkFill),
                        ),
                      ),
                    ),
                  if (onFavorite != null)
                    Positioned(
                      top: MacrovaSpacing.sm,
                      right: MacrovaSpacing.sm,
                      child: IconButton(
                        onPressed: onFavorite,
                        icon: Icon(
                          isFavorite ? Icons.favorite : Icons.favorite_border,
                          color: isFavorite ? tokens.accent : MacrovaColors.onDarkFill,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(MacrovaSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    meta,
                    style: MacrovaTypography.caption(tokens.inkTertiary),
                  ),
                  const SizedBox(height: MacrovaSpacing.xs),
                  Text(
                    recipe.name,
                    style: MacrovaTypography.subtitle(tokens.inkPrimary),
                  ),
                  if (description != null) ...[
                    const SizedBox(height: MacrovaSpacing.sm),
                    Text(
                      description!,
                      style: MacrovaTypography.body(tokens.inkSecondary),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  const SizedBox(height: MacrovaSpacing.md),
                  Divider(color: tokens.lineSoft, height: 1),
                  const SizedBox(height: MacrovaSpacing.md),
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
    );
  }
}

class _RowRecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;
  final String? imageUrl;
  final String? subtitle;

  const _RowRecipeCard({
    required this.recipe,
    required this.onView,
    required this.imageUrl,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final sub = subtitle ??
        (recipe.ingredients.isEmpty
            ? 'No nutrition data'
            : '${recipe.servings} servings');

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderSm,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: InkWell(
        onTap: onView,
        borderRadius: MacrovaRadius.borderSm,
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.md),
          child: Row(
            children: [
              _RecipeThumbnail(
                tokens: tokens,
                imageUrl: imageUrl,
                width: 64,
                height: 64,
                borderRadius: MacrovaRadius.borderSm,
              ),
              const SizedBox(width: MacrovaSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recipe.name,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      sub,
                      style: MacrovaTypography.caption(tokens.inkTertiary),
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    '${recipe.perServingCalories.round()}',
                    style: MacrovaTypography.label(tokens.inkPrimary).copyWith(
                      fontFeatures: MacrovaTypography.tabularFigures,
                    ),
                  ),
                  Text(
                    'kcal',
                    style: MacrovaTypography.caption(tokens.inkTertiary),
                  ),
                  Text(
                    '${recipe.perServingProteinG.round()}g P',
                    style: MacrovaTypography.caption(tokens.macroProtein).copyWith(
                      fontFeatures: MacrovaTypography.tabularFigures,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MiniRecipeCard extends StatelessWidget {
  final Recipe recipe;
  final VoidCallback? onView;
  final String? imageUrl;
  final String? subtitle;

  const _MiniRecipeCard({
    required this.recipe,
    required this.onView,
    required this.imageUrl,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final sub = subtitle ??
        '${recipe.perServingCalories.round()} kcal';

    return SizedBox(
      width: 240,
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: MacrovaRadius.borderSm,
          side: BorderSide(color: tokens.lineDefault),
        ),
        child: InkWell(
          onTap: onView,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AspectRatio(
                aspectRatio: 4 / 3,
                child: _RecipeThumbnail(
                  tokens: tokens,
                  imageUrl: imageUrl,
                  height: double.infinity,
                  borderRadius: BorderRadius.zero,
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(MacrovaSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      recipe.name,
                      style: Theme.of(context).textTheme.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      sub,
                      style: MacrovaTypography.caption(tokens.inkTertiary),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
