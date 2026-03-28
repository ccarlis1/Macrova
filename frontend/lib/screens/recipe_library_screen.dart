import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/recipe_builder_coordinator.dart';
import '../providers/recipe_provider.dart';
import '../widgets/app_shell.dart';
import '../widgets/recipe_card.dart';

class RecipeLibraryScreen extends StatelessWidget {
  const RecipeLibraryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final recipeProvider = context.watch<RecipeProvider>();
    final recipes = recipeProvider.recipes;
    final minScrollHeight = MediaQuery.sizeOf(context).height * 0.5;

    return Column(
      children: [
        if (recipeProvider.syncLoading)
          const LinearProgressIndicator(minHeight: 2),
        if (recipeProvider.syncError != null)
          Material(
            color: Theme.of(context).colorScheme.errorContainer,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  Icon(
                    Icons.cloud_off_outlined,
                    color: Theme.of(context).colorScheme.onErrorContainer,
                    size: 22,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Could not refresh server recipes: ${recipeProvider.syncError}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color:
                                Theme.of(context).colorScheme.onErrorContainer,
                          ),
                    ),
                  ),
                  TextButton(
                    onPressed: () => recipeProvider.syncSummariesFromApi(),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            ),
          ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: recipeProvider.syncSummariesFromApi,
            child: recipes.isEmpty && !recipeProvider.syncLoading
                ? ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: [
                      SizedBox(
                        height: minScrollHeight,
                        child: Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.menu_book_outlined,
                                size: 64,
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSurfaceVariant,
                              ),
                              const SizedBox(height: 16),
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 24),
                                child: Text(
                                  'No recipes yet. Create your first recipe or '
                                  'pull to refresh if the server has a recipe pool.',
                                  textAlign: TextAlign.center,
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodyLarge
                                      ?.copyWith(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .onSurfaceVariant,
                                      ),
                                ),
                              ),
                              const SizedBox(height: 16),
                              FilledButton.icon(
                                onPressed: () {
                                  context
                                      .read<RecipeBuilderCoordinator>()
                                      .startCreate();
                                  final shell = context
                                      .findAncestorStateOfType<AppShellState>();
                                  shell?.navigateTo(2);
                                },
                                icon: const Icon(Icons.add),
                                label: const Text('Create Recipe'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  )
                : LayoutBuilder(
                    builder: (context, constraints) {
                      final crossCount = constraints.maxWidth > 900
                          ? 3
                          : constraints.maxWidth > 600
                              ? 2
                              : 1;

                      return GridView.builder(
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.all(24),
                        gridDelegate:
                            SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: crossCount,
                          mainAxisSpacing: 16,
                          crossAxisSpacing: 16,
                          childAspectRatio: 0.75,
                        ),
                        itemCount: recipes.length,
                        itemBuilder: (context, i) {
                          final recipe = recipes[i];
                          return RecipeCard(
                            recipe: recipe,
                            onView: () {
                              context
                                  .read<RecipeBuilderCoordinator>()
                                  .openForEdit(recipe);
                              final shell = context
                                  .findAncestorStateOfType<AppShellState>();
                              shell?.navigateTo(2);
                            },
                          );
                        },
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }
}
