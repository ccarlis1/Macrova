import 'package:uuid/uuid.dart';

enum IngredientSource { saved, api, custom }

// ignore: prefer_const_constructors
final _resolveIdUuid = Uuid();

class Ingredient {
  final String id;
  final String name;
  final double caloriesPer100g;
  final double proteinPer100g;
  final double carbsPer100g;
  final double fatPer100g;
  final Map<String, double> micronutrientsPer100g;
  final Map<String, double> unitConversions;
  final IngredientSource source;

  const Ingredient({
    required this.id,
    required this.name,
    this.caloriesPer100g = 0,
    this.proteinPer100g = 0,
    this.carbsPer100g = 0,
    this.fatPer100g = 0,
    this.micronutrientsPer100g = const {},
    this.unitConversions = const {},
    this.source = IngredientSource.custom,
  });

  Ingredient copyWith({
    String? id,
    String? name,
    double? caloriesPer100g,
    double? proteinPer100g,
    double? carbsPer100g,
    double? fatPer100g,
    Map<String, double>? micronutrientsPer100g,
    Map<String, double>? unitConversions,
    IngredientSource? source,
  }) {
    return Ingredient(
      id: id ?? this.id,
      name: name ?? this.name,
      caloriesPer100g: caloriesPer100g ?? this.caloriesPer100g,
      proteinPer100g: proteinPer100g ?? this.proteinPer100g,
      carbsPer100g: carbsPer100g ?? this.carbsPer100g,
      fatPer100g: fatPer100g ?? this.fatPer100g,
      micronutrientsPer100g:
          micronutrientsPer100g ?? this.micronutrientsPer100g,
      unitConversions: unitConversions ?? this.unitConversions,
      source: source ?? this.source,
    );
  }

  /// Scale nutrition values by quantity in grams.
  double caloriesForGrams(double grams) => caloriesPer100g * grams / 100;
  double proteinForGrams(double grams) => proteinPer100g * grams / 100;
  double carbsForGrams(double grams) => carbsPer100g * grams / 100;
  double fatForGrams(double grams) => fatPer100g * grams / 100;

  /// Convert a quantity in the given unit to grams using unitConversions.
  double toGrams(double quantity, String unit) {
    if (unit == 'g') return quantity;
    final gramsPerUnit = unitConversions[unit];
    if (gramsPerUnit == null) return quantity;
    return quantity * gramsPerUnit;
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'calories_per_100g': caloriesPer100g,
        'protein_per_100g': proteinPer100g,
        'carbs_per_100g': carbsPer100g,
        'fat_per_100g': fatPer100g,
        'micronutrients_per_100g': micronutrientsPer100g,
        'unit_conversions': unitConversions,
        'source': source.name,
      };

  factory Ingredient.fromJson(Map<String, dynamic> json) {
    return Ingredient(
      id: json['id'] as String,
      name: json['name'] as String,
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
      source: IngredientSource.values.firstWhere(
        (e) => e.name == json['source'],
        orElse: () => IngredientSource.custom,
      ),
    );
  }

  /// Maps `POST /api/v1/ingredients/resolve` JSON to a saved [Ingredient] row.
  factory Ingredient.fromResolveResponse(Map<String, dynamic> json) {
    final per = json['per_100g'] as Map<String, dynamic>? ?? {};
    final microRaw = json['micronutrients'] as Map<String, dynamic>? ?? {};
    final fdc = json['fdc_id'];
    final id = (fdc is String && fdc.isNotEmpty)
        ? fdc
        : _resolveIdUuid.v4();
    return Ingredient(
      id: id,
      name: (json['name'] as String?)?.trim().isNotEmpty == true
          ? json['name'] as String
          : 'Ingredient',
      caloriesPer100g: (per['calories'] as num?)?.toDouble() ?? 0,
      proteinPer100g: (per['protein_g'] as num?)?.toDouble() ?? 0,
      carbsPer100g: (per['carbs_g'] as num?)?.toDouble() ?? 0,
      fatPer100g: (per['fat_g'] as num?)?.toDouble() ?? 0,
      micronutrientsPer100g: microRaw.map(
        (k, v) => MapEntry(k, (v as num).toDouble()),
      ),
      unitConversions: const {},
      source: IngredientSource.api,
    );
  }
}
