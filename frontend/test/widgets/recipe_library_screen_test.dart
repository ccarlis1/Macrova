import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/providers/recipe_builder_coordinator.dart';
import 'package:macrova/providers/recipe_provider.dart';
import 'package:macrova/screens/recipe_library_screen.dart';
import 'package:macrova/widgets/empty_state.dart';
import 'package:provider/provider.dart';

Future<RecipeBuilderCoordinator> pumpLibrary(WidgetTester tester) async {
  final recipes = RecipeProvider();
  final coordinator = RecipeBuilderCoordinator();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<RecipeProvider>.value(value: recipes),
        ChangeNotifierProvider<RecipeBuilderCoordinator>.value(
          value: coordinator,
        ),
      ],
      child: const MaterialApp(
        home: Scaffold(body: RecipeLibraryScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return coordinator;
}

void main() {
  group('RecipeLibraryScreen', () {
    testWidgets(
      'Given no recipes, When the library renders, Then the EmptyState '
      'add affordance is shown',
      (tester) async {
        await pumpLibrary(tester);

        expect(find.byType(EmptyState), findsOneWidget);
        expect(find.text('Create your first recipe'), findsOneWidget);
      },
    );

    testWidgets(
      'Given the empty state, When the add affordance is tapped, Then a '
      'pending create action is queued on the coordinator',
      (tester) async {
        final coordinator = await pumpLibrary(tester);

        await tester.tap(find.text('Create your first recipe'));
        await tester.pump();

        expect(
          coordinator.takePendingAction(),
          isA<RecipeBuilderPendingCreate>(),
        );
      },
    );
  });
}
