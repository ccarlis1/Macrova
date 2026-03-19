import 'package:flutter/material.dart';

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
              if (index == 6) {
                // Agent Pane placeholder
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Agent Pane coming soon')),
                );
                return;
              }
              setState(() => _selectedIndex = index);
            },
          ),
          const VerticalDivider(thickness: 1, width: 1),
          Expanded(
            child: IndexedStack(
              index: _selectedIndex.clamp(0, 5),
              children: const [
                ProfileScreen(),
                IngredientHubScreen(),
                RecipeBuilderScreen(),
                RecipeLibraryScreen(),
                PlannerConfigScreen(),
                MealPlanViewScreen(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
