import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/micronutrient_metadata.dart';
import '../models/models.dart';
import '../models/user_profile.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/failure_panel.dart';
import '../widgets/meal_card.dart';
import '../widgets/meal_plan_calendar.dart';
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
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final planProvider = context.watch<MealPlanProvider>();
    final mealPlan = planProvider.mealPlan;
    final profile = context.watch<ProfileProvider>().profile;

    if (mealPlan == null) {
      return _EmptyPlanState(tokens: tokens);
    }

    final totalNutrition = mealPlan.totalNutrition;
    // Deterministic planner reports feasibility via `success`. A false value is
    // an actionable failure (FailurePanel); true-with-warnings is an advisory.
    final isFailure = !mealPlan.success;

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

              if (_showCalendar) ...[
                MealPlanCalendar(dailyPlans: mealPlan.dailyPlans),
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
              // the view toggle so the outcome is never hidden.
              if (isFailure) ...[
                const SizedBox(height: MacrovaSpacing.sectionTop),
                _buildFailurePanel(mealPlan),
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
    final days = mealPlan.dailyPlans;
    if (days.isEmpty || days.every((d) => d.meals.isEmpty)) {
      return Center(
        child: Text(
          'No meals in this plan',
          style: MacrovaTypography.body(tokens.inkTertiary),
        ),
      );
    }

    final blocks = <Widget>[];
    for (final d in days) {
      if (d.meals.isEmpty) continue;
      blocks.add(
        SectionHeader(
          title: 'Day ${d.day}',
          action: Text(
            '${d.dayTotals.calories.round()} kcal \u2022 '
            '${d.dayTotals.proteinG.round()}g P \u2022 '
            '${d.dayTotals.carbsG.round()}g C \u2022 '
            '${d.dayTotals.fatG.round()}g F',
            style: MacrovaTypography.caption(tokens.inkTertiary).copyWith(
              fontFeatures: MacrovaTypography.tabularFigures,
            ),
          ),
        ),
      );
      for (final meal in d.meals) {
        final recipeName = meal.recipe['name'] as String? ?? 'Unknown Recipe';
        // Missing/unresolved recipes are surfaced by the model as an error meal
        // named "Missing recipe …" — the only per-slot warn signal the plan
        // response carries. Everything else stays in the default ok state
        // (pinned/empty/workout data is not present in the plan response).
        final isMissing = recipeName.startsWith('Missing recipe');
        blocks.add(
          Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: MealCard(
              mealType: meal.mealType,
              recipeName: recipeName,
              calories: meal.nutrition.calories,
              proteinG: meal.nutrition.proteinG,
              carbsG: meal.nutrition.carbsG,
              fatG: meal.nutrition.fatG,
              slotState: isMissing ? MealSlotState.warn : MealSlotState.ok,
              warningText: isMissing ? 'Recipe unavailable' : null,
            ),
          ),
        );
      }
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

  /// Re-structures the flattened failure warnings back into a [FailurePanel]
  /// without inventing data: the termination code is recovered from the
  /// "Planner ended with …" line the model appends; remaining lines are the
  /// cause.
  Widget _buildFailurePanel(MealPlan mealPlan) {
    String? code;
    final causeLines = <String>[];
    for (final w in mealPlan.warnings) {
      final match = RegExp(r'^Planner ended with (.+)$').firstMatch(w);
      if (match != null) {
        code = match.group(1)?.trim();
      } else {
        causeLines.add(w);
      }
    }
    final cause = causeLines.isNotEmpty
        ? causeLines.join('\n')
        : 'The planner could not build a feasible plan for these constraints.';
    return FailurePanel(
      terminationCode: code ?? '\u2014',
      cause: cause,
    );
  }
}

class _EmptyPlanState extends StatelessWidget {
  final MacrovaTokens tokens;

  const _EmptyPlanState({required this.tokens});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
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
