import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/micronutrient_defaults.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

// BE-20: ProfileProvider fetches the server's new-user micronutrient default
// per demographic; it never writes it into the profile.

/// A fake `GET /api/v1/micronutrient_defaults` serving the captured fixtures
/// (adult_male, pregnancy; the other two reuse adult_male's goals under their
/// own name). Records every call; [failNext] makes the next calls throw, and
/// [gate] holds responses until completed.
class FakeMicronutrientDefaultsServer {
  final List<String> calls = [];
  int failNext = 0;
  Completer<void>? gate;

  static Map<String, dynamic> fixture(String demographic) {
    final file = demographic == 'pregnancy'
        ? 'micronutrient_defaults_pregnancy.json'
        : 'micronutrient_defaults_adult_male.json';
    final json = jsonDecode(File('test/fixtures/$file').readAsStringSync())
        as Map<String, dynamic>;
    return json..['demographic'] = demographic;
  }

  Future<MicronutrientDefaults> fetch(String demographic) async {
    calls.add(demographic);
    final g = gate;
    if (g != null) await g.future;
    if (failNext > 0) {
      failNext--;
      throw const ApiException(
        statusCode: 0,
        code: 'HTTP_ERROR',
        message: 'Connection refused',
      );
    }
    return MicronutrientDefaults.fromJson(fixture(demographic));
  }

  ProfileProvider provider() => ProfileProvider(micronutrientDefaultsFn: fetch);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('Given Not set or an unsupported value, Then nothing is fetched',
      () async {
    final server = FakeMicronutrientDefaultsServer();
    final p = server.provider();

    expect(await p.loadMicronutrientDefaults(''), isNull);
    expect(await p.loadMicronutrientDefaults('teen_male'), isNull);
    expect(server.calls, isEmpty);
  });

  test(
      'Given a demographic, Then it is fetched once and cached; the profile '
      'is unchanged', () async {
    final server = FakeMicronutrientDefaultsServer();
    final p = server.provider();

    final d = await p.loadMicronutrientDefaults('adult_male');
    expect(d!.goals['vitamin_c_mg'], 90.0);
    expect(p.micronutrientDefaultsFor('adult_male'), same(d));
    expect(await p.loadMicronutrientDefaults('adult_male'), same(d));
    expect(server.calls, ['adult_male']);
    expect(p.profile.micronutrientGoals.toPlanMicronutrientGoals(), isNull);
  });

  test('Given a failure, Then the error is kept and a retry refetches',
      () async {
    final server = FakeMicronutrientDefaultsServer()..failNext = 1;
    final p = server.provider();

    expect(await p.loadMicronutrientDefaults('pregnancy'), isNull);
    expect(p.micronutrientDefaultsError('pregnancy'), 'Connection refused');
    expect(p.micronutrientDefaultsFor('pregnancy'), isNull);

    final d = await p.loadMicronutrientDefaults('pregnancy');
    expect(d!.leftOut, contains('vitamin_e_mg'));
    expect(p.micronutrientDefaultsError('pregnancy'), isNull);
    expect(server.calls, ['pregnancy', 'pregnancy']);
  });

  test('While a fetch runs, Then loading is reported for that demographic',
      () async {
    final server = FakeMicronutrientDefaultsServer()..gate = Completer<void>();
    final p = server.provider();

    final pending = p.loadMicronutrientDefaults('lactation');
    expect(p.micronutrientDefaultsLoading('lactation'), isTrue);
    expect(p.micronutrientDefaultsLoading('adult_male'), isFalse);

    server.gate!.complete();
    await pending;
    expect(p.micronutrientDefaultsLoading('lactation'), isFalse);
    expect(p.micronutrientDefaultsFor('lactation')!.demographic, 'lactation');
  });
}
