import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import '../features/agent/agent_api.dart';
import '../features/agent/llm_config_provider.dart';
import '../models/ingredient.dart';
import '../models/nutrition_summary.dart';
import '../models/recipe.dart';
import '../providers/ingredient_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_builder_coordinator.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import 'recipe_builder_mode.dart';
import '../widgets/nutrition_totals_panel.dart';
import '../widgets/section_header.dart';

const _uuid = Uuid();

class RecipeBuilderScreen extends StatefulWidget {
  const RecipeBuilderScreen({super.key});

  @override
  State<RecipeBuilderScreen> createState() => RecipeBuilderScreenState();
}

class _IngredientLine {
  const _IngredientLine({required this.lineId, required this.entry});
  final String lineId;
  final RecipeIngredientEntry entry;
}

class RecipeBuilderScreenState extends State<RecipeBuilderScreen> {
  final _nameCtrl = TextEditingController();
  final _servingsCtrl = TextEditingController(text: '1');
  final _cookingTimeCtrl = TextEditingController(text: '0');
  final _instructionsCtrl = TextEditingController();
  List<_IngredientLine> _lines = [];
  String? _editingRecipeId;
  Timer? _summaryDebounce;
  NutritionSummary? _serverSummary;
  /// Fingerprint of the draft used for [_serverSummary]; avoids showing stale API totals.
  String? _serverSummaryFingerprint;
  bool _summaryLoading = false;
  String? _summaryError;
  bool _hydratingRecipe = false;
  RecipeBuilderCoordinator? _coordinator;

  RecipeBuilderMode get _mode => _editingRecipeId == null
      ? RecipeBuilderMode.create
      : RecipeBuilderMode.edit;

  List<RecipeIngredientEntry> get _ingredients =>
      _lines.map((l) => l.entry).toList();

  @override
  void dispose() {
    _coordinator?.removeListener(_onCoordinatorChanged);
    _summaryDebounce?.cancel();
    _nameCtrl.dispose();
    _servingsCtrl.dispose();
    _cookingTimeCtrl.dispose();
    _instructionsCtrl.dispose();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final next = context.read<RecipeBuilderCoordinator>();
    if (!identical(_coordinator, next)) {
      _coordinator?.removeListener(_onCoordinatorChanged);
      _coordinator = next;
      _coordinator!.addListener(_onCoordinatorChanged);
      _onCoordinatorChanged();
    }
  }

  void _onCoordinatorChanged() {
    final coord = _coordinator;
    if (coord == null || !mounted) return;
    final action = coord.takePendingAction();
    if (action == null) return;
    if (action is RecipeBuilderPendingCreate) {
      _clear();
    } else if (action is RecipeBuilderPendingEdit) {
      final recipeProvider = context.read<RecipeProvider>();
      unawaited(loadRecipeWithHydration(action.recipe, recipeProvider));
    }
  }

  void _scheduleNutritionSummary() {
    _summaryDebounce?.cancel();
    _summaryDebounce = Timer(const Duration(milliseconds: 450), () {
      if (!mounted) return;
      _runNutritionSummary();
    });
  }

  /// Stable key for the draft sent to [ApiService.nutritionSummary].
  String _nutritionFingerprint(Recipe r) {
    final segs = r.ingredients
        .map(
          (e) =>
              '${e.ingredientName.trim().toLowerCase()}|${e.quantity}|${e.unit.trim().toLowerCase()}',
        )
        .join('\n');
    return '${r.servings}|$segs';
  }

  /// Server summary uses local hub + USDA cache; it can still undercount vs line-level data.
  bool _shouldTrustServerSummary(NutritionSummary server, Recipe draft) {
    final clientCal = draft.totalCalories;
    if (clientCal <= 0) return true;
    return server.calories >= clientCal * 0.85;
  }

  Future<void> _runNutritionSummary() async {
    final draft = _buildRecipe();
    if (draft.ingredients.isEmpty) {
      if (!mounted) return;
      setState(() {
        _serverSummary = null;
        _serverSummaryFingerprint = null;
        _summaryLoading = false;
        _summaryError = null;
      });
      return;
    }
    final requestFp = _nutritionFingerprint(draft);
    setState(() {
      _summaryLoading = true;
      _summaryError = null;
    });
    try {
      final lines = draft.ingredients
          .map(
            (e) => {
              'name': e.ingredientName,
              'quantity': e.quantity,
              'unit': e.unit,
            },
          )
          .toList();
      final summary = await ApiService.nutritionSummary(
        servings: draft.servings,
        ingredientLines: lines,
      );
      if (!mounted) return;
      setState(() {
        _serverSummary = summary;
        _serverSummaryFingerprint = requestFp;
        _summaryLoading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _serverSummary = null;
        _serverSummaryFingerprint = null;
        _summaryLoading = false;
        _summaryError = e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _serverSummary = null;
        _serverSummaryFingerprint = null;
        _summaryLoading = false;
        _summaryError = e.toString();
      });
    }
  }

  void loadRecipe(Recipe recipe) {
    setState(() {
      _editingRecipeId = recipe.id;
      _nameCtrl.text = recipe.name;
      _servingsCtrl.text = recipe.servings.toString();
      _cookingTimeCtrl.text = recipe.cookingTimeMinutes.toString();
      _instructionsCtrl.text = recipe.instructions.join('\n');
      _lines = recipe.ingredients
          .map(
            (e) => _IngredientLine(lineId: _uuid.v4(), entry: e),
          )
          .toList();
      _serverSummary = null;
      _serverSummaryFingerprint = null;
      _summaryError = null;
      _summaryLoading = recipe.ingredients.isNotEmpty;
    });
    _scheduleNutritionSummary();
  }

  /// Fetches full recipe from the API when [recipe] is id/name-only (no lines).
  Future<void> loadRecipeWithHydration(
    Recipe recipe,
    RecipeProvider recipeProvider,
  ) async {
    if (recipe.ingredients.isNotEmpty) {
      loadRecipe(recipe);
      return;
    }
    setState(() => _hydratingRecipe = true);
    try {
      final full = await recipeProvider.fetchRecipeDetail(recipe.id);
      if (!mounted) return;
      loadRecipe(full);
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
      loadRecipe(recipe);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
      loadRecipe(recipe);
    } finally {
      if (mounted) {
        setState(() => _hydratingRecipe = false);
      }
    }
  }

  void _clear() {
    setState(() {
      _editingRecipeId = null;
      _nameCtrl.clear();
      _servingsCtrl.text = '1';
      _cookingTimeCtrl.text = '0';
      _instructionsCtrl.clear();
      _lines = [];
      _serverSummary = null;
      _serverSummaryFingerprint = null;
      _summaryLoading = false;
      _summaryError = null;
    });
    _summaryDebounce?.cancel();
  }

  Future<void> _discardOrClear() async {
    if (_editingRecipeId != null) {
      final recipeProvider = context.read<RecipeProvider>();
      final original = recipeProvider.getRecipeById(_editingRecipeId!);
      if (original != null && original.ingredients.isNotEmpty) {
        loadRecipe(original);
      } else if (original != null) {
        await loadRecipeWithHydration(original, recipeProvider);
      } else {
        _clear();
      }
    } else {
      _clear();
    }
  }

  void _addIngredient(Ingredient ing) {
    setState(() {
      _lines.add(
        _IngredientLine(
          lineId: _uuid.v4(),
          entry: RecipeIngredientEntry(
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
          ),
        ),
      );
    });
    _scheduleNutritionSummary();
  }

  void _removeIngredient(String lineId) {
    setState(() => _lines.removeWhere((l) => l.lineId == lineId));
    _scheduleNutritionSummary();
  }

  void _updateQuantityForLine(String lineId, double quantity) {
    final i = _lines.indexWhere((l) => l.lineId == lineId);
    if (i < 0) return;
    setState(() {
      _lines[i] = _IngredientLine(
        lineId: lineId,
        entry: _lines[i].entry.copyWith(quantity: quantity),
      );
    });
    _scheduleNutritionSummary();
  }

  void _updateUnitForLine(String lineId, String unit) {
    final i = _lines.indexWhere((l) => l.lineId == lineId);
    if (i < 0) return;
    setState(() {
      _lines[i] = _IngredientLine(
        lineId: lineId,
        entry: _lines[i].entry.copyWith(unit: unit),
      );
    });
    _scheduleNutritionSummary();
  }

  List<String> _instructionLinesFromController() {
    return [
      for (final line in _instructionsCtrl.text.split(RegExp(r'\r?\n')))
        if (line.trim().isNotEmpty) line.trim(),
    ];
  }

  Recipe _buildRecipe() {
    final parsedCook =
        int.tryParse(_cookingTimeCtrl.text.trim()) ?? 0;
    return Recipe(
      id: _editingRecipeId ?? _uuid.v4(),
      name: _nameCtrl.text.trim(),
      ingredients: _ingredients,
      servings: int.tryParse(_servingsCtrl.text.trim()) ?? 1,
      cookingTimeMinutes: parsedCook < 0 ? 0 : parsedCook,
      instructions: _instructionLinesFromController(),
    );
  }

  Future<void> _showLlmGenerateDialog() async {
    final gate = context.read<LlmConfigProvider>();
    if (!gate.llmReady) return;
    final themeHint = _nameCtrl.text.trim().isEmpty
        ? 'balanced dinners'
        : _nameCtrl.text.trim();
    final countCtrl = TextEditingController(text: '2');
    final ctxCtrl = TextEditingController(
      text: jsonEncode({'theme': themeHint}),
    );
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        var busy = false;
        return StatefulBuilder(
          builder: (ctx, setDialogState) {
            return AlertDialog(
              title: const Text('Generate recipes (LLM)'),
              content: SizedBox(
                width: 420,
                height: 320,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: countCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Count (1–20)',
                      ),
                      keyboardType: TextInputType.number,
                      enabled: !busy,
                    ),
                    const SizedBox(height: 12),
                    Expanded(
                      child: TextField(
                        controller: ctxCtrl,
                        decoration: const InputDecoration(
                          labelText: 'Context JSON',
                          alignLabelWithHint: true,
                          border: OutlineInputBorder(),
                        ),
                        maxLines: 8,
                        enabled: !busy,
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: busy ? null : () => Navigator.of(ctx).pop(),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: busy
                      ? null
                      : () async {
                          final hostContext = context;
                          final n = int.tryParse(countCtrl.text.trim());
                          if (n == null || n < 1 || n > 20) return;
                          Map<String, dynamic> genContext;
                          try {
                            final dec = jsonDecode(ctxCtrl.text.trim());
                            if (dec is! Map) return;
                            genContext = Map<String, dynamic>.from(dec);
                          } catch (_) {
                            return;
                          }
                          setDialogState(() => busy = true);
                          try {
                            await AgentApi.generateValidatedRecipes(
                              count: n,
                              context: genContext,
                            );
                            if (!hostContext.mounted) return;
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            await hostContext.read<RecipeProvider>().syncSummariesFromApi();
                            if (!hostContext.mounted) return;
                            ScaffoldMessenger.of(hostContext).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Recipes generated on server. Check Library.',
                                ),
                              ),
                            );
                          } on ApiException catch (e) {
                            if (!hostContext.mounted) return;
                            gate.revokeReady(e.message);
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            ScaffoldMessenger.of(hostContext).showSnackBar(
                              SnackBar(content: Text(e.message)),
                            );
                          } catch (e) {
                            if (!hostContext.mounted) return;
                            gate.revokeReady(e.toString());
                            Navigator.of(ctx).pop();
                            if (!hostContext.mounted) return;
                            ScaffoldMessenger.of(hostContext).showSnackBar(
                              SnackBar(content: Text(e.toString())),
                            );
                          }
                        },
                  child: Text(busy ? 'Running…' : 'Generate'),
                ),
              ],
            );
          },
        );
      },
    );
    countCtrl.dispose();
    ctxCtrl.dispose();
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

    try {
      if (_editingRecipeId != null) {
        await recipeProvider.updateRecipe(recipe);
      } else {
        await recipeProvider.addRecipe(recipe);
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Recipe "${recipe.name}" saved')),
      );
      if (_editingRecipeId == null) {
        _clear();
      } else {
        loadRecipe(recipe);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Saved on this device, but server sync failed: ${e.message}',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Saved on this device, but server sync failed: $e',
          ),
        ),
      );
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
    final server = _serverSummary;
    final draftFp = _nutritionFingerprint(recipe);
    final serverMatchesDraft =
        server != null && _serverSummaryFingerprint == draftFp;
    final useServerTotals = server != null &&
        !_summaryLoading &&
        recipe.ingredients.isNotEmpty &&
        serverMatchesDraft &&
        _shouldTrustServerSummary(server, recipe);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 800;

        final builderPanel = SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SectionHeader(
                title: _mode == RecipeBuilderMode.create
                    ? 'Create Recipe'
                    : 'Edit Recipe',
              ),
              if (_hydratingRecipe)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Row(
                    children: [
                      const SizedBox(
                        width: 22,
                        height: 22,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Loading recipe from server…',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    ],
                  ),
                ),
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Recipe Name'),
                onChanged: (_) {
                  setState(() {});
                  _scheduleNutritionSummary();
                },
              ),
              const SizedBox(height: 16),
              Text('Recipe Ingredients',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              ..._lines.map(
                (line) => _IngredientQuantityRow(
                  lineId: line.lineId,
                  entry: line.entry,
                  onQuantityChanged: (q) =>
                      _updateQuantityForLine(line.lineId, q),
                  onUnitChanged: (u) => _updateUnitForLine(line.lineId, u),
                  onRemove: () => _removeIngredient(line.lineId),
                ),
              ),
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
                onChanged: (_) {
                  setState(() {});
                  _scheduleNutritionSummary();
                },
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _cookingTimeCtrl,
                decoration: const InputDecoration(
                  labelText: 'Cooking time (minutes)',
                ),
                keyboardType: TextInputType.number,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _instructionsCtrl,
                decoration: const InputDecoration(
                  labelText: 'Instructions (one step per line)',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(),
                ),
                maxLines: 8,
                minLines: 3,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  OutlinedButton(
                    onPressed: _discardOrClear,
                    child: Text(
                      _mode == RecipeBuilderMode.create
                          ? 'Clear Recipe'
                          : 'Discard changes',
                    ),
                  ),
                  const SizedBox(width: 12),
                  FilledButton(
                    onPressed: _save,
                    child: Text(
                      _mode == RecipeBuilderMode.create ? 'Create' : 'Update',
                    ),
                  ),
                ],
              ),
              if (context.watch<LlmConfigProvider>().llmReady) ...[
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: _showLlmGenerateDialog,
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('Generate on server (LLM)'),
                  ),
                ),
              ],
            ],
          ),
        );

        final totalsPanel = SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_summaryLoading && recipe.ingredients.isNotEmpty)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: LinearProgressIndicator(minHeight: 2),
                ),
              if (_summaryError != null &&
                  !useServerTotals &&
                  recipe.ingredients.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(
                    'Server nutrition unavailable — showing client estimate. '
                    '($_summaryError)',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.error,
                        ),
                  ),
                ),
              NutritionTotalsPanel(
                title: useServerTotals
                    ? 'Nutrition (server)'
                    : 'Live Nutrition Totals',
                calories:
                    useServerTotals ? server.calories : recipe.totalCalories,
                proteinG:
                    useServerTotals ? server.proteinG : recipe.totalProteinG,
                carbsG: useServerTotals ? server.carbsG : recipe.totalCarbsG,
                fatG: useServerTotals ? server.fatG : recipe.totalFatG,
                perServingCalories: useServerTotals
                    ? server.perServingCalories
                    : recipe.perServingCalories,
                perServingProteinG: useServerTotals
                    ? server.perServingProteinG
                    : recipe.perServingProteinG,
                perServingCarbsG: useServerTotals
                    ? server.perServingCarbsG
                    : recipe.perServingCarbsG,
                perServingFatG: useServerTotals
                    ? server.perServingFatG
                    : recipe.perServingFatG,
                servings: recipe.servings,
                micronutrients: useServerTotals
                    ? server.micronutrients
                    : recipe.totalMicronutrients,
                micronutrientTargets: microTargets,
              ),
            ],
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

String _formatQuantityLabel(double q) {
  if ((q - q.roundToDouble()).abs() < 1e-9) {
    return q.round().toString();
  }
  return q.toString();
}

class _IngredientQuantityRow extends StatefulWidget {
  const _IngredientQuantityRow({
    required this.lineId,
    required this.entry,
    required this.onQuantityChanged,
    required this.onUnitChanged,
    required this.onRemove,
  });

  final String lineId;
  final RecipeIngredientEntry entry;
  final ValueChanged<double> onQuantityChanged;
  final ValueChanged<String> onUnitChanged;
  final VoidCallback onRemove;

  @override
  State<_IngredientQuantityRow> createState() => _IngredientQuantityRowState();
}

class _IngredientQuantityRowState extends State<_IngredientQuantityRow> {
  late final TextEditingController _qtyCtrl;

  @override
  void initState() {
    super.initState();
    _qtyCtrl = TextEditingController(
      text: _formatQuantityLabel(widget.entry.quantity),
    );
  }

  @override
  void didUpdateWidget(covariant _IngredientQuantityRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.entry.quantity != widget.entry.quantity) {
      final parsed = double.tryParse(_qtyCtrl.text);
      final matches = parsed != null &&
          (parsed - widget.entry.quantity).abs() < 1e-9;
      if (!matches) {
        _qtyCtrl.text = _formatQuantityLabel(widget.entry.quantity);
      }
    }
  }

  @override
  void dispose() {
    _qtyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ing = widget.entry;
    return Card(
      key: ValueKey(widget.lineId),
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
                  Text(
                    ing.ingredientName,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      SizedBox(
                        width: 80,
                        child: TextField(
                          controller: _qtyCtrl,
                          decoration: const InputDecoration(
                            labelText: 'Qty',
                          ),
                          keyboardType: TextInputType.number,
                          onEditingComplete: () {
                            final t = _qtyCtrl.text.trim();
                            if (t.isEmpty) {
                              _qtyCtrl.text =
                                  _formatQuantityLabel(widget.entry.quantity);
                            }
                          },
                          onChanged: (v) {
                            final t = v.trim();
                            if (t.isEmpty) {
                              return;
                            }
                            final qty = double.tryParse(t);
                            if (qty == null) {
                              return;
                            }
                            widget.onQuantityChanged(qty);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      DropdownButton<String>(
                        value: ing.unit,
                        items: ing.availableUnits
                            .map(
                              (u) => DropdownMenuItem(
                                value: u,
                                child: Text(u),
                              ),
                            )
                            .toList(),
                        onChanged: (v) {
                          if (v != null) widget.onUnitChanged(v);
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
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: Theme.of(context).colorScheme.primary,
                      ),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 20),
                  onPressed: widget.onRemove,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
