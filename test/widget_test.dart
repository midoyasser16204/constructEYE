import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:constructEYE/ui/screens/profile_screen/ProfileScreen.dart';

void main() {
  testWidgets('Profile screen smoke test', (WidgetTester tester) async {
    // Build ProfileScreen directly
    await tester.pumpWidget(
      const MaterialApp(
        home: ProfileScreen(),
      ),
    );

    // Verify that ProfileScreen is shown
    expect(find.text('Profile'), findsOneWidget);
    expect(find.byType(GestureDetector), findsWidgets);
  });
}
