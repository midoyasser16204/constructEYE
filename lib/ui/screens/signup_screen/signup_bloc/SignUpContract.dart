// lib/ui/screens/signup_screen/signup_bloc/signup_contract.dart
import 'package:flutter/material.dart';

/// --------------------------
/// 🔹 Signup Events (User Actions)
/// --------------------------
abstract class SignupEvent {}

class NameChanged extends SignupEvent {
  final String name;
  NameChanged(this.name);
}

class EmailChanged extends SignupEvent {
  final String email;
  EmailChanged(this.email);
}

class PasswordChanged extends SignupEvent {
  final String password;
  PasswordChanged(this.password);
}

class ConfirmPasswordChanged extends SignupEvent {
  final String confirmPassword;
  ConfirmPasswordChanged(this.confirmPassword);
}

class SignupSubmitted extends SignupEvent {}

class ClearGeneralError extends SignupEvent {}

/// --------------------------
/// 🔹 Signup State (UI State)
/// --------------------------
class SignupState {
  final String name;
  final String email;
  final String password;
  final String confirmPassword;
  final bool isSubmitting;
  final bool isSuccess;
  final String? nameError;
  final String? emailError;
  final String? passwordError;
  final String? confirmPasswordError;
  final String? generalError;

  bool get isNameValid => name.isNotEmpty;
  bool get isEmailValid => email.contains('@');
  bool get isPasswordValid => password.length >= 4;
  bool get passwordsMatch => password == confirmPassword;

  bool get canSubmit =>
      isNameValid &&
          isEmailValid &&
          isPasswordValid &&
          passwordsMatch &&
          !isSubmitting;

  SignupState({
    this.name = '',
    this.email = '',
    this.password = '',
    this.confirmPassword = '',
    this.isSubmitting = false,
    this.isSuccess = false,
    this.nameError,
    this.emailError,
    this.passwordError,
    this.confirmPasswordError,
    this.generalError,
  });

  SignupState copyWith({
    String? name,
    String? email,
    String? password,
    String? confirmPassword,
    bool? isSubmitting,
    bool? isSuccess,
    String? nameError,
    String? emailError,
    String? passwordError,
    String? confirmPasswordError,
    String? generalError,
  }) {
    return SignupState(
      name: name ?? this.name,
      email: email ?? this.email,
      password: password ?? this.password,
      confirmPassword: confirmPassword ?? this.confirmPassword,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      isSuccess: isSuccess ?? this.isSuccess,
      nameError: nameError,
      emailError: emailError,
      passwordError: passwordError,
      confirmPasswordError: confirmPasswordError,
      generalError: generalError,
    );
  }
}
