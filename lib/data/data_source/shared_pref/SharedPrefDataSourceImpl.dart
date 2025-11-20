import 'package:constructEYE/data/data_source/shared_pref/ISharedPrefDataSource.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SharedPrefDataSourceImpl implements SharedPrefDataSource{
  static const String _uidKey = 'uid';
  static const String _isDarkThemeKey = 'is_dark_theme';

  final SharedPreferences _prefs;

  SharedPrefDataSourceImpl(this._prefs);

  // ====================== UID ======================
  @override
  Future<void> saveUid({required String uid}) async {
    await _prefs.setString(_uidKey, uid);
  }

  @override
  String? getUid() {
    return _prefs.getString(_uidKey);
  }

  @override
  Future<void> removeUid() async {
    await _prefs.remove(_uidKey);
  }

  // ====================== Theme ======================
  @override
  Future<void> saveTheme({required bool isDark}) async {
    await _prefs.setBool(_isDarkThemeKey, isDark);
  }

  @override
  bool getTheme() {
    return _prefs.getBool(_isDarkThemeKey) ?? false; // default light
  }
}
