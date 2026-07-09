import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/llm_config_provider.dart';
import '../models/models.dart';
import '../models/recipe.dart';
import '../models/user_profile.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../theme/tokens.dart';
import '../widgets/advisory_card.dart';
import '../widgets/app_shell.dart';
import '../widgets/empty_state.dart';
import '../widgets/failure_panel.dart';
import '../widgets/meal_card.dart';
import '../widgets/recipe_card.dart';
import '../widgets/section_header.dart';
import '../widgets/stat_card.dart';
import '../widgets/sticky_cta.dart';

/// Home dashboard: Day 1 plan vs targets, composed from existing providers only.
class TodayScreen extends StatelessWidget {
  const TodayScreen({super.key});

  static const int _navPlanner = 5;
  static const int _navAgent = 7;

  void _go(BuildContext context, int index) {
    context.findAncestorStateOfType<AppShellState>()?.navigateTo(index);
  }

  String _greetingFor(DateTime now) {
    final hour = now.hour;
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }

  MealPlanDay? _day1(MealPlan plan) {
    for (final d in plan.dailyPlans) {
      if (d.day == 1) return d;
    }
    return plan.dailyPlans.isNotEmpty ? plan.dailyPlans.first : null;
  }

  String? _preferredTimeForMeal(MealPlanProvider planProvider, int mealIndex0) {
    final schedule = planProvider.scheduleDays;
    if (schedule.isEmpty) return null;
    final meals = schedule.first.meals;
    if (mealIndex0 < 0 || mealIndex0 >= meals.length) return null;
    final t = meals[mealIndex0].preferredTime;
    if (t == null || t.trim().isEmpty) return null;
    return t.trim();
  }

  Recipe? _libraryMatch(RecipeProvider recipes, Meal meal) {
    final name = meal.recipe['name'] as String? ?? '';
    if (name.isEmpty || name.startsWith('Missing recipe')) return null;
    for (final r in recipes.recipes) {
      if (r.name == name) return r;
    }
    return null;
  }

  double _progress(double actual, double target) {
    if (target <= 0) return 0;
    return actual / target;
  }

  @override
  Widget build(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;
    final planProvider = context.watch<MealPlanProvider>();
    final profile = context.watch<ProfileProvider>().profile;
    final recipes = context.watch<RecipeProvider>();
    final llmReady = context.watch<LlmConfigProvider>().llmReady;
    final mealPlan = planProvider.mealPlan;
    final now = DateTime.now();

    if (planProvider.loading || planProvider.syncing) {
      return const Center(child: EmptyState.loading(label: 'Loading plan…'));
    }

    if (mealPlan == null) {
      return _EmptyToday(
        tokens: tokens,
        greeting: _greetingFor(now),
        error: planProvider.error,
        llmReady: llmReady,
        recipes: recipes.recipes,
        onOpenPlanner: () => _go(context, _navPlanner),
        onOpenAgent: () => _go(context, _navAgent),
      );
    }

    final day1 = _day1(mealPlan);
    final isFailure = !mealPlan.success;

    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _greetingFor(now),
                      style: MacrovaTypography.headline(tokens.inkPrimary),
                    ),
                    const SizedBox(height: MacrovaSpacing.xs),
                    Text(
                      isFailure
                          ? 'Latest plan did not succeed — see details below.'
                          : 'Day 1 of your current meal plan.',
                      style: MacrovaTypography.body(tokens.inkTertiary),
                    ),
                    const SizedBox(height: MacrovaSpacing.sectionTop),

                    if (planProvider.error != null) ...[
                      AdvisoryCard(
                        variant: AdvisoryVariant.warn,
                        title: 'Planning error',
                        description: planProvider.error!,
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],

                    if (isFailure) ...[
                      _buildFailurePanel(mealPlan),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ] else if (mealPlan.warnings.isNotEmpty) ...[
                      const SectionHeader(title: 'Advisories'),
                      AdvisoryCard(
                        variant: AdvisoryVariant.warn,
                        title: 'Plan generated with advisories',
                        description: mealPlan.warnings.join('\n'),
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],

                    if (!isFailure && day1 != null) ...[
                      _buildProgressBanner(
                        tokens,
                        day1.dayTotals,
                        mealPlan.goals,
                        profile,
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],

                    _buildAgentEntry(tokens, llmReady, () {
                      _go(context, _navAgent);
                    }),
                    const SizedBox(height: MacrovaSpacing.sectionTop),

                    if (!isFailure && day1 != null && day1.meals.isNotEmpty) ...[
                      _buildUpNext(
                        context,
                        tokens,
                        day1.meals.first,
                        planProvider,
                        recipes,
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                      _buildTodaysPlan(
                        context,
                        tokens,
                        day1,
                        planProvider,
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],

                    if (recipes.recipes.isNotEmpty) ...[
                      _buildSuggestions(tokens, recipes.recipes),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],

                    // Space for sticky CTA
                    const SizedBox(height: MacrovaSpacing.xxl),
                  ],
                ),
              ),
            ),
          ),
        ),
        StickyCta(
          label: isFailure ? 'Plan failed' : 'Plan ready',
          detail: _stickyDetail(mealPlan),
          actions: [
            StickyCtaAction(
              label: isFailure ? 'Open Planner' : 'Re-generate',
              isPrimary: true,
              onPressed: () => _go(context, _navPlanner),
            ),
          ],
        ),
      ],
    );
  }

  String _stickyDetail(MealPlan plan) {
    final mealCount = plan.meals.length;
    final dayCount = plan.days;
    return '$dayCount day${dayCount == 1 ? '' : 's'} · $mealCount meal${mealCount == 1 ? '' : 's'}';
  }

  Widget _buildProgressBanner(
    MacrovaTokens tokens,
    NutritionProfile dayTotals,
    NutritionGoals goals,
    UserProfile profile,
  ) {
    final calTarget =
        goals.calories > 0 ? goals.calories.toDouble() : profile.calories;
    final proteinTarget =
        goals.proteinG > 0 ? goals.proteinG : profile.proteinG;
    final carbTarget = goals.carbsG > 0 ? goals.carbsG : profile.carbsG;
    final fatTarget = goals.fatGMax > 0
        ? (goals.fatGMin + goals.fatGMax) / 2
        : profile.fatG;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Day 1 plan vs targets',
          subtitle:
              'Planned totals vs daily targets '
              '(${calTarget.round()} kcal · ${proteinTarget.round()}g P · '
              '${carbTarget.round()}g C · ${fatTarget.round()}g F) — not eaten so far',
        ),
        _StatCardGrid(
          cards: [
            StatCard(
              label: 'Calories',
              value: '${dayTotals.calories.round()}',
              unit: 'kcal',
              progress: _progress(dayTotals.calories, calTarget),
            ),
            StatCard(
              label: 'Protein',
              value: '${dayTotals.proteinG.round()}',
              unit: 'g',
              progress: _progress(dayTotals.proteinG, proteinTarget),
              variant: StatCardVariant.protein,
            ),
            StatCard(
              label: 'Carbs',
              value: '${dayTotals.carbsG.round()}',
              unit: 'g',
              progress: _progress(dayTotals.carbsG, carbTarget),
              variant: StatCardVariant.carb,
            ),
            StatCard(
              label: 'Fat',
              value: '${dayTotals.fatG.round()}',
              unit: 'g',
              progress: _progress(dayTotals.fatG, fatTarget),
              variant: StatCardVariant.fat,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildAgentEntry(
    MacrovaTokens tokens,
    bool llmReady,
    VoidCallback onOpen,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: 'Plan with words',
          subtitle: 'Describe what you want — Macrova drafts it',
        ),
        Material(
          color: tokens.surfaceTint,
          shape: RoundedRectangleBorder(
            borderRadius: MacrovaRadius.borderMd,
            side: BorderSide(color: tokens.lineDefault),
          ),
          child: InkWell(
            onTap: onOpen,
            borderRadius: MacrovaRadius.borderMd,
            child: Padding(
              padding: const EdgeInsets.all(MacrovaSpacing.lg),
              child: Row(
                children: [
                  Icon(
                    Icons.smart_toy_outlined,
                    color: llmReady ? tokens.accent : tokens.inkQuaternary,
                  ),
                  const SizedBox(width: MacrovaSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          llmReady
                              ? 'Open Agent Pane'
                              : 'Set up Agent to plan with words',
                          style: MacrovaTypography.subtitle(tokens.inkPrimary),
                        ),
                        const SizedBox(height: MacrovaSpacing.xs),
                        Text(
                          llmReady
                              ? 'Parse → match → generate with your configured LLM'
                              : 'LLM credentials required before assisted planning',
                          style: MacrovaTypography.caption(tokens.inkTertiary),
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: tokens.inkQuaternary),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUpNext(
    BuildContext context,
    MacrovaTokens tokens,
    Meal meal,
    MealPlanProvider planProvider,
    RecipeProvider recipes,
  ) {
    final time = _preferredTimeForMeal(planProvider, 0);
    final library = _libraryMatch(recipes, meal);
    final recipeName = meal.recipe['name'] as String? ?? 'Unknown Recipe';
    final subtitleParts = <String>[
      meal.mealType,
      if (time != null) time,
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Up next',
          subtitle: time != null
              ? '${meal.mealType} · preferred time $time'
              : meal.mealType,
        ),
        // Prefer RecipeCard.hero when library has real nutrition; otherwise
        // MealCard so plan macros are not shown as zeros.
        if (library != null && library.ingredients.isNotEmpty)
          RecipeCard.hero(
            recipe: library,
            badge: meal.mealType,
            subtitle: subtitleParts.join(' · '),
            onView: () => _go(context, _navPlanner),
          )
        else
          MealCard(
            mealType: meal.mealType,
            recipeName: recipeName,
            calories: meal.nutrition.calories,
            proteinG: meal.nutrition.proteinG,
            carbsG: meal.nutrition.carbsG,
            fatG: meal.nutrition.fatG,
            timeLabel: time,
            slotState: recipeName.startsWith('Missing recipe')
                ? MealSlotState.warn
                : MealSlotState.ok,
            warningText: recipeName.startsWith('Missing recipe')
                ? 'Recipe unavailable'
                : null,
            onTap: () => _go(context, _navPlanner),
          ),
      ],
    );
  }

  Widget _buildTodaysPlan(
    BuildContext context,
    MacrovaTokens tokens,
    MealPlanDay day1,
    MealPlanProvider planProvider,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Day 1',
          subtitle: '${day1.meals.length} meal${day1.meals.length == 1 ? '' : 's'}',
          linkLabel: 'Edit',
          onLink: () => _go(context, _navPlanner),
        ),
        for (var i = 0; i < day1.meals.length; i++) ...[
          Builder(
            builder: (context) {
              final meal = day1.meals[i];
              final recipeName =
                  meal.recipe['name'] as String? ?? 'Unknown Recipe';
              final isMissing = recipeName.startsWith('Missing recipe');
              return Padding(
                padding: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
                child: MealCard(
                  mealType: meal.mealType,
                  recipeName: recipeName,
                  calories: meal.nutrition.calories,
                  proteinG: meal.nutrition.proteinG,
                  carbsG: meal.nutrition.carbsG,
                  fatG: meal.nutrition.fatG,
                  timeLabel: _preferredTimeForMeal(planProvider, i),
                  slotState:
                      isMissing ? MealSlotState.warn : MealSlotState.ok,
                  warningText: isMissing ? 'Recipe unavailable' : null,
                ),
              );
            },
          ),
        ],
      ],
    );
  }

  Widget _buildSuggestions(MacrovaTokens tokens, List<Recipe> all) {
    final slice = all.take(8).toList(growable: false);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: 'From your library',
          subtitle: 'Recipes already in your collection',
        ),
        SizedBox(
          height: 200,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: slice.length,
            separatorBuilder: (_, __) =>
                const SizedBox(width: MacrovaSpacing.md),
            itemBuilder: (context, index) {
              final r = slice[index];
              return SizedBox(
                width: 160,
                child: RecipeCard.mini(
                  recipe: r,
                  subtitle: r.ingredients.isEmpty
                      ? null
                      : '${r.perServingCalories.round()} kcal',
                ),
              );
            },
          ),
        ),
      ],
    );
  }

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

class _EmptyToday extends StatelessWidget {
  final MacrovaTokens tokens;
  final String greeting;
  final String? error;
  final bool llmReady;
  final List<Recipe> recipes;
  final VoidCallback onOpenPlanner;
  final VoidCallback onOpenAgent;

  const _EmptyToday({
    required this.tokens,
    required this.greeting,
    required this.error,
    required this.llmReady,
    required this.recipes,
    required this.onOpenPlanner,
    required this.onOpenAgent,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 800),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      greeting,
                      style: MacrovaTypography.headline(tokens.inkPrimary),
                    ),
                    const SizedBox(height: MacrovaSpacing.xs),
                    Text(
                      'No meal plan yet. Generate one from the Planner.',
                      style: MacrovaTypography.body(tokens.inkTertiary),
                    ),
                    const SizedBox(height: MacrovaSpacing.sectionTop),
                    if (error != null) ...[
                      AdvisoryCard(
                        variant: AdvisoryVariant.warn,
                        title: 'Planning error',
                        description: error!,
                      ),
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                    ],
                    EmptyState(
                      icon: Icons.calendar_today_outlined,
                      label: 'Open Planner to generate a plan',
                      onTap: onOpenPlanner,
                    ),
                    const SizedBox(height: MacrovaSpacing.sectionTop),
                    SectionHeader(
                      title: 'Plan with words',
                      subtitle: llmReady
                          ? 'Describe what you want — Macrova drafts it'
                          : 'Set up Agent credentials to plan with words',
                    ),
                    Material(
                      color: tokens.surfaceTint,
                      shape: RoundedRectangleBorder(
                        borderRadius: MacrovaRadius.borderMd,
                        side: BorderSide(color: tokens.lineDefault),
                      ),
                      child: InkWell(
                        onTap: onOpenAgent,
                        borderRadius: MacrovaRadius.borderMd,
                        child: Padding(
                          padding: const EdgeInsets.all(MacrovaSpacing.lg),
                          child: Row(
                            children: [
                              Icon(
                                Icons.smart_toy_outlined,
                                color: llmReady
                                    ? tokens.accent
                                    : tokens.inkQuaternary,
                              ),
                              const SizedBox(width: MacrovaSpacing.md),
                              Expanded(
                                child: Text(
                                  llmReady
                                      ? 'Open Agent Pane'
                                      : 'Set up Agent',
                                  style: MacrovaTypography.subtitle(
                                    tokens.inkPrimary,
                                  ),
                                ),
                              ),
                              Icon(
                                Icons.chevron_right,
                                color: tokens.inkQuaternary,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                    if (recipes.isNotEmpty) ...[
                      const SizedBox(height: MacrovaSpacing.sectionTop),
                      const SectionHeader(
                        title: 'From your library',
                        subtitle: 'Recipes already in your collection',
                      ),
                      SizedBox(
                        height: 200,
                        child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemCount: recipes.take(8).length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(width: MacrovaSpacing.md),
                          itemBuilder: (context, index) {
                            final r = recipes[index];
                            return SizedBox(
                              width: 160,
                              child: RecipeCard.mini(recipe: r),
                            );
                          },
                        ),
                      ),
                    ],
                    const SizedBox(height: MacrovaSpacing.xxl),
                  ],
                ),
              ),
            ),
          ),
        ),
        StickyCta(
          label: 'No plan yet',
          detail: 'Generate a meal plan to fill Today',
          actions: [
            StickyCtaAction(
              label: 'Open Planner',
              isPrimary: true,
              onPressed: onOpenPlanner,
            ),
          ],
        ),
      ],
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
