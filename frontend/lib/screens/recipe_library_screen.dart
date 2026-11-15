import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/recipe.dart';
import '../providers/recipe_builder_coordinator.dart';
import '../providers/recipe_provider.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/app_shell.dart';
import '../widgets/empty_state.dart';
import '../widgets/recipe_card.dart';
import '../widgets/section_header.dart';
import '../widgets/starter_pack_sheet.dart';

class RecipeLibraryScreen extends StatelessWidget {
  const RecipeLibraryScreen({super.key});

  static const syncRejectionsKey = Key('recipe_library_sync_rejections');

  /// Header action that opens the starter pack (FE-16).
  static const starterPackKey = Key('recipe_library_starter_pack');

  /// Empty-state affordances (FE-16).
  static const emptyStarterPackKey = Key('recipe_library_empty_starter_pack');
  static const emptyBuildKey = Key('recipe_library_empty_build');

  @override
  Widget build(BuildContext context) {
    final recipeProvider = context.watch<RecipeProvider>();
    final recipes = recipeProvider.recipes;
    final minScrollHeight = MediaQuery.sizeOf(context).height * 0.5;

    void openCreate() {
      context.read<RecipeBuilderCoordinator>().startCreate();
      final shell = context.findAncestorStateOfType<AppShellState>();
      shell?.navigateTo(3);
    }

    void openStarterPack() => StarterPackSheet.show(context);

    void openRecipe(Recipe recipe) {
      context.read<RecipeBuilderCoordinator>().openForEdit(recipe);
      final shell = context.findAncestorStateOfType<AppShellState>();
      shell?.navigateTo(3);
    }

    return Column(
      children: [
        if (recipeProvider.syncLoading)
          const LinearProgressIndicator(minHeight: 2),
        if (recipeProvider.syncError != null)
          _SyncErrorBanner(
            message: recipeProvider.syncError!,
            onRetry: recipeProvider.syncSummariesFromApi,
          ),
        // Per-recipe sync rejections (BE-19). Whole-request failures keep
        // using the banner above.
        if (recipeProvider.recipeSyncErrors.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              MacrovaSpacing.screenGutter,
              MacrovaSpacing.md,
              MacrovaSpacing.screenGutter,
              0,
            ),
            child: AdvisoryCard(
              key: syncRejectionsKey,
              variant: AdvisoryVariant.warn,
              title: recipeProvider.recipeSyncErrors.length == 1
                  ? 'A recipe was not saved to the server'
                  : '${recipeProvider.recipeSyncErrors.length} recipes were '
                      'not saved to the server',
              description: [
                'Saved on this device only; the planner can\'t use '
                    '${recipeProvider.recipeSyncErrors.length == 1 ? 'it' : 'them'} '
                    'until fixed and saved again.',
                for (final e in recipeProvider.recipeSyncErrors) e.displayText,
              ].join('\n'),
            ),
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: recipeProvider.syncSummariesFromApi,
            child: recipes.isEmpty && !recipeProvider.syncLoading
                ? _EmptyLibrary(
                    minScrollHeight: minScrollHeight,
                    onCreate: openCreate,
                    onStarterPack: openStarterPack,
                  )
                : _RecipeGrid(
                    recipes: recipes,
                    onView: openRecipe,
                    onCreate: openCreate,
                    onStarterPack: openStarterPack,
                    isFavorite: recipeProvider.isFavorite,
                    onFavorite: recipeProvider.toggleFavorite,
                  ),
          ),
        ),
      ],
    );
  }
}

/// Token-styled inline advisory row for a recipe-sync failure, preserving the
/// Retry action that re-runs [RecipeProvider.syncSummariesFromApi].
class _SyncErrorBanner extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const _SyncErrorBanner({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: MacrovaSpacing.screenGutter,
        vertical: MacrovaSpacing.md,
      ),
      decoration: BoxDecoration(
        color: tokens.accentSoft,
        border: Border(bottom: BorderSide(color: tokens.lineDefault)),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_off_outlined, color: tokens.accentDeep, size: 20),
          const SizedBox(width: MacrovaSpacing.md),
          Expanded(
            child: Text(
              'Could not refresh server recipes: $message',
              style: MacrovaTypography.caption(tokens.inkSecondary),
            ),
          ),
          const SizedBox(width: MacrovaSpacing.sm),
          TextButton(
            onPressed: () => onRetry(),
            child: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}

/// Scrollable empty state (keeps pull-to-refresh): start from the starter
/// pack (FE-16) or build a recipe in the Recipe Builder via [startCreate].
class _EmptyLibrary extends StatelessWidget {
  final double minScrollHeight;
  final VoidCallback onCreate;
  final VoidCallback onStarterPack;

  const _EmptyLibrary({
    required this.minScrollHeight,
    required this.onCreate,
    required this.onStarterPack,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(
        horizontal: MacrovaSpacing.screenGutter,
      ),
      children: [
        ConstrainedBox(
          constraints: BoxConstraints(minHeight: minScrollHeight),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: MacrovaSpacing.mobileMaxWidth,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  EmptyState(
                    key: RecipeLibraryScreen.emptyStarterPackKey,
                    icon: Icons.inventory_2_outlined,
                    label: 'Start from the starter pack',
                    onTap: onStarterPack,
                  ),
                  const SizedBox(height: MacrovaSpacing.md),
                  EmptyState(
                    key: RecipeLibraryScreen.emptyBuildKey,
                    icon: Icons.menu_book_outlined,
                    label: 'Build a recipe',
                    onTap: onCreate,
                  ),
                  const SizedBox(height: MacrovaSpacing.md),
                  Text(
                    'No recipes yet. Pick the ones you would eat from the '
                    'starter pack, build your own, or pull to refresh.',
                    textAlign: TextAlign.center,
                    style: MacrovaTypography.caption(tokens.inkTertiary),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Recipe library body: a featured hero on wider layouts plus a responsive
/// grid of standard recipe cards. Visual only — every card routes through the
/// same [RecipeBuilderCoordinator.openForEdit] path.
class _RecipeGrid extends StatelessWidget {
  final List<Recipe> recipes;
  final void Function(Recipe recipe) onView;
  final VoidCallback onCreate;
  final VoidCallback onStarterPack;
  final bool Function(String recipeId) isFavorite;
  final Future<void> Function(String recipeId) onFavorite;

  const _RecipeGrid({
    required this.recipes,
    required this.onView,
    required this.onCreate,
    required this.onStarterPack,
    required this.isFavorite,
    required this.onFavorite,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final crossCount = constraints.maxWidth > 900
            ? 3
            : constraints.maxWidth > 600
                ? 2
                : 1;

        final showHero = crossCount > 1 && recipes.length > 2;
        final featured = showHero ? recipes.first : null;
        final gridRecipes = showHero ? recipes.sublist(1) : recipes;

        return CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                MacrovaSpacing.xlAlt,
                MacrovaSpacing.xlAlt,
                MacrovaSpacing.xlAlt,
                0,
              ),
              sliver: SliverToBoxAdapter(
                child: SectionHeader(
                  title: 'Recipes',
                  subtitle:
                      '${recipes.length} recipe${recipes.length == 1 ? '' : 's'}',
                  linkLabel: 'New',
                  onLink: onCreate,
                  action: TextButton.icon(
                    key: RecipeLibraryScreen.starterPackKey,
                    onPressed: onStarterPack,
                    icon: const Icon(Icons.inventory_2_outlined, size: 18),
                    label: const Text('Starter pack'),
                  ),
                ),
              ),
            ),
            if (featured != null)
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                  MacrovaSpacing.xlAlt,
                  0,
                  MacrovaSpacing.xlAlt,
                  MacrovaSpacing.lg,
                ),
                sliver: SliverToBoxAdapter(
                  child: RecipeCard.hero(
                    recipe: featured,
                    badge: 'Featured',
                    isFavorite: isFavorite(featured.id),
                    onFavorite: () => onFavorite(featured.id),
                    description: isFavorite(featured.id)
                        ? 'Saved on this device'
                        : null,
                    onView: () => onView(featured),
                  ),
                ),
              ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                MacrovaSpacing.xlAlt,
                0,
                MacrovaSpacing.xlAlt,
                MacrovaSpacing.xlAlt,
              ),
              sliver: SliverGrid(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: crossCount,
                  mainAxisSpacing: MacrovaSpacing.lg,
                  crossAxisSpacing: MacrovaSpacing.lg,
                  childAspectRatio: 0.75,
                ),
                delegate: SliverChildBuilderDelegate(
                  (context, i) {
                    final recipe = gridRecipes[i];
                    return RecipeCard(
                      recipe: recipe,
                      onView: () => onView(recipe),
                    );
                  },
                  childCount: gridRecipes.length,
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}
