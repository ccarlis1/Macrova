import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../features/agent/agent_pane_screen.dart';
import '../features/agent/agent_setup_screen.dart';
import '../features/agent/llm_config_provider.dart';
import '../providers/ingredient_provider.dart';
import '../providers/recipe_builder_coordinator.dart';
import '../providers/recipe_provider.dart';
import '../screens/ingredient_hub_screen.dart';
import '../screens/meal_plan_view_screen.dart';
import '../screens/planner_config_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/recipe_builder_screen.dart';
import '../screens/recipe_library_screen.dart';
import '../theme/tokens.dart';
import 'sidebar_nav.dart';

/// Width at which the shell switches from bottom [NavigationBar] to sidebar rail.
const kAppShellBreakpoint = 760.0;

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

  void _onDestinationSelected(int index) {
    if (index == 2) {
      context.read<RecipeBuilderCoordinator>().startCreate();
    }
    setState(() => _selectedIndex = index);
  }

  Widget _buildIndexedStack(BuildContext context) {
    return IndexedStack(
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
            final ready = context.read<LlmConfigProvider>().llmReady;
            if (ready) return const AgentPaneScreen();
            return AgentSetupScreen(
              onOpenProfile: () => navigateTo(0),
            );
          },
        ),
      ],
    );
  }

  Widget _buildBottomNavigationBar(BuildContext context) {
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: tokens.stickyBar,
        border: Border(top: BorderSide(color: tokens.lineDefault)),
        boxShadow: MacrovaElevation.shadowCta,
      ),
      child: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onDestinationSelected,
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        destinations: AppNavItems.navigationDestinations,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= kAppShellBreakpoint;

        if (wide) {
          return Scaffold(
            body: Row(
              children: [
                SidebarNav(
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: _onDestinationSelected,
                ),
                const VerticalDivider(thickness: 1, width: 1),
                Expanded(child: _buildIndexedStack(context)),
              ],
            ),
          );
        }

        return Scaffold(
          body: _buildIndexedStack(context),
          bottomNavigationBar: _buildBottomNavigationBar(context),
        );
      },
    );
  }
}
