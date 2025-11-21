import 'package:constructEYE/domain/entities/UserEntity.dart';
import 'package:constructEYE/domain/repository/UserRepository.dart';

import '../../repository/AuthenticationRepository.dart';
import 'GetCurrentUserUseCase.dart';

class GetCurrentUserUseCaseImpl implements GetCurrentUserUseCase {

  final UserRepository _repository;

  GetCurrentUserUseCaseImpl(this._repository);

  @override
  Future<UserEntity?> execute() {
    return _repository.getCurrentUser();
  }
}