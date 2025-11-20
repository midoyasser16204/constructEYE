import 'package:shared_preferences/shared_preferences.dart';

abstract class SharedPrefDataSource {
  Future<void> saveUid({required String uid});

  String? getUid();

  Future<void> removeUid();

  // ====================== Theme ======================
  Future<void> saveTheme({required bool isDark});

  bool getTheme() ;
}
