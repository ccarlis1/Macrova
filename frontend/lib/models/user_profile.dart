class MicronutrientGoals {
  final double vitaminAUg;
  final double vitaminCMg;
  final double ironMg;
  final double calciumMg;
  final double fiberG;
  final double sodiumMg;

  const MicronutrientGoals({
    this.vitaminAUg = 0,
    this.vitaminCMg = 0,
    this.ironMg = 0,
    this.calciumMg = 0,
    this.fiberG = 0,
    this.sodiumMg = 0,
  });

  MicronutrientGoals copyWith({
    double? vitaminAUg,
    double? vitaminCMg,
    double? ironMg,
    double? calciumMg,
    double? fiberG,
    double? sodiumMg,
  }) {
    return MicronutrientGoals(
      vitaminAUg: vitaminAUg ?? this.vitaminAUg,
      vitaminCMg: vitaminCMg ?? this.vitaminCMg,
      ironMg: ironMg ?? this.ironMg,
      calciumMg: calciumMg ?? this.calciumMg,
      fiberG: fiberG ?? this.fiberG,
      sodiumMg: sodiumMg ?? this.sodiumMg,
    );
  }

  Map<String, dynamic> toJson() => {
        'vitamin_a_ug': vitaminAUg,
        'vitamin_c_mg': vitaminCMg,
        'iron_mg': ironMg,
        'calcium_mg': calciumMg,
        'fiber_g': fiberG,
        'sodium_mg': sodiumMg,
      };

  factory MicronutrientGoals.fromJson(Map<String, dynamic> json) {
    return MicronutrientGoals(
      vitaminAUg: (json['vitamin_a_ug'] as num?)?.toDouble() ?? 0,
      vitaminCMg: (json['vitamin_c_mg'] as num?)?.toDouble() ?? 0,
      ironMg: (json['iron_mg'] as num?)?.toDouble() ?? 0,
      calciumMg: (json['calcium_mg'] as num?)?.toDouble() ?? 0,
      fiberG: (json['fiber_g'] as num?)?.toDouble() ?? 0,
      sodiumMg: (json['sodium_mg'] as num?)?.toDouble() ?? 0,
    );
  }
}

class UserProfile {
  final double calories;
  final double proteinG;
  final double carbsG;
  final double fatG;
  final double proteinPct;
  final double carbsPct;
  final double fatPct;
  final bool calorieDeficitMode;
  final String demographicGroup;
  final List<String> allergies;
  final MicronutrientGoals micronutrientGoals;
  final String ingredientApiKey;
  final String llmApiKey;

  const UserProfile({
    this.calories = 2000,
    this.proteinG = 150,
    this.carbsG = 200,
    this.fatG = 67,
    this.proteinPct = 30,
    this.carbsPct = 40,
    this.fatPct = 30,
    this.calorieDeficitMode = false,
    this.demographicGroup = '',
    this.allergies = const [],
    this.micronutrientGoals = const MicronutrientGoals(),
    this.ingredientApiKey = '',
    this.llmApiKey = '',
  });

  UserProfile copyWith({
    double? calories,
    double? proteinG,
    double? carbsG,
    double? fatG,
    double? proteinPct,
    double? carbsPct,
    double? fatPct,
    bool? calorieDeficitMode,
    String? demographicGroup,
    List<String>? allergies,
    MicronutrientGoals? micronutrientGoals,
    String? ingredientApiKey,
    String? llmApiKey,
  }) {
    return UserProfile(
      calories: calories ?? this.calories,
      proteinG: proteinG ?? this.proteinG,
      carbsG: carbsG ?? this.carbsG,
      fatG: fatG ?? this.fatG,
      proteinPct: proteinPct ?? this.proteinPct,
      carbsPct: carbsPct ?? this.carbsPct,
      fatPct: fatPct ?? this.fatPct,
      calorieDeficitMode: calorieDeficitMode ?? this.calorieDeficitMode,
      demographicGroup: demographicGroup ?? this.demographicGroup,
      allergies: allergies ?? this.allergies,
      micronutrientGoals: micronutrientGoals ?? this.micronutrientGoals,
      ingredientApiKey: ingredientApiKey ?? this.ingredientApiKey,
      llmApiKey: llmApiKey ?? this.llmApiKey,
    );
  }

  /// Calculate macro grams from calorie total and percentage ratios.
  /// Protein & carbs = 4 kcal/g, fat = 9 kcal/g.
  UserProfile calculateMacrosFromRatios() {
    return copyWith(
      proteinG: (calories * proteinPct / 100) / 4,
      carbsG: (calories * carbsPct / 100) / 4,
      fatG: (calories * fatPct / 100) / 9,
    );
  }

  Map<String, dynamic> toJson() => {
        'calories': calories,
        'protein_g': proteinG,
        'carbs_g': carbsG,
        'fat_g': fatG,
        'protein_pct': proteinPct,
        'carbs_pct': carbsPct,
        'fat_pct': fatPct,
        'calorie_deficit_mode': calorieDeficitMode,
        'demographic_group': demographicGroup,
        'allergies': allergies,
        'micronutrient_goals': micronutrientGoals.toJson(),
        'ingredient_api_key': ingredientApiKey,
        'llm_api_key': llmApiKey,
      };

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      calories: (json['calories'] as num?)?.toDouble() ?? 2000,
      proteinG: (json['protein_g'] as num?)?.toDouble() ?? 150,
      carbsG: (json['carbs_g'] as num?)?.toDouble() ?? 200,
      fatG: (json['fat_g'] as num?)?.toDouble() ?? 67,
      proteinPct: (json['protein_pct'] as num?)?.toDouble() ?? 30,
      carbsPct: (json['carbs_pct'] as num?)?.toDouble() ?? 40,
      fatPct: (json['fat_pct'] as num?)?.toDouble() ?? 30,
      calorieDeficitMode: json['calorie_deficit_mode'] as bool? ?? false,
      demographicGroup: json['demographic_group'] as String? ?? '',
      allergies: List<String>.from(json['allergies'] ?? const []),
      micronutrientGoals: json['micronutrient_goals'] != null
          ? MicronutrientGoals.fromJson(
              json['micronutrient_goals'] as Map<String, dynamic>)
          : const MicronutrientGoals(),
      ingredientApiKey: json['ingredient_api_key'] as String? ?? '',
      llmApiKey: json['llm_api_key'] as String? ?? '',
    );
  }
}
