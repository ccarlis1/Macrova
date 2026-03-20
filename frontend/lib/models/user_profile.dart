/// Daily RDI-style targets; field names match `config/user_profile.yaml` `micronutrient_goals`
/// and Python `MicronutrientProfile` (snake_case in JSON).
class MicronutrientGoals {
  final double vitaminAUg;
  final double vitaminCMg;
  final double vitaminDIu;
  final double vitaminEMg;
  final double vitaminKUg;
  final double b1ThiamineMg;
  final double b2RiboflavinMg;
  final double b3NiacinMg;
  final double b5PantothenicAcidMg;
  final double b6PyridoxineMg;
  final double b12CobalaminUg;
  final double folateUg;
  final double calciumMg;
  final double copperMg;
  final double ironMg;
  final double magnesiumMg;
  final double manganeseMg;
  final double phosphorusMg;
  final double potassiumMg;
  final double seleniumUg;
  final double sodiumMg;
  final double zincMg;
  final double fiberG;
  final double omega3G;
  final double omega6G;

  const MicronutrientGoals({
    this.vitaminAUg = 0,
    this.vitaminCMg = 0,
    this.vitaminDIu = 0,
    this.vitaminEMg = 0,
    this.vitaminKUg = 0,
    this.b1ThiamineMg = 0,
    this.b2RiboflavinMg = 0,
    this.b3NiacinMg = 0,
    this.b5PantothenicAcidMg = 0,
    this.b6PyridoxineMg = 0,
    this.b12CobalaminUg = 0,
    this.folateUg = 0,
    this.calciumMg = 0,
    this.copperMg = 0,
    this.ironMg = 0,
    this.magnesiumMg = 0,
    this.manganeseMg = 0,
    this.phosphorusMg = 0,
    this.potassiumMg = 0,
    this.seleniumUg = 0,
    this.sodiumMg = 0,
    this.zincMg = 0,
    this.fiberG = 0,
    this.omega3G = 0,
    this.omega6G = 0,
  });

  MicronutrientGoals copyWith({
    double? vitaminAUg,
    double? vitaminCMg,
    double? vitaminDIu,
    double? vitaminEMg,
    double? vitaminKUg,
    double? b1ThiamineMg,
    double? b2RiboflavinMg,
    double? b3NiacinMg,
    double? b5PantothenicAcidMg,
    double? b6PyridoxineMg,
    double? b12CobalaminUg,
    double? folateUg,
    double? calciumMg,
    double? copperMg,
    double? ironMg,
    double? magnesiumMg,
    double? manganeseMg,
    double? phosphorusMg,
    double? potassiumMg,
    double? seleniumUg,
    double? sodiumMg,
    double? zincMg,
    double? fiberG,
    double? omega3G,
    double? omega6G,
  }) {
    return MicronutrientGoals(
      vitaminAUg: vitaminAUg ?? this.vitaminAUg,
      vitaminCMg: vitaminCMg ?? this.vitaminCMg,
      vitaminDIu: vitaminDIu ?? this.vitaminDIu,
      vitaminEMg: vitaminEMg ?? this.vitaminEMg,
      vitaminKUg: vitaminKUg ?? this.vitaminKUg,
      b1ThiamineMg: b1ThiamineMg ?? this.b1ThiamineMg,
      b2RiboflavinMg: b2RiboflavinMg ?? this.b2RiboflavinMg,
      b3NiacinMg: b3NiacinMg ?? this.b3NiacinMg,
      b5PantothenicAcidMg:
          b5PantothenicAcidMg ?? this.b5PantothenicAcidMg,
      b6PyridoxineMg: b6PyridoxineMg ?? this.b6PyridoxineMg,
      b12CobalaminUg: b12CobalaminUg ?? this.b12CobalaminUg,
      folateUg: folateUg ?? this.folateUg,
      calciumMg: calciumMg ?? this.calciumMg,
      copperMg: copperMg ?? this.copperMg,
      ironMg: ironMg ?? this.ironMg,
      magnesiumMg: magnesiumMg ?? this.magnesiumMg,
      manganeseMg: manganeseMg ?? this.manganeseMg,
      phosphorusMg: phosphorusMg ?? this.phosphorusMg,
      potassiumMg: potassiumMg ?? this.potassiumMg,
      seleniumUg: seleniumUg ?? this.seleniumUg,
      sodiumMg: sodiumMg ?? this.sodiumMg,
      zincMg: zincMg ?? this.zincMg,
      fiberG: fiberG ?? this.fiberG,
      omega3G: omega3G ?? this.omega3G,
      omega6G: omega6G ?? this.omega6G,
    );
  }

  Map<String, dynamic> toJson() => {
        'vitamin_a_ug': vitaminAUg,
        'vitamin_c_mg': vitaminCMg,
        'vitamin_d_iu': vitaminDIu,
        'vitamin_e_mg': vitaminEMg,
        'vitamin_k_ug': vitaminKUg,
        'b1_thiamine_mg': b1ThiamineMg,
        'b2_riboflavin_mg': b2RiboflavinMg,
        'b3_niacin_mg': b3NiacinMg,
        'b5_pantothenic_acid_mg': b5PantothenicAcidMg,
        'b6_pyridoxine_mg': b6PyridoxineMg,
        'b12_cobalamin_ug': b12CobalaminUg,
        'folate_ug': folateUg,
        'calcium_mg': calciumMg,
        'copper_mg': copperMg,
        'iron_mg': ironMg,
        'magnesium_mg': magnesiumMg,
        'manganese_mg': manganeseMg,
        'phosphorus_mg': phosphorusMg,
        'potassium_mg': potassiumMg,
        'selenium_ug': seleniumUg,
        'sodium_mg': sodiumMg,
        'zinc_mg': zincMg,
        'fiber_g': fiberG,
        'omega_3_g': omega3G,
        'omega_6_g': omega6G,
      };

  /// Parse profile form fields (avoids depending on Flutter in this model).
  factory MicronutrientGoals.fromStringMap(Map<String, String> raw) {
    double p(String k) => double.tryParse(raw[k]?.trim() ?? '') ?? 0;
    return MicronutrientGoals(
      vitaminAUg: p('vitamin_a_ug'),
      vitaminCMg: p('vitamin_c_mg'),
      vitaminDIu: p('vitamin_d_iu'),
      vitaminEMg: p('vitamin_e_mg'),
      vitaminKUg: p('vitamin_k_ug'),
      b1ThiamineMg: p('b1_thiamine_mg'),
      b2RiboflavinMg: p('b2_riboflavin_mg'),
      b3NiacinMg: p('b3_niacin_mg'),
      b5PantothenicAcidMg: p('b5_pantothenic_acid_mg'),
      b6PyridoxineMg: p('b6_pyridoxine_mg'),
      b12CobalaminUg: p('b12_cobalamin_ug'),
      folateUg: p('folate_ug'),
      calciumMg: p('calcium_mg'),
      copperMg: p('copper_mg'),
      ironMg: p('iron_mg'),
      magnesiumMg: p('magnesium_mg'),
      manganeseMg: p('manganese_mg'),
      phosphorusMg: p('phosphorus_mg'),
      potassiumMg: p('potassium_mg'),
      seleniumUg: p('selenium_ug'),
      sodiumMg: p('sodium_mg'),
      zincMg: p('zinc_mg'),
      fiberG: p('fiber_g'),
      omega3G: p('omega_3_g'),
      omega6G: p('omega_6_g'),
    );
  }

  factory MicronutrientGoals.fromJson(Map<String, dynamic> json) {
    double rd(String k) => (json[k] as num?)?.toDouble() ?? 0;
    return MicronutrientGoals(
      vitaminAUg: rd('vitamin_a_ug'),
      vitaminCMg: rd('vitamin_c_mg'),
      vitaminDIu: rd('vitamin_d_iu'),
      vitaminEMg: rd('vitamin_e_mg'),
      vitaminKUg: rd('vitamin_k_ug'),
      b1ThiamineMg: rd('b1_thiamine_mg'),
      b2RiboflavinMg: rd('b2_riboflavin_mg'),
      b3NiacinMg: rd('b3_niacin_mg'),
      b5PantothenicAcidMg: rd('b5_pantothenic_acid_mg'),
      b6PyridoxineMg: rd('b6_pyridoxine_mg'),
      b12CobalaminUg: rd('b12_cobalamin_ug'),
      folateUg: rd('folate_ug'),
      calciumMg: rd('calcium_mg'),
      copperMg: rd('copper_mg'),
      ironMg: rd('iron_mg'),
      magnesiumMg: rd('magnesium_mg'),
      manganeseMg: rd('manganese_mg'),
      phosphorusMg: rd('phosphorus_mg'),
      potassiumMg: rd('potassium_mg'),
      seleniumUg: rd('selenium_ug'),
      sodiumMg: rd('sodium_mg'),
      zincMg: rd('zinc_mg'),
      fiberG: rd('fiber_g'),
      omega3G: rd('omega_3_g'),
      omega6G: rd('omega_6_g'),
    );
  }

  /// Daily targets for `POST /api/v1/plan` (`micronutrient_goals`). Omits zeros.
  Map<String, double>? toPlanMicronutrientGoals() {
    final m = <String, double>{};
    void add(String k, double v) {
      if (v > 0) m[k] = v;
    }

    add('vitamin_a_ug', vitaminAUg);
    add('vitamin_c_mg', vitaminCMg);
    add('vitamin_d_iu', vitaminDIu);
    add('vitamin_e_mg', vitaminEMg);
    add('vitamin_k_ug', vitaminKUg);
    add('b1_thiamine_mg', b1ThiamineMg);
    add('b2_riboflavin_mg', b2RiboflavinMg);
    add('b3_niacin_mg', b3NiacinMg);
    add('b5_pantothenic_acid_mg', b5PantothenicAcidMg);
    add('b6_pyridoxine_mg', b6PyridoxineMg);
    add('b12_cobalamin_ug', b12CobalaminUg);
    add('folate_ug', folateUg);
    add('calcium_mg', calciumMg);
    add('copper_mg', copperMg);
    add('iron_mg', ironMg);
    add('magnesium_mg', magnesiumMg);
    add('manganese_mg', manganeseMg);
    add('phosphorus_mg', phosphorusMg);
    add('potassium_mg', potassiumMg);
    add('selenium_ug', seleniumUg);
    add('sodium_mg', sodiumMg);
    add('zinc_mg', zincMg);
    add('fiber_g', fiberG);
    add('omega_3_g', omega3G);
    add('omega_6_g', omega6G);

    if (m.isEmpty) return null;
    return m;
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
  /// τ: prorated weekly micronutrient floor vs RDI (see `nutrition_goals.micronutrient_weekly_min_fraction` in YAML).
  final double micronutrientWeeklyMinFraction;
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
    this.micronutrientWeeklyMinFraction = 1.0,
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
    double? micronutrientWeeklyMinFraction,
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
      micronutrientWeeklyMinFraction:
          micronutrientWeeklyMinFraction ??
              this.micronutrientWeeklyMinFraction,
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
        'micronutrient_weekly_min_fraction': micronutrientWeeklyMinFraction,
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
      micronutrientWeeklyMinFraction:
          (json['micronutrient_weekly_min_fraction'] as num?)?.toDouble() ??
              1.0,
      ingredientApiKey: json['ingredient_api_key'] as String? ?? '',
      llmApiKey: json['llm_api_key'] as String? ?? '',
    );
  }
}
