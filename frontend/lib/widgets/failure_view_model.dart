import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/llm_config_provider.dart';
import '../models/micronutrient_metadata.dart';
import '../models/models.dart';
import '../providers/meal_plan_provider.dart';
import 'app_shell.dart';
import 'failure_panel.dart';
import 'starter_pack_sheet.dart';

/// Maps structured [PlanFailure] / incomplete plan status into [FailurePanel] props.
///
/// Field mapping (see `docs/frontend/failure-handling.md`):
/// `code` → code chip, `explanation` (else `message`) → headline,
/// `fix` (else `fix_hint`) → fix line. Failures naming a slot
/// (`day_index` + `slot_index`) render inline on that slot via [slotPanel];
/// the rest go to the hero panel. `report.failure_cause` drives the
/// recipe-help row ([recipeHelpRow]).
class FailureViewModel {
  /// Shell index of the Agent tab, which shows Agent Setup until the LLM gate is ready.
  static const int agentNavIndex = 7;

  /// `planning_mode` the "Find a recipe" action re-runs with.
  static const String findRecipePlanningMode = 'assisted';

  static const Key heroKey = ValueKey('failure-hero');
  static const Key findRecipeKey = ValueKey('failure-find-recipe');
  static const Key setupAiKey = ValueKey('failure-setup-ai');
  static const Key recipeGapKey = ValueKey('failure-recipe-gap');
  static const Key starterPackKey = ValueKey('failure-starter-pack');

  /// `failure_cause.cause` for a plan with no recipes to plan with (BE-22).
  static const String emptyPoolCause = 'EMPTY_POOL';

  /// Key of the inline row for a failure on 0-based [dayIndex] / [slotIndex].
  static Key slotKey(int dayIndex, int slotIndex) =>
      ValueKey('failure-slot-$dayIndex-$slotIndex');

  final String terminationCode;
  final String cause;
  final String? fixHint;
  /// Further hero failures (beyond the headline one), one row each.
  final List<FailureFixRow> fixes;
  /// Plan-wide diagnosis (`report.failure_cause`).
  final PlanFailureCause? failureCause;

  const FailureViewModel({
    required this.terminationCode,
    required this.cause,
    this.fixHint,
    this.fixes = const [],
    this.failureCause,
  });

  /// Headline for [failure]: `explanation`, else `message`.
  static String headlineOf(PlanFailure failure) {
    final e = failure.explanation?.trim();
    if (e != null && e.isNotEmpty) return e;
    return failure.message;
  }

  /// One-line fix for [failure]: `fix`, else `fix_hint`.
  static String? fixOf(PlanFailure failure) {
    final f = failure.fix?.trim();
    if (f != null && f.isNotEmpty) return f;
    return failure.fixHint;
  }

  factory FailureViewModel.fromPlanFailure(
    PlanFailure failure, {
    List<FailureFixRow> fixes = const [],
    PlanFailureCause? failureCause,
  }) {
    return FailureViewModel(
      terminationCode: failure.code,
      cause: headlineOf(failure),
      fixHint: fixOf(failure),
      fixes: fixes,
      failureCause: failureCause,
    );
  }

  /// Incomplete / non-success plan when no hero failure is available.
  factory FailureViewModel.incomplete({
    required String? planStatusMessage,
    String? fixHint,
    PlanFailureCause? failureCause,
  }) {
    final msg = planStatusMessage?.trim();
    return FailureViewModel(
      terminationCode: 'Incomplete plan',
      cause: (msg != null && msg.isNotEmpty) ? msg : 'Incomplete plan',
      fixHint: fixHint,
      failureCause: failureCause,
    );
  }

  /// Hero panel model for [plan].
  ///
  /// Every failure the screen does not render inline on its slot is shown
  /// here: the first as the headline, the rest as rows. [shownInline] says
  /// which slot failures the calling screen renders on their slot (Meal Plan
  /// View list: all; Today: day 1 only; default: none), so nothing is hidden.
  factory FailureViewModel.fromMealPlan(
    MealPlan plan, {
    bool Function(PlanFailure failure)? shownInline,
  }) {
    bool inline(PlanFailure f) =>
        f.isSlotFailure && shownInline != null && shownInline(f);
    final hero = [
      for (final f in plan.failures)
        if (!inline(f)) f,
    ];
    if (hero.isNotEmpty) {
      return FailureViewModel.fromPlanFailure(
        hero.first,
        fixes: [for (final f in hero.skip(1)) failureRow(f)],
        failureCause: plan.failureCause,
      );
    }
    final slotCount = plan.failures.where(inline).length;
    return FailureViewModel.incomplete(
      planStatusMessage: plan.planStatusMessage,
      fixHint: slotCount == 0
          ? null
          : slotCount == 1
              ? 'One meal slot could not be filled; it is marked below.'
              : '$slotCount meal slots could not be filled; they are marked below.',
      failureCause: plan.failureCause,
    );
  }

  /// Hero row for an extra failure: headline + "code · fix".
  static FailureFixRow failureRow(PlanFailure f) {
    final fix = fixOf(f);
    return FailureFixRow(
      label: headlineOf(f),
      description: fix == null ? f.code : '${f.code} · $fix',
    );
  }

  /// Failures that render inline on 0-based [dayIndex] / [slotIndex].
  static List<PlanFailure> slotFailuresAt(
    MealPlan plan,
    int dayIndex,
    int slotIndex,
  ) =>
      [
        for (final f in plan.failures)
          if (f.isSlotFailure &&
              f.dayIndex == dayIndex &&
              f.slotIndex == slotIndex)
            f,
      ];

  /// Sorted 0-based slot indices on [dayIndex] that have an inline failure.
  static List<int> failingSlotsOnDay(MealPlan plan, int dayIndex) {
    final slots = <int>{
      for (final f in plan.failures)
        if (f.isSlotFailure && f.dayIndex == dayIndex) f.slotIndex!,
    }.toList()
      ..sort();
    return slots;
  }

  /// One day's slot rows in slot order: each meal (built by [mealBuilder] from
  /// its index in [meals]) followed by the inline failures on its slot, and
  /// failing slots that have no meal in their own position. A meal's slot is
  /// its API `slot_index`, else its position.
  static List<Widget> slotRowsForDay({
    required MealPlan plan,
    required int dayIndex,
    required List<Meal> meals,
    required Widget Function(int mealIndex) mealBuilder,
    required Widget Function(Widget row) wrap,
  }) {
    final mealsBySlot = <int, List<int>>{};
    for (var i = 0; i < meals.length; i++) {
      mealsBySlot.putIfAbsent(meals[i].slotIndex ?? i, () => []).add(i);
    }
    final slots = <int>{
      ...mealsBySlot.keys,
      ...failingSlotsOnDay(plan, dayIndex),
    }.toList()
      ..sort();
    return [
      for (final slot in slots) ...[
        for (final i in mealsBySlot[slot] ?? const <int>[]) wrap(mealBuilder(i)),
        for (final f in slotFailuresAt(plan, dayIndex, slot)) wrap(slotPanel(f)),
      ],
    ];
  }

  /// Compact inline panel for a slot failure.
  static FailurePanel slotPanel(PlanFailure failure) => FailurePanel.slot(
        key: slotKey(failure.dayIndex ?? -1, failure.slotIndex ?? -1),
        terminationCode: failure.code,
        cause: headlineOf(failure),
        fixHint: fixOf(failure),
      );

  bool get recipeCouldHelp => failureCause?.recipeCouldHelp == true;

  /// One line built only from the non-null `recipe_gap` fields, or null when
  /// there is no gap or it has nothing to say.
  String? get recipeGapSummary {
    final gap = failureCause?.recipeGap;
    if (!recipeCouldHelp || gap == null) return null;
    return summarizeRecipeGap(gap);
  }

  static String? summarizeRecipeGap(PlanRecipeGap gap) {
    String n(double v) => v.round().toString();
    final macros = <String>[
      if (gap.perMealCalories != null) '${n(gap.perMealCalories!)} kcal',
      if (gap.perMealProteinG != null) '${n(gap.perMealProteinG!)} g protein',
      if (gap.perMealCarbsG != null) '${n(gap.perMealCarbsG!)} g carbs',
      if (gap.perMealFatGMax != null) 'at most ${n(gap.perMealFatGMax!)} g fat',
    ];
    final clauses = <String>[
      if (gap.nutrientMinPerRecipe.isNotEmpty)
        'rich in ${_join([
              for (final k in gap.nutrientMinPerRecipe.keys)
                micronutrientLabelForKey(k),
            ])}',
      if (gap.cookTimeCapMinutes != null)
        'ready in ${gap.cookTimeCapMinutes} min or less',
      if (gap.excludedIngredients.isNotEmpty)
        'without ${_joinCapped(gap.excludedIngredients, 3)}',
    ];
    if (macros.isEmpty && clauses.isEmpty) return null;
    final head = macros.isEmpty ? 'A recipe' : 'A recipe near ${_join(macros)}';
    if (clauses.isEmpty) return '$head would help.';
    return '$head, ${clauses.join(', ')}, would help.';
  }

  static String _join(List<String> items) {
    if (items.length <= 1) return items.join();
    return '${items.sublist(0, items.length - 1).join(', ')} and ${items.last}';
  }

  static String _joinCapped(List<String> items, int max) {
    if (items.length <= max) return _join(items);
    return _join([...items.take(max), '${items.length - max} more']);
  }

  /// Recipe-help row for the hero panel, or null when no recipe would help.
  ///
  /// Ready LLM gate + a re-runnable request → "Find a recipe" (re-plan with
  /// `planning_mode: assisted`). Not ready → "Set up AI help" (Agent Setup).
  /// Ready but no request to re-run (plan came from plan-from-text) → the gap
  /// summary only.
  FailureFixRow? recipeHelpRow({
    required bool llmReady,
    required bool canRerun,
    required VoidCallback onFindRecipe,
    required VoidCallback onSetUpAi,
  }) {
    if (!recipeCouldHelp) return null;
    final summary = recipeGapSummary ?? 'A new recipe could fill this gap.';
    if (!llmReady) {
      return FailureFixRow(
        key: setupAiKey,
        label: 'Set up AI help',
        description: summary,
        onTap: onSetUpAi,
      );
    }
    if (!canRerun) {
      return FailureFixRow(
        key: recipeGapKey,
        label: 'A recipe could help',
        description: summary,
      );
    }
    return FailureFixRow(
      key: findRecipeKey,
      label: 'Find a recipe',
      description: summary,
      onTap: onFindRecipe,
    );
  }

  FailurePanel toPanel({Key? key, List<FailureFixRow> actions = const []}) =>
      FailurePanel(
        key: key,
        terminationCode: terminationCode,
        cause: cause,
        fixHint: fixHint,
        fixes: [...fixes, ...actions],
      );

  /// Hero panel wired to the LLM gate, [MealPlanProvider] and shell navigation.
  ///
  /// Call from a build method under the app's providers.
  FailurePanel toHeroPanel(BuildContext context) {
    final llmReady = context.watch<LlmConfigProvider>().llmReady;
    final planProvider = context.watch<MealPlanProvider>();
    // An empty pool needs recipes the user picks (FE-16); the server's
    // assisted recovery declines to generate for an empty pool.
    final row = failureCause?.cause == emptyPoolCause
        ? FailureFixRow(
            key: starterPackKey,
            label: 'Start from the starter pack',
            description: 'Pick recipes you would eat, import them, then plan '
                'again.',
            onTap: () => StarterPackSheet.show(context),
          )
        : recipeHelpRow(
            llmReady: llmReady,
            canRerun: planProvider.canRerunLastRequest,
            onFindRecipe: () => findRecipe(context),
            onSetUpAi: () => context
                .findAncestorStateOfType<AppShellState>()
                ?.navigateTo(agentNavIndex),
          );
    return toPanel(key: heroKey, actions: [if (row != null) row]);
  }

  /// Re-run the current plan's request with `planning_mode: assisted`; like
  /// Planner Config, a failed assisted call revokes the LLM gate.
  static Future<void> findRecipe(BuildContext context) async {
    final planProvider = context.read<MealPlanProvider>();
    final llmGate = context.read<LlmConfigProvider>();
    if (!llmGate.llmReady) return;
    await planProvider.rerunLastRequest(planningMode: findRecipePlanningMode);
    final error = planProvider.error;
    if (error != null) llmGate.revokeReady(error);
  }
}
