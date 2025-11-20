import 'package:constructEYE/data/data_source/shared_pref/SharedPrefDataSource.dart';
import 'package:flutter/cupertino.dart';

class ThemeProvider extends ChangeNotifier {
  final SharedPrefDataSource _sharedPref;
  bool _isDark = false;

  ThemeProvider(this._sharedPref) {
    _isDark = _sharedPref.getTheme();
  }

  bool get isDark => _isDark;

  void toggleTheme() {
    _isDark = !_isDark;
    _sharedPref.saveTheme(isDark: _isDark);
    notifyListeners();
  }
}