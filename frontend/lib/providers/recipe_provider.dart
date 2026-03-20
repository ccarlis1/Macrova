import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../models/recipe.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

const _uuid = Uuid();

class RecipeProvider extends ChangeNotifier {
  List<Recipe> _localRecipes = [];
  List<RecipeSummary> _remoteSummaries = [];
  bool _loaded = false;
  bool _syncLoading = false;
  String? _syncError;

  /// Union of local full recipes and API id+name rows (see README recipe hybrid section).
  List<Recipe> get recipes {
    final map = <String, Recipe>{
      for (final r in _localRecipes) r.id: r,
    };
    for (final s in _remoteSummaries) {
      map.putIfAbsent(
        s.id,
        () => Recipe.apiSummary(id: s.id, name: s.name),
      );
    }
    final merged = map.values.toList()
      ..sort(
        (a, b) =>
            a.name.toLowerCase().compareTo(b.name.toLowerCase()),
      );
    return List.unmodifiable(merged);
  }

  bool get loaded => _loaded;
  bool get syncLoading => _syncLoading;
  String? get syncError => _syncError;

  /// Server ids from the last successful `GET /api/v1/recipes` (empty if never synced or error).
  Set<String> get remoteRecipeIds =>
      Set.unmodifiable(_remoteSummaries.map((s) => s.id));

  Future<void> load() async {
    _localRecipes = await StorageService.loadRecipes();
    _loaded = true;
    notifyListeners();
  }

  /// Fetches recipe id+name list from the API and merges into [recipes].
  /// Full nutrition and ingredients still come from local storage until a detail endpoint exists.
  Future<void> syncSummariesFromApi() async {
    _syncLoading = true;
    _syncError = null;
    notifyListeners();
    try {
      _remoteSummaries = await ApiService.listRecipes();
      _syncError = null;
    } catch (e) {
      _syncError = e is ApiException ? e.message : e.toString();
    } finally {
      _syncLoading = false;
      notifyListeners();
    }
  }

  Future<void> addRecipe(Recipe recipe) async {
    final withId =
        recipe.id.isEmpty ? recipe.copyWith(id: _uuid.v4()) : recipe;
    _localRecipes.add(withId);
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
  }

  Future<void> updateRecipe(Recipe recipe) async {
    final index = _localRecipes.indexWhere((r) => r.id == recipe.id);
    if (index != -1) {
      _localRecipes[index] = recipe;
      await StorageService.saveRecipes(_localRecipes);
      notifyListeners();
    }
  }

  Future<void> deleteRecipe(String id) async {
    _localRecipes.removeWhere((r) => r.id == id);
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
  }

  Recipe? getById(String id) {
    try {
      return _localRecipes.firstWhere((r) => r.id == id);
    } catch (_) {
      try {
        final s = _remoteSummaries.firstWhere((x) => x.id == id);
        return Recipe.apiSummary(id: s.id, name: s.name);
      } catch (_) {
        return null;
      }
    }
  }
}
