class IngredientSearchResultItem {
  final String fdcId;
  final String description;
  final double score;

  const IngredientSearchResultItem({
    required this.fdcId,
    required this.description,
    required this.score,
  });

  factory IngredientSearchResultItem.fromJson(Map<String, dynamic> json) {
    return IngredientSearchResultItem(
      fdcId: json['fdc_id'] as String,
      description: json['description'] as String,
      score: (json['score'] as num).toDouble(),
    );
  }
}

class IngredientSearchResponse {
  final List<IngredientSearchResultItem> results;

  const IngredientSearchResponse({required this.results});

  factory IngredientSearchResponse.fromJson(Map<String, dynamic> json) {
    final list = json['results'] as List<dynamic>? ?? const [];
    return IngredientSearchResponse(
      results: list
          .map(
            (e) => IngredientSearchResultItem.fromJson(
              e as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }
}
