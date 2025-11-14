import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/components/CustomButton.dart';
import 'package:constructEYE/ui/components/TextInputField.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../../data/repository/AuthenticationRepositoryImpl.dart';
import '../../../domain/usecase/login_use_case/LoginUseCaseImpl.dart';
import 'login_bloc/LogInBloc.dart';
import 'login_bloc/LogInContract.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final LoginBloc _bloc = LoginBloc(
    LoginUseCaseImpl(
      AuthenticationRepositoryImpl(
        firebaseAuth: FirebaseAuth.instance,
        firestore: FirebaseFirestore.instance,
      ),
    ),
  );

  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _bloc.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenHeight = MediaQuery.of(context).size.height;
    final screenWidth = MediaQuery.of(context).size.width;

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: Stack(
        children: [
          Positioned.fill(
            child: Image.asset(
              AppConstants.loginSignupBackgroundImage,
              fit: BoxFit.cover,
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(25),
            child: StreamBuilder<LoginState>(
              stream: _bloc.state,
              initialData: LoginState(),
              builder: (context, snapshot) {
                final state = snapshot.data!;

                // Show general error SnackBar
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (state.generalError != null) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(state.generalError!),
                        backgroundColor: theme.colorScheme.error,
                        duration: const Duration(seconds: 1),
                      ),
                    );
                    _bloc.eventSink.add(ClearGeneralError());
                  }
                });

                return SingleChildScrollView(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(height: screenHeight * 0.1),
                      Image.asset(
                        AppConstants.logoImage,
                        width: screenWidth * 0.6,
                        height: screenHeight * 0.2,
                      ),
                      SizedBox(height: screenHeight * 0.02),
                      Text(
                        AppConstants.welcomeBack,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontSize: 24,
                        ),
                      ),
                      SizedBox(height: screenHeight * 0.02),
                      Text(
                        AppConstants.signInMonitor,
                        style: theme.textTheme.bodyMedium,
                      ),
                      SizedBox(height: screenHeight * 0.04),
                      TextInputField(
                        title: AppConstants.email,
                        hintText: AppConstants.emailPlaceholder,
                        svgPrefixIcon: AppConstants.mailIcon,
                        controller: _emailController,
                        onChanged: (value) =>
                            _bloc.eventSink.add(EmailChanged(value)),
                        errorText: state.emailError,
                      ),
                      SizedBox(height: screenHeight * 0.02),
                      TextInputField(
                        title: AppConstants.password,
                        hintText: AppConstants.passwordPlaceholder,
                        svgPrefixIcon: AppConstants.passwordIcon,
                        isPassword: true,
                        controller: _passwordController,
                        onChanged: (value) =>
                            _bloc.eventSink.add(PasswordChanged(value)),
                        errorText: state.passwordError,
                      ),
                      SizedBox(height: screenHeight * 0.02),
                      GestureDetector(
                        onTap: () {
                          Navigator.pushNamed(
                            context,
                            AppConstants.forgetPasswordScreenRoute,
                          );
                        },
                        child: Align(
                          alignment: Alignment.centerRight,
                          child: Text(
                            AppConstants.forgetPassword,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: theme.colorScheme.primary,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),
                      SizedBox(height: screenHeight * 0.03),
                      state.isSubmitting
                          ? CustomButton(
                              text: AppConstants.pleaseWait,
                              onPressed: null,
                            )
                          : CustomButton(
                              text: AppConstants.logIn,
                              onPressed: () =>
                                  _bloc.eventSink.add(LoginSubmitted()),
                            ),
                      SizedBox(height: screenHeight * 0.02),
                      GestureDetector(
                        onTap: () {
                          Navigator.pushReplacementNamed(
                            context,
                            AppConstants.signupScreenRoute,
                          );
                        },
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              AppConstants.dontHaveAccount,
                              style: theme.textTheme.bodyMedium,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              AppConstants.signUp,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: theme.colorScheme.primary,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(height: screenHeight * 0.1),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
