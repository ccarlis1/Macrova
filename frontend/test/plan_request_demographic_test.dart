import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/agent_pane_screen.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/user_profile.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

PlanRequest _request({String? demographic}) => PlanRequest(
      dailyCalories: 2000,
      dailyProteinG: 150,
      dailyFatGMin: 50,
      dailyFatGMax: 70,
      demographic: demographic,
    );

List<String> _openapiDemographicEnum(String schemaName) {
  final openapi = jsonDecode(File('../openapi/openapi.json').readAsStringSync())
      as Map<String, dynamic>;
  final schemas = (openapi['components'] as Map)['schemas'] as Map;
  final props = (schemas[schemaName] as Map)['properties'] as Map;
  final anyOf = (props['demographic'] as Map)['anyOf'] as List;
  final withEnum = anyOf.cast<Map>().firstWhere((m) => m.containsKey('enum'));
  return List<String>.from(withEnum['enum'] as List);
}

void main() {
  group('PlanRequest.demographic (BE-17)', () {
    test('Given a supported demographic, When serialized, Then it is sent', () {
      for (final d in UserProfile.supportedDemographics) {
        expect(_request(demographic: d).toJson()['demographic'], d);
      }
    });

    test('Given null, empty or unsupported, When serialized, Then the key is '
        'omitted', () {
      for (final d in [null, '', '  ', 'teen_male', 'teen_female', 'child',
        'elderly_male']) {
        expect(
          _request(demographic: d).toJson().containsKey('demographic'),
          isFalse,
          reason: 'demographic=$d',
        );
      }
    });

    test('Given a demographic, When withPlanningMode copies the request, Then '
        'the demographic is kept', () {
      final copy =
          _request(demographic: 'pregnancy').withPlanningMode('assisted');
      expect(copy.demographic, 'pregnancy');
      expect(copy.toJson()['demographic'], 'pregnancy');
      expect(copy.planningMode, 'assisted');
    });

    test('Given JSON with demographic, When parsed, Then it round-trips', () {
      final parsed = PlanRequest.fromJson(
        _request(demographic: 'lactation').toJson(),
      );
      expect(parsed.demographic, 'lactation');
    });

    test('Given the OpenAPI snapshot, When the demographic enums are read, '
        'Then they equal the supported list', () {
      expect(_openapiDemographicEnum('PlanRequest'),
          UserProfile.supportedDemographics);
      expect(_openapiDemographicEnum('PlanFromTextRequest'),
          UserProfile.supportedDemographics);
    });
  });

  group('UserProfile demographic normalization', () {
    test('Given a saved unsupported value, When loaded, Then it is Not set and '
        'not sent', () {
      for (final d in ['teen_male', 'teen_female', 'child']) {
        final p = UserProfile.fromJson({'demographic_group': d});
        expect(p.demographicGroup, '', reason: d);
        expect(p.planDemographic, isNull, reason: d);
      }
    });

    test('Given a saved supported value, When loaded, Then it is kept', () {
      final p = UserProfile.fromJson({'demographic_group': 'adult_female'});
      expect(p.demographicGroup, 'adult_female');
      expect(p.planDemographic, 'adult_female');
    });

    test('Given repo YAML with an unsupported demographic, When loaded, Then '
        'it is Not set', () {
      final p = UserProfile.fromRepoYamlMap({
        'demographic': 'child',
        'nutrition_goals': {
          'daily_calories': 2000,
          'daily_protein_g': 150,
        },
      });
      expect(p.demographicGroup, '');
    });
  });

  group('planFromTextBody', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('Given a supported demographic, When the body is built, Then it is '
        'sent', () {
      final body = planFromTextBody(
        prompt: 'plan my week',
        meal: MealPlanProvider(),
        demographic: 'adult_male',
      );
      expect(body['demographic'], 'adult_male');
      expect(body['prompt'], 'plan my week');
      expect(body['planning_mode'], 'assisted');
    });

    test('Given no or an unsupported demographic, When the body is built, '
        'Then the key is omitted', () {
      for (final d in [null, '', 'teen_male']) {
        final body = planFromTextBody(
          prompt: 'p',
          meal: MealPlanProvider(),
          demographic: d,
        );
        expect(body.containsKey('demographic'), isFalse, reason: 'd=$d');
      }
    });
  });
}
