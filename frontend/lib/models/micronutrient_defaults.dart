/// New-user default micronutrient goals (Sprint 2 BE-20, D-A) from
/// `GET /api/v1/micronutrient_defaults?demographic=<demographic>`
/// (`MicronutrientDefaultsResponse` in `src/api/server.py`). The server owns
/// the values; the app keeps no copy. They are a starting point the Profile
/// screen fills in for a user with no goals of their own, never an override.
library;

import 'user_profile.dart';

class MicronutrientDefaults {
  /// One of [UserProfile.supportedDemographics].
  final String demographic;

  /// Nutrient key (e.g. `vitamin_c_mg`) -> daily amount: the demographic's
  /// RDIs minus [leftOut].
  final Map<String, double> goals;

  /// Nutrient keys the default leaves out (the bundled sample recipes can't
  /// meet them at the full weekly target), in reference-table order. A user
  /// may still add them back by entering a value.
  final List<String> leftOut;

  /// τ for the default goals.
  final double weeklyMinFraction;

  const MicronutrientDefaults({
    required this.demographic,
    required this.goals,
    this.leftOut = const [],
    required this.weeklyMinFraction,
  });

  factory MicronutrientDefaults.fromJson(Map<String, dynamic> json) {
    final demographic = json['demographic'];
    final goals = json['micronutrient_goals'];
    final leftOut = json['left_out'];
    final tau = json['micronutrient_weekly_min_fraction'];
    if (demographic is! String ||
        goals is! Map ||
        leftOut is! List ||
        tau is! num) {
      throw const FormatException(
        'micronutrient defaults need demographic, micronutrient_goals, '
        'left_out and micronutrient_weekly_min_fraction',
      );
    }
    final parsed = <String, double>{};
    goals.forEach((key, value) {
      if (key is! String || value is! num) {
        throw const FormatException('micronutrient goal must be key -> number');
      }
      parsed[key] = value.toDouble();
    });
    return MicronutrientDefaults(
      demographic: demographic,
      goals: parsed,
      leftOut: [
        for (final k in leftOut)
          if (k is String) k
      ],
      weeklyMinFraction: tau.toDouble(),
    );
  }
}
