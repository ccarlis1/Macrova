import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../providers/ingredient_provider.dart';
import '../widgets/ingredient_card.dart';
import '../widgets/macro_display.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/section_header.dart';

const _uuid = Uuid();

// Default RDA targets for micronutrient bars
const _defaultRda = {
  'vitamin_b6_mg': 1.3,
  'niacin_mg': 16.0,
  'selenium_ug': 55.0,
  'phosphorus_mg': 700.0,
  'vitamin_a_ug': 900.0,
  'vitamin_c_mg': 90.0,
  'iron_mg': 18.0,
  'calcium_mg': 1300.0,
  'fiber_g': 30.0,
  'sodium_mg': 2300.0,
};

const _microLabels = {
  'vitamin_a_ug': 'Vitamin A',
  'vitamin_c_mg': 'Vitamin C',
  'vitamin_b6_mg': 'Vitamin B6',
  'niacin_mg': 'Niacin',
  'iron_mg': 'Iron',
  'calcium_mg': 'Calcium',
  'fiber_g': 'Fiber',
  'sodium_mg': 'Sodium',
  'selenium_ug': 'Selenium',
  'phosphorus_mg': 'Phosphorus',
};

const _microUnits = {
  'vitamin_a_ug': 'mcg',
  'vitamin_c_mg': 'mg',
  'vitamin_b6_mg': 'mg',
  'niacin_mg': 'mg',
  'iron_mg': 'mg',
  'calcium_mg': 'mg',
  'fiber_g': 'g',
  'sodium_mg': 'mg',
  'selenium_ug': 'mcg',
  'phosphorus_mg': 'mg',
};

class IngredientHubScreen extends StatefulWidget {
  const IngredientHubScreen({super.key});

  @override
  State<IngredientHubScreen> createState() => _IngredientHubScreenState();
}

class _IngredientHubScreenState extends State<IngredientHubScreen> {
  final _searchCtrl = TextEditingController();
  IngredientSource? _sourceFilter;
  String? _selectedId;

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  void _showCreateDialog() {
    showDialog<void>(
      context: context,
      builder: (ctx) => _CreateIngredientDialog(
        onSave: (ingredient) {
          context.read<IngredientProvider>().addIngredient(ingredient);
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<IngredientProvider>();
    final results = provider.search(
      _searchCtrl.text,
      sourceFilter: _sourceFilter,
    );
    final selected =
        _selectedId != null ? provider.getById(_selectedId!) : null;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth > 800;

        final listPanel = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _searchCtrl,
                    decoration: const InputDecoration(
                      hintText: 'Search for ingredients...',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onChanged: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 12),
                  _buildFilterTabs(),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: results.isEmpty
                  ? Center(
                      child: Text(
                        'No ingredients found',
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: results.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 8),
                      itemBuilder: (_, i) {
                        final ing = results[i];
                        return IngredientCard(
                          ingredient: ing,
                          selected: ing.id == _selectedId,
                          onTap: () =>
                              setState(() => _selectedId = ing.id),
                        );
                      },
                    ),
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _showCreateDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('Create Custom Ingredient'),
                ),
              ),
            ),
          ],
        );

        final detailPanel = selected != null
            ? _buildDetailPanel(context, selected)
            : Center(
                child: Text(
                  'Select an ingredient to view details',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color:
                            Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              );

        if (wide) {
          return Row(
            children: [
              Expanded(flex: 2, child: listPanel),
              const VerticalDivider(width: 1),
              Expanded(flex: 3, child: detailPanel),
            ],
          );
        } else {
          return selected != null
              ? Column(
                  children: [
                    AppBar(
                      leading: IconButton(
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () =>
                            setState(() => _selectedId = null),
                      ),
                      title: Text(selected.name),
                    ),
                    Expanded(child: detailPanel),
                  ],
                )
              : listPanel;
        }
      },
    );
  }

  Widget _buildFilterTabs() {
    return Wrap(
      spacing: 8,
      children: [
        FilterChip(
          label: const Text('All'),
          selected: _sourceFilter == null,
          onSelected: (_) => setState(() => _sourceFilter = null),
        ),
        FilterChip(
          label: const Text('Saved'),
          selected: _sourceFilter == IngredientSource.saved,
          onSelected: (_) =>
              setState(() => _sourceFilter = IngredientSource.saved),
        ),
        FilterChip(
          label: const Text('API'),
          selected: _sourceFilter == IngredientSource.api,
          onSelected: (_) =>
              setState(() => _sourceFilter = IngredientSource.api),
        ),
        FilterChip(
          label: const Text('Custom'),
          selected: _sourceFilter == IngredientSource.custom,
          onSelected: (_) =>
              setState(() => _sourceFilter = IngredientSource.custom),
        ),
      ],
    );
  }

  Widget _buildDetailPanel(BuildContext context, Ingredient ing) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(title: ing.name),
          MacroDisplay(
            calories: ing.caloriesPer100g,
            proteinG: ing.proteinPer100g,
            carbsG: ing.carbsPer100g,
            fatG: ing.fatPer100g,
          ),
          const SizedBox(height: 8),
          Text(
            'per 100g',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          if (ing.micronutrientsPer100g.isNotEmpty) ...[
            const SizedBox(height: 24),
            Text(
              'Micronutrients (per 100g)',
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            ...ing.micronutrientsPer100g.entries.map((e) {
              final target = _defaultRda[e.key] ?? 0;
              final unit = _microUnits[e.key] ?? '';
              final label = _microLabels[e.key] ?? e.key;
              return MicronutrientBar(
                label: label,
                value: e.value,
                target: target,
                unit: unit,
                isLimit: e.key == 'sodium_mg',
              );
            }),
          ],
          const SizedBox(height: 24),
          Row(
            children: [
              FilledButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                        content:
                            Text('Navigate to Recipe Builder to add')),
                  );
                },
                icon: const Icon(Icons.add),
                label: const Text('Add to Recipe'),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: () {
                  showDialog<void>(
                    context: context,
                    builder: (ctx) => _CreateIngredientDialog(
                      initial: ing,
                      onSave: (updated) {
                        context
                            .read<IngredientProvider>()
                            .updateIngredient(updated);
                      },
                    ),
                  );
                },
                child: const Text('Edit'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CreateIngredientDialog extends StatefulWidget {
  final Ingredient? initial;
  final ValueChanged<Ingredient> onSave;

  const _CreateIngredientDialog({this.initial, required this.onSave});

  @override
  State<_CreateIngredientDialog> createState() =>
      _CreateIngredientDialogState();
}

class _CreateIngredientDialogState extends State<_CreateIngredientDialog> {
  final _nameCtrl = TextEditingController();
  final _caloriesCtrl = TextEditingController();
  final _proteinCtrl = TextEditingController();
  final _carbsCtrl = TextEditingController();
  final _fatCtrl = TextEditingController();
  final _gramsPerCupCtrl = TextEditingController();
  final _gramsPerTbspCtrl = TextEditingController();
  final _customUnitCtrl = TextEditingController();

  final List<MapEntry<String, TextEditingController>> _microRows = [];

  @override
  void initState() {
    super.initState();
    final ing = widget.initial;
    if (ing != null) {
      _nameCtrl.text = ing.name;
      _caloriesCtrl.text = ing.caloriesPer100g.toStringAsFixed(0);
      _proteinCtrl.text = ing.proteinPer100g.toStringAsFixed(1);
      _carbsCtrl.text = ing.carbsPer100g.toStringAsFixed(1);
      _fatCtrl.text = ing.fatPer100g.toStringAsFixed(1);
      final cup = ing.unitConversions['cup'];
      if (cup != null) _gramsPerCupCtrl.text = cup.toStringAsFixed(0);
      final tbsp = ing.unitConversions['tbsp'];
      if (tbsp != null) _gramsPerTbspCtrl.text = tbsp.toStringAsFixed(0);

      for (final e in ing.micronutrientsPer100g.entries) {
        _microRows.add(MapEntry(
          e.key,
          TextEditingController(text: e.value.toStringAsFixed(2)),
        ));
      }
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _caloriesCtrl.dispose();
    _proteinCtrl.dispose();
    _carbsCtrl.dispose();
    _fatCtrl.dispose();
    _gramsPerCupCtrl.dispose();
    _gramsPerTbspCtrl.dispose();
    _customUnitCtrl.dispose();
    for (final row in _microRows) {
      row.value.dispose();
    }
    super.dispose();
  }

  void _addMicroRow() {
    setState(() {
      _microRows.add(MapEntry('', TextEditingController()));
    });
  }

  void _save() {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;

    final conversions = <String, double>{};
    final cup = double.tryParse(_gramsPerCupCtrl.text.trim());
    if (cup != null && cup > 0) conversions['cup'] = cup;
    final tbsp = double.tryParse(_gramsPerTbspCtrl.text.trim());
    if (tbsp != null && tbsp > 0) conversions['tbsp'] = tbsp;
    final custom = double.tryParse(_customUnitCtrl.text.trim());
    if (custom != null && custom > 0) conversions['custom'] = custom;

    final micros = <String, double>{};
    for (final row in _microRows) {
      final key = row.key.trim();
      final val = double.tryParse(row.value.text.trim());
      if (key.isNotEmpty && val != null) {
        micros[key] = val;
      }
    }

    final ingredient = Ingredient(
      id: widget.initial?.id ?? _uuid.v4(),
      name: name,
      caloriesPer100g:
          double.tryParse(_caloriesCtrl.text.trim()) ?? 0,
      proteinPer100g:
          double.tryParse(_proteinCtrl.text.trim()) ?? 0,
      carbsPer100g: double.tryParse(_carbsCtrl.text.trim()) ?? 0,
      fatPer100g: double.tryParse(_fatCtrl.text.trim()) ?? 0,
      micronutrientsPer100g: micros,
      unitConversions: conversions,
      source: widget.initial?.source ?? IngredientSource.custom,
    );

    widget.onSave(ingredient);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(
          widget.initial != null ? 'Edit Ingredient' : 'Create Custom Ingredient'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: _nameCtrl,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              const SizedBox(height: 16),
              Text('Macros (per 100g)',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _caloriesCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Calories (kcal)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _proteinCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Protein (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _carbsCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Carbs (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _fatCtrl,
                      decoration: const InputDecoration(labelText: 'Fat (g)'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Text('Micronutrients',
                      style: Theme.of(context).textTheme.titleSmall),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _addMicroRow,
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Add Row'),
                  ),
                ],
              ),
              ..._microRows.asMap().entries.map((entry) {
                final i = entry.key;
                final row = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: TextField(
                          decoration:
                              const InputDecoration(hintText: 'Key (e.g. iron_mg)'),
                          controller: TextEditingController(text: row.key),
                          onChanged: (v) {
                            _microRows[i] = MapEntry(v, row.value);
                          },
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: row.value,
                          decoration:
                              const InputDecoration(hintText: 'Value'),
                          keyboardType: TextInputType.number,
                        ),
                      ),
                    ],
                  ),
                );
              }),
              const SizedBox(height: 16),
              Text('Unit Conversions',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _gramsPerCupCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Grams per cup'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: _gramsPerTbspCtrl,
                      decoration:
                          const InputDecoration(labelText: 'Grams per tbsp'),
                      keyboardType: TextInputType.number,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _customUnitCtrl,
                decoration:
                    const InputDecoration(labelText: 'Custom unit (g)'),
                keyboardType: TextInputType.number,
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          child: const Text('Save Ingredient'),
        ),
      ],
    );
  }
}
