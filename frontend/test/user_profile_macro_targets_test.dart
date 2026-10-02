import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/user_profile.dart';

void main() {
  group('UserProfile macro targets (§4.2)', () {
    test('MB-053 targets fall back to fat min (D9)', () {
      expect(UserProfile.deriveCarbsG(2000, 150, 150, 170), closeTo(12.5, 1e-9));
      expect(UserProfile.macroTargetsErrorFor(2000, 150, 150, 170), isNull);
    });

    test('fromRepoYamlMap keeps carbs still negative at fat min', () {
      final profile = UserProfile.fromRepoYamlMap({
        'nutrition_goals': {
          'daily_calories': 2000,
          'daily_protein_g': 150,
          'daily_fat_g': {'min': 160, 'max': 180},
        },
        'preferences': {'allergies': <String>[]},
      });

      expect(profile.carbsG, closeTo(-10.0, 1e-9));
      expect(profile.macroTargetsError, isNotNull);
      expect(profile.macroTargetsError, contains('2040'));
      expect(profile.macroTargetsError, contains('2000'));
    });

    test('fromRepoYamlMap does not swap inverted fat range', () {
      final profile = UserProfile.fromRepoYamlMap({
        'nutrition_goals': {
          'daily_calories': 2000,
          'daily_protein_g': 150,
          'daily_fat_g': {'min': 90, 'max': 60},
        },
        'preferences': {'allergies': <String>[]},
      });

      expect(profile.fatGMin, 90);
      expect(profile.fatGMax, 60);
      expect(profile.macroTargetsError, contains('Fat min is above fat max'));
    });

    test('deriveCarbsG matches backend formula for keto-like targets', () {
      final carbs = UserProfile.deriveCarbsG(1800, 130, 120, 140);
      expect(carbs, closeTo(27.5, 1e-9));
      expect(UserProfile.macroTargetsErrorFor(1800, 130, 120, 140), isNull);
    });

    test('zero calories is rejected', () {
      expect(
        UserProfile.macroTargetsErrorFor(0, 150, 60, 80),
        contains('greater than zero'),
      );
    });
  });
}
