import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/main.dart';

void main() {
  testWidgets('HelpDeskApp initial load smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const HelpDeskApp());
    expect(find.byType(HelpDeskApp), findsOneWidget);
  });
}
