import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../models/models.dart';
import '../models/recipe.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

const _uuid = Uuid();

/// Dev: `flutter run --dart-define=BUNDLE_SERVER_RECIPES=true`
const _bundleServerRecipes = bool.fromEnvironment(
  'BUNDLE_SERVER_RECIPES',
  defaultValue: false,
);

const _bundledRecipesAsset = 'assets/dev/server_recipes.json';

/// Resolves a recipe line label to a saved hub ingredient when the strings
/// are not identical (e.g. "jasmine rice in unsalted water" vs "jasmine rice").
Ingredient? _matchSavedIngredient(
  String rawLine,
  Map<String, Ingredient> byName,
) {
  final key = rawLine.toLowerCase().trim();
  if (key.isEmpty) return null;

  final direct = byName[key];
  if (direct != null) return direct;

  final head = key.split(',').first.trim();
  final headHit = byName[head];
  if (headHit != null) return headHit;

  // Prefer longest saved key contained in the recipe line (most specific).
  Ingredient? bestByContain;
  var bestLen = 0;
  for (final e in byName.entries) {
    final s = e.key;
    if (s.length < 3) continue;
    if (key.contains(s) && s.length > bestLen) {
      bestLen = s.length;
      bestByContain = e.value;
    }
  }
  if (bestByContain != null) return bestByContain;

  // Short line phrase appears inside a longer USDA-style saved name.
  if (key.length >= 6) {
    bestLen = 0;
    bestByContain = null;
    for (final e in byName.entries) {
      final s = e.key;
      if (s.length < 3) continue;
      if (s.contains(key) && s.length > bestLen) {
        bestLen = s.length;
        bestByContain = e.value;
      }
    }
    if (bestByContain != null) return bestByContain;
  }

  final tokens = key
      .split(RegExp(r'[^a-z0-9]+'))
      .where((t) => t.length >= 4)
      .toList()
    ..sort((a, b) => b.length.compareTo(a.length));
  for (final t in tokens) {
    bestLen = 0;
    Ingredient? tokenBest;
    for (final e in byName.entries) {
      final s = e.key;
      if (!s.contains(t)) continue;
      if (s.length > bestLen) {
        bestLen = s.length;
        tokenBest = e.value;
      }
    }
    if (tokenBest != null) return tokenBest;
  }
  return null;
}

class RecipeProvider extends ChangeNotifier {
  List<Recipe> _localRecipes = [];
  List<RecipeSummary> _remoteSummaries = [];
  bool _loaded = false;
  bool _syncLoading = false;
  String? _syncError;

  /// In-memory full recipes from [assets/dev/server_recipes.json] (by backend id).
  Map<String, Recipe>? _bundledById;
  bool _bundledAssetHydrateAttempted = false;

  int _ingredientEnrichmentSignature = 0;

  Recipe _withBundledFallback(Recipe r) {
    if (r.ingredients.isNotEmpty) return r;
    final full = _bundledById?[r.id];
    if (full != null && full.ingredients.isNotEmpty) return full;
    return r;
  }

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
    final merged = map.values.map(_withBundledFallback).toList()
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

  /// Loads bundled `server_recipes.json` into [_bundledById] and patches [_localRecipes]
  /// rows that have no ingredients. Does not require [BUNDLE_SERVER_RECIPES].
  Future<void> hydrateBundledServerRecipesFromAsset() async {
    if (_bundledAssetHydrateAttempted) return;
    _bundledAssetHydrateAttempted = true;
    try {
      final raw = await rootBundle.loadString(_bundledRecipesAsset);
      final list = Recipe.fromServerRecipesJsonRoot(
        jsonDecode(raw) as Map<String, dynamic>,
      );
      _bundledById = {for (final r in list) r.id: r};
      var changed = false;
      for (var i = 0; i < _localRecipes.length; i++) {
        final r = _localRecipes[i];
        if (r.ingredients.isEmpty) {
          final full = _bundledById![r.id];
          if (full != null && full.ingredients.isNotEmpty) {
            _localRecipes[i] = full;
            changed = true;
          }
        }
      }
      if (changed) {
        await StorageService.saveRecipes(_localRecipes);
      }
      notifyListeners();
    } catch (e, st) {
      _bundledById = {};
      debugPrint('hydrateBundledServerRecipesFromAsset: $e\n$st');
    }
  }

  /// Match recipe lines to [Ingredient.name] (lowercase) and copy per-100g data.
  Future<void> applyIngredientNutritionFromSavedIngredients(
    List<Ingredient> ingredients,
  ) async {
    if (ingredients.isEmpty) return;
    final sig = Object.hashAll(
      ingredients.map(
        (i) => Object.hash(i.id, i.name, i.caloriesPer100g),
      ),
    );
    if (sig == _ingredientEnrichmentSignature) return;
    _ingredientEnrichmentSignature = sig;

    final byName = <String, Ingredient>{};
    for (final i in ingredients) {
      byName[i.name.toLowerCase().trim()] = i;
    }

    var changed = false;
    _localRecipes = _localRecipes.map((r) {
      final e = _enrichRecipeLinesFromIngredients(r, byName);
      if (!identical(e, r)) changed = true;
      return e;
    }).toList();

    if (_bundledById != null && _bundledById!.isNotEmpty) {
      final next = <String, Recipe>{};
      for (final e in _bundledById!.entries) {
        final r = _enrichRecipeLinesFromIngredients(e.value, byName);
        if (!identical(r, e.value)) changed = true;
        next[e.key] = r;
      }
      _bundledById = next;
    }

    if (changed) {
      await StorageService.saveRecipes(_localRecipes);
      notifyListeners();
    }
  }

  Recipe _enrichRecipeLinesFromIngredients(
    Recipe r,
    Map<String, Ingredient> byName,
  ) {
    var any = false;
    final lines = <RecipeIngredientEntry>[];
    for (final line in r.ingredients) {
      final ing = _matchSavedIngredient(line.ingredientName, byName);
      if (ing != null && line.caloriesPer100g == 0) {
        lines.add(
          line.copyWith(
            ingredientId: ing.id,
            caloriesPer100g: ing.caloriesPer100g,
            proteinPer100g: ing.proteinPer100g,
            carbsPer100g: ing.carbsPer100g,
            fatPer100g: ing.fatPer100g,
            micronutrientsPer100g: ing.micronutrientsPer100g,
            unitConversions: ing.unitConversions,
          ),
        );
        any = true;
      } else {
        lines.add(line);
      }
    }
    return any ? r.copyWith(ingredients: lines) : r;
  }

  /// Merges [assets/dev/server_recipes.json] (copy of repo `data/recipes/recipes.json`)
  /// into local storage when [BUNDLE_SERVER_RECIPES] is true. Same id → replaced.
  Future<void> mergeBundledServerRecipesIfEnabled() async {
    if (!_bundleServerRecipes) return;
    try {
      final raw = await rootBundle.loadString(_bundledRecipesAsset);
      final bundled = Recipe.fromServerRecipesJsonRoot(
        jsonDecode(raw) as Map<String, dynamic>,
      );
      final byId = {for (final r in _localRecipes) r.id: r};
      for (final r in bundled) {
        byId[r.id] = r;
      }
      _localRecipes = byId.values.toList();
      await StorageService.saveRecipes(_localRecipes);
      notifyListeners();
    } catch (e, st) {
      debugPrint('mergeBundledServerRecipesIfEnabled failed: $e\n$st');
    }
  }

  /// Loads full recipe JSON from [ApiService.getRecipe] and merges into local storage.
  Future<Recipe> fetchRecipeDetail(String id) async {
    final recipe = await ApiService.getRecipe(id);
    final idx = _localRecipes.indexWhere((r) => r.id == id);
    if (idx >= 0) {
      _localRecipes[idx] = recipe;
    } else {
      _localRecipes.add(recipe);
    }
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
    return recipe;
  }

  /// Fetches recipe id+name list from the API and merges into [recipes].
  /// Full nutrition for known server ids can be loaded via [fetchRecipeDetail].
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
    Recipe? r;
    try {
      r = _localRecipes.firstWhere((x) => x.id == id);
    } catch (_) {
      try {
        final s = _remoteSummaries.firstWhere((x) => x.id == id);
        r = Recipe.apiSummary(id: s.id, name: s.name);
      } catch (_) {
        r = _bundledById?[id];
        return r;
      }
    }
    return _withBundledFallback(r);
  }
}
