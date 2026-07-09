import 'package:flutter/material.dart';

import '../theme/tokens.dart';
import 'macro_display.dart';

enum MealSlotState { ok, pinned, empty, warn, workout }

class MealCard extends StatelessWidget {
  final String mealType;
  final String recipeName;
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final MealSlotState slotState;
  final String? warningText;
  final String? timeLabel;
  /// Device-local cooked mark — independent of [MealSlotState.pinned].
  final bool isCooked;
  final VoidCallback? onTap;
  final VoidCallback? onAdd;

  const MealCard({
    super.key,
    required this.mealType,
    required this.recipeName,
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    this.slotState = MealSlotState.ok,
    this.warningText,
    this.timeLabel,
    this.isCooked = false,
    this.onTap,
    this.onAdd,
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
