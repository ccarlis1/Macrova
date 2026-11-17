import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/profile_pin.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/services/api_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../pin_test_helpers.dart';

// FE-15: pins live on MealPlanProvider (no pins provider); the server owns them.

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('Given server pins, When loadPins, Then they are keyed by slot', () async {
    final server = FakePinServer(pins: const [
      ProfilePin(dayIndex: 1, slotIndex: 0, recipeId: 'b'),
      ProfilePin(dayIndex: 0, slotIndex: 2, recipeId: 'a'),
    ]);
    final plan = server.provider();
    expect(plan.pinsLoaded, isFalse);

    await plan.loadPins();

    expect(plan.pinsLoaded, isTrue);
    expect(plan.pinCount, 2);
    expect(plan.pins.map((p) => (p.dayIndex, p.slotIndex)), [(0, 2), (1, 0)]);
    expect(plan.pinAt(0, 2)?.recipeId, 'a');
    expect(plan.pinAt(0, 0), isNull);
  });

  test('When pinning, Then it PUTs, re-fetches, and does not re-run the plan',
      () async {
    final server = FakePinServer();
    final plan = server.provider();

    await plan.pinRecipe(0, 1, 'recipe_001');

    expect(server.upserts, [(0, 1, 'recipe_001')]);
    expect(server.listCalls, 1);
    expect(plan.pinAt(0, 1)?.recipeId, 'recipe_001');
    expect(server.planRequests, isEmpty);
  });

  test('When unpinning and clearing, Then pins are re-fetched each time',
      () async {
    final server = FakePinServer(pins: const [
      ProfilePin(dayIndex: 0, slotIndex: 1, recipeId: 'a'),
      ProfilePin(dayIndex: 1, slotIndex: 0, recipeId: 'b'),
    ]);
    final plan = server.provider();
    await plan.loadPins();

    expect(await plan.unpinSlot(0, 1), isTrue);
    expect(plan.pinCount, 1);
    expect(await plan.clearPins(), 1);
    expect(plan.pinCount, 0);
    expect(server.listCalls, 3);
    expect(server.planRequests, isEmpty);
  });

  test('Given RECIPE_NOT_FOUND, When pinning, Then it throws and nothing changes',
      () async {
    final server = FakePinServer()..knownRecipeIds = {'recipe_001'};
    final plan = server.provider();

    await expectLater(
      plan.pinRecipe(0, 0, 'nope'),
      throwsA(isA<ApiException>()
          .having((e) => e.code, 'code', 'RECIPE_NOT_FOUND')),
    );
    expect(plan.pinCount, 0);
    expect(server.listCalls, 0);
  });

  test('Given a list failure, Then the server code is kept and pins stay',
      () async {
    final server = FakePinServer(pins: const [
      ProfilePin(dayIndex: 0, slotIndex: 0, recipeId: 'a'),
    ]);
    final plan = server.provider();
    await plan.loadPins();

    server.listError = const ApiException(
      statusCode: 400,
      code: 'PROFILE_PIN_INVALID',
      message: 'pins must be a list',
    );
    await plan.loadPins();

    expect(plan.pinsErrorCode, 'PROFILE_PIN_INVALID');
    expect(plan.pinsErrorMessage, 'pins must be a list');
    expect(plan.pinCount, 1);
  });

  test('pinSlotFor is (day - 1, slot_index), falling back to the position', () {
    expect(MealPlanProvider.pinSlotFor(1, 0, plannedMeal(slotIndex: 2)), (0, 2));
    expect(
      MealPlanProvider.pinSlotFor(3, 1, plannedMeal(slotIndex: null)),
      (2, 1),
    );
  });
}
