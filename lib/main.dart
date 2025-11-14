import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/screens/edit_profile_screen/EditProfileScreen.dart';
import 'package:constructEYE/ui/screens/login_screen/LogInScreen.dart';
import 'package:constructEYE/ui/screens/profile_screen/ProfileScreen.dart';
import 'package:constructEYE/ui/screens/signup_screen/SignUpScreen.dart';
import 'package:constructEYE/ui/screens/splash_screen/SplashScreen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'core/configures/FirebaseOptions.dart';
import 'core/themes/AppThemes.dart';
import 'core/themes/ThemeNotifier.dart';


void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  final themeNotifier = ThemeNotifier();

  runApp(MyApp(themeNotifier: themeNotifier));
}

class MyApp extends StatelessWidget {
  final ThemeNotifier themeNotifier;

  const MyApp({super.key, required this.themeNotifier});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeNotifier,
      builder: (context, currentTheme, _) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: AppConstants.appName,
          theme: AppThemes.lightTheme,
          darkTheme: AppThemes.darkTheme,
          themeMode: currentTheme,
          initialRoute: AppConstants.profileScreenRoute,
          routes: {
            AppConstants.profileScreenRoute: (context) =>
                ProfileScreen(themeNotifier: themeNotifier),
          },
        );
      },
    );
  }
}
