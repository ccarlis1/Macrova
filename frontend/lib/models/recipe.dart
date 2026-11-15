import 'ingredient.dart';

class RecipeIngredientEntry {
  final String ingredientId;
  final String ingredientName;
  final double quantity;
  final String unit;
  final double caloriesPer100g;
  final double proteinPer100g;
  final double carbsPer100g;
  final double fatPer100g;
  final Map<String, double> micronutrientsPer100g;
  final Map<String, double> unitConversions;

  /// False when the server couldn't resolve the ingredient or its unit
  /// (`resolved: false` on `GET /api/v1/recipes/{id}`); nutrition is then zero.
  final bool resolved;

  const RecipeIngredientEntry({
    required this.ingredientId,
    required this.ingredientName,
    this.quantity = 0,
    this.unit = 'g',
    this.caloriesPer100g = 0,
    this.proteinPer100g = 0,
    this.carbsPer100g = 0,
    this.fatPer100g = 0,
    this.micronutrientsPer100g = const {},
    this.unitConversions = const {},
    this.resolved = true,
  });

  /// Grams for this line ([gramsForUnit]). Throws [UnknownUnitException] when
  /// [unit] has no gram weight, so the nutrition getters below throw too:
  /// check [hasGramWeight] first, or use the [Recipe] totals, which leave such
  /// lines out.
  double get _grams => gramsForUnit(
        quantity: quantity,
        unit: unit,
        unitConversions: unitConversions,
        ingredientName: ingredientName,
      );

  /// False when [unit] has no gram weight for this line (FE-13): its nutrition
  /// is unknown and the Recipe Builder blocks saving.
  bool get hasGramWeight {
    try {
      _grams;
      return true;
    } on UnknownUnitException {
      return false;
    }
  }

  /// Weight of one [unit] to send as `grams_per_unit` (BE-19): the line's
  /// conversion for a non-`g` unit, or null when it has none.
  double? get gramsPerUnitToSend {
    if (unit == 'g') return null;
    final gramsPerUnit = unitConversions[unit];
    return gramsPerUnit != null && gramsPerUnit > 0 ? gramsPerUnit : null;
  }

  /// `{name, quantity, unit, grams_per_unit?}`: the line shape shared by
  /// `RecipeSyncIngredientLine` and `NutritionIngredientLine`, so the builder's
  /// summary weighs a line the same way the planner will after sync.
  Map<String, dynamic> toApiLine() {
    final gramsPerUnit = gramsPerUnitToSend;
    return {
      'name': ingredientName,
      'quantity': quantity,
      'unit': unit,
      if (gramsPerUnit != null) 'grams_per_unit': gramsPerUnit,
    };
  }

  double get calories => caloriesPer100g * _grams / 100;
  double get proteinG => proteinPer100g * _grams / 100;
  double get carbsG => carbsPer100g * _grams / 100;
  double get fatG => fatPer100g * _grams / 100;

  Map<String, double> get scaledMicronutrients {
    final g = _grams;
    return micronutrientsPer100g
        .map((key, value) => MapEntry(key, value * g / 100));
  }

  /// Units offered in the UI: [g], keys from [unitConversions], and [unit] if
  /// missing (server lines may use e.g. `tbsp` without a conversion entry).
  List<String> get availableUnits {
    final seen = <String>{};
    final out = <String>[];
    void add(String u) {
      if (u.isEmpty) return;
      if (seen.add(u)) out.add(u);
    }

    add('g');
    for (final k in unitConversions.keys) {
      add(k);
    }
    add(unit);
    return out;
  }

  RecipeIngredientEntry copyWith({
    String? ingredientId,
    String? ingredientName,
    double? quantity,
    String? unit,
    double? caloriesPer100g,
    double? proteinPer100g,
    double? carbsPer100g,
    double? fatPer100g,
    Map<String, double>? micronutrientsPer100g,
    Map<String, double>? unitConversions,
    bool? resolved,
  }) {
    return RecipeIngredientEntry(
      ingredientId: ingredientId ?? this.ingredientId,
      ingredientName: ingredientName ?? this.ingredientName,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      caloriesPer100g: caloriesPer100g ?? this.caloriesPer100g,
      proteinPer100g: proteinPer100g ?? this.proteinPer100g,
      carbsPer100g: carbsPer100g ?? this.carbsPer100g,
      fatPer100g: fatPer100g ?? this.fatPer100g,
      micronutrientsPer100g:
          micronutrientsPer100g ?? this.micronutrientsPer100g,
      unitConversions: unitConversions ?? this.unitConversions,
      resolved: resolved ?? this.resolved,
    );
  }

  Map<String, dynamic> toJson() => {
        'ingredient_id': ingredientId,
        'ingredient_name': ingredientName,
        'quantity': quantity,
        'unit': unit,
        'calories_per_100g': caloriesPer100g,
        'protein_per_100g': proteinPer100g,
        'carbs_per_100g': carbsPer100g,
        'fat_per_100g': fatPer100g,
        'micronutrients_per_100g': micronutrientsPer100g,
        'unit_conversions': unitConversions,
        'resolved': resolved,
      };

  factory RecipeIngredientEntry.fromJson(Map<String, dynamic> json) {
    return RecipeIngredientEntry(
      ingredientId: json['ingredient_id'] as String,
      ingredientName: json['ingredient_name'] as String,
      quantity: (json['quantity'] as num?)?.toDouble() ?? 0,
      unit: json['unit'] as String? ?? 'g',
      caloriesPer100g:
          (json['calories_per_100g'] as num?)?.toDouble() ?? 0,
      proteinPer100g:
          (json['protein_per_100g'] as num?)?.toDouble() ?? 0,
      carbsPer100g: (json['carbs_per_100g'] as num?)?.toDouble() ?? 0,
      fatPer100g: (json['fat_per_100g'] as num?)?.toDouble() ?? 0,
      micronutrientsPer100g:
          (json['micronutrients_per_100g'] as Map<String, dynamic>?)
                  ?.map((k, v) => MapEntry(k, (v as num).toDouble())) ??
              const {},
      unitConversions:
          (json['unit_conversions'] as Map<String, dynamic>?)
                  ?.map((k, v) => MapEntry(k, (v as num).toDouble())) ??
              const {},
      resolved: json['resolved'] as bool? ?? true,
    );
  }
}

class Recipe {
  final String id;
  final String name;
  final List<RecipeIngredientEntry> ingredients;
  final int servings;
  final int cookingTimeMinutes;
  final List<String> instructions;

  /// Canonical tag slugs by tag type (`context`, `time`, `nutrition`,
  /// `constraint`), as returned by `GET /api/v1/recipes/{id}` and edited in the
  /// Recipe Builder (`context` only). The server always derives `time` from
  /// [cookingTimeMinutes]; it is kept here for display but never sent on sync.
  /// This is the planner-facing tag source; the legacy `Recipe.tags` projection
  /// is not read by the app.
  final Map<String, List<String>> tagSlugsByType;

  /// Server-computed (`default_servings >= 2` and a hard-eligible `meal-prep`
  /// context tag). Read-only: never sent on sync; refreshed from the detail.
  final bool isMealPrepCapable;

  /// Cuisine from the tagger's closed vocabulary ([kCuisineVocabulary]), set in
  /// the Recipe Builder. Null when the app doesn't know it: the recipe detail
  /// doesn't return the stored cuisine. Sent as sync `cuisine` only when set.
  final String? cuisine;

  /// `cheap` | `standard` | `premium`, set in the Recipe Builder. Null when the
  /// app doesn't know it (not returned by the detail). Sent as sync
  /// `cost_level` only when set; the server stores `standard` otherwise.
  final String? costLevel;

  const Recipe({
    required this.id,
    required this.name,
    this.ingredients = const [],
    this.servings = 1,
    this.cookingTimeMinutes = 0,
    this.instructions = const [],
    this.tagSlugsByType = const {},
    this.isMealPrepCapable = false,
    this.cuisine,
    this.costLevel,
  });

  /// Canonical `context` slug that marks a recipe as batchable (FE-12 switch).
  static const mealPrepSlug = 'meal-prep';

  /// `context` slugs (meal roles, `meal-prep`, user context tags).
  List<String> get contextSlugs => tagSlugsByType['context'] ?? const [];

  bool get hasMealPrepTag => contextSlugs.contains(mealPrepSlug);

  /// Lines whose unit has no gram weight ([RecipeIngredientEntry.hasGramWeight]).
  /// They are unresolved: left out of every total below, never summed as grams.
  List<RecipeIngredientEntry> get linesWithoutGramWeight => [
        for (final e in ingredients)
          if (!e.hasGramWeight) e,
      ];

  /// Sums [value] over lines with a gram weight; an [UnknownUnitException]
  /// line counts as unresolved (excluded) rather than a wrong number.
  double _sumResolved(double Function(RecipeIngredientEntry e) value) {
    var sum = 0.0;
    for (final e in ingredients) {
      try {
        sum += value(e);
      } on UnknownUnitException {
        // Unresolved line: see [linesWithoutGramWeight].
      }
    }
    return sum;
  }

  double get totalCalories => _sumResolved((e) => e.calories);
  double get totalProteinG => _sumResolved((e) => e.proteinG);
  double get totalCarbsG => _sumResolved((e) => e.carbsG);
  double get totalFatG => _sumResolved((e) => e.fatG);

  double get perServingCalories =>
      servings > 0 ? totalCalories / servings : totalCalories;
  double get perServingProteinG =>
      servings > 0 ? totalProteinG / servings : totalProteinG;
  double get perServingCarbsG =>
      servings > 0 ? totalCarbsG / servings : totalCarbsG;
  double get perServingFatG =>
      servings > 0 ? totalFatG / servings : totalFatG;

  Map<String, double> get totalMicronutrients {
    final result = <String, double>{};
    for (final entry in ingredients) {
      if (!entry.hasGramWeight) continue; // unresolved line
      entry.scaledMicronutrients.forEach((key, value) {
        result[key] = (result[key] ?? 0) + value;
      });
    }
    return result;
  }

  Recipe copyWith({
    String? id,
    String? name,
    List<RecipeIngredientEntry>? ingredients,
    int? servings,
    int? cookingTimeMinutes,
    List<String>? instructions,
    Map<String, List<String>>? tagSlugsByType,
    bool? isMealPrepCapable,
    String? cuisine,
    String? costLevel,
  }) {
    return Recipe(
      id: id ?? this.id,
      name: name ?? this.name,
      ingredients: ingredients ?? this.ingredients,
      servings: servings ?? this.servings,
      cookingTimeMinutes: cookingTimeMinutes ?? this.cookingTimeMinutes,
      instructions: instructions ?? this.instructions,
      tagSlugsByType: tagSlugsByType ?? this.tagSlugsByType,
      isMealPrepCapable: isMealPrepCapable ?? this.isMealPrepCapable,
      cuisine: cuisine ?? this.cuisine,
      costLevel: costLevel ?? this.costLevel,
    );
  }

  /// `tag_slugs_by_type` JSON → map of non-empty string lists (unknown shapes dropped).
  static Map<String, List<String>> _tagSlugsFromJson(dynamic raw) {
    if (raw is! Map) return const {};
    final out = <String, List<String>>{};
    raw.forEach((key, value) {
      if (key is! String || value is! List) return;
      final slugs = [
        for (final s in value)
          if (s is String && s.trim().isNotEmpty) s.trim(),
      ];
      if (slugs.isNotEmpty) out[key] = slugs;
    });
    return out;
  }

  static String? _nonEmptyString(dynamic raw) =>
      raw is String && raw.trim().isNotEmpty ? raw.trim() : null;

  /// Sync `tag_slugs_by_type`: every type except the server-derived `time`.
  /// The server replaces the stored non-`time` types with what is sent, so the
  /// types read from the detail (nutrition, constraint) are sent back as-is.
  Map<String, List<String>> get _syncTagSlugsByType => {
        for (final e in tagSlugsByType.entries)
          if (e.key != 'time' && e.value.isNotEmpty) e.key: List.of(e.value),
      };

  static List<String> _instructionsFromJson(dynamic raw) {
    if (raw is! List) return const [];
    return [
      for (final x in raw) x?.toString() ?? '',
    ];
  }

  static int _cookingMinutesFromJson(Map<String, dynamic> json) {
    final v = json['cooking_time_minutes'];
    if (v is! num) return 0;
    final n = v.round();
    return n < 0 ? 0 : n;
  }

  /// Backend `data/recipes/recipes.json` entry → in-app [Recipe] (ingredient macros unknown).
  factory Recipe.fromServerRecipeMap(Map<String, dynamic> json) {
    final rawIngs = json['ingredients'] as List<dynamic>? ?? const [];
    final ingredients = <RecipeIngredientEntry>[];
    for (var i = 0; i < rawIngs.length; i++) {
      final item = rawIngs[i];
      if (item is! Map) continue;
      ingredients.add(
        _serverIngredientLine(Map<String, dynamic>.from(item), i),
      );
    }
    return Recipe(
      id: json['id'] as String,
      name: json['name'] as String,
      ingredients: ingredients,
      servings: 1,
      cookingTimeMinutes: _cookingMinutesFromJson(json),
      instructions: _instructionsFromJson(json['instructions']),
    );
  }

  static RecipeIngredientEntry _serverIngredientLine(
    Map<String, dynamic> m,
    int index,
  ) {
    final rawName = m['name'];
    final name = rawName == null
        ? ''
        : rawName is String
            ? rawName.trim()
            : rawName.toString().trim();
    final safeId = name.isEmpty
        ? 'line_$index'
        : 'srv_${name.toLowerCase().replaceAll(RegExp(r'\s+'), '_')}';
    final rawUnit = m['unit'];
    final unitStr = rawUnit == null
        ? 'g'
        : rawUnit is String
            ? rawUnit.trim()
            : rawUnit.toString();
    return RecipeIngredientEntry(
      ingredientId: safeId,
      ingredientName: name.isEmpty ? 'ingredient' : name,
      quantity: (m['quantity'] as num?)?.toDouble() ?? 0,
      unit: unitStr.isNotEmpty ? unitStr : 'g',
    );
  }

  /// Root object `{"recipes": [ ... ]}` as in `data/recipes/recipes.json`.
  static List<Recipe> fromServerRecipesJsonRoot(Map<String, dynamic> root) {
    final arr = root['recipes'] as List<dynamic>? ?? const [];
    return arr
        .map((e) => Recipe.fromServerRecipeMap(e as Map<String, dynamic>))
        .toList();
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'ingredients': ingredients.map((e) => e.toJson()).toList(),
        'servings': servings,
        'cooking_time_minutes': cookingTimeMinutes,
        'instructions': instructions,
        'tag_slugs_by_type': tagSlugsByType,
        'is_meal_prep_capable': isMealPrepCapable,
        if (cuisine != null) 'cuisine': cuisine,
        if (costLevel != null) 'cost_level': costLevel,
      };

  /// Body fragment for `POST /api/v1/recipes/sync` (server `RecipeSyncItem` shape).
  ///
  /// Tag fields are sent only when known, since the server keeps its stored
  /// value for an omitted field: `tag_slugs_by_type` when non-empty (minus
  /// `time`), `cuisine` / `cost_level` when set.
  Map<String, dynamic> toSyncPayload() {
    final tags = _syncTagSlugsByType;
    return {
      'id': id,
      'name': name,
      'cooking_time_minutes': cookingTimeMinutes,
      'instructions': instructions,
      'default_servings': servings,
      'ingredients': ingredients.map(_syncLine).toList(),
      if (tags.isNotEmpty) 'tag_slugs_by_type': tags,
      if (cuisine != null) 'cuisine': cuisine,
      if (costLevel != null) 'cost_level': costLevel,
    };
  }

  /// One `RecipeSyncIngredientLine` ([RecipeIngredientEntry.toApiLine]).
  /// `grams_per_unit` (BE-19) is the weight of one unit, sent when the unit
  /// isn't `g` and the line carries a conversion for it (copied from
  /// `Ingredient.unitConversions` or the detail's `unit_conversions`). The
  /// server uses it only when its own ingredient record has no conversion for
  /// that unit.
  static Map<String, dynamic> _syncLine(RecipeIngredientEntry e) =>
      e.toApiLine();

  factory Recipe.fromJson(Map<String, dynamic> json) {
    return Recipe(
      id: json['id'] as String,
      name: json['name'] as String,
      ingredients: (json['ingredients'] as List<dynamic>?)
              ?.map((e) => RecipeIngredientEntry.fromJson(
                  e as Map<String, dynamic>))
              .toList() ??
          const [],
      servings: json['servings'] as int? ?? 1,
      cookingTimeMinutes: _cookingMinutesFromJson(json),
      instructions: _instructionsFromJson(json['instructions']),
      tagSlugsByType: _tagSlugsFromJson(json['tag_slugs_by_type']),
      isMealPrepCapable: json['is_meal_prep_capable'] == true,
      cuisine: _nonEmptyString(json['cuisine']),
      costLevel: _nonEmptyString(json['cost_level']),
    );
  }

  /// Placeholder from `GET /api/v1/recipes` (id + name only) until a full recipe exists locally.
  factory Recipe.apiSummary({required String id, required String name}) {
    return Recipe(
      id: id,
      name: name,
      ingredients: const [],
      servings: 1,
      cookingTimeMinutes: 0,
      instructions: const [],
    );
  }
}
