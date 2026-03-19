import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../models/recipe.dart';
import '../providers/ingredient_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../widgets/nutrition_totals_panel.dart';
import '../widgets/section_header.dart';

const _uuid = Uuid();

class RecipeBuilderScreen extends StatefulWidget {
  const RecipeBuilderScreen({super.key});

  @override
  State<RecipeBuilderScreen> createState() => RecipeBuilderScreenState();
}

class RecipeBuilderScreenState extends State<RecipeBuilderScreen> {
  final _nameCtrl = TextEditingController();
  final _servingsCtrl = TextEditingController(text: '1');
  List<RecipeIngredientEntry> _ingredients = [];
  String? _editingRecipeId;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _servingsCtrl.dispose();
    super.dispose();
  }

  void loadRecipe(Recipe recipe) {
    setState(() {
      _editingRecipeId = recipe.id;
      _nameCtrl.text = recipe.name;
      _servingsCtrl.text = recipe.servings.toString();
      _ingredients = List.from(recipe.ingredients);
    });
  }

  void _clear() {
    setState(() {
      _editingRecipeId = null;
      _nameCtrl.clear();
      _servingsCtrl.text = '1';
      _ingredients = [];
    });
  }

  void _addIngredient(Ingredient ing) {
    setState(() {
      _ingredients.add(RecipeIngredientEntry(
        ingredientId: ing.id,
        ingredientName: ing.name,
        quantity: 100,
        unit: 'g',
        caloriesPer100g: ing.caloriesPer100g,
        proteinPer100g: ing.proteinPer100g,
        carbsPer100g: ing.carbsPer100g,
        fatPer100g: ing.fatPer100g,
        micronutrientsPer100g: ing.micronutrientsPer100g,
        unitConversions: ing.unitConversions,
      ));
    });
  }

  void _removeIngredient(int index) {
    setState(() => _ingredients.removeAt(index));
  }

  void _updateQuantity(int index, double quantity) {
    setState(() {
      _ingredients[index] = _ingredients[index].copyWith(quantity: quantity);
    });
  }

  void _updateUnit(int index, String unit) {
    setState(() {
      _ingredients[index] = _ingredients[index].copyWith(unit: unit);
    });
  }

  Recipe _buildRecipe() {
    return Recipe(
      id: _editingRecipeId ?? _uuid.v4(),
      name: _nameCtrl.text.trim(),
      ingredients: List.from(_ingredients),
      servings: int.tryParse(_servingsCtrl.text.trim()) ?? 1,
    );
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Recipe name is required')),
      );
      return;
    }
    if (_ingredients.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add at least one ingredient')),
      );
      return;
    }

    final recipe = _buildRecipe();
    final recipeProvider = context.read<RecipeProvider>();

    if (_editingRecipeId != null) {
      await recipeProvider.updateRecipe(recipe);
    } else {
      await recipeProvider.addRecipe(recipe);
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Recipe "${recipe.name}" saved')),
      );
      _clear();
    }
  }

  void _showAddIngredientDialog() {
    final ingProvider = context.read<IngredientProvider>();
    final searchCtrl = TextEditingController();

    showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            final results = ingProvider.search(searchCtrl.text);

            return AlertDialog(
              title: const Text('Add Ingredient'),
              content: SizedBox(
                width: 400,
                height: 400,
                child: Column(
                  children: [
                    TextField(
                      controller: searchCtrl,
                      decoration: const InputDecoration(
                        hintText: 'Search ingredients...',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 8),
                    Expanded(
                      child: results.isEmpty
                          ? const Center(child: Text('No ingredients found'))
                          : ListView.builder(
                              itemCount: results.length,
                              itemBuilder: (_, i) {
                                final ing = results[i];
                                return ListTile(
                                  title: Text(ing.name),
                                  subtitle: Text(
                                    '${ing.caloriesPer100g.round()} kcal | '
                                    'P: ${ing.proteinPer100g.round()}g | '
                                    'C: ${ing.carbsPer100g.round()}g | '
                                    'F: ${ing.fatPer100g.round()}g',
                                  ),
                                  onTap: () {
                                    _addIngredient(ing);
                                    Navigator.of(ctx).pop();
                                  },
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final recipe = _buildRecipe();
    final profile = context.watch<ProfileProvider>().profile;
    final microTargets = profile.micronutrientGoals.toJson().map(
          (k, v) => MapEntry(k, (v as num).toDouble()),
        );

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 800;

        final builderPanel = SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionHeader(title: 'Recipe Builder'),
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Recipe Name'),
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 16),
              Text('Recipe Ingredients',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              ..._ingredients.asMap().entries.map((entry) {
                final i = entry.key;
                final ing = entry.value;
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                    side: BorderSide(
                      color: Theme.of(context).colorScheme.outlineVariant,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Expanded(
                          flex: 3,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(ing.ingredientName,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleSmall),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  SizedBox(
                                    width: 80,
                                    child: TextField(
                                      controller: TextEditingController(
                                        text: ing.quantity
                                            .toStringAsFixed(0),
                                      ),
                                      decoration: const InputDecoration(
                                        labelText: 'Qty',
                                      ),
                                      keyboardType: TextInputType.number,
                                      onChanged: (v) {
                                        final qty =
                                            double.tryParse(v) ?? 0;
                                        _updateQuantity(i, qty);
                                      },
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  DropdownButton<String>(
                                    value: ing.unit,
                                    items: ing.availableUnits
                                        .map((u) => DropdownMenuItem(
                                              value: u,
                                              child: Text(u),
                                            ))
                                        .toList(),
                                    onChanged: (v) {
                                      if (v != null) _updateUnit(i, v);
                                    },
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Text(
                              '${ing.calories.round()} kcal',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .primary,
                                  ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete_outline,
                                  size: 20),
                              onPressed: () => _removeIngredient(i),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              }),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _showAddIngredientDialog,
                icon: const Icon(Icons.add),
                label: const Text('Add Ingredient'),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _servingsCtrl,
                decoration: const InputDecoration(
                  labelText: 'Number of Servings',
                ),
                keyboardType: TextInputType.number,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  OutlinedButton(
                    onPressed: _clear,
                    child: const Text('Clear Recipe'),
                  ),
                  const SizedBox(width: 12),
                  FilledButton(
                    onPressed: _save,
                    child: const Text('Save Recipe'),
                  ),
                ],
              ),
            ],
          ),
        );

        final totalsPanel = SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: NutritionTotalsPanel(
            title: 'Live Nutrition Totals',
            calories: recipe.totalCalories,
            proteinG: recipe.totalProteinG,
            carbsG: recipe.totalCarbsG,
            fatG: recipe.totalFatG,
            perServingCalories: recipe.perServingCalories,
            perServingProteinG: recipe.perServingProteinG,
            perServingCarbsG: recipe.perServingCarbsG,
            perServingFatG: recipe.perServingFatG,
            servings: recipe.servings,
            micronutrients: recipe.totalMicronutrients,
            micronutrientTargets: microTargets,
          ),
        );

        if (wide) {
          return Row(
            children: [
              Expanded(flex: 3, child: builderPanel),
              const VerticalDivider(width: 1),
              Expanded(flex: 2, child: totalsPanel),
            ],
          );
        } else {
          return SingleChildScrollView(
            child: Column(
              children: [
                builderPanel,
                const Divider(),
                totalsPanel,
              ],
            ),
          );
        }
      },
    );
  }
}
