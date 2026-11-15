import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/starter_recipe.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import 'advisory_card.dart';
import 'empty_state.dart';
import 'macrova_chip.dart';
import 'macrova_sheet.dart';
import 'sticky_cta.dart';

/// Starter-pack picker (FE-16): the user ticks the starter recipes they would
/// eat and imports them into their pool (`POST /api/v1/starter_recipes/import`).
/// Nothing is pre-selected and nothing is imported without the user's tap.
/// State lives on [RecipeProvider]; the selection is local to the sheet.
class StarterPackSheet extends StatefulWidget {
  const StarterPackSheet({super.key});

  static const importKey = Key('starter_pack_import');
  static const selectAllKey = Key('starter_pack_select_all');
  static const loadingKey = Key('starter_pack_loading');
  static const loadErrorKey = Key('starter_pack_load_error');
  static const retryKey = Key('starter_pack_retry');
  static const emptyKey = Key('starter_pack_empty');
  static const importErrorKey = Key('starter_pack_import_error');
  static Key rowKey(String id) => Key('starter_pack_row_$id');
  static Key checkboxKey(String id) => Key('starter_pack_check_$id');

  /// Opens the sheet over [context]. Resolves to the import result, or null
  /// when dismissed; after an import a snackbar says what was imported.
  static Future<StarterImportResult?> show(BuildContext context) async {
    // Modal routes sit beside the screen, so hand the provider over.
    final recipes = context.read<RecipeProvider>();
    final messenger = ScaffoldMessenger.maybeOf(context);
    final plan = Provider.of<MealPlanProvider?>(context, listen: false);
    final result = await showModalBottomSheet<StarterImportResult>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: MacrovaColors.scrim,
      builder: (_) => FractionallySizedBox(
        heightFactor: 1,
        child: ChangeNotifierProvider<RecipeProvider>.value(
          value: recipes,
          child: const StarterPackSheet(),
        ),
      ),
    );
    if (result != null) {
      messenger?.showSnackBar(
        SnackBar(
          content: Text(
            importSummary(
              result,
              plannerUsesSelection:
                  plan?.selectedRecipeIds.isNotEmpty ?? false,
            ),
          ),
        ),
      );
    }
    return result;
  }

  /// One line for the snackbar after an import. [plannerUsesSelection]: Planner
  /// Config sends only its ticked recipes, so new imports need ticking there.
  static String importSummary(
    StarterImportResult result, {
    bool plannerUsesSelection = false,
  }) {
    String recipes(int n) => n == 1 ? '1 recipe' : '$n recipes';
    final already = result.skipped
        .where((s) => s.reason == StarterImportSkipped.alreadyInPool)
        .length;
    final other = result.skipped.length - already;
    final n = result.imported.length;
    return [
      n == 0 ? 'Nothing imported.' : 'Imported ${recipes(n)} into your library.',
      if (already > 0)
        '${recipes(already)} ${already == 1 ? 'was' : 'were'} already there.',
      if (other > 0)
        '${recipes(other)} ${other == 1 ? 'is' : 'are'} not in the starter pack.',
      if (n > 0 && plannerUsesSelection)
        'Planner Config plans with the recipes ticked there: tick these to '
            'use them.',
    ].join(' ');
  }

  @override
  State<StarterPackSheet> createState() => _StarterPackSheetState();
}

class _StarterPackSheetState extends State<StarterPackSheet> {
  final Set<String> _selected = {};
  String? _importError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final recipes = context.read<RecipeProvider>();
      recipes.loadStarterRecipes();
      // Meal-role chips need the registry's semantic classes.
      recipes.loadTagRegistry();
    });
  }

  Future<void> _import(List<StarterRecipe> pack) async {
    final ids = [
      for (final r in pack)
        if (_selected.contains(r.id)) r.id,
    ];
    if (ids.isEmpty) return;
    setState(() => _importError = null);
    try {
      final result =
          await context.read<RecipeProvider>().importStarterRecipes(ids);
      if (!mounted) return;
      Navigator.of(context).pop(result);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _importError = '${e.message} (${e.code})');
    } catch (e) {
      if (!mounted) return;
      setState(() => _importError = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final recipes = context.watch<RecipeProvider>();
    final pack = recipes.starterRecipes ?? const <StarterRecipe>[];
    final inLibrary = recipes.libraryRecipeIds;
    final importable = [
      for (final r in pack)
        if (!inLibrary.contains(r.id)) r.id,
    ];
    // A recipe that joined the library since it was ticked can't be imported.
    _selected.removeWhere((id) => inLibrary.contains(id));
    final roleLabels = {
      for (final t in recipes.mealRoleTags) t.slug: t.display,
    };
    final importing = recipes.starterImporting;
    final allSelected =
        importable.isNotEmpty && importable.every(_selected.contains);
    final count = _selected.length;

    return MacrovaSheet(
      title: 'Starter pack',
      subtitle: 'Pick the recipes you would eat',
      onClose: () => Navigator.of(context).pop(),
      body: _body(tokens, recipes, pack, inLibrary, importable, roleLabels,
          allSelected, importing),
      cta: StickyCta(
        label: 'Import into your library',
        detail: count == 0
            ? 'Nothing selected'
            : '$count ${count == 1 ? 'recipe' : 'recipes'} selected',
        actions: [
          StickyCtaAction(
            key: StarterPackSheet.importKey,
            label: importing ? 'Importing…' : 'Import',
            isPrimary: true,
            onPressed: count == 0 || importing ? null : () => _import(pack),
          ),
        ],
      ),
    );
  }

  Widget _body(
    MacrovaTokens tokens,
    RecipeProvider recipes,
    List<StarterRecipe> pack,
    Set<String> inLibrary,
    List<String> importable,
    Map<String, String> roleLabels,
    bool allSelected,
    bool importing,
  ) {
    if (recipes.starterRecipes == null) {
      if (recipes.starterError != null && !recipes.starterLoading) {
        return ListView(
          padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
          children: [
            AdvisoryCard(
              key: StarterPackSheet.loadErrorKey,
              variant: AdvisoryVariant.warn,
              title: 'Could not load the starter pack',
              description: recipes.starterError!,
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                key: StarterPackSheet.retryKey,
                onPressed: recipes.loadStarterRecipes,
                child: const Text('Retry'),
              ),
            ),
          ],
        );
      }
      return const Center(
        child: EmptyState.loading(
          key: StarterPackSheet.loadingKey,
          label: 'Loading the starter pack…',
        ),
      );
    }
    if (pack.isEmpty) {
      return Padding(
        padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
        child: Text(
          'The server has no starter recipes.',
          key: StarterPackSheet.emptyKey,
          style: MacrovaTypography.body(tokens.inkTertiary),
        ),
      );
    }
    return ListView(
      padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
      children: [
        Text(
          'Imported recipes join your library as normal recipes you can edit, '
          'and the planner can use them.',
          style: MacrovaTypography.body(tokens.inkSecondary),
        ),
        const SizedBox(height: MacrovaSpacing.sm),
        Row(
          children: [
            Expanded(
              child: Text(
                '${pack.length} recipes · ${pack.length - importable.length} '
                'in your library',
                style: MacrovaTypography.caption(tokens.inkTertiary),
              ),
            ),
            TextButton(
              key: StarterPackSheet.selectAllKey,
              onPressed: importable.isEmpty || importing
                  ? null
                  : () => setState(() {
                        if (allSelected) {
                          _selected.clear();
                        } else {
                          _selected.addAll(importable);
                        }
                      }),
              child: Text(allSelected ? 'Clear selection' : 'Select all'),
            ),
          ],
        ),
        const Divider(height: 1),
        for (final r in pack)
          _StarterRow(
            recipe: r,
            inLibrary: inLibrary.contains(r.id),
            selected: _selected.contains(r.id),
            roleLabels: roleLabels,
            enabled: !importing,
            onChanged: () => setState(() {
              if (!_selected.remove(r.id)) _selected.add(r.id);
            }),
          ),
        if (_importError != null) ...[
          const SizedBox(height: MacrovaSpacing.md),
          AdvisoryCard(
            key: StarterPackSheet.importErrorKey,
            variant: AdvisoryVariant.warn,
            title: 'Nothing was imported',
            description: _importError!,
          ),
        ],
        const SizedBox(height: MacrovaSpacing.xl),
      ],
    );
  }
}

class _StarterRow extends StatelessWidget {
  const _StarterRow({
    required this.recipe,
    required this.inLibrary,
    required this.selected,
    required this.roleLabels,
    required this.enabled,
    required this.onChanged,
  });

  final StarterRecipe recipe;
  final bool inLibrary;
  final bool selected;

  /// Meal-role slug → display name from the tag registry.
  final Map<String, String> roleLabels;
  final bool enabled;
  final VoidCallback onChanged;

  String _facts() {
    final kcal = recipe.caloriesPerServing;
    final protein = recipe.proteinGPerServing;
    return [
      kcal == null ? 'kcal unknown' : '${kcal.round()} kcal',
      protein == null ? 'protein unknown' : '${protein.round()} g protein',
      '${recipe.cookingTimeMinutes} min',
    ].join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final canTick = !inLibrary && enabled;
    final roles = [
      for (final s in recipe.contextSlugs)
        if (roleLabels.containsKey(s)) roleLabels[s]!,
    ];

    return InkWell(
      key: StarterPackSheet.rowKey(recipe.id),
      onTap: canTick ? onChanged : null,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.sm),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Checkbox(
              key: StarterPackSheet.checkboxKey(recipe.id),
              value: !inLibrary && selected,
              onChanged: canTick ? (_) => onChanged() : null,
            ),
            const SizedBox(width: MacrovaSpacing.xs),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    recipe.name,
                    style: MacrovaTypography.bodyMedium(
                      inLibrary ? tokens.inkTertiary : tokens.inkPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    _facts(),
                    style: MacrovaTypography.caption(tokens.inkTertiary),
                  ),
                  if (!recipe.readyForPlanning)
                    Text(
                      recipe.unresolved.isEmpty
                          ? 'Some ingredients don\'t resolve: the planner '
                              'would skip it.'
                          : 'Doesn\'t resolve: '
                              '${recipe.unresolved.join(', ')}. The planner '
                              'would skip it.',
                      style: MacrovaTypography.caption(tokens.accentDeep),
                    ),
                  if (roles.isNotEmpty) ...[
                    const SizedBox(height: MacrovaSpacing.xs),
                    Wrap(
                      spacing: MacrovaSpacing.xs,
                      runSpacing: MacrovaSpacing.xs,
                      children: [
                        for (final role in roles) MacrovaChip(label: role),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            if (inLibrary)
              const Padding(
                padding: EdgeInsets.only(
                  left: MacrovaSpacing.sm,
                  top: MacrovaSpacing.sm,
                ),
                child: MacrovaChip(
                  label: 'In your library',
                  variant: MacrovaChipVariant.accent,
                  leadingIcon: Icons.check,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
