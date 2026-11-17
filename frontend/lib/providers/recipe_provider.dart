import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../models/ingredient.dart';
import '../models/models.dart';
import '../models/recipe.dart';
import '../models/recipe_sync_result.dart';
import '../models/starter_recipe.dart';
import '../models/tag.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

const _uuid = Uuid();

typedef RecipeDetailFn = Future<Recipe> Function(String id);
typedef TagListFn = Future<List<TagMeta>> Function();
typedef RecipeSummaryListFn = Future<List<RecipeSummary>> Function();
typedef StarterListFn = Future<List<StarterRecipe>> Function();
typedef StarterImportFn = Future<StarterImportResult> Function(
  List<String> ids,
);

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
  RecipeProvider({
    RecipeListSyncFn? recipeSyncFn,
    RecipeDetailFn? recipeDetailFn,
    TagListFn? tagListFn,
    RecipeSummaryListFn? recipeListFn,
    StarterListFn? starterListFn,
    StarterImportFn? starterImportFn,
  })  : _recipeSyncFn = recipeSyncFn ?? ApiService.syncRecipes,
        _recipeDetailFn = recipeDetailFn ?? ApiService.getRecipe,
        _tagListFn = tagListFn ?? (() => ApiService.listTags()),
        _recipeListFn = recipeListFn ?? ApiService.listRecipes,
        _starterListFn =
            starterListFn ?? (() => ApiService.listStarterRecipes()),
        _starterImportFn =
            starterImportFn ?? ((ids) => ApiService.importStarterRecipes(ids));

  final RecipeListSyncFn _recipeSyncFn;
  final RecipeDetailFn _recipeDetailFn;
  final TagListFn _tagListFn;
  final RecipeSummaryListFn _recipeListFn;
  final StarterListFn _starterListFn;
  final StarterImportFn _starterImportFn;

  /// `GET /api/v1/starter_recipes` (FE-16), fetched when the picker opens.
  List<StarterRecipe>? _starterRecipes;
  bool _starterLoading = false;
  String? _starterError;
  bool _starterImporting = false;

  /// `GET /api/v1/tags`, fetched once per session ([loadTagRegistry]).
  List<TagMeta>? _tagRegistry;
  String? _tagRegistryError;
  Future<void>? _tagRegistryInFlight;

  List<Recipe> _localRecipes = [];
  List<RecipeSummary> _remoteSummaries = [];
  bool _syncLoading = false;
  String? _syncError;

  /// Per-recipe rejections from `POST /recipes/sync` (BE-19), by recipe id
  /// (or the raw string when it names no recipe). See [recipeSyncErrors].
  final Map<String, RecipeSyncError> _recipeSyncErrors = {};

  /// Device-local favorite recipe ids (not a planner tag / not synced).
  final Set<String> _favoriteRecipeIds = {};

  int _ingredientEnrichmentSignature = 0;

  /// Stored recipes with at least one ingredient line (for `/recipes/sync` before planning).
  List<Recipe> get localFullRecipesForSync => List.unmodifiable(
        _localRecipes.where((r) => r.ingredients.isNotEmpty),
      );

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

  /// Registry tags, or null until [loadTagRegistry] succeeds.
  List<TagMeta>? get tagRegistry =>
      _tagRegistry == null ? null : List.unmodifiable(_tagRegistry!);
  String? get tagRegistryError => _tagRegistryError;

  /// Offerable `context` tags with `semantic_class == meal_role`, registry order.
  List<TagMeta> get mealRoleTags => [
        for (final t in _tagRegistry ?? const <TagMeta>[])
          if (t.isMealRole && t.isOfferable) t,
      ];

  /// Fetches the tag registry once per session; [force] refetches (retry).
  Future<void> loadTagRegistry({bool force = false}) {
    if (!force && _tagRegistry != null) return Future.value();
    final inFlight = _tagRegistryInFlight;
    if (inFlight != null) return inFlight;
    final f = _fetchTagRegistry();
    _tagRegistryInFlight = f;
    return f.whenComplete(() => _tagRegistryInFlight = null);
  }

  Future<void> _fetchTagRegistry() async {
    _tagRegistryError = null;
    notifyListeners();
    try {
      _tagRegistry = await _tagListFn();
    } catch (e) {
      _tagRegistryError = e is ApiException ? e.message : e.toString();
    } finally {
      notifyListeners();
    }
  }

  bool get syncLoading => _syncLoading;
  String? get syncError => _syncError;

  /// Latest server rejection per recipe, from the last sync that sent it:
  /// a later sync that stores the recipe (or [deleteRecipe]) clears it. These
  /// recipes are saved on this device only and the planner can't use them.
  List<RecipeSyncError> get recipeSyncErrors =>
      List.unmodifiable(_recipeSyncErrors.values);

  /// Server ids from the last successful `GET /api/v1/recipes` (empty if never synced or error).
  Set<String> get remoteRecipeIds =>
      Set.unmodifiable(_remoteSummaries.map((s) => s.id));

  bool isFavorite(String recipeId) => _favoriteRecipeIds.contains(recipeId);

  Future<void> load() async {
    _localRecipes = await StorageService.loadRecipes();
    _favoriteRecipeIds
      ..clear()
      ..addAll(await StorageService.loadFavoriteRecipeIds());
    notifyListeners();
  }

  Future<void> toggleFavorite(String recipeId) async {
    if (recipeId.isEmpty) return;
    if (_favoriteRecipeIds.contains(recipeId)) {
      _favoriteRecipeIds.remove(recipeId);
    } else {
      _favoriteRecipeIds.add(recipeId);
    }
    notifyListeners();
    await StorageService.saveFavoriteRecipeIds(_favoriteRecipeIds);
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

  /// Loads full recipe JSON from [ApiService.getRecipe] and merges into local storage.
  /// The detail's `cuisine` / `cost_level` / `dietary_flags` win over values
  /// remembered here; those are kept only when the server has none.
  Future<Recipe> fetchRecipeDetail(String id) async {
    final fetched = await _recipeDetailFn(id);
    final prior = _localById(id);
    final recipe = prior == null
        ? fetched
        : fetched.copyWith(
            cuisine: fetched.cuisine ?? prior.cuisine,
            costLevel: fetched.costLevel ?? prior.costLevel,
            dietaryFlags: fetched.dietaryFlags ?? prior.dietaryFlags,
          );
    final idx = _localRecipes.indexWhere((r) => r.id == id);
    if (idx >= 0) {
      _localRecipes[idx] = recipe;
    } else {
      _localRecipes.add(recipe);
    }
    _serverTagsLoadedIds.add(id);
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
    return recipe;
  }

  /// Refreshes the server-owned tag fields of a stored recipe from
  /// `GET /api/v1/recipes/{id}`, keeping its local lines: [Recipe.tagSlugsByType],
  /// [Recipe.isMealPrepCapable] and (server value wins when present)
  /// [Recipe.cuisine] / [Recipe.costLevel] / [Recipe.dietaryFlags]. Use before
  /// editing a server recipe whose tags were never loaded, since a sync with
  /// `tag_slugs_by_type` replaces the stored non-`time` tags.
  Future<Recipe> refreshServerTags(Recipe recipe) async {
    final detail = await _recipeDetailFn(recipe.id);
    final merged = recipe
        .copyWith(
          tagSlugsByType: detail.tagSlugsByType,
          isMealPrepCapable: detail.isMealPrepCapable,
        )
        .withServerTagFields(detail);
    final idx = _localRecipes.indexWhere((r) => r.id == recipe.id);
    if (idx >= 0) {
      _localRecipes[idx] = merged;
      await StorageService.saveRecipes(_localRecipes);
    }
    _serverTagsLoadedIds.add(recipe.id);
    notifyListeners();
    return merged;
  }

  /// Ids whose detail ([fetchRecipeDetail] / [refreshServerTags]) loaded this
  /// session, so their [Recipe.cuisine] / [Recipe.costLevel] are the server's.
  final Set<String> _serverTagsLoadedIds = {};

  /// Ids [loadServerTags] already tried this session (loaded or failed).
  final Set<String> _serverTagsAttemptedIds = {};
  int _serverTagsInFlight = 0;

  /// True when [id]'s tag fields came from the server this session.
  bool hasServerTags(String id) => _serverTagsLoadedIds.contains(id);

  /// Ids with server tag fields loaded this session ([hasServerTags]).
  Set<String> get serverTagsLoadedIds => Set.unmodifiable(_serverTagsLoadedIds);

  /// True while [loadServerTags] is fetching details.
  bool get serverTagsLoading => _serverTagsInFlight > 0;

  /// Loads the stored tag fields of [ids] from their details, once per session
  /// each (a failed id isn't retried). A stored recipe with lines keeps them
  /// ([refreshServerTags]); an id/name-only one is fetched in full
  /// ([fetchRecipeDetail]). One detail call per id: callers pass only the
  /// selected pool (Planner Config), never the whole library.
  Future<void> loadServerTags(Iterable<String> ids) async {
    final todo = [
      for (final id in ids)
        if (!_serverTagsLoadedIds.contains(id) &&
            _serverTagsAttemptedIds.add(id))
          id,
    ];
    if (todo.isEmpty) return;
    _serverTagsInFlight++;
    notifyListeners();
    try {
      for (final id in todo) {
        final local = _localById(id);
        try {
          if (local != null && local.ingredients.isNotEmpty) {
            await refreshServerTags(local);
          } else {
            await fetchRecipeDetail(id);
          }
        } catch (e) {
          // Not on the server, or unreachable: the id stays unchecked.
          debugPrint('loadServerTags($id): $e');
        }
      }
    } finally {
      _serverTagsInFlight--;
      notifyListeners();
    }
  }

  Recipe? _localById(String id) {
    for (final r in _localRecipes) {
      if (r.id == id) return r;
    }
    return null;
  }

  /// The starter pack, or null until [loadStarterRecipes] succeeds.
  List<StarterRecipe>? get starterRecipes =>
      _starterRecipes == null ? null : List.unmodifiable(_starterRecipes!);
  bool get starterLoading => _starterLoading;
  String? get starterError => _starterError;
  bool get starterImporting => _starterImporting;

  /// Ids in the library: stored here or listed by the server pool. A starter
  /// recipe with one of these ids shows as "In your library".
  Set<String> get libraryRecipeIds => {
        for (final r in _localRecipes) r.id,
        for (final s in _remoteSummaries) s.id,
      };

  /// Lists the starter pack (FE-16). Refetches each call (the picker calls it
  /// on open, and on retry); errors land in [starterError].
  Future<void> loadStarterRecipes() async {
    _starterLoading = true;
    _starterError = null;
    notifyListeners();
    try {
      _starterRecipes = await _starterListFn();
    } catch (e) {
      _starterError = e is ApiException ? e.message : e.toString();
    } finally {
      _starterLoading = false;
      notifyListeners();
    }
  }

  /// Copies the picked starter recipes into the server pool
  /// (`POST /api/v1/starter_recipes/import`), then refreshes the server list
  /// so they show in [recipes] like any server recipe. Nothing is stored on
  /// the device: `/plan` without `recipe_ids` reads the server pool, and the
  /// Recipe Builder loads the detail (with its unit conversions) on open.
  /// A whole-request failure throws; per-id skips are in the result.
  Future<StarterImportResult> importStarterRecipes(List<String> ids) async {
    _starterImporting = true;
    notifyListeners();
    try {
      final result = await _starterImportFn(ids);
      await syncSummariesFromApi();
      return result;
    } finally {
      _starterImporting = false;
      notifyListeners();
    }
  }

  /// Fetches recipe id+name list from the API and merges into [recipes].
  /// Full nutrition for known server ids can be loaded via [fetchRecipeDetail].
  Future<void> syncSummariesFromApi() async {
    _syncLoading = true;
    _syncError = null;
    notifyListeners();
    try {
      _remoteSummaries = await _recipeListFn();
      _syncError = null;
    } catch (e) {
      _syncError = e is ApiException ? e.message : e.toString();
    } finally {
      _syncLoading = false;
      notifyListeners();
    }
  }

  /// Saves [recipe] locally, then syncs it. The result's `errors` say whether
  /// the server rejected it (also kept in [recipeSyncErrors]); a whole-request
  /// failure throws after the local save.
  Future<RecipeSyncResult> addRecipe(Recipe recipe) async {
    final withId =
        recipe.id.isEmpty ? recipe.copyWith(id: _uuid.v4()) : recipe;
    _localRecipes.add(withId);
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
    final result = await _syncAndRecord([withId]);
    await syncSummariesFromApi();
    return result;
  }

  /// Like [addRecipe] for an existing recipe.
  Future<RecipeSyncResult> updateRecipe(Recipe recipe) async {
    final index = _localRecipes.indexWhere((r) => r.id == recipe.id);
    if (index != -1) {
      _localRecipes[index] = recipe;
    } else {
      _localRecipes.add(recipe);
    }
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
    final result = await _syncAndRecord([recipe]);
    await syncSummariesFromApi();
    return result;
  }

  /// Runs [_recipeSyncFn] and replaces the stored rejections of the sent
  /// recipes with this response's.
  Future<RecipeSyncResult> _syncAndRecord(List<Recipe> batch) async {
    final result = await _recipeSyncFn(batch);
    for (final r in batch) {
      _recipeSyncErrors.remove(r.id);
      // The server recomputes stored tags (e.g. is_meal_prep_capable) on
      // sync, so the loaded detail values are stale: reload on next need.
      _serverTagsLoadedIds.remove(r.id);
      _serverTagsAttemptedIds.remove(r.id);
    }
    _recipeSyncErrors.removeWhere((_, e) => e.recipeId == null);
    for (final e in result.errors) {
      _recipeSyncErrors[e.recipeId ?? e.raw] = e;
    }
    notifyListeners();
    return result;
  }

  Future<void> deleteRecipe(String id) async {
    _localRecipes.removeWhere((r) => r.id == id);
    _recipeSyncErrors.remove(id);
    await StorageService.saveRecipes(_localRecipes);
    notifyListeners();
  }

  /// Alias for [getById] (library / builder call sites).
  Recipe? getRecipeById(String id) => getById(id);

  Recipe? getById(String id) {
    final local = _localById(id);
    if (local != null) return local;
    for (final s in _remoteSummaries) {
      if (s.id == id) return Recipe.apiSummary(id: s.id, name: s.name);
    }
    return null;
  }
}
