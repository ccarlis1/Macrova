/// Starter-pack DTOs (Sprint 2 FE-16) for `GET /api/v1/starter_recipes` and
/// `POST /api/v1/starter_recipes/import` (`src/api/server.py`, BE-22). The
/// server owns the pack (`data/recipes/recipes.json.example` and its shipped
/// tags); the app never keeps a copy, it only lists and imports.
library;

/// One recipe of the starter pack (`StarterRecipe`).
class StarterRecipe {
  final String id;
  final String name;
  final int cookingTimeMinutes;

  /// Null when an ingredient doesn't resolve (see [unresolved]).
  final double? caloriesPerServing;
  final double? proteinGPerServing;

  /// The shipped tags by type (`context`, `time`, ...).
  final Map<String, List<String>> tagSlugsByType;

  /// False when an ingredient or unit doesn't resolve: the planner would drop
  /// the recipe. Defaults to true when an older server omits it.
  final bool readyForPlanning;
  final List<String> unresolved;

  const StarterRecipe({
    required this.id,
    required this.name,
    this.cookingTimeMinutes = 0,
    this.caloriesPerServing,
    this.proteinGPerServing,
    this.tagSlugsByType = const {},
    this.readyForPlanning = true,
    this.unresolved = const [],
  });

  /// `context` slugs (meal roles among them).
  List<String> get contextSlugs => tagSlugsByType['context'] ?? const [];

  factory StarterRecipe.fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final name = json['name'];
    if (id is! String || id.isEmpty || name is! String) {
      throw const FormatException('starter recipe needs id and name');
    }
    final minutes = json['cooking_time_minutes'];
    final unresolved = json['unresolved'];
    return StarterRecipe(
      id: id,
      name: name,
      cookingTimeMinutes: minutes is num ? minutes.round() : 0,
      caloriesPerServing: (json['calories_per_serving'] as num?)?.toDouble(),
      proteinGPerServing: (json['protein_g_per_serving'] as num?)?.toDouble(),
      tagSlugsByType: _tagSlugs(json['tag_slugs_by_type']),
      readyForPlanning: json['ready_for_planning'] as bool? ?? true,
      unresolved: unresolved is List
          ? [for (final u in unresolved) if (u is String) u]
          : const [],
    );
  }

  /// `StarterRecipesResponse`: `{"recipes": [...]}`.
  static List<StarterRecipe> listFromResponse(Map<String, dynamic> json) {
    final raw = json['recipes'];
    if (raw is! List) {
      throw const FormatException('starter list response has no recipes');
    }
    return [
      for (final r in raw)
        if (r is Map) StarterRecipe.fromJson(Map<String, dynamic>.from(r)),
    ];
  }

  static Map<String, List<String>> _tagSlugs(dynamic raw) {
    if (raw is! Map) return const {};
    final out = <String, List<String>>{};
    raw.forEach((key, value) {
      if (key is! String || value is! List) return;
      final slugs = [
        for (final s in value)
          if (s is String && s.isNotEmpty) s,
      ];
      if (slugs.isNotEmpty) out[key] = slugs;
    });
    return out;
  }
}

/// Why an id was not imported (`StarterImportSkipped`).
class StarterImportSkipped {
  /// `already_in_pool`: the user's pool already has this id.
  static const alreadyInPool = 'already_in_pool';

  /// `not_a_starter_recipe`: the id isn't in the starter pack.
  static const notAStarterRecipe = 'not_a_starter_recipe';

  final String id;
  final String reason;

  const StarterImportSkipped({required this.id, required this.reason});

  factory StarterImportSkipped.fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final reason = json['reason'];
    if (id is! String || reason is! String) {
      throw const FormatException('skipped entry needs id and reason');
    }
    return StarterImportSkipped(id: id, reason: reason);
  }

  @override
  bool operator ==(Object other) =>
      other is StarterImportSkipped && other.id == id && other.reason == reason;

  @override
  int get hashCode => Object.hash(id, reason);

  @override
  String toString() => 'StarterImportSkipped($id, $reason)';
}

/// `StarterImportResponse`: `{imported: [ids], skipped: [{id, reason}]}`.
/// A partial import is still HTTP 200; nothing in [skipped] was written.
class StarterImportResult {
  final List<String> imported;
  final List<StarterImportSkipped> skipped;

  const StarterImportResult({
    this.imported = const [],
    this.skipped = const [],
  });

  factory StarterImportResult.fromJson(Map<String, dynamic> json) {
    final imported = json['imported'];
    final skipped = json['skipped'];
    if (imported is! List || skipped is! List) {
      throw const FormatException(
        'import response needs imported and skipped',
      );
    }
    return StarterImportResult(
      imported: [for (final id in imported) if (id is String) id],
      skipped: [
        for (final s in skipped)
          if (s is Map)
            StarterImportSkipped.fromJson(Map<String, dynamic>.from(s)),
      ],
    );
  }
}
