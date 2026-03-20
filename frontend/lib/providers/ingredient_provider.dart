import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../services/storage_service.dart';

const _uuid = Uuid();

/// Dev: `flutter run --dart-define=BUNDLE_CACHED_INGREDIENTS=true`
const _bundleCachedIngredients = bool.fromEnvironment(
  'BUNDLE_CACHED_INGREDIENTS',
  defaultValue: false,
);

const _bundledCachedIngredientsAsset = 'assets/dev/cached_ingredients.json';

class IngredientProvider extends ChangeNotifier {
  List<Ingredient> _ingredients = [];
  bool _loaded = false;

  List<Ingredient> get ingredients => List.unmodifiable(_ingredients);
  bool get loaded => _loaded;

  Future<void> load() async {
    _ingredients = await StorageService.loadIngredients();
    _loaded = true;
    notifyListeners();
  }

  /// Merges [assets/dev/cached_ingredients.json] (from
  /// `scripts/export_flutter_cached_ingredients_bundle.py`) into local storage.
  /// Same [Ingredient.id] (fdc_id string) → replaced. [IngredientSource.saved].
  Future<void> mergeBundledCachedIngredientsIfEnabled() async {
    if (!_bundleCachedIngredients) return;
    try {
      final raw = await rootBundle.loadString(_bundledCachedIngredientsAsset);
      final bundled = Ingredient.fromCachedIngredientsBundleRoot(
        jsonDecode(raw) as Map<String, dynamic>,
      );
      final byId = {for (final i in _ingredients) i.id: i};
      for (final i in bundled) {
        byId[i.id] = i;
      }
      _ingredients = byId.values.toList();
      await StorageService.saveIngredients(_ingredients);
      notifyListeners();
    } catch (e, st) {
      debugPrint('mergeBundledCachedIngredientsIfEnabled failed: $e\n$st');
    }
  }

  List<Ingredient> search(String query, {IngredientSource? sourceFilter}) {
    var results = _ingredients;
    if (sourceFilter != null) {
      results = results.where((i) => i.source == sourceFilter).toList();
    }
    if (query.isNotEmpty) {
      final lower = query.toLowerCase();
      results =
          results.where((i) => i.name.toLowerCase().contains(lower)).toList();
    }
    return results;
  }

  Future<void> addIngredient(Ingredient ingredient) async {
    final withId = ingredient.id.isEmpty
        ? ingredient.copyWith(id: _uuid.v4())
        : ingredient;
    _ingredients.add(withId);
    await StorageService.saveIngredients(_ingredients);
    notifyListeners();
  }

  Future<void> updateIngredient(Ingredient ingredient) async {
    final index = _ingredients.indexWhere((i) => i.id == ingredient.id);
    if (index != -1) {
      _ingredients[index] = ingredient;
      await StorageService.saveIngredients(_ingredients);
      notifyListeners();
    }
  }

  Future<void> deleteIngredient(String id) async {
    _ingredients.removeWhere((i) => i.id == id);
    await StorageService.saveIngredients(_ingredients);
    notifyListeners();
  }

  Ingredient? getById(String id) {
    try {
      return _ingredients.firstWhere((i) => i.id == id);
    } catch (_) {
      return null;
    }
  }
}
