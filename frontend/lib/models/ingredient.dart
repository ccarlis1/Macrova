import 'package:uuid/uuid.dart';

enum IngredientSource { saved, api, custom }

/// A line's [unit] has no gram weight for [ingredientName]: no entry in its
/// unit conversions and not a mass unit. Its nutrition is unknown, so callers
/// mark the line unresolved instead of using the quantity as grams.
class UnknownUnitException implements Exception {
  final String unit;
  final String ingredientName;

  const UnknownUnitException(this.unit, this.ingredientName);

  @override
  String toString() =>
      "UnknownUnitException: no gram weight for '$unit' ($ingredientName)";
}

/// Grams for [quantity] of [unit], with the same rules as the server's
/// `NutritionCalculator.record_grams` for units it can know without a
/// per-ingredient record: `g` (and `gram`/`grams`), the [unitConversions]
/// entry for the unit, `oz` (and `ounce`/`ounces`) at 28.35 g, and
/// `to taste` as 0 g (excluded from nutrition). Anything else throws
/// [UnknownUnitException]: no density guesses, no "treat as grams".
double gramsForUnit({
  required double quantity,
  required String unit,
  required Map<String, double> unitConversions,
  required String ingredientName,
}) {
  final raw = unit.trim().toLowerCase();
  if (raw == 'to taste') return 0;
  final canonical = _unitAliases[raw] ?? raw;
  if (canonical == 'g') return quantity;
  final gramsPerUnit = unitConversions[unit] ?? unitConversions[canonical];
  if (gramsPerUnit != null && gramsPerUnit > 0) return quantity * gramsPerUnit;
  if (canonical == 'oz') return quantity * _ozToGrams;
  throw UnknownUnitException(unit, ingredientName);
}

/// Server `NutritionCalculator.OZ_TO_GRAMS` (mass, valid for any ingredient).
const _ozToGrams = 28.35;

const _unitAliases = {
  'gram': 'g',
  'grams': 'g',
  'ounce': 'oz',
  'ounces': 'oz',
};

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

  /// One USDA-backed row from `.cache/ingredients/*.json` (Python [CacheEntry] dump).
  factory Ingredient.fromPythonCacheFile(Map<String, dynamic> json) {
    final nut = json['nutrition'] as Map<String, dynamic>? ?? {};
    final microRaw = nut['micronutrients'] as Map<String, dynamic>? ?? {};
    final fdc = json['fdc_id'];
    final id = fdc != null ? fdc.toString() : _resolveIdUuid.v4();
    final canonical = (json['canonical_name'] as String?)?.trim();
    final desc = (json['description'] as String?)?.trim();
    final name = (canonical != null && canonical.isNotEmpty)
        ? canonical
        : (desc != null && desc.isNotEmpty)
            ? desc
            : 'Ingredient';
    return Ingredient(
      id: id,
      name: name,
      caloriesPer100g: (nut['calories'] as num?)?.toDouble() ?? 0,
      proteinPer100g: (nut['protein_g'] as num?)?.toDouble() ?? 0,
      carbsPer100g: (nut['carbs_g'] as num?)?.toDouble() ?? 0,
      fatPer100g: (nut['fat_g'] as num?)?.toDouble() ?? 0,
      micronutrientsPer100g: microRaw.map(
        (k, v) => MapEntry(k, (v as num).toDouble()),
      ),
      unitConversions: const {},
      source: IngredientSource.saved,
    );
  }

  /// Bundle root `{"ingredients": [ ... ]}` from [cached_ingredients.json].
  static List<Ingredient> fromCachedIngredientsBundleRoot(
    Map<String, dynamic> root,
  ) {
    final arr = root['ingredients'] as List<dynamic>? ?? const [];
    return arr
        .map((e) => Ingredient.fromPythonCacheFile(e as Map<String, dynamic>))
        .toList();
  }
}
