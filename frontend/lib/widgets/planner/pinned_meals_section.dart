import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/meal_plan_provider.dart';
import '../../services/api_service.dart';
import '../../theme/tokens.dart';
import '../section_header.dart';

/// Planner Config: how many meals are pinned on the server, and "Clear pins"
/// (confirm first). Pins are server-owned (FE-15); the count is
/// [MealPlanProvider.pinCount] after [MealPlanProvider.loadPins]. Clearing
/// does not re-run the plan.
class PinnedMealsSection extends StatefulWidget {
  const PinnedMealsSection({super.key});

  static const countKey = Key('pinned_meals_count');
  static const clearKey = Key('pinned_meals_clear');
  static const clearConfirmKey = Key('pinned_meals_clear_confirm');
  static const clearDismissKey = Key('pinned_meals_clear_dismiss');
  static const errorKey = Key('pinned_meals_error');
  static const retryKey = Key('pinned_meals_retry');

  /// "No pinned meals", "1 pinned meal", "3 pinned meals".
  static String countLabel(int n) => n == 0
      ? 'No pinned meals'
      : n == 1
          ? '1 pinned meal'
          : '$n pinned meals';

  @override
  State<PinnedMealsSection> createState() => _PinnedMealsSectionState();
}

class _PinnedMealsSectionState extends State<PinnedMealsSection> {
  bool _clearing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<MealPlanProvider>().loadPins();
    });
  }

  Future<void> _confirmClear(int count) async {
    final plan = context.read<MealPlanProvider>();
    final messenger = ScaffoldMessenger.maybeOf(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear all pins?'),
        content: Text(
          'This removes ${PinnedMealsSection.countLabel(count).toLowerCase()} '
          'from the server. The planner can choose any recipe for those '
          'slots the next time you plan.',
        ),
        actions: [
          TextButton(
            key: PinnedMealsSection.clearDismissKey,
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Keep pins'),
          ),
          TextButton(
            key: PinnedMealsSection.clearConfirmKey,
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Clear pins'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    setState(() => _clearing = true);
    try {
      final n = await plan.clearPins();
      messenger?.showSnackBar(
        SnackBar(
          content: Text(
            'Cleared ${n == 1 ? '1 pin' : '$n pins'}. '
            'Applies next time you plan.',
          ),
        ),
      );
    } on ApiException catch (e) {
      messenger?.showSnackBar(
        SnackBar(content: Text('Pins not cleared (${e.code}): ${e.message}')),
      );
    } catch (e) {
      messenger?.showSnackBar(SnackBar(content: Text('Pins not cleared: $e')));
    } finally {
      if (mounted) setState(() => _clearing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final plan = context.watch<MealPlanProvider>();
    final count = plan.pinCount;
    final errorCode = plan.pinsErrorCode;
    final errorMessage = plan.pinsErrorMessage;
    final hasError = errorCode != null || errorMessage != null;

    final String countText;
    if (!plan.pinsLoaded) {
      countText = plan.pinsLoading ? 'Loading pins…' : 'Pins not loaded';
    } else {
      countText = PinnedMealsSection.countLabel(count);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'Pinned meals'),
        Text(
          'Pin a meal from its detail sheet on Meal Plan View to keep it in '
          'that slot when you re-plan. Meal prep beats pins; pins beat tags.',
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
        const SizedBox(height: MacrovaSpacing.sm),
        Row(
          children: [
            Expanded(
              child: Text(
                countText,
                key: PinnedMealsSection.countKey,
                style: MacrovaTypography.bodyMedium(tokens.inkSecondary),
              ),
            ),
            OutlinedButton(
              key: PinnedMealsSection.clearKey,
              onPressed: count == 0 || _clearing || plan.pinsLoading
                  ? null
                  : () => _confirmClear(count),
              child: const Text('Clear pins'),
            ),
          ],
        ),
        if (hasError) ...[
          const SizedBox(height: MacrovaSpacing.xs),
          Row(
            children: [
              Expanded(
                child: Text(
                  errorCode == null
                      ? 'Pins unavailable: $errorMessage'
                      : 'Pins unavailable ($errorCode): $errorMessage',
                  key: PinnedMealsSection.errorKey,
                  style: MacrovaTypography.caption(tokens.semanticWarningText),
                ),
              ),
              TextButton(
                key: PinnedMealsSection.retryKey,
                onPressed: plan.pinsLoading ? null : plan.loadPins,
                child: const Text('Retry'),
              ),
            ],
          ),
        ],
      ],
    );
  }
}
