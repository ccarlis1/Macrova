import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/providers/ingredient_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/screens/ingredient_hub_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:provider/provider.dart';

Future<void> _pumpHub(WidgetTester tester) async {
  final profile = ProfileProvider();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<IngredientProvider>(
          create: (_) => IngredientProvider(),
        ),
        ChangeNotifierProvider<LlmConfigProvider>(
          create: (_) => LlmConfigProvider(profile),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: IngredientHubScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  group('IngredientHubScreen', () {
    testWidgets(
      'Given local mode, When rendered, Then MacrovaChip filters and search '
      'anchor are shown',
      (tester) async {
        tester.view.physicalSize = const Size(1200, 800);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await _pumpHub(tester);

        expect(find.byType(MacrovaChip), findsWidgets);
        expect(find.text('Search for ingredients...'), findsOneWidget);
        expect(find.text('Remote (USDA)'), findsOneWidget);
      },
    );

    testWidgets(
      'Given local mode, When Remote (USDA) chip is tapped, Then the search '
      'hint switches to USDA and back when Saved is tapped',
      (tester) async {
        tester.view.physicalSize = const Size(1200, 800);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await _pumpHub(tester);

        await tester.tap(find.text('Remote (USDA)'));
        await tester.pumpAndSettle();

        expect(find.text('Search USDA FoodData Central…'), findsOneWidget);
        expect(find.text('Search for ingredients...'), findsNothing);
        expect(find.text('SR Legacy only'), findsOneWidget);

        await tester.tap(find.text('Saved'));
        await tester.pumpAndSettle();

        expect(find.text('Search for ingredients...'), findsOneWidget);
        expect(find.text('Search USDA FoodData Central…'), findsNothing);
      },
    );
  });
}
