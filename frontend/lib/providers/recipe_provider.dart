import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../models/recipe.dart';
import '../services/storage_service.dart';

const _uuid = Uuid();

class RecipeProvider extends ChangeNotifier {
  List<Recipe> _recipes = [];
  bool _loaded = false;

  List<Recipe> get recipes => List.unmodifiable(_recipes);
  bool get loaded => _loaded;

  Future<void> load() async {
    _recipes = await StorageService.loadRecipes();
    _loaded = true;
    notifyListeners();
  }

  Future<void> addRecipe(Recipe recipe) async {
    final withId =
        recipe.id.isEmpty ? recipe.copyWith(id: _uuid.v4()) : recipe;
    _recipes.add(withId);
    await StorageService.saveRecipes(_recipes);
    notifyListeners();
  }

  Future<void> updateRecipe(Recipe recipe) async {
    final index = _recipes.indexWhere((r) => r.id == recipe.id);
    if (index != -1) {
      _recipes[index] = recipe;
      await StorageService.saveRecipes(_recipes);
      notifyListeners();
    }
  }

  Future<void> deleteRecipe(String id) async {
    _recipes.removeWhere((r) => r.id == id);
    await StorageService.saveRecipes(_recipes);
    notifyListeners();
  }

  Recipe? getById(String id) {
    try {
      return _recipes.firstWhere((r) => r.id == id);
    } catch (_) {
      return null;
    }
  }
}
