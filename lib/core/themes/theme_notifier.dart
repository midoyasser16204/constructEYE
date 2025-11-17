import 'package:flutter/material.dart';
import 'theme_prefs.dart';

class ThemeNotifier extends ChangeNotifier {
  bool isDark;

  ThemeNotifier(this.isDark);

  void toggleTheme(bool value) {
    isDark = value;
    ThemePrefs.saveTheme(isDark);
    notifyListeners();
  }
}
