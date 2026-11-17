import 'recipe.dart';

/// Pushes recipes to `POST /api/v1/recipes/sync` ([ApiService.syncRecipes] or
/// a test fake).
typedef RecipeListSyncFn = Future<RecipeSyncResult> Function(
  List<Recipe> recipes,
);

/// One entry of the sync response's `errors` (BE-19): a recipe the server
/// rejected and did not store, sent as `"<recipe id>: <CODE>: <message>"`
/// (codes such as `UNIT_NOT_CONVERTIBLE`, `INGREDIENT_UNRESOLVED`,
/// `INVALID_REQUEST`). When the string doesn't have that shape, [recipeId] and
/// [code] are null and [message] is the raw string.
class RecipeSyncError {
  /// The string as the server sent it.
  final String raw;
  final String? recipeId;

  /// Name of the sent recipe with [recipeId], when known.
  final String? recipeName;
  final String? code;
  final String message;

  const RecipeSyncError({
    required this.raw,
    required this.message,
    this.recipeId,
    this.recipeName,
    this.code,
  });

  static final _codeAndMessage = RegExp(r'^([A-Z][A-Z0-9_]*): (.*)$', dotAll: true);

  /// Parses [raw], matching its id prefix against the [sent] recipes first
  /// (ids may contain `:`), then falling back to the first `": "`.
  factory RecipeSyncError.parse(String raw, {List<Recipe> sent = const []}) {
    Recipe? match;
    for (final r in sent) {
      if (r.id.isNotEmpty &&
          raw.startsWith('${r.id}: ') &&
          (match == null || r.id.length > match.id.length)) {
        match = r;
      }
    }
    String? id;
    String rest;
    if (match != null) {
      id = match.id;
      rest = raw.substring(match.id.length + 2);
    } else {
      final cut = raw.indexOf(': ');
      if (cut <= 0) return RecipeSyncError(raw: raw, message: raw);
      id = raw.substring(0, cut);
      rest = raw.substring(cut + 2);
    }
    final m = _codeAndMessage.firstMatch(rest);
    if (m == null) {
      // An id prefix without a CODE: only trust it when it is a sent id.
      return match == null
          ? RecipeSyncError(raw: raw, message: raw)
          : RecipeSyncError(
              raw: raw,
              recipeId: id,
              recipeName: match.name,
              message: rest,
            );
    }
    return RecipeSyncError(
      raw: raw,
      recipeId: id,
      recipeName: match?.name,
      code: m.group(1),
      message: m.group(2)!,
    );
  }

  /// Recipe label for the UI: its name, else its id, else null.
  String? get recipeLabel {
    final name = recipeName?.trim();
    if (name != null && name.isNotEmpty) return name;
    return recipeId;
  }

  /// `"<recipe>: <message>"`, or the raw string when the recipe is unknown.
  String get displayText {
    final label = recipeLabel;
    return label == null ? raw : '$label: $message';
  }

  @override
  String toString() => 'RecipeSyncError($raw)';
}

/// `POST /api/v1/recipes/sync` response (`RecipeSyncResponse`): the stored ids
/// and one [RecipeSyncError] per rejected recipe (not stored, not in
/// [syncedIds]).
class RecipeSyncResult {
  final List<String> syncedIds;
  final List<RecipeSyncError> errors;

  const RecipeSyncResult({
    this.syncedIds = const [],
    this.errors = const [],
  });

  /// Parses the response body; `errors` is optional (older servers omit it).
  /// Throws [FormatException] when `synced_ids` is missing.
  factory RecipeSyncResult.fromJson(
    Map<String, dynamic> json, {
    List<Recipe> sent = const [],
  }) {
    final ids = json['synced_ids'];
    if (ids is! List) {
      throw const FormatException('Missing synced_ids in sync response');
    }
    final rawErrors = json['errors'];
    return RecipeSyncResult(
      syncedIds: [for (final e in ids) e.toString()],
      errors: [
        if (rawErrors is List)
          for (final e in rawErrors)
            if (e != null) RecipeSyncError.parse(e.toString(), sent: sent),
      ],
    );
  }
}
