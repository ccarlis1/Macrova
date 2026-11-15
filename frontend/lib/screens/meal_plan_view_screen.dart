import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/micronutrient_metadata.dart';
import '../models/models.dart';
import '../models/user_profile.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/failure_view_model.dart';
import '../widgets/meal_card.dart';
import '../widgets/meal_detail_sheet.dart';
import '../widgets/meal_plan_calendar.dart';
import '../widgets/meal_prep_tray.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/section_header.dart';
import '../widgets/segmented_control.dart';
import '../widgets/stat_card.dart';

class MealPlanViewScreen extends StatefulWidget {
  const MealPlanViewScreen({super.key});

  @override
  State<MealPlanViewScreen> createState() => _MealPlanViewScreenState();
}

class _MealPlanViewScreenState extends State<MealPlanViewScreen> {
  bool _showCalendar = false;

  @override
  void initState() {
    super.initState();
    // Batches are server-owned: fetch the active ones for the tray.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      context.read<MealPlanProvider>().loadMealPrepBatches();
    });
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final planProvider = context.watch<MealPlanProvider>();
    final mealPlan = planProvider.mealPlan;
    final profile = context.watch<ProfileProvider>().profile;

    if (mealPlan == null) {
      // The meal-prep tray is always visible, even before a plan exists.
      return SingleChildScrollView(
        padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 800),
            child: Column(
              children: [
                const MealPrepTray(),
                const SizedBox(height: MacrovaSpacing.sectionTop),
                _EmptyPlanState(tokens: tokens),
              ],
            ),
          ),
        ),
      );
    }

    final totalNutrition = mealPlan.totalNutrition;
    // UX branch key is plan_status (not success / termination_code).
    final isIncomplete = mealPlan.planStatus != 'success';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 800),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Meal Plan View',
                      style: MacrovaTypography.headline(tokens.inkPrimary),
                    ),
                  ),
                  const SizedBox(width: MacrovaSpacing.md),
                  SegmentedControl<bool>(
                    value: _showCalendar,
                    onChanged: (v) => setState(() => _showCalendar = v),
                    options: const [
                      SegmentedOption(value: false, label: 'Daily List'),
                      SegmentedOption(value: true, label: 'Calendar'),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.xlAlt),
              const MealPrepTray(),
              const SizedBox(height: MacrovaSpacing.xlAlt),

              if (_showCalendar) ...[
                MealPlanCalendar(
                  dailyPlans: mealPlan.dailyPlans,
                  isCooked: planProvider.isCooked,
                  onMealTap: (day, mealIndex, meal) {
                    MealDetailSheet.show(
                      context: context,
                      meal: meal,
                      day: day,
                      mealIndex: mealIndex,
                      isCooked: planProvider.isCooked(day, mealIndex),
                      onToggleCooked: () =>
                          planProvider.toggleCooked(day, mealIndex),
                    );
                  },
                ),
              ] else ...[
                // Plan-wide macro totals (whole horizon; multi-day = sum or
                // weekly_totals).
                _buildTotals(context, tokens, mealPlan.days, totalNutrition),
                const SizedBox(height: MacrovaSpacing.xlAlt),

                // Plan micronutrients vs profile targets (daily × plan length).
                _buildMicronutrients(context, tokens, profile, mealPlan),
                const SizedBox(height: MacrovaSpacing.sectionTop),

                // Per-day breakdown from API daily_plans.
                _buildDailyBreakdown(context, tokens, mealPlan),
              ],

              // Structured planner outcome: keep actionable failures distinct
              // from success-with-warnings advisories. Rendered regardless of
              // the view toggle so the outcome is never hidden. The daily list
              // shows slot failures on their slot; the calendar has no slot
              // rows, so there they join the hero panel.
              if (isIncomplete) ...[
                const SizedBox(height: MacrovaSpacing.sectionTop),
                FailureViewModel.fromMealPlan(
                  mealPlan,
                  shownInline: _showCalendar ? null : (_) => true,
                ).toHeroPanel(context),
                // Pre-plan sync rejections may be why the plan failed, so
                // they show here too (the server's warnings stay success-only).
                if (mealPlan.syncWarnings.isNotEmpty) ...[
                  const SizedBox(height: MacrovaSpacing.md),
                  syncWarningsCard(mealPlan),
                ],
              ] else if (mealPlan.warnings.isNotEmpty) ...[
                const SizedBox(height: MacrovaSpacing.sectionTop),
                const SectionHeader(title: 'Advisories'),
                AdvisoryCard(
                  variant: AdvisoryVariant.warn,
                  title: 'Plan generated with advisories',
                  description: mealPlan.warnings.join('\n'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTotals(
    BuildContext context,
    MacrovaTokens tokens,
    int planDays,
    dynamic totalNutrition,
  ) {
    final title = planDays > 1 ? 'Plan totals' : 'Daily totals';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: title),
        _StatCardGrid(
          cards: [
            StatCard(
              label: 'Calories',
              value: '${totalNutrition.calories.round()}',
              unit: 'kcal',
            ),
            StatCard(
              label: 'Protein',
              value: '${totalNutrition.proteinG.round()}',
              unit: 'g',
              variant: StatCardVariant.protein,
            ),
            StatCard(
              label: 'Carbs',
              value: '${totalNutrition.carbsG.round()}',
              unit: 'g',
              variant: StatCardVariant.carb,
            ),
            StatCard(
              label: 'Fat',
              value: '${totalNutrition.fatG.round()}',
              unit: 'g',
              variant: StatCardVariant.fat,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildMicronutrients(
    BuildContext context,
    MacrovaTokens tokens,
    UserProfile profile,
    MealPlan mealPlan,
  ) {
    final goals = profile.micronutrientGoals;
    final microJson = goals.toJson();
    final hasGoals = microJson.values.any((v) => (v as num) > 0);

    if (!hasGoals) return const SizedBox.shrink();

    final actual = mealPlan.totalNutrition.micronutrients;
    final periodDays = mealPlan.days.clamp(1, 7);

    final rows = <Widget>[];
    for (final meta in kMicronutrientsInDisplayOrder) {
      if (((microJson[meta.key] as num?)?.toDouble() ?? 0) > 0) {
        rows.add(
          Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: MicronutrientBar(
              label: meta.label,
              value: actual[meta.key] ?? 0,
              target: (microJson[meta.key] as num).toDouble() * periodDays,
              unit: meta.unit,
              isLimit: meta.isLimit,
            ),
          ),
        );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Micronutrient Targets',
          subtitle: 'Plan totals vs daily profile goals × $periodDays day(s)',
        ),
        Container(
          padding: const EdgeInsets.all(MacrovaSpacing.lg),
          decoration: BoxDecoration(
            borderRadius: MacrovaRadius.borderMd,
            border: Border.all(color: tokens.lineDefault),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: rows,
          ),
        ),
      ],
    );
  }

  Widget _buildDailyBreakdown(
    BuildContext context,
    MacrovaTokens tokens,
    MealPlan mealPlan,
  ) {
    final planProvider = context.watch<MealPlanProvider>();
    // Days with meals, plus days that only carry slot failures (0-based
    // day_index → 1-based MealPlanDay.day).
    final mealsByDay = <int, MealPlanDay>{
      for (final d in mealPlan.dailyPlans)
        if (d.meals.isNotEmpty) d.day: d,
    };
    final dayNumbers = <int>{
      ...mealsByDay.keys,
      for (final f in mealPlan.failures)
        if (f.isSlotFailure) f.dayIndex! + 1,
    }.toList()
      ..sort();
    if (dayNumbers.isEmpty) {
      return Center(
        child: Text(
          'No meals in this plan',
          style: MacrovaTypography.body(tokens.inkTertiary),
        ),
      );
    }

    final blocks = <Widget>[];
    for (final dayNumber in dayNumbers) {
      final d = mealsByDay[dayNumber];
      final dayMeals = d?.meals ?? const <Meal>[];
      blocks.add(
        SectionHeader(
          title: 'Day $dayNumber',
          action: d == null
              ? null
              : Text(
                  '${d.dayTotals.calories.round()} kcal \u2022 '
                  '${d.dayTotals.proteinG.round()}g P \u2022 '
                  '${d.dayTotals.carbsG.round()}g C \u2022 '
                  '${d.dayTotals.fatG.round()}g F',
                  style: MacrovaTypography.caption(tokens.inkTertiary)
                      .copyWith(
                    fontFeatures: MacrovaTypography.tabularFigures,
                  ),
                ),
        ),
      );
      blocks.addAll(
        FailureViewModel.slotRowsForDay(
          plan: mealPlan,
          dayIndex: dayNumber - 1,
          meals: dayMeals,
          wrap: (row) => Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: row,
          ),
          mealBuilder: (i) {
            final meal = dayMeals[i];
            final recipeName =
                meal.recipe['name'] as String? ?? 'Unknown Recipe';
            // Missing/unresolved recipes are surfaced by the model as an
            // error meal named "Missing recipe …"; structured slot failures
            // render as inline FailurePanel rows next to the slot.
            final isMissing = recipeName.startsWith('Missing recipe');
            final day = dayNumber;
            final mealIndex = i;
            return MealCard(
              mealType: meal.mealType,
              recipeName: recipeName,
              calories: meal.nutrition.calories,
              proteinG: meal.nutrition.proteinG,
              carbsG: meal.nutrition.carbsG,
              fatG: meal.nutrition.fatG,
              mealTypeMatch: meal.mealTypeMatch,
              source: meal.source,
              servings: meal.servings,
              slotState: isMissing ? MealSlotState.warn : MealSlotState.ok,
              warningText: isMissing ? 'Recipe unavailable' : null,
              isCooked: planProvider.isCooked(day, mealIndex),
              onTap: () {
                MealDetailSheet.show(
                  context: context,
                  meal: meal,
                  day: day,
                  mealIndex: mealIndex,
                  isCooked: planProvider.isCooked(day, mealIndex),
                  onToggleCooked: () =>
                      planProvider.toggleCooked(day, mealIndex),
                );
              },
            );
          },
        ),
      );
      blocks.add(const SizedBox(height: MacrovaSpacing.lg));
    }
    if (blocks.isNotEmpty) {
      blocks.removeLast();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: blocks,
    );
  }
}

/// Key of the sync-rejection advisory on a failed or partial plan.
const syncWarningsCardKey = Key('plan_sync_warnings');

/// [AdvisoryCard] for [MealPlan.syncWarnings] next to the `FailurePanel`
/// (Today and Meal Plan View).
Widget syncWarningsCard(MealPlan plan) => AdvisoryCard(
      key: syncWarningsCardKey,
      variant: AdvisoryVariant.warn,
      title: plan.syncWarnings.length == 1
          ? 'A recipe was not synced'
          : '${plan.syncWarnings.length} recipes were not synced',
      description: plan.syncWarnings.join('\n'),
    );

class _EmptyPlanState extends StatelessWidget {
  final MacrovaTokens tokens;

  const _EmptyPlanState({required this.tokens});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: MacrovaSpacing.xxl),
          Icon(
            Icons.view_list_outlined,
            size: 64,
            color: tokens.inkQuaternary,
          ),
          const SizedBox(height: MacrovaSpacing.lg),
          Text(
            'Generate a plan from the Planner tab',
            style: MacrovaTypography.body(tokens.inkTertiary),
          ),
        ],
      ),
    );
  }
}

class _StatCardGrid extends StatelessWidget {
  final List<Widget> cards;

  const _StatCardGrid({required this.cards});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        const spacing = MacrovaSpacing.md;
        final columns = constraints.maxWidth >= 480 ? 4 : 2;
        final width =
            (constraints.maxWidth - spacing * (columns - 1)) / columns;
        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          children: [
            for (final card in cards) SizedBox(width: width, child: card),
          ],
        );
      },
    );
  }
}
