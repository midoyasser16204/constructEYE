import 'package:flutter/material.dart';

/// --------------------------
/// 🔹 Events
/// --------------------------
abstract class ForgetPasswordEvent {}

class EmailChanged extends ForgetPasswordEvent {
  final String email;
  EmailChanged(this.email);
}

class SubmitForgetPassword extends ForgetPasswordEvent {}

class ClearGeneralError extends ForgetPasswordEvent {}

/// --------------------------
/// 🔹 State
/// --------------------------
class ForgetPasswordState {
  final String email;
  final bool isSubmitting;
  final bool isSuccess;
  final String? emailError;
  final String? generalError;

  bool get isEmailValid => email.contains('@');
  bool get canSubmit => isEmailValid && !isSubmitting;

  ForgetPasswordState({
    this.email = '',
    this.emailError,
    this.generalError,
    this.isSubmitting = false,
    this.isSuccess = false,
  });

  ForgetPasswordState copyWith({
    String? email,
    bool? isSubmitting,
    bool? isSuccess,
    String? emailError,
    String? generalError,
  }) {
    return ForgetPasswordState(
      email: email ?? this.email,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      isSuccess: isSuccess ?? this.isSuccess,
      emailError: emailError,
      generalError: generalError,
    );
  }
}
