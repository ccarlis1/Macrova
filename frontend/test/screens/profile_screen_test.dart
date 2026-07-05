import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:macrova/features/agent/llm_config_provider.dart';
import 'package:macrova/providers/profile_provider.dart';
import 'package:macrova/screens/profile_screen.dart';
import 'package:macrova/theme/app_theme.dart';
import 'package:macrova/widgets/macrova_chip.dart';
import 'package:provider/provider.dart';

Future<void> pumpProfileScreen(WidgetTester tester) async {
  // Tall/wide surface so the whole form is laid out without scrolling.
  tester.view.physicalSize = const Size(1000, 4000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final profile = ProfileProvider();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider<ProfileProvider>.value(value: profile),
        ChangeNotifierProvider<LlmConfigProvider>.value(
          value: LlmConfigProvider(profile),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light,
        home: const Scaffold(body: ProfileScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Finder allergyField() => find.byWidgetPredicate(
      (w) =>
          w is TextField &&
          w.decoration?.hintText == 'Type allergy or restriction...',
    );

void main() {
  group('ProfileScreen (restyled)', () {
    testWidgets(
      'Given the profile anchor, When rendered, Then the nutrition-targets '
      'section header is present',
      (tester) async {
        await pumpProfileScreen(tester);

        expect(find.text('Editable Nutrition Targets'), findsOneWidget);
      },
    );

    testWidgets(
      'Given an empty allergy list, When an allergy is added and removed, '
      'Then the removable MacrovaChip appears and disappears',
      (tester) async {
        await pumpProfileScreen(tester);

        // Given: empty-state message is shown, no chip yet.
        expect(
          find.text(
            'No allergies added - meal plans will consider all ingredients',
          ),
          findsOneWidget,
        );
        expect(find.byType(MacrovaChip), findsNothing);

        // When: typing an allergy and tapping Add.
        await tester.enterText(allergyField(), 'Peanuts');
        await tester.tap(find.text('Add'));
        await tester.pumpAndSettle();

        // Then: a removable chip renders with the allergy label.
        expect(find.byType(MacrovaChip), findsOneWidget);
        expect(find.text('Peanuts'), findsOneWidget);

        // When: tapping the chip's remove affordance.
        await tester.tap(find.byIcon(Icons.close));
        await tester.pumpAndSettle();

        // Then: the chip is gone and the empty state returns.
        expect(find.byType(MacrovaChip), findsNothing);
        expect(find.text('Peanuts'), findsNothing);
      },
    );

    testWidgets(
      'Given the deficit segmented control, When On/Off are tapped, '
      'Then the selected segment tracks the toggle',
      (tester) async {
        await pumpProfileScreen(tester);

        SegmentedButton<bool> control() =>
            tester.widget<SegmentedButton<bool>>(
              find.byType(SegmentedButton<bool>),
            );

        // Given: deficit mode defaults to off.
        expect(control().selected, {false});

        // When: selecting On.
        await tester.tap(find.text('On'));
        await tester.pumpAndSettle();

        // Then: the control reflects the enabled state.
        expect(control().selected, {true});

        // When: selecting Off again.
        await tester.tap(find.text('Off'));
        await tester.pumpAndSettle();

        // Then: the control returns to disabled.
        expect(control().selected, {false});
      },
    );
  });
}
