class NutritionSummary {
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final double perServingCalories;
  final double perServingProteinG;
  final double perServingCarbsG;
  final double perServingFatG;
  final Map<String, double> micronutrients;
  final int servings;

  const NutritionSummary({
    required this.calories,
    required this.proteinG,
    required this.carbsG,
    required this.fatG,
    required this.perServingCalories,
    required this.perServingProteinG,
    required this.perServingCarbsG,
    required this.perServingFatG,
    required this.micronutrients,
    required this.servings,
  });

  factory NutritionSummary.fromJson(Map<String, dynamic> json) {
    final microRaw = json['micronutrients'] as Map<String, dynamic>?;
    return NutritionSummary(
      calories: (json['calories'] as num).toDouble(),
      proteinG: (json['protein_g'] as num).toDouble(),
      carbsG: (json['carbs_g'] as num).toDouble(),
      fatG: (json['fat_g'] as num).toDouble(),
      perServingCalories:
          (json['per_serving_calories'] as num).toDouble(),
      perServingProteinG:
          (json['per_serving_protein_g'] as num).toDouble(),
      perServingCarbsG:
          (json['per_serving_carbs_g'] as num).toDouble(),
      perServingFatG: (json['per_serving_fat_g'] as num).toDouble(),
      micronutrients: microRaw?.map(
            (k, v) => MapEntry(k, (v as num).toDouble()),
          ) ??
          const {},
      servings: json['servings'] as int? ?? 1,
    );
  }
}
