import 'package:flutter/material.dart';

import '../models/models.dart';
import '../theme/tokens.dart';
import 'meal_card.dart';
import 'section_header.dart';

/// Plan-horizon calendar strip bound to [MealPlan.dailyPlans].
///
/// Uses 1-based plan day indices from the API — not a Gregorian month grid.
class MealPlanCalendar extends StatefulWidget {
  final List<MealPlanDay> dailyPlans;

  const MealPlanCalendar({
    super.key,
    required this.dailyPlans,
  });

  @override
  State<MealPlanCalendar> createState() => _MealPlanCalendarState();
}

class _MealPlanCalendarState extends State<MealPlanCalendar> {
  late int? _selectedDay;

  @override
  void initState() {
    super.initState();
    _selectedDay = _initialSelectedDay(widget.dailyPlans);
  }

  @override
  void didUpdateWidget(MealPlanCalendar oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.dailyPlans, widget.dailyPlans)) {
      final stillValid = widget.dailyPlans.any((d) => d.day == _selectedDay);
      if (!stillValid) {
        _selectedDay = _initialSelectedDay(widget.dailyPlans);
      }
    }
  }

  static int? _initialSelectedDay(List<MealPlanDay> days) {
    if (days.isEmpty) return null;
    for (final d in days) {
      if (d.meals.isNotEmpty) return d.day;
    }
    return days.first.day;
  }

  MealPlanDay? get _selectedPlanDay {
    final selected = _selectedDay;
    if (selected == null) return null;
    for (final d in widget.dailyPlans) {
      if (d.day == selected) return d;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final days = widget.dailyPlans;

    if (days.isEmpty || days.every((d) => d.meals.isEmpty)) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.xxl),
          child: Text(
            'No meals in this plan',
            style: MacrovaTypography.body(tokens.inkTertiary),
          ),
        ),
      );
    }

    final selected = _selectedPlanDay;

    return Column(
      key: const ValueKey('meal-plan-calendar'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Plan days',
          subtitle: '${days.length} day${days.length == 1 ? '' : 's'} in horizon',
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            const spacing = MacrovaSpacing.md;
            final columns = constraints.maxWidth >= 480
                ? days.length.clamp(1, 7)
                : (days.length >= 4 ? 4 : days.length.clamp(1, 3));
            final width =
                (constraints.maxWidth - spacing * (columns - 1)) / columns;
            return Wrap(
              spacing: spacing,
              runSpacing: spacing,
              children: [
                for (final day in days)
                  SizedBox(
                    width: width,
                    child: _DayCell(
                      day: day,
                      selected: day.day == _selectedDay,
                      tokens: tokens,
                      onTap: () => setState(() => _selectedDay = day.day),
                    ),
                  ),
              ],
            );
          },
        ),
        if (selected != null) ...[
          const SizedBox(height: MacrovaSpacing.sectionTop),
          _SelectedDayDetail(day: selected, tokens: tokens),
        ],
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final MealPlanDay day;
  final bool selected;
  final MacrovaTokens tokens;
  final VoidCallback onTap;

  const _DayCell({
    required this.day,
    required this.selected,
    required this.tokens,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final mealCount = day.meals.length;
    final kcal = day.dayTotals.calories.round();

    return Material(
      color: selected ? tokens.accentSoft : tokens.surfaceTint,
      borderRadius: MacrovaRadius.borderMd,
      child: InkWell(
        key: ValueKey('calendar-day-${day.day}'),
        onTap: onTap,
        borderRadius: MacrovaRadius.borderMd,
        child: Container(
          padding: const EdgeInsets.all(MacrovaSpacing.md),
          decoration: BoxDecoration(
            borderRadius: MacrovaRadius.borderMd,
            border: Border.all(
              color: selected ? tokens.accent : tokens.lineDefault,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Day ${day.day}',
                style: MacrovaTypography.title(tokens.inkPrimary),
              ),
              const SizedBox(height: MacrovaSpacing.xs),
              Text(
                mealCount == 0 ? 'No meals' : '$mealCount meal${mealCount == 1 ? '' : 's'}',
                style: MacrovaTypography.caption(tokens.inkTertiary),
              ),
              const SizedBox(height: MacrovaSpacing.sm),
              Text(
                '$kcal kcal',
                style: MacrovaTypography.metric(tokens.inkSecondary).copyWith(
                  fontSize: 16,
                  fontFeatures: MacrovaTypography.tabularFigures,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectedDayDetail extends StatelessWidget {
  final MealPlanDay day;
  final MacrovaTokens tokens;

  const _SelectedDayDetail({
    required this.day,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    final totals = day.dayTotals;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Day ${day.day}',
          action: Text(
            '${totals.calories.round()} kcal \u2022 '
            '${totals.proteinG.round()}g P \u2022 '
            '${totals.carbsG.round()}g C \u2022 '
            '${totals.fatG.round()}g F',
            style: MacrovaTypography.caption(tokens.inkTertiary).copyWith(
              fontFeatures: MacrovaTypography.tabularFigures,
            ),
          ),
        ),
        if (day.meals.isEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
            child: Text(
              'No meals on this day',
              style: MacrovaTypography.body(tokens.inkTertiary),
            ),
          )
        else
          for (final meal in day.meals)
            Padding(
              padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
              child: _mealCardFor(meal),
            ),
      ],
    );
  }

  /// Same slot-state mapping as Daily List in [MealPlanViewScreen].
  static MealCard _mealCardFor(Meal meal) {
    final recipeName = meal.recipe['name'] as String? ?? 'Unknown Recipe';
    final isMissing = recipeName.startsWith('Missing recipe');
    return MealCard(
      mealType: meal.mealType,
      recipeName: recipeName,
      calories: meal.nutrition.calories,
      proteinG: meal.nutrition.proteinG,
      carbsG: meal.nutrition.carbsG,
      fatG: meal.nutrition.fatG,
      slotState: isMissing ? MealSlotState.warn : MealSlotState.ok,
      warningText: isMissing ? 'Recipe unavailable' : null,
    );
  }
}
