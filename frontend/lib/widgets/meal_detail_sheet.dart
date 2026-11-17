import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/meal_prep_batch.dart';
import '../models/models.dart';
import '../providers/meal_plan_provider.dart';
import '../services/api_service.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';
import 'macrova_chip.dart';
import 'macrova_sheet.dart';
import 'sticky_cta.dart';

/// Meal-slot detail sheet: summary, a Pin/Unpin action for the slot (FE-15)
/// and the local Mark cooked CTA. No Swap.
///
/// The pin action needs a [MealPlanProvider] above the sheet; without one
/// (e.g. isolated widget tests) it is not shown. It pins the plan's own
/// 0-based `(day - 1, meal.slotIndex)`, re-fetches pins, and does not re-run
/// the plan ("Applies next time you plan").
class MealDetailSheet {
  MealDetailSheet._();

  /// Batch variant (FE-14): shown when `meal.source == meal_prep_batch`.
  static const mealPrepKey = Key('meal_detail_meal_prep');

  /// "Pinned" row, shown when the plan placed this meal from a pin.
  static const pinnedKey = Key('meal_detail_pinned');

  /// The Pin / Unpin button.
  static const pinActionKey = Key('meal_detail_pin_action');

  /// Pin status line (pinned or not, and which recipe).
  static const pinStatusKey = Key('meal_detail_pin_status');

  /// One-line precedence explanation (batch slots: meal prep overrides pins).
  static const pinPrecedenceKey = Key('meal_detail_pin_precedence');

  /// "Applies next time you plan".
  static const pinNextPlanKey = Key('meal_detail_pin_next_plan');

  /// Server code + message of a failed pin / unpin.
  static const pinErrorKey = Key('meal_detail_pin_error');

  static Future<void> show({
    required BuildContext context,
    required Meal meal,
    required int day,
    required int mealIndex,
    required bool isCooked,
    required VoidCallback onToggleCooked,
  }) {
    final recipeName = meal.recipe['name'] as String? ?? 'Unknown Recipe';
    final cookedLabel = isCooked ? 'Mark not cooked' : 'Mark cooked';

    return MacrovaSheet.show(
      context: context,
      title: meal.mealType,
      subtitle: 'Day $day',
      body: _MealDetailBody(
        meal: meal,
        recipeName: recipeName,
        day: day,
        mealIndex: mealIndex,
      ),
      cta: StickyCta(
        label: 'This device only',
        detail: isCooked ? 'Marked cooked' : 'Not marked cooked',
        actions: [
          StickyCtaAction(
            label: cookedLabel,
            isPrimary: true,
            onPressed: () {
              onToggleCooked();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
    );
  }
}

class _MealDetailBody extends StatelessWidget {
  final Meal meal;
  final String recipeName;
  final int day;
  final int mealIndex;

  const _MealDetailBody({
    required this.meal,
    required this.recipeName,
    required this.day,
    required this.mealIndex,
  });

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return ListView(
      padding: const EdgeInsets.only(top: MacrovaSpacing.lg),
      children: [
        Text(
          recipeName,
          style: MacrovaTypography.subtitle(tokens.inkPrimary),
        ),
        if (meal.isMealPrepBatch) ...[
          const SizedBox(height: MacrovaSpacing.sm),
          Row(
            key: MealDetailSheet.mealPrepKey,
            children: [
              const MacrovaChip(
                label: 'Meal prep',
                variant: MacrovaChipVariant.accent,
                leadingIcon: Icons.kitchen_outlined,
              ),
              const SizedBox(width: MacrovaSpacing.sm),
              Expanded(
                child: Text(
                  meal.servings == null
                      ? 'From a meal-prep batch'
                      : 'From a meal-prep batch · '
                          '${servingsLabel(meal.servings!)}',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
              ),
            ],
          ),
        ],
        if (meal.source == Meal.sourcePinnedAssignment) ...[
          const SizedBox(height: MacrovaSpacing.sm),
          Row(
            key: MealDetailSheet.pinnedKey,
            children: [
              const MacrovaChip(
                label: 'Pinned',
                variant: MacrovaChipVariant.pinned,
                leadingIcon: Icons.push_pin_outlined,
              ),
              const SizedBox(width: MacrovaSpacing.sm),
              Expanded(
                child: Text(
                  'Placed here by a pin',
                  style: MacrovaTypography.caption(tokens.inkTertiary),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: MacrovaSpacing.md),
        MacroDisplay(
          calories: meal.nutrition.calories,
          proteinG: meal.nutrition.proteinG,
          carbsG: meal.nutrition.carbsG,
          fatG: meal.nutrition.fatG,
        ),
        if (context.watch<MealPlanProvider?>() != null) ...[
          const SizedBox(height: MacrovaSpacing.xl),
          _PinSection(meal: meal, day: day, mealIndex: mealIndex),
        ],
        const SizedBox(height: MacrovaSpacing.xl),
        Text(
          'Cooked status is saved on this device only. '
          'It is not sent to the planner.',
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
      ],
    );
  }
}

/// Pin / Unpin for the slot the sheet shows (FE-15). Reads and changes pins
/// on [MealPlanProvider]; never re-runs the plan.
class _PinSection extends StatefulWidget {
  final Meal meal;
  final int day;
  final int mealIndex;

  const _PinSection({
    required this.meal,
    required this.day,
    required this.mealIndex,
  });

  @override
  State<_PinSection> createState() => _PinSectionState();
}

class _PinSectionState extends State<_PinSection> {
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // The Pin/Unpin label needs the server's pins; fetch them once if no
    // screen has yet.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final plan = context.read<MealPlanProvider>();
      if (!plan.pinsLoaded && !plan.pinsLoading) plan.loadPins();
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on ApiException catch (e) {
      _error = '${e.code}: ${e.message}';
    } catch (e) {
      _error = e.toString();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final plan = context.watch<MealPlanProvider>();
    final meal = widget.meal;
    final (dayIndex, slotIndex) =
        MealPlanProvider.pinSlotFor(widget.day, widget.mealIndex, meal);
    final pin = plan.pinAt(dayIndex, slotIndex);
    final recipeId = meal.recipeId;
    final isBatch = meal.isMealPrepBatch;

    final String status;
    if (pin == null) {
      status = 'Not pinned';
    } else if (pin.recipeId == recipeId) {
      status = 'Pinned to this slot';
    } else {
      status = 'Another recipe is pinned to this slot (${pin.recipeId})';
    }

    // Pinning needs a recipe id; a batch slot can't take a new pin (the
    // batch lock wins), but an existing pin there can still be removed.
    final canAct = !_busy &&
        !plan.pinsLoading &&
        (pin != null || (!isBatch && recipeId != null && recipeId.isNotEmpty));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.push_pin_outlined, size: 18, color: tokens.pinned),
            const SizedBox(width: MacrovaSpacing.sm),
            Expanded(
              child: Text(
                status,
                key: MealDetailSheet.pinStatusKey,
                style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
              ),
            ),
            const SizedBox(width: MacrovaSpacing.sm),
            OutlinedButton(
              key: MealDetailSheet.pinActionKey,
              onPressed: !canAct
                  ? null
                  : () => _run(() async {
                        if (pin != null) {
                          await plan.unpinSlot(dayIndex, slotIndex);
                        } else {
                          await plan.pinRecipe(dayIndex, slotIndex, recipeId!);
                        }
                      }),
              child: Text(pin == null ? 'Pin' : 'Unpin'),
            ),
          ],
        ),
        const SizedBox(height: MacrovaSpacing.xs),
        Text(
          isBatch
              ? 'Meal prep overrides pins for this meal'
              : 'A pin keeps this recipe here when you re-plan. '
                  'Meal prep beats pins; pins beat tags.',
          key: MealDetailSheet.pinPrecedenceKey,
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
        Text(
          'Applies next time you plan',
          key: MealDetailSheet.pinNextPlanKey,
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
        if (_error != null) ...[
          const SizedBox(height: MacrovaSpacing.xs),
          Text(
            _error!,
            key: MealDetailSheet.pinErrorKey,
            style: MacrovaTypography.caption(tokens.semanticWarningText),
          ),
        ],
      ],
    );
  }
}
