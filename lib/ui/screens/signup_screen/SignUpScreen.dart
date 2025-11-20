import 'package:constructEYE/di/DependencyInjection.dart';
import 'package:constructEYE/ui/screens/signup_screen/signup_bloc/SignUpBloc.dart';
import 'package:constructEYE/ui/screens/signup_screen/signup_bloc/SignUpContract.dart';
import 'package:flutter/material.dart';
import '../../../core/constants/AppConstants.dart';
import '../../components/CustomButton.dart';
import '../../components/TextInputField.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  late final SignupBloc _bloc = getIt<SignupBloc>();

  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _bloc.dispose();
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
            child: StreamBuilder<SignupState>(
              stream: _bloc.state,
              initialData: SignupState(),
              builder: (context, snapshot) {
                final state = snapshot.data!;

                // Use addPostFrameCallback to avoid build errors
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  // Show general error
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

                  // Navigate when signup is successful
                  if (state.isSuccess) {
                    Navigator.pushReplacementNamed(
                      context,
                      AppConstants.profileScreenRoute, // your profile route
                    );
                  }
                });

                return SingleChildScrollView(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(height: screenHeight * 0.04),
                      Image.asset(
                        AppConstants.logoImage,
                        width: screenWidth * 0.6,
                        height: screenHeight * 0.2,
                      ),
                      SizedBox(height: screenHeight * 0.02),

                      /// -------- Title --------
                      Text(
                        AppConstants.createAccount,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          fontSize: 24,
                        ),
                      ),
                      SizedBox(height: screenHeight * 0.02),

                      /// -------- Subtitle --------
                      Text(
                        AppConstants.signUpMonitor,
                        style: theme.textTheme.bodyMedium,
                        textAlign: TextAlign.center,
                      ),
                      SizedBox(height: screenHeight * 0.02),

                      /// -------- Input Fields --------
                      TextInputField(
                        title: AppConstants.name,
                        hintText: AppConstants.namePlaceholder,
                        svgPrefixIcon: AppConstants.personIcon,
                        controller: _nameController,
                        onChanged: (value) =>
                            _bloc.eventSink.add(NameChanged(value)),
                        errorText: state.nameError,
                      ),
                      SizedBox(height: screenHeight * 0.02),

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

                      TextInputField(
                        title: AppConstants.confirmPassword,
                        hintText: AppConstants.confirmPasswordPlaceholder,
                        svgPrefixIcon: AppConstants.passwordIcon,
                        isPassword: true,
                        controller: _confirmPasswordController,
                        onChanged: (value) =>
                            _bloc.eventSink.add(ConfirmPasswordChanged(value)),
                        errorText: state.confirmPasswordError,
                      ),

                      SizedBox(height: screenHeight * 0.03),

                      /// -------- Button --------
                      state.isSubmitting
                          ? CustomButton(
                              text: AppConstants.pleaseWait,
                              onPressed: null,
                            )
                          : CustomButton(
                              text: AppConstants.signUp,
                              onPressed: () =>
                                  _bloc.eventSink.add(SignupSubmitted()),
                            ),

                      SizedBox(height: screenHeight * 0.02),

                      GestureDetector(
                        onTap: () {
                          Navigator.pushReplacementNamed(
                            context,
                            AppConstants.loginScreenRoute,
                          );
                        },
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              AppConstants.alreadyHaveAccount,
                              style: theme.textTheme.bodyMedium,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              AppConstants.logIn,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: theme.colorScheme.primary,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
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
