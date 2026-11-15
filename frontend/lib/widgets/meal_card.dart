import 'package:flutter/material.dart';

import '../models/meal_prep_batch.dart';
import '../models/models.dart';
import '../theme/tokens.dart';
import 'macro_display.dart';
import 'macrova_chip.dart';

enum MealSlotState { ok, pinned, empty, warn, workout }

class MealCard extends StatelessWidget {
  final String mealType;
  final String recipeName;
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  /// §4.3: false shows a soft mismatch chip; null/true hide it.
  final bool? mealTypeMatch;
  final MealSlotState slotState;
  final String? warningText;
  final String? timeLabel;
  /// Device-local cooked mark — independent of [MealSlotState.pinned].
  final bool isCooked;
  final VoidCallback? onTap;
  final VoidCallback? onAdd;

  /// `Meal.source` (`PlannedMeal.source`). [Meal.sourceMealPrepBatch] shows
  /// the batch variant: a "Meal prep" badge plus [servings] when set. Other
  /// values (planner, pinned, null) look unchanged.
  final String? source;

  /// Batch servings for this slot (`Meal.servings`); shown on batch meals only.
  final double? servings;

  /// A server pin exists for this slot (`MealPlanProvider.pinForMeal`). When
  /// the plan itself didn't place a pin here (it predates the pin), the card
  /// shows "Pinned · next plan". Ignored on meal-prep batch meals: the batch
  /// lock wins over a pin.
  final bool hasPin;

  static const mealPrepBadgeKey = Key('meal_card_meal_prep_badge');
  static const mealPrepServingsKey = Key('meal_card_meal_prep_servings');

  /// Pin badge (FE-15), on pinned meals and on slots pinned after this plan.
  static const pinBadgeKey = Key('meal_card_pin_badge');

  bool get isMealPrepBatch => source == Meal.sourceMealPrepBatch;

  /// The plan placed this meal from a pin (`source == pinned_assignment`).
  bool get isPinnedAssignment => source == Meal.sourcePinnedAssignment;

  /// Pin badge label, or null when no pin badge shows. Precedence: a batch
  /// meal never shows one; a meal the plan pinned is "Pinned"; a slot pinned
  /// since the plan ran is "Pinned · next plan".
  String? get pinBadgeLabel {
    if (isMealPrepBatch) return null;
    if (isPinnedAssignment) return 'Pinned';
    if (hasPin) return 'Pinned · next plan';
    return null;
  }

  const MealCard({
    super.key,
    required this.mealType,
    required this.recipeName,
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.mealTypeMatch,
    this.slotState = MealSlotState.ok,
    this.warningText,
    this.timeLabel,
    this.isCooked = false,
    this.onTap,
    this.onAdd,
    this.source,
    this.servings,
    this.hasPin = false,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    if (slotState == MealSlotState.empty) {
      return _EmptySlot(
        label: recipeName.isNotEmpty ? recipeName : '+ Add…',
        onTap: onAdd ?? onTap,
        tokens: tokens,
      );
    }

    if (slotState == MealSlotState.workout) {
      return _WorkoutSlot(
        label: recipeName,
        timeLabel: timeLabel,
        onTap: onTap,
        tokens: tokens,
      );
    }

    final isPinned = slotState == MealSlotState.pinned;
    final hasWarn = slotState == MealSlotState.warn;
    final pinLabel = pinBadgeLabel;

    return Card(
      color: isPinned ? tokens.pinnedSoft : null,
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderSm,
        side: BorderSide(
          color: isPinned ? tokens.pinned.withValues(alpha: 0.3) : tokens.lineDefault,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: MacrovaRadius.borderSm,
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.md),
          child: Row(
            children: [
              if (timeLabel != null) ...[
                SizedBox(
                  width: 44,
                  child: Text(
                    timeLabel!,
                    style: MacrovaTypography.labelCaps(tokens.inkTertiary),
                  ),
                ),
              ],
              _MealThumbnail(tokens: tokens, isCooked: isCooked),
              const SizedBox(width: MacrovaSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      mealType,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: tokens.accent,
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    Text(
                      recipeName,
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: isCooked ? tokens.inkTertiary : null,
                          ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (hasWarn && warningText != null) ...[
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          Icon(
                            Icons.warning_amber_rounded,
                            size: 14,
                            color: tokens.semanticWarning,
                          ),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              warningText!,
                              style: MacrovaTypography.caption(tokens.semanticWarningText),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                    if (isMealPrepBatch) ...[
                      const SizedBox(height: MacrovaSpacing.xs),
                      Wrap(
                        spacing: MacrovaSpacing.sm,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          const MacrovaChip(
                            key: mealPrepBadgeKey,
                            label: 'Meal prep',
                            variant: MacrovaChipVariant.accent,
                            leadingIcon: Icons.kitchen_outlined,
                          ),
                          if (servings != null)
                            Text(
                              servingsLabel(servings!),
                              key: mealPrepServingsKey,
                              style:
                                  MacrovaTypography.caption(tokens.inkTertiary),
                            ),
                        ],
                      ),
                    ],
                    if (pinLabel != null) ...[
                      const SizedBox(height: MacrovaSpacing.xs),
                      MacrovaChip(
                        key: pinBadgeKey,
                        label: pinLabel,
                        variant: MacrovaChipVariant.pinned,
                        leadingIcon: Icons.push_pin_outlined,
                      ),
                    ],
                    if (mealTypeMatch == false) ...[
                      const SizedBox(height: MacrovaSpacing.xs),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: MacrovaSpacing.sm,
                          vertical: 2,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: MacrovaRadius.borderSm,
                          border: Border.all(color: tokens.lineDefault),
                        ),
                        child: Text(
                          'Not tagged as $mealType',
                          style: MacrovaTypography.caption(tokens.inkTertiary),
                        ),
                      ),
                    ],
                    const SizedBox(height: MacrovaSpacing.xs),
                    MacroDisplay(
                      calories: calories,
                      proteinG: proteinG,
                      carbsG: carbsG,
                      fatG: fatG,
                      compact: true,
                    ),
                  ],
                ),
              ),
              if (isCooked)
                Padding(
                  padding: const EdgeInsets.only(left: MacrovaSpacing.sm),
                  child: Icon(
                    Icons.check_circle,
                    size: 18,
                    color: tokens.semanticSuccess,
                  ),
                ),
              if (isPinned)
                Container(
                  width: 8,
                  height: 8,
                  margin: const EdgeInsets.only(left: MacrovaSpacing.sm),
                  decoration: BoxDecoration(
                    color: tokens.pinned,
                    shape: BoxShape.circle,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MealThumbnail extends StatelessWidget {
  final MacrovaTokens tokens;
  final bool isCooked;

  const _MealThumbnail({required this.tokens, this.isCooked = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            tokens.accentTint,
            tokens.accent.withValues(alpha: 0.6),
          ],
        ),
        borderRadius: MacrovaRadius.borderSm,
      ),
      child: Icon(
        isCooked ? Icons.check : Icons.restaurant,
        color: tokens.inkQuaternary,
      ),
    );
  }
}

class _EmptySlot extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final MacrovaTokens tokens;

  const _EmptySlot({
    required this.label,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: MacrovaRadius.borderSm,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.lg),
        decoration: BoxDecoration(
          borderRadius: MacrovaRadius.borderSm,
          border: Border.all(
            color: tokens.lineDefault,
            width: 1.5,
            strokeAlign: BorderSide.strokeAlignInside,
          ),
        ),
        child: Center(
          child: Text(
            label,
            style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
          ),
        ),
      ),
    );
  }
}

class _WorkoutSlot extends StatelessWidget {
  final String label;
  final String? timeLabel;
  final VoidCallback? onTap;
  final MacrovaTokens tokens;

  const _WorkoutSlot({
    required this.label,
    required this.timeLabel,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: MacrovaRadius.borderSm,
      child: Container(
        padding: const EdgeInsets.all(MacrovaSpacing.md),
        decoration: BoxDecoration(
          borderRadius: MacrovaRadius.borderSm,
          border: Border.all(
            color: tokens.lineDefault,
            width: 1.5,
            strokeAlign: BorderSide.strokeAlignInside,
          ),
        ),
        child: Row(
          children: [
            if (timeLabel != null) ...[
              SizedBox(
                width: 44,
                child: Text(
                  timeLabel!,
                  style: MacrovaTypography.labelCaps(tokens.inkTertiary),
                ),
              ),
            ],
            Icon(Icons.fitness_center, color: tokens.inkTertiary, size: 20),
            const SizedBox(width: MacrovaSpacing.sm),
            Expanded(
              child: Text(
                label,
                style: MacrovaTypography.label(tokens.inkSecondary),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
