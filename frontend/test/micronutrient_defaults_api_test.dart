import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:macrova/models/micronutrient_defaults.dart';
import 'package:macrova/services/api_service.dart';

// BE-20: `GET /api/v1/micronutrient_defaults` client and DTO, against
// responses captured in-process from the committed backend (see
// test/fixtures/README.md).

String _fixture(String name) => File('test/fixtures/$name').readAsStringSync();

Map<String, dynamic> _json(String name) =>
    jsonDecode(_fixture(name)) as Map<String, dynamic>;

void main() {
  group('MicronutrientDefaults DTO', () {
    test(
        'Given the captured adult_male default, Then 22 goals, vitamin D and '
        'omega-3/6 left out and tau 1.0 parse', () {
      final d = MicronutrientDefaults.fromJson(
        _json('micronutrient_defaults_adult_male.json'),
      );

      expect(d.demographic, 'adult_male');
      expect(d.goals, hasLength(22));
      expect(d.goals['vitamin_c_mg'], 90.0);
      expect(d.goals['b1_thiamine_mg'], 1.2);
      expect(d.goals['fiber_g'], 38.0);
      expect(d.goals.containsKey('omega_3_g'), isFalse);
      expect(d.goals.containsKey('vitamin_d_iu'), isFalse);
      expect(d.leftOut, ['vitamin_d_iu', 'omega_3_g', 'omega_6_g']);
      expect(d.weeklyMinFraction, 1.0);
    });

    test('Given the captured pregnancy default, Then vitamin E is left out too',
        () {
      final d = MicronutrientDefaults.fromJson(
        _json('micronutrient_defaults_pregnancy.json'),
      );
      expect(d.demographic, 'pregnancy');
      expect(d.goals, hasLength(21));
      expect(
        d.leftOut,
        ['vitamin_d_iu', 'vitamin_e_mg', 'omega_3_g', 'omega_6_g'],
      );
      expect(d.goals.containsKey('vitamin_e_mg'), isFalse);
    });

    test('Given a response missing a field, Then a FormatException', () {
      final json = _json('micronutrient_defaults_adult_male.json')
        ..remove('left_out');
      expect(() => MicronutrientDefaults.fromJson(json), throwsFormatException);
    });

    test('Given a non-numeric goal, Then a FormatException', () {
      final json = _json('micronutrient_defaults_adult_male.json');
      (json['micronutrient_goals'] as Map<String, dynamic>)['vitamin_c_mg'] =
          'lots';
      expect(() => MicronutrientDefaults.fromJson(json), throwsFormatException);
    });
  });

  group('ApiService.fetchMicronutrientDefaults', () {
    test('When fetching, Then GET with ?demographic= and the DTO parses',
        () async {
      final client = MockClient((req) async {
        expect(req.method, 'GET');
        expect(req.url.path, '/api/v1/micronutrient_defaults');
        expect(req.url.queryParameters, {'demographic': 'adult_male'});
        return http.Response(
          _fixture('micronutrient_defaults_adult_male.json'),
          200,
        );
      });
      final d = await ApiService.fetchMicronutrientDefaults(
        'adult_male',
        client: client,
      );
      expect(d.goals['vitamin_a_ug'], 900.0);
    });

    test(
        'Given the captured 400 envelope, Then ApiException carries '
        'INVALID_REQUEST', () async {
      final client = MockClient(
        (_) async => http.Response(
          _fixture('micronutrient_defaults_error_invalid.json'),
          400,
        ),
      );
      await expectLater(
        ApiService.fetchMicronutrientDefaults('teen_male', client: client),
        throwsA(
          isA<ApiException>()
              .having((e) => e.statusCode, 'statusCode', 400)
              .having((e) => e.code, 'code', 'INVALID_REQUEST'),
        ),
      );
    });

    test('Given a 200 that is not the shape, Then INVALID_RESPONSE', () async {
      final client = MockClient((_) async => http.Response('{}', 200));
      await expectLater(
        ApiService.fetchMicronutrientDefaults('adult_male', client: client),
        throwsA(
          isA<ApiException>().having((e) => e.code, 'code', 'INVALID_RESPONSE'),
        ),
      );
    });
  });
}
