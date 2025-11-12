import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/components/customButton.dart';
import 'package:constructEYE/ui/components/textInputField.dart';
import 'package:flutter/material.dart';
import 'package:constructEYE/core/colors/AppColors.dart';
import 'login_bloc/login_bloc.dart';
import 'login_bloc/login_contract.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final LoginBloc _bloc = LoginBloc();
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
    final screenHeight = MediaQuery
        .of(context)
        .size
        .height;
    final screenWidth = MediaQuery
        .of(context)
        .size
        .width;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: StreamBuilder<LoginState>(
          stream: _bloc.state,
          initialData: LoginState(),
          builder: (context, snapshot) {
            final state = snapshot.data!;

            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (state.generalError != null) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(state.generalError!),
                    backgroundColor: AppColors.errorColor,
                    duration: const Duration(seconds: 1),
                  ),
                );
                _bloc.eventSink.add(ClearGeneralError());
              }
            });

            return Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Image.asset(
                  AppConstants.logoImage,
                  width: screenWidth * 0.6,
                  height: screenHeight * 0.2,
                ),
                SizedBox(height: screenHeight * 0.02),
                const Text(
                  AppConstants.welcomeBack,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.primaryColor,
                  ),
                ),
                SizedBox(height: screenHeight * 0.02),
                const Text(
                  AppConstants.signInMonitor,
                  style: TextStyle(fontSize: 12, color: AppColors.text),
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
                Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    AppConstants.forgetPassword,
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.primaryColor,
                    ),
                  ),
                ),
                SizedBox(height: screenHeight * 0.03),
                state.isSubmitting
                    ? CustomButton(
                  text: AppConstants.pleaseWait,
                  textColor: AppColors.secondaryColor,
                  buttonColor: AppColors.primaryColor,
                  onPressed: null,
                )
                    : CustomButton(
                  text: AppConstants.login,
                  textColor: AppColors.secondaryColor,
                  buttonColor: AppColors.primaryColor,
                  onPressed: () => _bloc.eventSink.add(LoginSubmitted()),
                ),
                SizedBox(height: screenHeight * 0.02),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      AppConstants.dontHaveAccount,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.text,
                      ),
                    ),
                    Text(
                        AppConstants.signUp,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.primaryColor,
                        ),
                      ),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}