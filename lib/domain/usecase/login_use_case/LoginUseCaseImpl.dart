
import 'package:constructEYE/domain/repository/AuthenticationRepository.dart';
import '../../entities/UserEntity.dart';
import 'LoginUseCase.dart';

class LoginUseCaseImpl implements LoginUseCase {
  final AuthenticationRepository _repository;

  LoginUseCaseImpl(this._repository);

  @override
  Future<UserEntity> execute(String email, String password) {
    return _repository.login(email: email, password: password);
  }
}