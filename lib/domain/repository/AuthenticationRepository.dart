import 'package:constructEYE/domain/entities/UserEntity.dart';

abstract class AuthenticationRepository {
  /// Sign in with email & password
  Future<UserEntity> login({required String email, required String password});

  /// Register a new user
  Future<UserEntity> register({
    required String email,
    required String password,
    required String fullName,
  });

  /// Send password reset email
  Future<void> forgotPassword({required String email});

  /// Optional: get current user
  Future<UserEntity?> getCurrentUser();
}
