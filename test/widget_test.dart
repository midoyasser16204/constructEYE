import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:constructEYE/main.dart';
import 'package:constructEYE/core/themes/ThemeNotifier.dart';

void main() {
  testWidgets('Profile screen smoke test', (WidgetTester tester) async {
    final themeNotifier = ThemeNotifier();

    // Build our app and trigger a frame.
    await tester.pumpWidget(MyApp(themeNotifier: themeNotifier));

    // Verify that ProfileScreen is shown
    expect(find.text('Profile'), findsOneWidget);
    expect(find.byType(GestureDetector), findsWidgets);
  });
}
