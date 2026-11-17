/// One server-side pin: `ProfilePinDto` from `/api/v1/profile/pins`
/// (`src/api/server.py`). The server owns pins (stored in its profile YAML)
/// and applies them to every `/api/v1/plan`; plan requests never carry them.
///
/// Index bases (FE-15, checked against the committed backend): [dayIndex] and
/// [slotIndex] are 0-based, the same coordinate as meal-prep batch
/// assignments. The plan response shows the slot as `daily_plans[].day ==
/// dayIndex + 1` and `PlannedMeal.slot_index == slotIndex`. Flutter's request
/// `MealSlot.index` is 1-based and is not the pin coordinate.
class ProfilePin {
  final int dayIndex;
  final int slotIndex;
  final String recipeId;

  const ProfilePin({
    required this.dayIndex,
    required this.slotIndex,
    required this.recipeId,
  });

  factory ProfilePin.fromJson(Map<String, dynamic> json) {
    final day = json['day_index'];
    final slot = json['slot_index'];
    final recipeId = json['recipe_id'];
    if (day is! num || slot is! num || recipeId is! String) {
      throw const FormatException(
        'pin needs day_index, slot_index and recipe_id',
      );
    }
    return ProfilePin(
      dayIndex: day.toInt(),
      slotIndex: slot.toInt(),
      recipeId: recipeId,
    );
  }

  /// `ProfilePinListResponse`: `{"pins": [...]}`.
  static List<ProfilePin> listFromResponse(Map<String, dynamic> json) {
    final raw = json['pins'];
    if (raw is! List) {
      throw const FormatException('pin list response has no pins');
    }
    return [
      for (final p in raw)
        if (p is Map) ProfilePin.fromJson(Map<String, dynamic>.from(p)),
    ];
  }

  @override
  bool operator ==(Object other) =>
      other is ProfilePin &&
      other.dayIndex == dayIndex &&
      other.slotIndex == slotIndex &&
      other.recipeId == recipeId;

  @override
  int get hashCode => Object.hash(dayIndex, slotIndex, recipeId);

  @override
  String toString() => 'ProfilePin($dayIndex, $slotIndex, $recipeId)';
}

/// `ProfilePinDeleteResponse`: whether a pin was removed, and which.
class ProfilePinDeleteResult {
  final bool deleted;
  final ProfilePin? pin;

  const ProfilePinDeleteResult({required this.deleted, this.pin});

  factory ProfilePinDeleteResult.fromJson(Map<String, dynamic> json) {
    final deleted = json['deleted'];
    if (deleted is! bool) {
      throw const FormatException('unpin response has no deleted flag');
    }
    final pin = json['pin'];
    return ProfilePinDeleteResult(
      deleted: deleted,
      pin: pin is Map ? ProfilePin.fromJson(Map<String, dynamic>.from(pin)) : null,
    );
  }
}
