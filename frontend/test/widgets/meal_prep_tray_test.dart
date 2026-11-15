import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/models/meal_prep_batch.dart';
import 'package:macrova/services/api_service.dart';
import 'package:macrova/services/storage_service.dart';
import 'package:macrova/widgets/create_batch_sheet.dart';
import 'package:macrova/widgets/meal_prep_tray.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'meal_prep_test_helpers.dart';

// FE-14: meal-prep tray (empty, populated, cancel confirm, collapse).

MealPrepBatch _batch() =>
    MealPrepBatch.listFromResponse(fixtureJson('meal_prep_batches_list.json'))
        .single;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<void> pumpTray(
    WidgetTester tester,
    FakeMealPrepServer server, {
    bool loadFirst = true,
  }) async {
    tester.view.physicalSize = const Size(900, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final plan = server.provider();
    await plan.load();
    if (loadFirst) await plan.loadMealPrepBatches();
    final recipes = await recipeProviderWith([capableRecipe]);
    await tester.pumpWidget(
      wrapWithProviders(const MealPrepTray(), plan: plan, recipes: recipes),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
      'Given no batches, Then the tray still renders, explains meal prep and '
      'offers + New batch, which opens the create sheet', (tester) async {
    await pumpTray(tester, FakeMealPrepServer());

    expect(find.byKey(MealPrepTray.trayKey), findsOneWidget);
    expect(find.textContaining('Cook once, eat several times'), findsOneWidget);
    expect(find.byKey(MealPrepTray.emptyKey), findsOneWidget);
    expect(find.text('+ New batch'), findsOneWidget);

    await tester.tap(find.byKey(MealPrepTray.emptyKey));
    await tester.pumpAndSettle();

    expect(find.byType(CreateBatchSheet), findsOneWidget);
  });

  testWidgets(
      'Given an active batch, Then its recipe name, remaining/total servings '
      'and cook date are listed', (tester) async {
    final b = _batch();
    await pumpTray(tester, FakeMealPrepServer(batches: [b]));

    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsOneWidget);
    expect(find.text('Overnight Oat Bowl'), findsOneWidget);
    expect(find.text('1/3 servings left · cook 2026-11-14'), findsOneWidget);
    expect(find.text('Day 1 · meal 1, Day 2 · meal 1'), findsOneWidget);
    expect(find.text('Meal prep · 1 active'), findsOneWidget);
    expect(find.byKey(MealPrepTray.newBatchKey), findsOneWidget);
    expect(find.byKey(MealPrepTray.emptyKey), findsNothing);
  });

  testWidgets(
      'Given cancel is tapped, When the dialog is dismissed, Then nothing is '
      'cancelled; When confirmed, Then the batch is cancelled and the tray '
      'refreshes', (tester) async {
    final b = _batch();
    final server = FakeMealPrepServer(batches: [b]);
    await pumpTray(tester, server);

    await tester.tap(find.byKey(MealPrepTray.cancelKey(b.id)));
    await tester.pumpAndSettle();
    expect(find.text('Cancel this batch?'), findsOneWidget);

    await tester.tap(find.byKey(MealPrepTray.cancelDismissKey));
    await tester.pumpAndSettle();
    expect(server.cancelled, isEmpty);
    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsOneWidget);

    final listsBefore = server.listCalls;
    await tester.tap(find.byKey(MealPrepTray.cancelKey(b.id)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(MealPrepTray.cancelConfirmKey));
    await tester.pumpAndSettle();

    expect(server.cancelled, [b.id]);
    expect(server.listCalls, listsBefore + 1);
    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsNothing);
    expect(find.byKey(MealPrepTray.emptyKey), findsOneWidget);
    expect(find.textContaining('Batch cancelled'), findsOneWidget);
  });

  testWidgets(
      'Given the tray, When collapsed, Then the body hides and the choice is '
      'stored; a new session starts collapsed, a fresh install expanded',
      (tester) async {
    final b = _batch();
    final server = FakeMealPrepServer(batches: [b]);
    await pumpTray(tester, server);

    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsOneWidget);

    await tester.tap(find.byKey(MealPrepTray.toggleKey));
    await tester.pumpAndSettle();

    expect(find.byKey(MealPrepTray.trayKey), findsOneWidget);
    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsNothing);
    expect(await StorageService.loadMealPrepTrayCollapsed(), isTrue);

    final next = server.provider();
    await next.load();
    expect(next.mealPrepTrayCollapsed, isTrue);

    SharedPreferences.setMockInitialValues({});
    final fresh = server.provider();
    await fresh.load();
    expect(fresh.mealPrepTrayCollapsed, isFalse);

    await tester.tap(find.byKey(MealPrepTray.toggleKey));
    await tester.pumpAndSettle();
    expect(find.byKey(MealPrepTray.batchKey(b.id)), findsOneWidget);
  });

  testWidgets(
      'Given the list fails, Then the server code is shown with Retry, which '
      'reloads', (tester) async {
    final server = FakeMealPrepServer(batches: [_batch()])
      ..listError = const ApiException(
        statusCode: 500,
        code: 'INTERNAL_ERROR',
        message: 'store unreadable',
      );
    await pumpTray(tester, server);

    expect(find.byKey(MealPrepTray.errorKey), findsOneWidget);
    expect(
      find.text(
          'Couldn\'t load meal-prep batches (INTERNAL_ERROR): store unreadable'),
      findsOneWidget,
    );

    server.listError = null;
    await tester.tap(find.byKey(MealPrepTray.retryKey));
    await tester.pumpAndSettle();

    expect(find.byKey(MealPrepTray.errorKey), findsNothing);
    expect(find.text('Overnight Oat Bowl'), findsOneWidget);
  });
}
