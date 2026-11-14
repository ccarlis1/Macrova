/// Tag registry DTOs and the closed tag vocabularies the app sends on sync.
library;

/// Cuisine values accepted by `RecipeSyncItem.cuisine`: the tagger's closed
/// `CUISINE_VOCABULARY` (`src/llm/recipe_tagger.py`), exposed only as the
/// OpenAPI enum on `RecipeSyncItem.cuisine` (no endpoint lists it). `unknown`
/// is the server's "no cuisine" value. Kept in lockstep by
/// `test/tag_registry_dto_test.dart`, which reads `openapi/openapi.json`.
const kCuisineVocabulary = <String>[
  'american',
  'mexican',
  'italian',
  'mediterranean',
  'middle-eastern',
  'indian',
  'chinese',
  'japanese',
  'korean',
  'thai',
  'vietnamese',
  'french',
  'greek',
  'spanish',
  'latin-american',
  'african',
  'caribbean',
  'british',
  'german',
  'eastern-european',
  'fusion',
  'unknown',
];

/// The server's stored cuisine when none was set.
const kCuisineUnknown = 'unknown';

/// `BudgetLevel` values accepted by `RecipeSyncItem.cost_level` (and the pool
/// filter). The server stores `standard` when none was set.
const kCostLevelDefault = 'standard';

/// "middle-eastern" → "Middle Eastern".
String tagValueLabel(String value) => value
    .split(RegExp(r'[-_]'))
    .where((w) => w.isNotEmpty)
    .map((w) => w[0].toUpperCase() + w.substring(1))
    .join(' ');

/// One entry of `GET /api/v1/tags` (`tag_routes.py::_to_payload`).
class TagMeta {
  final String slug;
  final String display;

  /// `context` | `time` | `nutrition` | `constraint` (JSON key `type`).
  final String type;

  /// `system` | `user` | `llm`.
  final String source;
  final String? createdAt;
  final List<String> aliases;
  final int recipeCount;

  /// `capability` | `meal_role` | `exclusion` | `nutrition_claim` |
  /// `identity_hint` | `effort_system`.
  final String? semanticClass;

  /// `proposed` | `approved` | `rejected`, or null (non-LLM tags).
  final String? eligibility;
  final bool? hardFilterAllowed;
  final bool? softScoreAllowed;
  final bool? displayOnly;
  final bool plannerHardEligible;

  const TagMeta({
    required this.slug,
    required this.display,
    required this.type,
    required this.source,
    this.createdAt,
    this.aliases = const [],
    this.recipeCount = 0,
    this.semanticClass,
    this.eligibility,
    this.hardFilterAllowed,
    this.softScoreAllowed,
    this.displayOnly,
    this.plannerHardEligible = false,
  });

  static const mealRoleClass = 'meal_role';

  /// Tag-semantics contract: only `approved` tags, or non-LLM user/system tags
  /// that are not `proposed`/`rejected`, may be offered for tagging.
  bool get isOfferable {
    final e = eligibility;
    if (e == 'approved') return true;
    if (e == 'proposed' || e == 'rejected') return false;
    return source == 'system' || source == 'user';
  }

  bool get isMealRole =>
      type == 'context' && semanticClass == mealRoleClass;

  factory TagMeta.fromJson(Map<String, dynamic> json) {
    final rawAliases = json['aliases'];
    return TagMeta(
      slug: json['slug'] as String,
      display: (json['display'] as String?) ?? json['slug'] as String,
      type: json['type'] as String,
      source: (json['source'] as String?) ?? '',
      createdAt: json['created_at'] as String?,
      aliases: rawAliases is List
          ? [for (final a in rawAliases) if (a is String) a]
          : const [],
      recipeCount: (json['recipe_count'] as num?)?.toInt() ?? 0,
      semanticClass: json['semantic_class'] as String?,
      eligibility: json['eligibility'] as String?,
      hardFilterAllowed: json['hard_filter_allowed'] as bool?,
      softScoreAllowed: json['soft_score_allowed'] as bool?,
      displayOnly: json['display_only'] as bool?,
      plannerHardEligible: json['planner_hard_eligible'] == true,
    );
  }

  /// `{"tags": [...]}` → tags; entries that aren't objects are skipped.
  static List<TagMeta> listFromResponse(Map<String, dynamic> body) {
    final raw = body['tags'];
    if (raw is! List) {
      throw const FormatException('Missing "tags" list in tag response');
    }
    return [
      for (final t in raw)
        if (t is Map) TagMeta.fromJson(Map<String, dynamic>.from(t)),
    ];
  }
}
