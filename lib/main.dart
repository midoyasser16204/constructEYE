import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/screens/profile_screen/ProfileScreen.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'core/configures/FirebaseOptions.dart';
import 'core/themes/AppThemes.dart';

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
      initialRoute: AppConstants.profileScreenRoute,
      routes: {
        AppConstants.profileScreenRoute: (context) => const ProfileScreen(),
      },
    );
  }
}
