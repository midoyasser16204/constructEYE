import 'dart:io';
import 'package:constructEYE/domain/entities/UserEntity.dart';
import 'package:constructEYE/domain/repository/UserRepository.dart';
import 'UpdateUserProfileUseCase.dart';

class UpdateUserProfileUseCaseImpl implements UpdateUserProfileUseCase {

  final UserRepository _repository;

  UpdateUserProfileUseCaseImpl(this._repository);

  @override
  Future<UserEntity> execute({
    required UserEntity user,
    File? newImage,
  }) {
    return _repository.updateUserProfile(
      user,
      newImage,
    );
  }
}
