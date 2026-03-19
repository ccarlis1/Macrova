import 'package:flutter_test/flutter_test.dart';

import 'package:macrova/main.dart';

void main() {
  testWidgets('App boots with Macrova shell', (WidgetTester tester) async {
    await tester.pumpWidget(const MacrovaApp());
    expect(find.text('Macrova'), findsOneWidget);
  });
}
