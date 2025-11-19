import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/screens/profile_screen/ProfileScreen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'core/configures/FirebaseOptions.dart';
import 'core/themes/AppThemes.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  final prefs = await SharedPreferences.getInstance();
  final isDark = prefs.getBool('isDark') ?? false;

  runApp(
    ChangeNotifierProvider(
      create: (_) => ThemeProvider(isDark),
      child: const MyApp(),
    ),
  );
}

class ThemeProvider extends ChangeNotifier {
  bool _isDark;

  ThemeProvider(this._isDark);

  bool get isDark => _isDark;

  toggleTheme() async {
    _isDark = !_isDark;
    notifyListeners();
    SharedPreferences prefs = await SharedPreferences.getInstance();
    prefs.setBool('isDark', _isDark);
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final themeProvider = Provider.of<ThemeProvider>(context);

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: AppConstants.appName,
      theme: AppThemes.lightTheme,
      darkTheme: AppThemes.darkTheme,
      themeMode: themeProvider.isDark ? ThemeMode.dark : ThemeMode.light,
      initialRoute: AppConstants.profileScreenRoute,
      routes: {
        AppConstants.profileScreenRoute: (context) => const ProfileScreen(),
      },
    );
  }
}