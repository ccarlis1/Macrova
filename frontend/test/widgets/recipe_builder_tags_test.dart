import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/models/recipe.dart';
import 'package:macrova/models/recipe_sync_result.dart';
import 'package:macrova/models/tag.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/recipe_builder_screen.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _json(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync())
        as Map<String, dynamic>;

List<TagMeta> _registry() =>
    TagMeta.listFromResponse(_json('tags_list_response.json'));

/// A local recipe with no tags (as saved before FE-12).
const _untagged = Recipe(
  id: 'local-1',
  name: 'Oat Bowl',
  ingredients: [
    RecipeIngredientEntry(
      ingredientId: 'i1',
      ingredientName: 'oats',
      quantity: 50,
      unit: 'g',
    ),
  ],
  servings: 1,
);

class _Harness {
  _Harness({TagListFn? tagListFn}) {
    recipes = RecipeProvider(
      recipeSyncFn: (batch) async {
        synced.addAll(batch);
        return RecipeSyncResult(syncedIds: batch.map((r) => r.id).toList());
      },
      recipeDetailFn: (id) async {
        detailCalls.add(id);
        return Recipe.fromJson(_json('recipe_detail_meal_prep.json'));
      },
      tagListFn: tagListFn ?? () async => _registry(),
    );
  }

  late final RecipeProvider recipes;
  final coord = RecipeBuilderCoordinator();
  final synced = <Recipe>[];
  final detailCalls = <String>[];

  Map<String, dynamic> get lastPayload => synced.last.toSyncPayload();

  Future<void> pump(WidgetTester tester) async {
    tester.view.physicalSize = const Size(1200, 3200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await recipes.load();
    final profile = ProfileProvider();
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light,
        home: Scaffold(
          body: MultiProvider(
            providers: [
              ChangeNotifierProvider.value(value: profile),
              ChangeNotifierProvider.value(value: LlmConfigProvider(profile)),
              ChangeNotifierProvider.value(value: IngredientProvider()),
              ChangeNotifierProvider.value(value: recipes),
              ChangeNotifierProvider.value(value: coord),
            ],
            child: const RecipeBuilderScreen(),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> open(WidgetTester tester, Recipe recipe) async {
    coord.openForEdit(recipe);
    await tester.pumpAndSettle();
  }

  Future<void> tapKey(WidgetTester tester, Key key) async {
    await tester.ensureVisible(find.byKey(key));
    await tester.tap(find.byKey(key));
    await tester.pumpAndSettle();
  }

  Future<void> save(WidgetTester tester) async {
    await tester.tap(find.text('Update'));
    await tester.pumpAndSettle();
  }
}

bool _chipSelected(WidgetTester tester, Key key) =>
    tester.widget<MacrovaChip>(find.byKey(key)).selected;

bool _switchOn(WidgetTester tester) => tester
    .widget<Switch>(find.byKey(RecipeBuilderScreenState.mealPrepSwitchKey))
    .value;

String _servingsText(WidgetTester tester) => tester
    .widget<TextField>(
      find.widgetWithText(TextField, 'Number of Servings'),
    )
    .controller!
    .text;

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Recipe Builder tags (FE-12)', () {
    testWidgets(
        'Given the registry, Then only meal_role context tags are offered as '
        'meal roles', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      for (final slug in ['breakfast', 'lunch', 'dinner', 'snack']) {
        expect(
          find.byKey(RecipeBuilderScreenState.mealRoleChipKey(slug)),
          findsOneWidget,
        );
      }
      expect(
        find.byKey(RecipeBuilderScreenState.mealRoleChipKey('meal-prep')),
        findsNothing,
      );
      expect(
        find.byKey(RecipeBuilderScreenState.mealRoleChipKey('time-2')),
        findsNothing,
      );
    });

    testWidgets(
        'Given no meal role, When saving, Then save is blocked with an inline '
        'error', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(tester, _untagged);

      await h.save(tester);

      expect(find.byKey(RecipeBuilderScreenState.mealRoleErrorKey),
          findsOneWidget);
      expect(h.synced, isEmpty);
    });

    testWidgets(
        'Given meal roles picked, When saving, Then they land in '
        'tagSlugsByType.context and the sync payload', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(tester, _untagged);

      await h.tapKey(
          tester, RecipeBuilderScreenState.mealRoleChipKey('breakfast'));
      await h.tapKey(tester, RecipeBuilderScreenState.mealRoleChipKey('snack'));
      await h.save(tester);

      expect(find.byKey(RecipeBuilderScreenState.mealRoleErrorKey),
          findsNothing);
      expect(h.synced, hasLength(1));
      expect(h.synced.single.tagSlugsByType, {
        'context': ['breakfast', 'snack'],
      });
      expect(h.lastPayload['tag_slugs_by_type'], {
        'context': ['breakfast', 'snack'],
      });
      expect(h.lastPayload.containsKey('cuisine'), isFalse);
      expect(h.lastPayload.containsKey('cost_level'), isFalse);
    });

    testWidgets(
        'Given cuisine and cost picked, When saving, Then they are top-level '
        'sync fields, not slugs', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(tester, _untagged);

      await h.tapKey(tester, RecipeBuilderScreenState.mealRoleChipKey('lunch'));
      await h.tapKey(
          tester, RecipeBuilderScreenState.cuisineChipKey('middle-eastern'));
      await h.tapKey(tester, RecipeBuilderScreenState.costChipKey('cheap'));
      await h.save(tester);

      final p = h.lastPayload;
      expect(p['cuisine'], 'middle-eastern');
      expect(p['cost_level'], 'cheap');
      expect(p['tag_slugs_by_type'], {
        'context': ['lunch'],
      });
      expect(find.text('Middle Eastern'), findsOneWidget);
      expect(
        find.byKey(RecipeBuilderScreenState.cuisineChipKey('unknown')),
        findsNothing,
      );
    });

    testWidgets(
        'Given a cuisine the recipe had, When it is cleared, Then the server '
        '"unknown" value is sent', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(
        tester,
        _untagged.copyWith(
          tagSlugsByType: {
            'context': ['dinner'],
          },
          cuisine: 'thai',
          costLevel: 'premium',
        ),
      );
      expect(
        _chipSelected(tester, RecipeBuilderScreenState.cuisineChipKey('thai')),
        isTrue,
      );
      expect(
        _chipSelected(tester, RecipeBuilderScreenState.costChipKey('premium')),
        isTrue,
      );

      await h.tapKey(tester, RecipeBuilderScreenState.cuisineChipKey('thai'));
      await h.tapKey(tester, RecipeBuilderScreenState.costChipKey('premium'));
      await h.save(tester);

      expect(h.lastPayload['cuisine'], 'unknown');
      expect(h.lastPayload['cost_level'], 'standard');
    });

    testWidgets(
        'Given 1 serving, When meal-prep is switched ON, Then meal-prep is '
        'added and servings bump to 2 with a note', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(tester, _untagged);
      expect(_servingsText(tester), '1');

      await h.tapKey(tester, RecipeBuilderScreenState.mealPrepSwitchKey);

      expect(_switchOn(tester), isTrue);
      expect(_servingsText(tester), '2');
      expect(find.byKey(RecipeBuilderScreenState.mealPrepNoteKey),
          findsOneWidget);

      await h.tapKey(
          tester, RecipeBuilderScreenState.mealRoleChipKey('dinner'));
      await h.save(tester);

      expect(h.lastPayload['default_servings'], 2);
      expect(h.lastPayload['tag_slugs_by_type'], {
        'context': ['meal-prep', 'dinner'],
      });
    });

    testWidgets(
        'Given meal-prep ON, When servings drop below 2, Then save is blocked',
        (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(tester, _untagged);
      await h.tapKey(tester, RecipeBuilderScreenState.mealPrepSwitchKey);
      await h.tapKey(
          tester, RecipeBuilderScreenState.mealRoleChipKey('dinner'));

      await tester.enterText(
        find.widgetWithText(TextField, 'Number of Servings'),
        '1',
      );
      await tester.pumpAndSettle();
      await h.save(tester);

      expect(h.synced, isEmpty);
      expect(
        find.text('A meal-prep recipe needs at least 2 servings.'),
        findsOneWidget,
      );
    });

    testWidgets(
        'Given a meal-prep recipe, When meal-prep is switched OFF, Then '
        'meal-prep is removed from context', (tester) async {
      final h = _Harness();
      await h.pump(tester);
      await h.open(
        tester,
        Recipe.fromJson(_json('recipe_detail_meal_prep.json')),
      );
      expect(_switchOn(tester), isTrue);

      await h.tapKey(tester, RecipeBuilderScreenState.mealPrepSwitchKey);

      expect(_switchOn(tester), isFalse);
      expect(find.byKey(RecipeBuilderScreenState.mealPrepNoteKey),
          findsNothing);
      await h.save(tester);

      expect(h.lastPayload['tag_slugs_by_type'], {
        'context': ['breakfast'],
        'nutrition': ['high-fiber'],
      });
      expect(h.lastPayload['default_servings'], 2);
    });

    testWidgets(
        'Given an existing server recipe, When opened, Then its tags are '
        'pre-selected from the detail payload', (tester) async {
      final h = _Harness();
      await h.pump(tester);

      await h.open(
        tester,
        Recipe.apiSummary(id: 'fe12-oat-bowl', name: 'Overnight Oat Bowl'),
      );

      expect(h.detailCalls, ['fe12-oat-bowl']);
      expect(
        _chipSelected(
            tester, RecipeBuilderScreenState.mealRoleChipKey('breakfast')),
        isTrue,
      );
      for (final slug in ['lunch', 'dinner', 'snack']) {
        expect(
          _chipSelected(
              tester, RecipeBuilderScreenState.mealRoleChipKey(slug)),
          isFalse,
        );
      }
      expect(_switchOn(tester), isTrue);
      expect(_servingsText(tester), '2');

      // Saving unchanged keeps the server's other types and drops `time`.
      await h.save(tester);
      expect(h.lastPayload['tag_slugs_by_type'], {
        'context': ['breakfast', 'meal-prep'],
        'nutrition': ['high-fiber'],
      });
    });

    testWidgets(
        'Given the registry fails to load, Then an error with Retry is shown '
        'and Retry recovers', (tester) async {
      var fail = true;
      final h = _Harness(
        tagListFn: () async {
          if (fail) {
            throw const ApiException(
              statusCode: 503,
              code: 'HTTP_ERROR',
              message: 'offline',
            );
          }
          return _registry();
        },
      );
      await h.pump(tester);

      expect(find.byKey(RecipeBuilderScreenState.tagsRetryKey), findsOneWidget);
      expect(
        find.byKey(RecipeBuilderScreenState.mealRoleChipKey('breakfast')),
        findsNothing,
      );

      fail = false;
      await h.tapKey(tester, RecipeBuilderScreenState.tagsRetryKey);

      expect(find.byKey(RecipeBuilderScreenState.tagsRetryKey), findsNothing);
      expect(
        find.byKey(RecipeBuilderScreenState.mealRoleChipKey('breakfast')),
        findsOneWidget,
      );
    });
  });
}
