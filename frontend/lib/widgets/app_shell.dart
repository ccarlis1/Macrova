import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/agent_pane_screen.dart';
import '../features/agent/agent_setup_screen.dart';
import '../features/agent/llm_config_provider.dart';
import '../providers/ingredient_provider.dart';
import '../providers/recipe_provider.dart';
import '../screens/ingredient_hub_screen.dart';
import '../screens/meal_plan_view_screen.dart';
import '../screens/planner_config_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/recipe_builder_screen.dart';
import '../screens/recipe_library_screen.dart';
import 'sidebar_nav.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => AppShellState();
}

class AppShellState extends State<AppShell> {
  int _selectedIndex = 0;
  IngredientProvider? _ingredientProvider;
  void _onIngredientsChanged() {
    if (!mounted || _ingredientProvider == null) return;
    unawaited(
      context.read<RecipeProvider>().applyIngredientNutritionFromSavedIngredients(
            _ingredientProvider!.ingredients,
          ),
    );
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final ing = context.read<IngredientProvider>();
      final rec = context.read<RecipeProvider>();
      _ingredientProvider = ing;
      ing.addListener(_onIngredientsChanged);
      unawaited(rec.applyIngredientNutritionFromSavedIngredients(ing.ingredients));
    });
  }

  @override
  void dispose() {
    _ingredientProvider?.removeListener(_onIngredientsChanged);
    super.dispose();
  }

  void navigateTo(int index) {
    setState(() => _selectedIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          SidebarNav(
            selectedIndex: _selectedIndex,
            onDestinationSelected: (index) {
              setState(() => _selectedIndex = index);
            },
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(
            child: IndexedStack(
              index: _selectedIndex.clamp(0, 6),
              children: [
                const ProfileScreen(),
                const IngredientHubScreen(),
                const RecipeBuilderScreen(),
                const RecipeLibraryScreen(),
                const PlannerConfigScreen(),
                const MealPlanViewScreen(),
                ListenableBuilder(
                  listenable: context.read<LlmConfigProvider>(),
                  builder: (context, _) {
                    final ready =
                        context.read<LlmConfigProvider>().llmReady;
                    if (ready) return const AgentPaneScreen();
                    return AgentSetupScreen(
                      onOpenProfile: () => navigateTo(0),
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
