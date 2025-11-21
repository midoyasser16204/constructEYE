import 'dart:io';
import 'package:constructEYE/domain/entities/UserEntity.dart';

abstract class UpdateUserProfileUseCase {
  Future<UserEntity> execute({
    required UserEntity user,
    File? newImage,
  });
}
