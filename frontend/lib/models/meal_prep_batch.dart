/// One serving slot of a meal-prep batch: `MealPrepAssignmentResponse` (with
/// [date] / [slotId]) or, for a create request, `AssignmentInput` in canonical
/// form (`src/api/meal_prep_routes.py`).
///
/// Index bases (checked against the committed backend, FE-14): [dayIndex] and
/// [slotIndex] are 0-based. The plan response's `daily_plans[].day` is
/// `day_index + 1`, and its `PlannedMeal.slot_index` is the same 0-based
/// [slotIndex]: a batch at (0, 0) is day 1's first meal (`MealPlanDay.day == 1`,
/// `Meal.slotIndex == 0`).
class MealPrepAssignment {
  final int dayIndex;
  final int slotIndex;
  final double servings;

  /// `cook_date + day_index` (ISO date); response only.
  final String? date;

  /// Legacy alias of [slotIndex]; response only.
  final int? slotId;

  const MealPrepAssignment({
    required this.dayIndex,
    required this.slotIndex,
    this.servings = 1,
    this.date,
    this.slotId,
  });

  factory MealPrepAssignment.fromJson(Map<String, dynamic> json) {
    final day = json['day_index'];
    final slot = json['slot_index'];
    if (day is! num || slot is! num) {
      throw const FormatException('assignment needs day_index and slot_index');
    }
    return MealPrepAssignment(
      dayIndex: day.toInt(),
      slotIndex: slot.toInt(),
      servings: (json['servings'] as num?)?.toDouble() ?? 1,
      date: json['date'] as String?,
      slotId: (json['slot_id'] as num?)?.toInt(),
    );
  }

  /// Canonical `AssignmentInput` (the server rejects mixing in `date`/`slot_id`).
  Map<String, dynamic> toRequestJson() => {
        'day_index': dayIndex,
        'slot_index': slotIndex,
        'servings': servings,
      };
}

/// `MealPrepBatchResponse` from `/api/v1/meal_prep_batches`. Batches are owned
/// by the server: the app keeps only the last fetched list (on
/// `MealPlanProvider`) and never sends batches with a plan request.
class MealPrepBatch {
  final String id;
  final String recipeId;
  final int totalServings;
  final double assignedServings;
  final double remainingServings;

  /// ISO date (`YYYY-MM-DD`). The server validates only its format; it is the
  /// base the response's assignment `date`s are counted from (day_index 0).
  final String cookDate;

  /// `active` for a listed active batch; a cancelled one is `consumed`.
  final String status;
  final List<MealPrepAssignment> assignments;

  const MealPrepBatch({
    required this.id,
    required this.recipeId,
    required this.totalServings,
    required this.assignedServings,
    required this.remainingServings,
    required this.cookDate,
    required this.status,
    this.assignments = const [],
  });

  factory MealPrepBatch.fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final recipeId = json['recipe_id'];
    final total = json['total_servings'];
    if (id is! String || recipeId is! String || total is! num) {
      throw const FormatException(
        'meal-prep batch needs id, recipe_id and total_servings',
      );
    }
    final rawAssignments = json['assignments'];
    return MealPrepBatch(
      id: id,
      recipeId: recipeId,
      totalServings: total.toInt(),
      assignedServings: (json['assigned_servings'] as num?)?.toDouble() ?? 0,
      remainingServings: (json['remaining_servings'] as num?)?.toDouble() ??
          total.toDouble(),
      cookDate: json['cook_date'] as String? ?? '',
      status: json['status'] as String? ?? '',
      assignments: [
        if (rawAssignments is List)
          for (final a in rawAssignments)
            if (a is Map) MealPrepAssignment.fromJson(Map<String, dynamic>.from(a)),
      ],
    );
  }

  /// `MealPrepBatchListResponse`: `{"batches": [...]}`.
  static List<MealPrepBatch> listFromResponse(Map<String, dynamic> json) {
    final raw = json['batches'];
    if (raw is! List) {
      throw const FormatException('meal-prep list response has no batches');
    }
    return [
      for (final b in raw)
        if (b is Map) MealPrepBatch.fromJson(Map<String, dynamic>.from(b)),
    ];
  }
}

/// ISO `YYYY-MM-DD` for [d] (the `cook_date` format).
String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-'
    '${d.month.toString().padLeft(2, '0')}-'
    '${d.day.toString().padLeft(2, '0')}';

/// "1 serving", "2 servings", "1.5 servings".
String servingsLabel(num servings) {
  final n = servings == servings.roundToDouble()
      ? servings.round().toString()
      : servings.toString();
  return servings == 1 ? '1 serving' : '$n servings';
}
