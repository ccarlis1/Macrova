import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/user_profile.dart';

void main() {
  test(
    'Given YAML with max_daily_calories, When fromRepoYamlMap, Then number and switch are set',
    () {
      final profile = UserProfile.fromRepoYamlMap({
        'nutrition_goals': {
          'daily_calories': 2000,
          'daily_protein_g': 130,
          'daily_fat_g': {'min': 50, 'max': 70},
          'max_daily_calories': 1700,
          'micronutrient_weekly_min_fraction': 1.0,
        },
        'preferences': {'allergies': <String>[]},
        'demographic': 'adult_male',
      });

      expect(profile.maxDailyCalories, 1700);
      expect(profile.calorieDeficitMode, isTrue);
      expect(profile.legacyDeficitModePending, isFalse);
    },
  );

  test(
    'Given old profile with bool only, When fromJson, Then switch on and ceiling null',
    () {
      final profile = UserProfile.fromJson({
        'calories': 2000,
        'protein_g': 150,
        'carbs_g': 200,
        'fat_g_min': 60,
        'fat_g_max': 74,
        'calorie_deficit_mode': true,
      });

      expect(profile.maxDailyCalories, isNull);
      expect(profile.calorieDeficitMode, isTrue);
      expect(profile.legacyDeficitModePending, isTrue);
    },
  );

  test(
    'Given profile with ceiling, When toJson/fromJson round-trip, Then number is kept',
    () {
      const original = UserProfile(calories: 2000, maxDailyCalories: 1800);
      final restored = UserProfile.fromJson(original.toJson());

      expect(restored.maxDailyCalories, 1800);
      expect(restored.calorieDeficitMode, isTrue);
      expect(restored.legacyDeficitModePending, isFalse);
      expect(original.toJson()['max_daily_calories'], 1800);
      expect(original.toJson()['calorie_deficit_mode'], isTrue);
    },
  );

  test(
    'Given ceiling set, When copyWith clearMaxDailyCalories, Then null and switch off',
    () {
      const profile = UserProfile(maxDailyCalories: 1700);
      final cleared = profile.copyWith(clearMaxDailyCalories: true);

      expect(cleared.maxDailyCalories, isNull);
      expect(cleared.calorieDeficitMode, isFalse);
      expect(cleared.legacyDeficitModePending, isFalse);
    },
  );

  test(
    'Given legacy pending, When copyWith clearMaxDailyCalories, Then switch off',
    () {
      final pending = UserProfile.fromJson({
        'calories': 2000,
        'calorie_deficit_mode': true,
      });
      final cleared = pending.copyWith(clearMaxDailyCalories: true);

      expect(cleared.maxDailyCalories, isNull);
      expect(cleared.calorieDeficitMode, isFalse);
      expect(cleared.legacyDeficitModePending, isFalse);
    },
  );

  test(
    'Given legacy pending, When copyWith maxDailyCalories, Then value set and pending cleared',
    () {
      final pending = UserProfile.fromJson({
        'calories': 2000,
        'calorie_deficit_mode': true,
      });
      final resolved = pending.copyWith(maxDailyCalories: 1800);

      expect(resolved.maxDailyCalories, 1800);
      expect(resolved.calorieDeficitMode, isTrue);
      expect(resolved.legacyDeficitModePending, isFalse);
    },
  );
}
