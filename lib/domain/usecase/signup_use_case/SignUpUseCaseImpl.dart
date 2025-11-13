import 'package:constructEYE/domain/repository/AuthenticationRepository.dart';
import '../../entities/UserEntity.dart';
import 'SignUpUseCase.dart';

class SignUpUseCaseImpl implements SignUpUseCase {
  final AuthenticationRepository _repository;

  SignUpUseCaseImpl(this._repository);

  @override
  Future<UserEntity> execute({
    required String email,
    required String password,
    required String fullName,
  }) {
    return _repository.register(email: email, password: password, fullName: fullName);
  }
}