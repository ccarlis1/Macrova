import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/meal_prep_batch.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import 'create_batch_sheet.dart';
import 'empty_state.dart';
import 'macrova_chip.dart';

/// Always-visible meal-prep tray at the top of Meal Plan View (FE-14). Lists
/// the server's active batches from [MealPlanProvider.mealPrepBatches], with
/// cancel (confirmed first) and "+ New batch" ([CreateBatchSheet]). Collapse is
/// a device-local convenience ([MealPlanProvider.mealPrepTrayCollapsed]);
/// the tray starts expanded.
class MealPrepTray extends StatelessWidget {
  const MealPrepTray({super.key});

  static const trayKey = Key('meal_prep_tray');
  static const toggleKey = Key('meal_prep_tray_toggle');
  static const newBatchKey = Key('meal_prep_tray_new_batch');
  static const emptyKey = Key('meal_prep_tray_empty');
  static const errorKey = Key('meal_prep_tray_error');
  static const retryKey = Key('meal_prep_tray_retry');
  static const cancelConfirmKey = Key('meal_prep_cancel_confirm');
  static const cancelDismissKey = Key('meal_prep_cancel_dismiss');
  static Key batchKey(String id) => Key('meal_prep_batch_$id');
  static Key cancelKey(String id) => Key('meal_prep_cancel_$id');

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final plan = context.watch<MealPlanProvider>();
    final recipes = context.watch<RecipeProvider>();
    final collapsed = plan.mealPrepTrayCollapsed;
    final batches = plan.mealPrepBatches;

    return Container(
      key: trayKey,
      padding: const EdgeInsets.all(MacrovaSpacing.lg),
      decoration: BoxDecoration(
        color: tokens.surfaceTint,
        borderRadius: MacrovaRadius.borderMd,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.kitchen_outlined, color: tokens.accent, size: 20),
              const SizedBox(width: MacrovaSpacing.sm),
              Expanded(
                child: Text(
                  batches.isEmpty
                      ? 'Meal prep'
                      : 'Meal prep · ${batches.length} active',
                  style: MacrovaTypography.titleSm(tokens.inkPrimary),
                ),
              ),
              if (!collapsed && batches.isNotEmpty)
                MacrovaChip(
                  key: newBatchKey,
                  label: '+ New batch',
                  variant: MacrovaChipVariant.dashedAdd,
                  onTap: () => _openSheet(context),
                ),
              IconButton(
                key: toggleKey,
                tooltip: collapsed ? 'Expand meal prep' : 'Collapse meal prep',
                icon: Icon(collapsed ? Icons.expand_more : Icons.expand_less),
                color: tokens.inkTertiary,
                onPressed: () => plan.setMealPrepTrayCollapsed(!collapsed),
              ),
            ],
          ),
          if (!collapsed) ...[
            const SizedBox(height: MacrovaSpacing.sm),
            ..._body(context, tokens, plan, recipes, batches),
          ],
        ],
      ),
    );
  }

  List<Widget> _body(
    BuildContext context,
    MacrovaTokens tokens,
    MealPlanProvider plan,
    RecipeProvider recipes,
    List<MealPrepBatch> batches,
  ) {
    final out = <Widget>[];
    final errorMessage = plan.mealPrepErrorMessage;
    if (errorMessage != null) {
      final code = plan.mealPrepErrorCode;
      out.add(
        Row(
          key: errorKey,
          children: [
            Expanded(
              child: Text(
                'Couldn\'t load meal-prep batches'
                '${code == null ? '' : ' ($code)'}: $errorMessage',
                style: MacrovaTypography.caption(tokens.semanticWarningText),
              ),
            ),
            TextButton(
              key: retryKey,
              onPressed: plan.mealPrepLoading ? null : plan.loadMealPrepBatches,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }
    if (batches.isEmpty) {
      if (plan.mealPrepLoading) {
        out.add(const EmptyState.loading(label: 'Loading batches…'));
        return out;
      }
      out
        ..add(
          Text(
            'Cook once, eat several times. A batch fixes a meal-prep recipe to '
            'the plan slots you pick, and the planner fills the rest around '
            'it.',
            style: MacrovaTypography.caption(tokens.inkTertiary),
          ),
        )
        ..add(const SizedBox(height: MacrovaSpacing.md))
        ..add(
          EmptyState(
            key: emptyKey,
            icon: Icons.kitchen_outlined,
            label: '+ New batch',
            onTap: () => _openSheet(context),
          ),
        );
      return out;
    }
    for (final b in batches) {
      out.add(_BatchRow(
        batch: b,
        recipeName: recipes.getById(b.recipeId)?.name ?? b.recipeId,
        onCancel: () => _confirmCancel(context, b),
      ));
    }
    return out;
  }

  static Future<void> _openSheet(BuildContext context) async {
    final messenger = ScaffoldMessenger.maybeOf(context);
    final reran = await CreateBatchSheet.show(context);
    if (reran == null) return;
    messenger?.showSnackBar(
      SnackBar(
        content: Text(
          reran
              ? 'Batch created. The plan was re-run with its slots.'
              : 'Batch created. Generate a plan to use it.',
        ),
      ),
    );
  }

  static Future<void> _confirmCancel(
    BuildContext context,
    MealPrepBatch batch,
  ) async {
    final plan = context.read<MealPlanProvider>();
    final messenger = ScaffoldMessenger.maybeOf(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel this batch?'),
        content: Text(
          'The planner stops reserving its '
          '${batch.assignments.length == 1 ? 'slot' : '${batch.assignments.length} slots'}. '
          'Meals already in this plan stay until you re-generate it.',
        ),
        actions: [
          TextButton(
            key: cancelDismissKey,
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Keep batch'),
          ),
          TextButton(
            key: cancelConfirmKey,
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Cancel batch'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await plan.cancelMealPrepBatch(batch.id);
      messenger?.showSnackBar(
        const SnackBar(
          content: Text('Batch cancelled. Re-generate the plan to free its '
              'slots.'),
        ),
      );
    } on ApiException catch (e) {
      messenger?.showSnackBar(
        SnackBar(content: Text('Batch not cancelled (${e.code}): ${e.message}')),
      );
    } catch (e) {
      messenger?.showSnackBar(
        SnackBar(content: Text('Batch not cancelled: $e')),
      );
    }
  }
}

class _BatchRow extends StatelessWidget {
  final MealPrepBatch batch;
  final String recipeName;
  final VoidCallback onCancel;

  const _BatchRow({
    required this.batch,
    required this.recipeName,
    required this.onCancel,
  });

  static String _num(double v) =>
      v == v.roundToDouble() ? v.round().toString() : v.toString();

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final slots = [
      for (final a in batch.assignments)
        'Day ${a.dayIndex + 1} · meal ${a.slotIndex + 1}',
    ];
    return Padding(
      key: MealPrepTray.batchKey(batch.id),
      padding: const EdgeInsets.only(top: MacrovaSpacing.sm),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  recipeName,
                  style: MacrovaTypography.bodyMedium(tokens.inkPrimary),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '${_num(batch.remainingServings)}/${batch.totalServings} '
                  'servings left · cook ${batch.cookDate}',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
                if (slots.isNotEmpty)
                  Text(
                    slots.join(', '),
                    style: MacrovaTypography.caption(tokens.inkQuaternary),
                  ),
              ],
            ),
          ),
          IconButton(
            key: MealPrepTray.cancelKey(batch.id),
            tooltip: 'Cancel batch',
            icon: const Icon(Icons.close),
            color: tokens.inkTertiary,
            onPressed: onCancel,
          ),
        ],
      ),
    );
  }
}
