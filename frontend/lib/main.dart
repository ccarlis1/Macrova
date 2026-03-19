import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/ingredient_provider.dart';
import 'providers/meal_plan_provider.dart';
import 'providers/profile_provider.dart';
import 'providers/recipe_provider.dart';
import 'theme.dart';
import 'widgets/app_shell.dart';

void main() => runApp(const MacrovaApp());

class MacrovaApp extends StatelessWidget {
  const MacrovaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ProfileProvider()..load()),
        ChangeNotifierProvider(create: (_) => IngredientProvider()..load()),
        ChangeNotifierProvider(create: (_) => RecipeProvider()..load()),
        ChangeNotifierProvider(create: (_) => MealPlanProvider()),
      ],
      child: MaterialApp(
        title: 'Macrova',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const AppShell(),
      ),
    );
  }
}
