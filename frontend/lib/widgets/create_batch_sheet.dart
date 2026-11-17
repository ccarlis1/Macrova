import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/meal_prep_batch.dart';
import '../models/recipe.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import 'advisory_card.dart';
import 'empty_state.dart';
import 'macrova_chip.dart';
import 'macrova_sheet.dart';
import 'num_pill.dart';
import 'section_header.dart';
import 'sticky_cta.dart';

/// Single-screen create-batch sheet (FE-14): recipe, servings, cook date and
/// the current plan's slots, then `POST /api/v1/meal_prep_batches`. Not a
/// wizard and no drag-and-drop. State lives on [MealPlanProvider].
class CreateBatchSheet extends StatefulWidget {
  const CreateBatchSheet({super.key, this.today});

  /// Cook-date default; null means the device's today (tests pin it).
  final DateTime? today;

  static const servingsKey = Key('create_batch_servings');
  static const cookDateKey = Key('create_batch_cook_date');
  static const noRecipesKey = Key('create_batch_no_recipes');
  static const noSlotsKey = Key('create_batch_no_slots');
  static const slotsFullKey = Key('create_batch_slots_full');
  static const poolWarningKey = Key('create_batch_pool_warning');
  static const errorKey = Key('create_batch_error');
  static Key recipeKey(String id) => Key('create_batch_recipe_$id');

  /// [dayIndex] / [slotIndex] are 0-based (batch assignment coordinates).
  static Key slotKey(int dayIndex, int slotIndex) =>
      Key('create_batch_slot_${dayIndex}_$slotIndex');

  /// Opens the sheet over [context]. Resolves to `null` when dismissed, else
  /// whether the plan was re-run with the new batch
  /// ([MealPlanProvider.createMealPrepBatch]).
  static Future<bool?> show(BuildContext context, {DateTime? today}) {
    // Modal routes sit beside the screen, so hand the providers over.
    final plan = context.read<MealPlanProvider>();
    final recipes = context.read<RecipeProvider>();
    return showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: MacrovaColors.scrim,
      builder: (_) => FractionallySizedBox(
        heightFactor: 1,
        child: MultiProvider(
          providers: [
            ChangeNotifierProvider<MealPlanProvider>.value(value: plan),
            ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
          ],
          child: CreateBatchSheet(today: today),
        ),
      ),
    );
  }

  @override
  State<CreateBatchSheet> createState() => _CreateBatchSheetState();
}

class _CreateBatchSheetState extends State<CreateBatchSheet> {
  String? _recipeId;
  int _servings = 2;
  late DateTime _cookDate;
  final Set<(int, int)> _slots = {};
  bool _submitting = false;
  ApiException? _error;
  String? _otherError;

  @override
  void initState() {
    super.initState();
    final t = widget.today ?? DateTime.now();
    _cookDate = DateTime(t.year, t.month, t.day);
    // `is_meal_prep_capable` is server-computed: refresh it for recipes that
    // carry the meal-prep tag but weren't loaded since their last save.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final recipes = context.read<RecipeProvider>();
      recipes.loadServerTags([
        for (final r in recipes.recipes)
          if (r.hasMealPrepTag && !recipes.hasServerTags(r.id)) r.id,
      ]);
    });
  }

  bool _dayTaken(int dayIndex) => _slots.any((s) => s.$1 == dayIndex);

  void _toggleSlot(PlanSlotOption o) {
    setState(() {
      final key = (o.dayIndex, o.slotIndex);
      if (!_slots.remove(key)) _slots.add(key);
      _error = null;
      _otherError = null;
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _cookDate,
      firstDate: _cookDate.subtract(const Duration(days: 365)),
      lastDate: _cookDate.add(const Duration(days: 365)),
    );
    if (picked != null && mounted) setState(() => _cookDate = picked);
  }

  Future<void> _submit() async {
    final recipeId = _recipeId;
    if (recipeId == null || _slots.isEmpty) return;
    setState(() {
      _submitting = true;
      _error = null;
      _otherError = null;
    });
    final sorted = _slots.toList()
      ..sort((a, b) => a.$1 != b.$1 ? a.$1.compareTo(b.$1) : a.$2.compareTo(b.$2));
    try {
      final reran = await context.read<MealPlanProvider>().createMealPrepBatch(
            recipeId: recipeId,
            totalServings: _servings,
            cookDate: isoDate(_cookDate),
            assignments: [
              for (final (day, slot) in sorted)
                MealPrepAssignment(dayIndex: day, slotIndex: slot),
            ],
          );
      if (!mounted) return;
      Navigator.of(context).pop(reran);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = e;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _otherError = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final plan = context.watch<MealPlanProvider>();
    final recipes = context.watch<RecipeProvider>();
    final capable = [
      for (final r in recipes.recipes)
        if (r.isMealPrepCapable) r,
    ];
    if (_recipeId != null && !capable.any((r) => r.id == _recipeId)) {
      _recipeId = null;
    }
    final options = plan.planSlotOptions;
    final full = _slots.length >= _servings;
    final canSubmit = _recipeId != null && _slots.isNotEmpty && !_submitting;
    final poolIds = plan.lastRequest?.recipeIds;
    final outOfPool = _recipeId != null &&
        poolIds != null &&
        poolIds.isNotEmpty &&
        !poolIds.contains(_recipeId);

    return MacrovaSheet(
      title: 'New meal-prep batch',
      subtitle: 'Cook once, eat it in several planned meals',
      onClose: () => Navigator.of(context).pop(),
      body: ListView(
        padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
        children: [
          Text(
            'Selected slots are fixed assignments, not preferences: every plan '
            'puts this recipe there until you cancel the batch.',
            style: MacrovaTypography.body(tokens.inkSecondary),
          ),
          const SizedBox(height: MacrovaSpacing.lg),
          const SectionHeader(title: 'Recipe'),
          _recipeSection(tokens, recipes, capable),
          const SizedBox(height: MacrovaSpacing.lg),
          const SectionHeader(
            title: 'Servings',
            subtitle: 'Total servings you cook (at least 2)',
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: NumPill(
              key: CreateBatchSheet.servingsKey,
              value: _servings,
              min: _slots.length > 2 ? _slots.length : 2,
              onChange: (v) => setState(() => _servings = v.toInt()),
            ),
          ),
          const SizedBox(height: MacrovaSpacing.lg),
          const SectionHeader(
            title: 'Cook date',
            subtitle: 'Defaults to today; the server dates each slot from it '
                '(plan day 1 is the cook date)',
          ),
          Align(
            alignment: Alignment.centerLeft,
            child: MacrovaChip(
              key: CreateBatchSheet.cookDateKey,
              label: isoDate(_cookDate),
              leadingIcon: Icons.calendar_today_outlined,
              onTap: _submitting ? null : _pickDate,
            ),
          ),
          const SizedBox(height: MacrovaSpacing.lg),
          SectionHeader(
            title: 'Slots',
            subtitle: '${_slots.length} of $_servings servings assigned',
          ),
          ..._slotSection(tokens, options, full),
          if (outOfPool) ...[
            const SizedBox(height: MacrovaSpacing.md),
            const AdvisoryCard(
              key: CreateBatchSheet.poolWarningKey,
              variant: AdvisoryVariant.warn,
              title: 'This recipe is not in your selected pool',
              description:
                  'The current plan only uses the recipes selected in Planner '
                  'Config, so the batch slots would fail. Add this recipe to '
                  'the pool, then re-generate.',
            ),
          ],
          if (_error != null || _otherError != null) ...[
            const SizedBox(height: MacrovaSpacing.md),
            _errorCard(),
          ],
          const SizedBox(height: MacrovaSpacing.xl),
        ],
      ),
      cta: StickyCta(
        label: 'New batch',
        detail: _recipeId == null
            ? 'Pick a recipe and slots'
            : '${servingsLabel(_servings)} · ${_slots.length} '
                '${_slots.length == 1 ? 'slot' : 'slots'}',
        actions: [
          StickyCtaAction(
            label: _submitting ? 'Creating…' : 'Create batch',
            isPrimary: true,
            onPressed: canSubmit ? _submit : null,
          ),
        ],
      ),
    );
  }

  Widget _recipeSection(
    MacrovaTokens tokens,
    RecipeProvider recipes,
    List<Recipe> capable,
  ) {
    if (capable.isEmpty) {
      if (recipes.serverTagsLoading) {
        return const EmptyState.loading(label: 'Checking recipes…');
      }
      return const AdvisoryCard(
        key: CreateBatchSheet.noRecipesKey,
        variant: AdvisoryVariant.info,
        title: 'No meal-prep capable recipes',
        description: 'Mark a recipe meal-prep capable in the Recipe Builder '
            '(switch on, 2 or more servings), then come back.',
      );
    }
    return Wrap(
      spacing: MacrovaSpacing.xs,
      runSpacing: MacrovaSpacing.xs,
      children: [
        for (final r in capable)
          MacrovaChip(
            key: CreateBatchSheet.recipeKey(r.id),
            label: r.name,
            selected: _recipeId == r.id,
            onTap: _submitting
                ? null
                : () => setState(() {
                      _recipeId = _recipeId == r.id ? null : r.id;
                      _error = null;
                      _otherError = null;
                    }),
          ),
      ],
    );
  }

  List<Widget> _slotSection(
    MacrovaTokens tokens,
    List<PlanSlotOption> options,
    bool full,
  ) {
    if (options.isEmpty) {
      return [
        Text(
          'Generate a plan first: slots come from the current plan.',
          key: CreateBatchSheet.noSlotsKey,
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
      ];
    }
    final days = <int, List<PlanSlotOption>>{};
    for (final o in options) {
      days.putIfAbsent(o.dayIndex, () => []).add(o);
    }
    return [
      Text(
        'One slot per day: the planner never repeats a recipe within a day.',
        style: MacrovaTypography.caption(tokens.inkTertiary),
      ),
      if (full)
        Text(
          'Every serving has a slot. Add servings to pick more.',
          key: CreateBatchSheet.slotsFullKey,
          style: MacrovaTypography.caption(tokens.accentDeep),
        ),
      for (final e in days.entries) ...[
        const SizedBox(height: MacrovaSpacing.sm),
        Text(
          'Day ${e.key + 1}',
          style: MacrovaTypography.label(tokens.inkSecondary),
        ),
        const SizedBox(height: MacrovaSpacing.xs),
        Wrap(
          spacing: MacrovaSpacing.xs,
          runSpacing: MacrovaSpacing.xs,
          children: [
            for (final o in e.value)
              Builder(builder: (_) {
                final selected = _slots.contains((o.dayIndex, o.slotIndex));
                final blocked =
                    !selected && (full || _dayTaken(o.dayIndex));
                return Opacity(
                  opacity: blocked ? 0.45 : 1,
                  child: MacrovaChip(
                    key: CreateBatchSheet.slotKey(o.dayIndex, o.slotIndex),
                    label: 'Meal ${o.slotIndex + 1}'
                        '${o.label == null ? ' (unfilled)' : ' · ${o.label}'}',
                    selected: selected,
                    onTap: _submitting || blocked ? null : () => _toggleSlot(o),
                  ),
                );
              }),
          ],
        ),
      ],
    ];
  }

  Widget _errorCard() {
    final e = _error;
    if (e == null) {
      return AdvisoryCard(
        key: CreateBatchSheet.errorKey,
        variant: AdvisoryVariant.warn,
        title: 'Batch not created',
        description: _otherError ?? '',
      );
    }
    final (title, fix) = switch (e.code) {
      'BATCH_CONFLICT' => (
          'A slot is already taken by another batch',
          'Pick other slots, or cancel the other batch in the tray.',
        ),
      'RECIPE_NOT_BATCHABLE' => (
          'This recipe can\'t be batched',
          'Fix: in the Recipe Builder, switch on "Meal-prep capable" with 2 '
              'or more servings, save, then try again.',
        ),
      'RECIPE_NOT_FOUND' => (
          'The server doesn\'t have this recipe',
          'Save it in the Recipe Builder so it syncs, then try again.',
        ),
      _ => ('Batch not created', null),
    };
    return AdvisoryCard(
      key: CreateBatchSheet.errorKey,
      variant: AdvisoryVariant.warn,
      title: '$title (${e.code})',
      description: fix == null ? e.message : '${e.message}\n$fix',
    );
  }
}
