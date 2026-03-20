class IngredientMatchAccepted {
  const IngredientMatchAccepted({
    required this.originalQuery,
    required this.normalizedName,
    required this.confidence,
  });

  final String originalQuery;
  final String normalizedName;
  final double confidence;

  factory IngredientMatchAccepted.fromJson(Map<String, dynamic> json) {
    return IngredientMatchAccepted(
      originalQuery: json['original_query'] as String,
      normalizedName: json['normalized_name'] as String,
      confidence: (json['confidence'] as num).toDouble(),
    );
  }
}

class IngredientMatchRejected {
  const IngredientMatchRejected({
    required this.originalQuery,
    required this.code,
    required this.message,
  });

  final String originalQuery;
  final String code;
  final String message;

  factory IngredientMatchRejected.fromJson(Map<String, dynamic> json) {
    return IngredientMatchRejected(
      originalQuery: json['original_query'] as String,
      code: json['code'] as String,
      message: json['message'] as String,
    );
  }
}

class IngredientMatchResult {
  const IngredientMatchResult({
    required this.accepted,
    required this.rejected,
  });

  final List<IngredientMatchAccepted> accepted;
  final List<IngredientMatchRejected> rejected;

  factory IngredientMatchResult.fromJson(Map<String, dynamic> json) {
    final acc = json['accepted'] as List<dynamic>? ?? const [];
    final rej = json['rejected'] as List<dynamic>? ?? const [];
    return IngredientMatchResult(
      accepted: acc
          .map((e) =>
              IngredientMatchAccepted.fromJson(e as Map<String, dynamic>))
          .toList(),
      rejected: rej
          .map((e) =>
              IngredientMatchRejected.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class RecipeGenFailure {
  const RecipeGenFailure({
    required this.code,
    required this.message,
  });

  final String code;
  final String message;

  factory RecipeGenFailure.fromJson(Map<String, dynamic> json) {
    return RecipeGenFailure(
      code: json['code'] as String,
      message: json['message'] as String,
    );
  }
}

class RecipeGenerationResult {
  const RecipeGenerationResult({
    required this.acceptedCount,
    required this.rejectedCount,
    required this.recipeIds,
    required this.failures,
  });

  final int acceptedCount;
  final int rejectedCount;
  final List<String> recipeIds;
  final List<RecipeGenFailure> failures;

  factory RecipeGenerationResult.fromJson(Map<String, dynamic> json) {
    final fails = json['failures'] as List<dynamic>? ?? const [];
    final ids = json['recipe_ids'] as List<dynamic>? ?? const [];
    return RecipeGenerationResult(
      acceptedCount: json['accepted_count'] as int,
      rejectedCount: json['rejected_count'] as int,
      recipeIds: ids.map((e) => e.toString()).toList(),
      failures: fails
          .map((e) => RecipeGenFailure.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
