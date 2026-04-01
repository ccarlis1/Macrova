import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';

import '../models/micronutrient_metadata.dart';
import '../models/models.dart';
import '../models/user_profile.dart';
import '../providers/meal_plan_provider.dart';
import '../providers/optimization_job_provider.dart';
import '../providers/profile_provider.dart';
import '../providers/recipe_provider.dart';
import '../services/api_service.dart';
import '../services/grocery_optimize_payload.dart';
import '../widgets/macro_display.dart';
import '../widgets/meal_card.dart';
import '../widgets/micronutrient_bar.dart';
import '../widgets/optimize_cart_button.dart';
import '../widgets/optimization_progress.dart';
import '../widgets/section_header.dart';

class MealPlanViewScreen extends StatefulWidget {
  const MealPlanViewScreen({super.key});

  @override
  State<MealPlanViewScreen> createState() => _MealPlanViewScreenState();
}

class _MealPlanViewScreenState extends State<MealPlanViewScreen> {
  bool _showCalendar = false;
  DateTime? _optimizeStartedAt;
  String? _lastShownResultRunId;

  @override
  Widget build(BuildContext context) {
    final planProvider = context.watch<MealPlanProvider>();
    final mealPlan = planProvider.mealPlan;
    final profile = context.watch<ProfileProvider>().profile;
    final recipeProvider = context.watch<RecipeProvider>();
    final optimizeJob = context.watch<OptimizationJobProvider>();

    if (mealPlan == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.view_list_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'Generate a plan from the Planner tab',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      );
    }

    final totalNutrition = mealPlan.totalNutrition;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 800),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // View toggle
              Row(
                children: [
                  Text(
                    'Meal Plan View',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const Spacer(),
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(
                        value: false,
                        label: Text('Daily List'),
                      ),
                      ButtonSegment(
                        value: true,
                        label: Text('Calendar'),
                      ),
                    ],
                    selected: {_showCalendar},
                    onSelectionChanged: (s) =>
                        setState(() => _showCalendar = s.first),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: OptimizeCartButton(
                  busy: optimizeJob.isBusy,
                  onPressed: () => _startAsyncGroceryOptimize(
                    mealPlan,
                    recipeProvider,
                    optimizeJob,
                  ),
                ),
              ),
              ..._buildOptimizeJobPanel(context, optimizeJob),
              const SizedBox(height: 24),

              if (_showCalendar) ...[
                Center(
                  child: Text(
                    'Calendar view coming soon',
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: Theme.of(context)
                              .colorScheme
                              .onSurfaceVariant,
                        ),
                  ),
                ),
              ] else ...[
                // Plan-wide macro totals (whole horizon; multi-day = sum or weekly_totals)
                _buildWeeklyTotals(context, mealPlan.days, totalNutrition),
                const SizedBox(height: 16),

                // Plan micronutrients vs profile targets (daily × plan length)
                _buildWeeklyMicronutrients(context, profile, mealPlan),
                const SizedBox(height: 24),

                // Per-day breakdown from API daily_plans
                _buildDailyBreakdown(context, mealPlan),
              ],

              if (mealPlan.warnings.isNotEmpty) ...[
                const SizedBox(height: 24),
                const SectionHeader(title: 'Warnings'),
                ...mealPlan.warnings.map((w) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.warning_amber,
                              size: 16,
                              color: Theme.of(context).colorScheme.error),
                          const SizedBox(width: 8),
                          Expanded(child: Text(w)),
                        ],
                      ),
                    )),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildWeeklyTotals(
      BuildContext context, int planDays, dynamic totalNutrition) {
    final title = planDays > 1 ? 'Plan totals' : 'Daily totals';
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            MacroDisplay(
              calories: totalNutrition.calories,
              proteinG: totalNutrition.proteinG,
              carbsG: totalNutrition.carbsG,
              fatG: totalNutrition.fatG,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWeeklyMicronutrients(
    BuildContext context,
    UserProfile profile,
    MealPlan mealPlan,
  ) {
    final goals = profile.micronutrientGoals;
    final microJson = goals.toJson();
    final hasGoals = microJson.values.any((v) => (v as num) > 0);

    if (!hasGoals) return const SizedBox.shrink();

    final actual = mealPlan.totalNutrition.micronutrients;
    final periodDays = mealPlan.days.clamp(1, 7);

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Micronutrient Targets',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Plan totals vs daily profile goals × $periodDays day(s)',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 12),
            for (final meta in kMicronutrientsInDisplayOrder) ...[
              if (((microJson[meta.key] as num?)?.toDouble() ?? 0) > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: MicronutrientBar(
                    label: meta.label,
                    value: actual[meta.key] ?? 0,
                    target:
                        (microJson[meta.key] as num).toDouble() * periodDays,
                    unit: meta.unit,
                    isLimit: meta.isLimit,
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildDailyBreakdown(BuildContext context, MealPlan mealPlan) {
    final days = mealPlan.dailyPlans;
    if (days.isEmpty ||
        days.every((d) => d.meals.isEmpty)) {
      return Center(
        child: Text(
          'No meals in this plan',
          style: Theme.of(context).textTheme.bodyMedium,
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
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      );
      for (final meal in d.meals) {
        final recipeName =
            meal.recipe['name'] as String? ?? 'Unknown Recipe';
        blocks.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: MealCard(
              mealType: meal.mealType,
              recipeName: recipeName,
              calories: meal.nutrition.calories,
              proteinG: meal.nutrition.proteinG,
              carbsG: meal.nutrition.carbsG,
              fatG: meal.nutrition.fatG,
            ),
          ),
        );
      }
      blocks.add(const SizedBox(height: 16));
    }
    if (blocks.isNotEmpty) {
      blocks.removeLast();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: blocks,
    );
  }

  List<Widget> _buildOptimizeJobPanel(
    BuildContext context,
    OptimizationJobProvider job,
  ) {
    final status = job.status;
    final started = _optimizeStartedAt;

    if (status == null) return [];

    if ((status.isQueued || status.isRunning) && started != null) {
      return [
        const SizedBox(height: 12),
        OptimizationProgress(status: status, startedAt: started),
      ];
    }

    if (status.isFailed) {
      final err = status.error;
      final msg = err?.message ?? 'Optimization failed';
      final retryable = err?.retryable == true;
      return [
        const SizedBox(height: 12),
        Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: Theme.of(context).colorScheme.errorContainer),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.error_outline,
                        color: Theme.of(context).colorScheme.error),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Cart optimization failed',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(msg),
                if (retryable) ...[
                  const SizedBox(height: 4),
                  Text(
                    'This error is likely transient. Retrying may succeed.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color:
                              Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: job.isBusy ? null : () => job.retry(),
                  child: const Text('Retry'),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () {
                    setState(() {
                      _optimizeStartedAt = null;
                      _lastShownResultRunId = null;
                    });
                    job.dismissUi();
                  },
                  child: const Text('Dismiss'),
                ),
              ],
            ),
          ),
        ),
      ];
    }

    if (status.isCompleted && status.result != null) {
      final runId = status.result!['runId']?.toString() ?? '';
      if (runId.isNotEmpty && runId != _lastShownResultRunId) {
        _lastShownResultRunId = runId;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          _showGroceryResultDialog(status.result!);
        });
      }

      final st = status.stats;
      return [
        const SizedBox(height: 12),
        Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Cart ready',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (st != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Cache hits: ${st.cacheHits} · '
                    'Search latency: ${st.searchLatency} ms',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  children: [
                    FilledButton.tonal(
                      onPressed: () =>
                          _showGroceryResultDialog(status.result!),
                      child: const Text('View cart summary'),
                    ),
                    const SizedBox(width: 8),
                    TextButton(
                      onPressed: () {
                        setState(() {
                          _optimizeStartedAt = null;
                          _lastShownResultRunId = null;
                        });
                        job.dismissUi();
                      },
                      child: const Text('Dismiss'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ];
    }

    return [];
  }

  Future<void> _startAsyncGroceryOptimize(
    MealPlan mealPlan,
    RecipeProvider recipes,
    OptimizationJobProvider job,
  ) async {
    final mealPlanId = const Uuid().v4();
    final body = buildGroceryOptimizeRequestBody(
      mealPlan: mealPlan,
      recipes: recipes,
      mealPlanId: mealPlanId,
    );
    if (body == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not build a cart: ensure meals include recipe IDs and recipes have ingredients.',
          ),
        ),
      );
      return;
    }

    setState(() => _optimizeStartedAt = DateTime.now());

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Cart optimization started — progress updates below.',
          ),
          duration: Duration(seconds: 4),
        ),
      );
    }

    try {
      await job.startOptimizeCart(
        groceryBody: body,
        mealPlanId: mealPlanId,
      );
    } on ApiException catch (e) {
      if (mounted) {
        setState(() => _optimizeStartedAt = null);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message)),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() => _optimizeStartedAt = null);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _showGroceryResultDialog(Map<String, dynamic> result) async {
    final ms = result['multiStoreOptimization'];
    final cost = ms is Map<String, dynamic> ? ms['totalCost'] : null;
    final cart = result['cartPlan'];
    final lines =
        cart is Map<String, dynamic> ? cart['lines'] as List<dynamic>? : null;
    final nLines = lines?.length ?? 0;
    final skipped = result['skippedIngredients'] as List<dynamic>?;

    // Build store → friendly name map from `stores` array when present.
    final stores = result['stores'];
    final storeNameById = <String, String>{};
    if (stores is List) {
      for (final s in stores) {
        if (s is Map<String, dynamic>) {
          final id = s['id']?.toString();
          if (id == null) continue;
          final base = s['baseUrl']?.toString();
          storeNameById[id] = base ?? id;
        }
      }
    }

    // Group selected products by store using multiStoreOptimization.storePlans.
    final storePlans =
        ms is Map<String, dynamic> ? ms['storePlans'] as Map<String, dynamic>? : null;
    final storeSections = <Widget>[];
    if (storePlans != null) {
      storePlans.forEach((storeId, products) {
        if (products is! List) return;
        final storeLabel = storeNameById[storeId] ?? storeId;
        final productTiles = <Widget>[];
        for (final p in products) {
          if (p is! Map<String, dynamic>) continue;
          final product = p['product'] as Map<String, dynamic>?;
          if (product == null) continue;
          final candidate =
              product['candidate'] as Map<String, dynamic>? ?? const {};
          final name = candidate['name']?.toString() ?? 'Unknown product';
          final packCount = (p['packCount'] as num?)?.toDouble() ?? 1;
          final totalPackPrice =
              (product['totalPackPrice'] as num?)?.toDouble();
          final unitPrice = (product['unitPrice'] as num?)?.toDouble();
          String priceText;
          if (totalPackPrice != null) {
            priceText =
                '\$${(totalPackPrice * packCount).toStringAsFixed(2)} for ${packCount.toStringAsFixed(0)} pack(s)';
          } else if (unitPrice != null) {
            priceText = '\$${unitPrice.toStringAsFixed(2)} per unit';
          } else {
            priceText = 'Price unavailable';
          }
          productTiles.add(
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(name),
              subtitle: Text(priceText),
            ),
          );
        }
        if (productTiles.isEmpty) return;
        storeSections.addAll([
          const SizedBox(height: 12),
          Text(
            storeLabel,
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: 4),
          ...productTiles,
        ]);
      });
    }

    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Grocery cart'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Estimated total: '
                '${cost != null ? "\$${cost.toString()}" : "—"}',
                style: Theme.of(ctx).textTheme.titleMedium,
              ),
              const SizedBox(height: 8),
              Text('$nLines cart line(s)'),
              if (storeSections.isNotEmpty) ...[
                const SizedBox(height: 12),
                ...storeSections,
              ],
              if (skipped != null && skipped.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  'Skipped staples: ${skipped.length} (e.g. salt, water)',
                  style: Theme.of(ctx).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }
}
