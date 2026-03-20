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
  });

  double get _grams {
    if (unit == 'g') return quantity;
    final gramsPerUnit = unitConversions[unit];
    if (gramsPerUnit == null) return quantity;
    return quantity * gramsPerUnit;
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

  List<String> get availableUnits {
    return ['g', ...unitConversions.keys];
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
    );
  }
}

class Recipe {
  final String id;
  final String name;
  final List<RecipeIngredientEntry> ingredients;
  final int servings;

  const Recipe({
    required this.id,
    required this.name,
    this.ingredients = const [],
    this.servings = 1,
  });

  double get totalCalories =>
      ingredients.fold(0, (sum, e) => sum + e.calories);
  double get totalProteinG =>
      ingredients.fold(0, (sum, e) => sum + e.proteinG);
  double get totalCarbsG =>
      ingredients.fold(0, (sum, e) => sum + e.carbsG);
  double get totalFatG =>
      ingredients.fold(0, (sum, e) => sum + e.fatG);

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
  }) {
    return Recipe(
      id: id ?? this.id,
      name: name ?? this.name,
      ingredients: ingredients ?? this.ingredients,
      servings: servings ?? this.servings,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'ingredients': ingredients.map((e) => e.toJson()).toList(),
        'servings': servings,
      };

  /// Body fragment for `POST /api/v1/recipes/sync` (server `RecipeSyncItem` shape).
  Map<String, dynamic> toSyncPayload() => {
        'id': id,
        'name': name,
        'cooking_time_minutes': 0,
        'instructions': <String>[],
        'ingredients': ingredients
            .map(
              (e) => {
                'name': e.ingredientName,
                'quantity': e.quantity,
                'unit': e.unit,
              },
            )
            .toList(),
      };

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
    );
  }

  /// Placeholder from `GET /api/v1/recipes` (id + name only) until a full recipe exists locally.
  factory Recipe.apiSummary({required String id, required String name}) {
    return Recipe(id: id, name: name, ingredients: const [], servings: 1);
  }
}
