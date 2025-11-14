import 'package:constructEYE/core/constants/AppConstants.dart';
import 'package:constructEYE/ui/components/CustomButton.dart';
import 'package:constructEYE/ui/components/TextInputField.dart';
import 'package:constructEYE/ui/components/AppSvgIcon.dart';
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../../../data/repository/AuthenticationRepositoryImpl.dart';
import '../../../domain/usecase/forget_password_use_case/ForgetPasswordUseCaseImpl.dart';
import 'forget_password_bloc/ForgetPasswordBloc.dart';
import 'forget_password_bloc/ForgetPasswordContract.dart';

class ForgetPasswordScreen extends StatefulWidget {
  const ForgetPasswordScreen({super.key});

  @override
  State<ForgetPasswordScreen> createState() => _ForgetPasswordScreenState();
}

class _ForgetPasswordScreenState extends State<ForgetPasswordScreen> {
  final ForgetPasswordBloc _bloc = ForgetPasswordBloc(
    ForgotPasswordUseCaseImpl(
      AuthenticationRepositoryImpl(
        firebaseAuth: FirebaseAuth.instance,
        firestore: FirebaseFirestore.instance,
      ),
    ),
  );

  final _emailController = TextEditingController();

  @override
  void dispose() {
    _bloc.dispose();
    _emailController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final height = MediaQuery.of(context).size.height;
    final width = MediaQuery.of(context).size.width;

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
            child: StreamBuilder<ForgetPasswordState>(
              stream: _bloc.state,
              initialData: ForgetPasswordState(),
              builder: (context, snapshot) {
                final state = snapshot.data!;

                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (state.generalError != null) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(state.generalError!),
                        backgroundColor: theme.colorScheme.error,
                      ),
                    );
                    _bloc.eventSink.add(ClearGeneralError());
                  }

                  if (state.isSuccess) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text("Reset link sent to your email"),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  }
                });

                return SingleChildScrollView(
                  child: ConstrainedBox(
                    constraints: BoxConstraints(minHeight: height),
                    child: Column(
                      children: [
                        SizedBox(height: height * 0.05),

                        /// Back Arrow
                        GestureDetector(
                          onTap: () => Navigator.pop(context),
                          child: Align(
                            alignment: Alignment.centerLeft,
                            child: GestureDetector(
                              onTap: () => Navigator.pop(context),
                              child: AppSvgIcon(
                                lightPath: AppConstants.whiteArrowBackIcon,
                                darkPath: AppConstants.blackArrowBackIcon,
                                size: width * 0.1,
                              ),
                            ),
                          ),
                        ),
                        SizedBox(height: height * 0.03),

                        /// Logo
                        Image.asset(
                          AppConstants.logoImage,
                          width: width * 0.4,
                          height: height * 0.15,
                        ),

                        SizedBox(height: height * 0.02),

                        /// Title
                        Text(
                          AppConstants.forgetPassword,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                          ),
                        ),

                        SizedBox(height: height * 0.01),

                        /// Subtitle
                        Text(
                          textAlign: TextAlign.center,
                          AppConstants.forgetPasswordSubtitle,
                          style: theme.textTheme.bodyMedium,
                        ),

                        SizedBox(height: height * 0.04),

                        /// Email Input
                        TextInputField(
                          title: AppConstants.email,
                          hintText: AppConstants.emailPlaceholder,
                          svgPrefixIcon: AppConstants.mailIcon,
                          controller: _emailController,
                          onChanged: (value) =>
                              _bloc.eventSink.add(EmailChanged(value)),
                          errorText: state.emailError,
                        ),

                        SizedBox(height: height * 0.03),

                        /// Submit Button
                        state.isSubmitting
                            ? const CustomButton(
                                text: AppConstants.pleaseWait,
                                onPressed: null,
                              )
                            : CustomButton(
                                text: AppConstants.resetPassword,
                                onPressed: () {
                                  _bloc.eventSink.add(SubmitForgetPassword());
                                },
                              ),

                        SizedBox(height: height * 0.02),

                        /// Back to Login
                        Align(
                          alignment: Alignment.centerLeft,
                          child: GestureDetector(
                            onTap: () {
                              Navigator.pushReplacementNamed(
                                context,
                                AppConstants.loginScreenRoute,
                              );
                            },
                            child: Text(
                              AppConstants.backToLogin,
                              style: theme.textTheme.bodySmall,
                            ),
                          ),
                        ),

                        SizedBox(height: height * 0.1),
                      ],
                    ),
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
