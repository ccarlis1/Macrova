/// Display metadata for keys matching [MicronutrientProfile] / `config/user_profile.yaml` `micronutrient_goals`.
class MicronutrientFieldDisplay {
  final String key;
  final String label;
  final String unit;
  final bool isLimit;

  const MicronutrientFieldDisplay({
    required this.key,
    required this.label,
    required this.unit,
    this.isLimit = false,
  });
}

/// Order matches backend `MicronutrientProfile` / YAML.
const List<MicronutrientFieldDisplay> kMicronutrientsInDisplayOrder = [
  // Vitamins
  MicronutrientFieldDisplay(key: 'vitamin_a_ug', label: 'Vitamin A', unit: 'mcg'),
  MicronutrientFieldDisplay(key: 'vitamin_c_mg', label: 'Vitamin C', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'vitamin_d_iu', label: 'Vitamin D', unit: 'IU'),
  MicronutrientFieldDisplay(key: 'vitamin_e_mg', label: 'Vitamin E', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'vitamin_k_ug', label: 'Vitamin K', unit: 'mcg'),
  MicronutrientFieldDisplay(key: 'b1_thiamine_mg', label: 'B1 Thiamine', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'b2_riboflavin_mg', label: 'B2 Riboflavin', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'b3_niacin_mg', label: 'B3 Niacin', unit: 'mg'),
  MicronutrientFieldDisplay(
    key: 'b5_pantothenic_acid_mg',
    label: 'B5 Pantothenic acid',
    unit: 'mg',
  ),
  MicronutrientFieldDisplay(key: 'b6_pyridoxine_mg', label: 'B6 Pyridoxine', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'b12_cobalamin_ug', label: 'B12 Cobalamin', unit: 'mcg'),
  MicronutrientFieldDisplay(key: 'folate_ug', label: 'Folate', unit: 'mcg'),
  // Minerals
  MicronutrientFieldDisplay(key: 'calcium_mg', label: 'Calcium', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'copper_mg', label: 'Copper', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'iron_mg', label: 'Iron', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'magnesium_mg', label: 'Magnesium', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'manganese_mg', label: 'Manganese', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'phosphorus_mg', label: 'Phosphorus', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'potassium_mg', label: 'Potassium', unit: 'mg'),
  MicronutrientFieldDisplay(key: 'selenium_ug', label: 'Selenium', unit: 'mcg'),
  MicronutrientFieldDisplay(
    key: 'sodium_mg',
    label: 'Sodium',
    unit: 'mg',
    isLimit: true,
  ),
  MicronutrientFieldDisplay(key: 'zinc_mg', label: 'Zinc', unit: 'mg'),
  // Other
  MicronutrientFieldDisplay(key: 'fiber_g', label: 'Fiber', unit: 'g'),
  MicronutrientFieldDisplay(key: 'omega_3_g', label: 'Omega-3', unit: 'g'),
  MicronutrientFieldDisplay(key: 'omega_6_g', label: 'Omega-6', unit: 'g'),
];

String micronutrientLabelForKey(String key) {
  for (final e in kMicronutrientsInDisplayOrder) {
    if (e.key == key) return e.label;
  }
  return key;
}

String micronutrientUnitForKey(String key) {
  for (final e in kMicronutrientsInDisplayOrder) {
    if (e.key == key) return e.unit;
  }
  return '';
}

bool micronutrientIsLimitKey(String key) {
  for (final e in kMicronutrientsInDisplayOrder) {
    if (e.key == key) return e.isLimit;
  }
  return false;
}
