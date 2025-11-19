import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/screens/login_screen/LogInScreen.dart';
import 'package:constructEYE/ui/screens/signup_screen/SignUpScreen.dart';
import 'package:constructEYE/ui/screens/splash_screen/SplashScreen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'core/configures/FirebaseOptions.dart';
import 'core/themes/AppThemes.dart';
// import 'package:firebase_core/firebase_core.dart';
// import 'package:cloud_firestore/cloud_firestore.dart';
// import 'core/configures/FirebaseOptions.dart';

void main() async {
   WidgetsFlutterBinding.ensureInitialized();
   await Firebase.initializeApp(
     options: DefaultFirebaseOptions.currentPlatform,
   );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: AppConstants.appName,
      theme: AppThemes.lightTheme,
      darkTheme: AppThemes.darkTheme,
      themeMode: ThemeMode.light,
      initialRoute: AppConstants.splashScreenRoute,
      routes: {
        AppConstants.splashScreenRoute: (context) => const SplashScreen(),
        AppConstants.loginScreenRoute: (context) => const LoginScreen(),
        AppConstants.signupScreenRoute: (context) => const SignupScreen(),
      },
    );
  }
}