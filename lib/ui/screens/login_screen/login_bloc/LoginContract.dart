import 'package:flutter/material.dart';

/// --------------------------
/// 🔹 Login Events (User Actions)
/// --------------------------
abstract class LoginEvent {}

class EmailChanged extends LoginEvent {
  final String email;
  EmailChanged(this.email);
}

class PasswordChanged extends LoginEvent {
  final String password;
  PasswordChanged(this.password);
}

class LoginSubmitted extends LoginEvent {}

class ClearGeneralError extends LoginEvent {}

/// --------------------------
/// 🔹 Login State (UI State)
/// --------------------------
class LoginState {
  final String email;
  final String password;
  final bool isSubmitting;
  final bool isSuccess;
  final String? emailError;
  final String? passwordError;
  final String? generalError;

  bool get isEmailValid => email.contains('@');
  bool get isPasswordValid => password.length >= 4;
  bool get canSubmit => isEmailValid && isPasswordValid && !isSubmitting;

  LoginState({
    this.email = '',
    this.password = '',
    this.isSubmitting = false,
    this.isSuccess = false,
    this.emailError,
    this.passwordError,
    this.generalError,
  });

  LoginState copyWith({
    String? email,
    String? password,
    bool? isSubmitting,
    bool? isSuccess,
    String? emailError,
    String? passwordError,
    String? generalError,
  }) {
    return LoginState(
      email: email ?? this.email,
      password: password ?? this.password,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      isSuccess: isSuccess ?? this.isSuccess,
      emailError: emailError,
      passwordError: passwordError,
      generalError: generalError,
    );
  }
}
