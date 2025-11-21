import 'dart:io';

import '../entities/UserEntity.dart';

abstract class UserRepository {

  Future<UserEntity?> getCurrentUser();

  /// Update user profile
  Future<UserEntity> updateUserProfile(UserEntity user,File? newImage);
}