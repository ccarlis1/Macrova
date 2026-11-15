import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/models.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/planner_config_screen.dart';
import 'package:macrova/screens/profile_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../providers/profile_provider_defaults_test.dart'
    show FakeMicronutrientDefaultsServer;

// BE-20 (Flutter): a new user's Profile starts from the server's default
// micronutrient goals for the chosen demographic; every value stays editable,
// and a user's own goals are never replaced.

void _bigView(WidgetTester tester) {
  tester.view.physicalSize = const Size(1000, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

Future<void> _pumpProfile(WidgetTester tester, ProfileProvider profile) async {
  _bigView(tester);
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: LlmConfigProvider(profile),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: ProfileScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _pickDemographic(WidgetTester tester, String label) async {
  await tester.tap(find.byKey(ProfileScreen.demographicFieldKey));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

String _field(WidgetTester tester, String nutrientKey) => tester
    .widget<TextFormField>(find.byKey(ProfileScreen.microFieldKey(nutrientKey)))
    .controller!
    .text;

String _tau(WidgetTester tester) => tester
    .widget<TextFormField>(find.byKey(ProfileScreen.microTauFieldKey))
    .controller!
    .text;

Future<void> _saveProfile(WidgetTester tester) async {
  final button = find.widgetWithText(FilledButton, 'Save Profile');
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

/// Saves a profile with [microGoals] and [demographic] to device storage and
/// loads it, as a returning user.
Future<ProfileProvider> _savedUser(
  FakeMicronutrientDefaultsServer server, {
  String demographic = '',
  Map<String, double> microGoals = const {},
}) async {
  SharedPreferences.setMockInitialValues({
    'user_profile': jsonEncode({
      'demographic_group': demographic,
      'micronutrient_goals': microGoals,
      'micronutrient_weekly_min_fraction': 0.8,
    }),
  });
  final p = server.provider();
  await p.load();
  return p;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
      'Given a new user, When Adult Male is picked, Then the fields show its '
      'default goals and tau, and the left-out line names Vitamin D, Omega-3 '
      'and Omega-6',
      (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    final profile = server.provider();
    await _pumpProfile(tester, profile);
    expect(_field(tester, 'vitamin_c_mg'), '');

    await _pickDemographic(tester, 'Adult Male (19-50)');

    expect(server.calls, ['adult_male']);
    expect(_field(tester, 'vitamin_c_mg'), '90');
    expect(_field(tester, 'b1_thiamine_mg'), '1.2');
    expect(_field(tester, 'copper_mg'), '0.9');
    expect(_field(tester, 'fiber_g'), '38');
    expect(_field(tester, 'vitamin_d_iu'), '');
    expect(_field(tester, 'omega_3_g'), '');
    expect(_field(tester, 'omega_6_g'), '');
    expect(_tau(tester), '1');

    final line = tester
        .widget<Text>(find.byKey(ProfileScreen.microDefaultsLeftOutKey))
        .data!;
    expect(line, contains('Adult Male (19-50)'));
    expect(line, contains('Left out: Vitamin D, Omega-3, Omega-6'));
    expect(line, contains('enter a value'));

    // Nothing is stored until the user saves.
    expect(profile.profile.demographicGroup, '');
    expect(
        profile.profile.micronutrientGoals.toPlanMicronutrientGoals(), isNull);
  });

  testWidgets(
      'Given Pregnancy, Then the left-out line also names Vitamin E and its '
      'field starts empty', (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    await _pumpProfile(tester, server.provider());

    await _pickDemographic(tester, 'Pregnancy');

    expect(_field(tester, 'vitamin_e_mg'), '');
    expect(
      tester
          .widget<Text>(find.byKey(ProfileScreen.microDefaultsLeftOutKey))
          .data,
      contains('Left out: Vitamin D, Vitamin E, Omega-3, Omega-6'),
    );
  });

  testWidgets(
      'Given the default is shown, When one value is edited, saved and a plan '
      'is generated, Then the request carries the edited value and the other '
      'defaults', (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    final profile = server.provider();
    await _pumpProfile(tester, profile);
    await _pickDemographic(tester, 'Adult Male (19-50)');

    await tester.enterText(
      find.byKey(ProfileScreen.microFieldKey('vitamin_c_mg')),
      '120',
    );
    await tester.enterText(
      find.byKey(ProfileScreen.microFieldKey('omega_3_g')),
      '1.6',
    );
    await _saveProfile(tester);

    expect(profile.profile.demographicGroup, 'adult_male');
    expect(profile.profile.micronutrientGoals.vitaminCMg, 120);

    // Plan from Planner Config with the saved profile.
    final requests = <PlanRequest>[];
    final mealPlan = MealPlanProvider(
      planFn: (request) async {
        requests.add(request);
        return MealPlan.fromPlanApiV1Response({
          'success': true,
          'plan_status': 'success',
          'days': 1,
          'daily_plans': const [],
          'goals': const {},
          'warnings': const <String>[],
          'report': {'failures': const <dynamic>[]},
        });
      },
      recipeSyncFn: (batch) async =>
          RecipeSyncResult(syncedIds: [for (final r in batch) r.id]),
    )..setDays(1);
    final recipes = RecipeProvider(recipeListFn: () async => []);
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider<ProfileProvider>.value(value: profile),
          ChangeNotifierProvider<LlmConfigProvider>.value(
            value: LlmConfigProvider(profile),
          ),
          ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
          ChangeNotifierProvider<MealPlanProvider>.value(value: mealPlan),
        ],
        child: MaterialApp(
          theme: AppTheme.light,
          home: const Scaffold(body: PlannerConfigScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final generate = find.widgetWithText(FilledButton, 'Generate Meal Plan');
    await tester.ensureVisible(generate);
    await tester.tap(generate);
    await tester.pumpAndSettle();

    final defaults = FakeMicronutrientDefaultsServer.fixture('adult_male');
    final expected = <String, double>{
      for (final e
          in (defaults['micronutrient_goals'] as Map<String, dynamic>).entries)
        e.key: (e.value as num).toDouble(),
      'vitamin_c_mg': 120,
      'omega_3_g': 1.6,
    };
    final request = requests.single;
    expect(request.micronutrientGoals, expected);
    expect(request.micronutrientWeeklyMinFraction, 1.0);
    expect(request.demographic, 'adult_male');
    final json = request.toJson();
    expect(json['micronutrient_goals'], expected);
    expect(
        (json['micronutrient_goals'] as Map).containsKey('omega_6_g'), isFalse);
  });

  testWidgets(
      'Given a returning user with goals of their own, When the screen opens '
      'and the demographic changes, Then nothing is fetched or overwritten',
      (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    final profile = await _savedUser(
      server,
      demographic: 'adult_female',
      microGoals: const {'vitamin_c_mg': 75, 'iron_mg': 18},
    );
    await _pumpProfile(tester, profile);

    expect(server.calls, isEmpty);
    expect(_field(tester, 'vitamin_c_mg'), '75');
    expect(_tau(tester), '0.8');

    await _pickDemographic(tester, 'Pregnancy');

    expect(server.calls, isEmpty);
    expect(_field(tester, 'vitamin_c_mg'), '75');
    expect(_field(tester, 'iron_mg'), '18');
    expect(_field(tester, 'b1_thiamine_mg'), '');
    expect(_tau(tester), '0.8');
    expect(find.byKey(ProfileScreen.microDefaultsLeftOutKey), findsNothing);
  });

  testWidgets(
      'Given a saved demographic and no goals, When the screen opens, Then it '
      'starts from that default', (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    final profile = await _savedUser(server, demographic: 'lactation');
    await _pumpProfile(tester, profile);

    expect(server.calls, ['lactation']);
    expect(_field(tester, 'vitamin_c_mg'), '90');
    expect(_tau(tester), '1');
  });

  testWidgets(
      'Given an unedited default, When the demographic changes, Then the new '
      'default replaces it; once a value is edited, a change keeps the fields',
      (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    await _pumpProfile(tester, server.provider());

    await _pickDemographic(tester, 'Adult Male (19-50)');
    expect(_field(tester, 'vitamin_e_mg'), '15');

    await _pickDemographic(tester, 'Pregnancy');
    expect(server.calls, ['adult_male', 'pregnancy']);
    expect(_field(tester, 'vitamin_e_mg'), '');

    await tester.enterText(
      find.byKey(ProfileScreen.microFieldKey('vitamin_c_mg')),
      '200',
    );
    await tester.pump();
    await _pickDemographic(tester, 'Adult Female (19-50)');

    expect(server.calls, ['adult_male', 'pregnancy']);
    expect(_field(tester, 'vitamin_c_mg'), '200');
    expect(_field(tester, 'vitamin_e_mg'), '');
  });

  testWidgets(
      'Given the fetch fails, Then goals stay untouched and a notice offers '
      'Retry, which applies the default', (tester) async {
    final server = FakeMicronutrientDefaultsServer()..failNext = 1;
    await _pumpProfile(tester, server.provider());

    await _pickDemographic(tester, 'Adult Female (19-50)');

    expect(find.byKey(ProfileScreen.microDefaultsErrorKey), findsOneWidget);
    expect(find.textContaining('goals are unchanged'), findsOneWidget);
    expect(_field(tester, 'vitamin_c_mg'), '');
    expect(_tau(tester), '1');
    expect(find.byKey(ProfileScreen.microDefaultsLeftOutKey), findsNothing);

    await tester.tap(find.byKey(ProfileScreen.microDefaultsRetryKey));
    await tester.pumpAndSettle();

    expect(server.calls, ['adult_female', 'adult_female']);
    expect(find.byKey(ProfileScreen.microDefaultsErrorKey), findsNothing);
    expect(_field(tester, 'vitamin_c_mg'), '90');
    expect(find.byKey(ProfileScreen.microDefaultsLeftOutKey), findsOneWidget);
  });

  testWidgets(
      'While the default loads, Then a loading hint shows; a value typed '
      'meanwhile is not overwritten', (tester) async {
    final server = FakeMicronutrientDefaultsServer()..gate = Completer<void>();
    await _pumpProfile(tester, server.provider());

    await tester.tap(find.byKey(ProfileScreen.demographicFieldKey));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Adult Male (19-50)').last);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.byKey(ProfileScreen.microDefaultsLoadingKey), findsOneWidget);

    await tester.enterText(
      find.byKey(ProfileScreen.microFieldKey('zinc_mg')),
      '9',
    );
    server.gate!.complete();
    await tester.pumpAndSettle();

    expect(find.byKey(ProfileScreen.microDefaultsLoadingKey), findsNothing);
    expect(_field(tester, 'zinc_mg'), '9');
    expect(_field(tester, 'vitamin_c_mg'), '');
  });

  testWidgets('Given Not set, Then nothing is fetched and fields stay',
      (tester) async {
    final server = FakeMicronutrientDefaultsServer();
    await _pumpProfile(tester, server.provider());
    expect(server.calls, isEmpty);

    await _pickDemographic(tester, 'Adult Male (19-50)');
    await _pickDemographic(tester, 'Not set');

    expect(server.calls, ['adult_male']);
    expect(_field(tester, 'vitamin_c_mg'), '90');
    expect(find.byKey(ProfileScreen.microDefaultsLoadingKey), findsNothing);
    expect(find.byKey(ProfileScreen.microDefaultsErrorKey), findsNothing);
  });
}
