import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/recipe_provider.dart';
import '../widgets/app_shell.dart';
import '../widgets/recipe_card.dart';
import 'recipe_builder_screen.dart';

class RecipeLibraryScreen extends StatelessWidget {
  const RecipeLibraryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final recipes = context.watch<RecipeProvider>().recipes;

    if (recipes.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.menu_book_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'No recipes yet. Create your first recipe!',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () {
                // Navigate to Recipe Builder (index 2)
                final shell =
                    context.findAncestorStateOfType<AppShellState>();
                shell?.navigateTo(2);
              },
              icon: const Icon(Icons.add),
              label: const Text('Create Recipe'),
            ),
          ],
        ),
      );
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        final crossCount = constraints.maxWidth > 900
            ? 3
            : constraints.maxWidth > 600
                ? 2
                : 1;

        return GridView.builder(
          padding: const EdgeInsets.all(24),
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
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
                // Navigate to Recipe Builder and load the recipe
                final shell =
                    context.findAncestorStateOfType<AppShellState>();
                shell?.navigateTo(2);
                // Find the RecipeBuilderScreen state and load the recipe
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  final builderState = context
                      .findAncestorStateOfType<RecipeBuilderScreenState>();
                  builderState?.loadRecipe(recipe);
                });
              },
            );
          },
        );
      },
    );
  }
}
