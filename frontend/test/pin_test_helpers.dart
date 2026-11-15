import 'package:macrova/models/models.dart';
import 'package:macrova/models/profile_pin.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/providers/meal_plan_provider.dart';
import 'package:macrova/services/api_service.dart';

/// Fake `/api/v1/profile/pins` server (FE-15): an in-memory pin table with
/// the routes' upsert / delete / clear semantics, plus call logs.
class FakePinServer {
  FakePinServer({List<ProfilePin>? pins}) {
    for (final p in pins ?? const <ProfilePin>[]) {
      _pins[(p.dayIndex, p.slotIndex)] = p;
    }
  }

  final Map<(int, int), ProfilePin> _pins = {};
  int listCalls = 0;
  final List<(int, int, String)> upserts = [];
  final List<(int, int)> deletes = [];
  int clearCalls = 0;
  final List<PlanRequest> planRequests = [];

  /// Recipe ids the server knows; others fail with `RECIPE_NOT_FOUND`.
  Set<String>? knownRecipeIds;

  /// Thrown by every list call while set.
  ApiException? listError;

  List<ProfilePin> get pins => _pins.values.toList();

  Future<List<ProfilePin>> list() async {
    listCalls++;
    final e = listError;
    if (e != null) throw e;
    return pins;
  }

  Future<ProfilePin> upsert(int dayIndex, int slotIndex, String recipeId) async {
    upserts.add((dayIndex, slotIndex, recipeId));
    final known = knownRecipeIds;
    if (known != null && !known.contains(recipeId)) {
      throw ApiException(
        statusCode: 404,
        code: 'RECIPE_NOT_FOUND',
        message: "No recipe with id '$recipeId'",
      );
    }
    final pin = ProfilePin(
      dayIndex: dayIndex,
      slotIndex: slotIndex,
      recipeId: recipeId,
    );
    _pins[(dayIndex, slotIndex)] = pin;
    return pin;
  }

  Future<ProfilePinDeleteResult> delete(int dayIndex, int slotIndex) async {
    deletes.add((dayIndex, slotIndex));
    final removed = _pins.remove((dayIndex, slotIndex));
    return ProfilePinDeleteResult(deleted: removed != null, pin: removed);
  }

  Future<int> clear() async {
    clearCalls++;
    final n = _pins.length;
    _pins.clear();
    return n;
  }

  /// A [MealPlanProvider] wired to this fake; its plan calls are logged in
  /// [planRequests] (pins must never trigger one).
  MealPlanProvider provider() => MealPlanProvider(
        recipeSyncFn: (r) async =>
            RecipeSyncResult(syncedIds: [for (final x in r) x.id]),
        planFn: (req) async {
          planRequests.add(req);
          throw StateError('pins must not re-run the plan');
        },
        mealPrepListFn: () async => const [],
        pinListFn: list,
        pinUpsertFn: upsert,
        pinDeleteFn: delete,
        pinClearFn: clear,
      );
}

/// A planned meal as `Meal.fromPlanApiV1` builds it.
Meal plannedMeal({
  String name = 'Rice Bowl',
  String recipeId = 'recipe_001',
  int? slotIndex = 1,
  String? source = Meal.sourcePlanner,
  String? batchId,
  double? servings,
}) =>
    Meal.fromPlanApiV1({
      'recipe_id': recipeId,
      'name': name,
      'meal_type': 'lunch',
      'slot_index': slotIndex,
      'source': source,
      'batch_id': batchId,
      'servings': servings,
      'nutrition': {
        'calories': 500,
        'protein_g': 30,
        'fat_g': 15,
        'carbs_g': 50,
      },
      'busyness_level': 2,
    });
